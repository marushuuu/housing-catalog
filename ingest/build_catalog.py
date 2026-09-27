"""確認済みの抽出データをまとめて、Webアプリが読む data/catalog.json を作る。

入力:
  data/catalogs.json                     カタログの一覧
  data/reviewed/<catalog_id>/p*.json     人が確認した抽出データ（review_status = "verified"）
  data/raw/<catalog_id>/p*/              extract_page.py の出力（図・写真ファイル）
  data/samples/*.json                    動作確認用のダミー品番（--no-samples で除外）
出力:
  data/catalog.json
  public/catalog-assets/<catalog_id>/p<page>/...   施主向けに表示する図・写真

使い方:
  python ingest/build_catalog.py
  python ingest/build_catalog.py --include-drafts   # 未確認の extraction.json も含める（確認用）
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC_ASSETS = ROOT / "public" / "catalog-assets"


def normalize_code(code: str) -> str:
    """品番の表記ゆれ（全角・小文字・空白・ハイフン類）を吸収した検索キー。"""
    s = unicodedata.normalize("NFKC", code).upper()
    return re.sub(r"[\s\-‐‑–—―ー_/・]", "", s)


def slug(*parts: str) -> str:
    return "-".join(re.sub(r"\s+", "", p) for p in parts)


def load_pages(include_drafts: bool) -> list[dict]:
    pages: dict[tuple[str, int], dict] = {}
    if include_drafts:
        for f in sorted((DATA / "raw").glob("*/p*/extraction.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            pages[(d["catalog_id"], d["page"])] = d
    for f in sorted((DATA / "reviewed").glob("*/p*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("review_status") != "verified":
            print(f"skip (未確認): {f.relative_to(ROOT)}")
            continue
        pages[(d["catalog_id"], d["page"])] = d
    return [pages[k] for k in sorted(pages)]


def publish_asset(catalog_id: str, page: int, asset_id: str, labels: dict) -> dict | None:
    raw_dir = DATA / "raw" / catalog_id / f"p{page:04d}"
    page_json = json.loads((raw_dir / "page.json").read_text(encoding="utf-8"))
    asset = next((a for a in page_json["assets"] if a["id"] == asset_id), None)
    if asset is None:
        print(f"warn: {catalog_id} p{page} に {asset_id} がありません")
        return None
    dest_dir = PUBLIC_ASSETS / catalog_id / f"p{page:04d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(raw_dir / asset["file"], dest_dir / asset["file"])
    label = labels.get(asset_id, {})
    pix = pymupdf.Pixmap(str(dest_dir / asset["file"]))
    return {
        "id": f"{catalog_id}/p{page}/{asset_id}",
        "src": f"/catalog-assets/{catalog_id}/p{page:04d}/{asset['file']}",
        "width": pix.width,
        "height": pix.height,
        "kind": asset["kind"],
        "role": label.get("role", "other"),
        "caption": label.get("caption", ""),
        "catalog_id": catalog_id,
        "page": page,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-drafts", action="store_true")
    ap.add_argument("--no-samples", action="store_true")
    args = ap.parse_args()

    catalogs = json.loads((DATA / "catalogs.json").read_text(encoding="utf-8"))
    if PUBLIC_ASSETS.exists():
        shutil.rmtree(PUBLIC_ASSETS)

    series_by_name: dict[str, dict] = {}
    products: list[dict] = []
    assets: dict[str, dict] = {}

    def resolve(catalog_id: str, page: int, ids: list[str], labels: dict) -> list[str]:
        out = []
        for asset_id in ids:
            key = f"{catalog_id}/p{page}/{asset_id}"
            if key not in assets:
                a = publish_asset(catalog_id, page, asset_id, labels)
                if a is None:
                    continue
                assets[key] = a
            out.append(key)
        return out

    def add_product(p: dict, catalog_id: str, page: int, labels: dict, status: str, sample: bool) -> None:
        products.append({
            **{k: v for k, v in p.items() if k not in ("asset_ids", "catalog_id", "page")},
            "key": normalize_code(p["code"]),
            "series_id": series_by_name.get(p["series"], {}).get("id"),
            "assets": resolve(catalog_id, page, p.get("asset_ids", []), labels),
            "source": {"catalog_id": catalog_id, "page": page},
            "review_status": status,
            "is_sample": sample,
        })

    pages = load_pages(args.include_drafts)
    for d in pages:
        cid, page = d["catalog_id"], d["page"]
        labels = {a["asset_id"]: a for a in d.get("assets", [])}
        for s in d.get("series", []):
            entry = series_by_name.setdefault(s["name"], {
                "id": slug(cid, s["name"]),
                "name": s["name"],
                "category": s["category"],
                "description": s.get("description"),
                "features": [],
                "lineup": [],
                "notes": [],
                "assets": [],
                "sources": [],
            })
            entry["features"] += [f for f in s.get("features", []) if f not in entry["features"]]
            entry["lineup"] += [x for x in s.get("lineup", []) if x not in entry["lineup"]]
            entry["notes"] += [n for n in d.get("notes", []) if n not in entry["notes"]]
            entry["assets"] += resolve(cid, page, s.get("asset_ids", []), labels)
            entry["sources"].append({"catalog_id": cid, "page": page})
        for p in d.get("products", []):
            add_product(p, cid, page, labels, d["review_status"], sample=False)

    if not args.no_samples:
        for f in sorted((DATA / "samples").glob("*.json")):
            for p in json.loads(f.read_text(encoding="utf-8"))["products"]:
                labels = {}
                for d in pages:
                    if (d["catalog_id"], d["page"]) == (p["catalog_id"], p["page"]):
                        labels = {a["asset_id"]: a for a in d.get("assets", [])}
                add_product(p, p["catalog_id"], p["page"], labels, "sample", sample=True)

    seen: dict[str, str] = {}
    for p in products:
        if p["key"] in seen:
            print(f"warn: 品番の重複 {p['code']} / {seen[p['key']]}")
        seen[p["key"]] = p["code"]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalogs": catalogs,
        "series": list(series_by_name.values()),
        "products": products,
        "assets": assets,
    }
    (DATA / "catalog.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"catalog.json: {len(out['series'])} series, {len(products)} products, {len(assets)} assets")


if __name__ == "__main__":
    main()
