"""確認済みの抽出データを、共有データベース（db/schema.sql）へ書き込む。

書き込み先はデータ構築システム（このリポジトリ）だけが持つデータベースで、
帳票作成システム（housing-spec-sheet）はここを読み取り専用で参照する。
そのため、Webアプリ用にファイルを出力していた旧 build_catalog.py の代わりに、
このスクリプトを使う（build_catalog.py は廃止）。

入力:
  data/catalogs.json                     カタログの一覧
  data/reviewed/<catalog_id>/p*.json     人が確認した抽出データ（review_status = "verified"）
  data/raw/<catalog_id>/p*/              extract_page.py の出力（図・写真ファイル）
  data/samples/*.json                    動作確認用のダミー品番（--no-samples で除外）
出力:
  DATABASE_URL の指すPostgres（catalogs / series / products / assets / *_assets）
  storage/<catalog_id>/p<page>/...       図・写真の実ファイル
                                          （本番では、この内容をオブジェクトストレージへ同期する）

使い方:
  export DATABASE_URL=postgres://user:pass@host:5432/housing_catalog
  python ingest/load_db.py
  python ingest/load_db.py --include-drafts   # 未確認の extraction.json も含める（確認用。本番投入前提ではない）
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from pathlib import Path

import pymupdf
import psycopg2.extras

from db.config import connect

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STORAGE = ROOT / "storage"


def normalize_code(code: str) -> str:
    """品番の表記ゆれ（全角・小文字・空白・ハイフン類）を吸収した検索キー。
    housing-spec-sheet 側の検索でも同じ規則を使う（README参照）。"""
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


def stage_asset(catalog_id: str, page: int, asset_id: str, labels: dict) -> dict | None:
    """ページ切り出しデータから1つの図・写真を storage/ に配置し、DB行を組み立てる。"""
    raw_dir = DATA / "raw" / catalog_id / f"p{page:04d}"
    page_json = json.loads((raw_dir / "page.json").read_text(encoding="utf-8"))
    asset = next((a for a in page_json["assets"] if a["id"] == asset_id), None)
    if asset is None:
        print(f"warn: {catalog_id} p{page} に {asset_id} がありません")
        return None
    rel_path = f"{catalog_id}/p{page:04d}/{asset['file']}"
    dest = STORAGE / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(raw_dir / asset["file"], dest)
    label = labels.get(asset_id, {})
    pix = pymupdf.Pixmap(str(dest))
    return {
        "id": f"{catalog_id}/p{page}/{asset_id}",
        "catalog_id": catalog_id,
        "page": page,
        "kind": asset["kind"],
        "role": label.get("role", "other"),
        "caption": label.get("caption", ""),
        "file_path": rel_path,
        "width": pix.width,
        "height": pix.height,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--include-drafts", action="store_true")
    ap.add_argument("--no-samples", action="store_true")
    args = ap.parse_args()

    catalogs = json.loads((DATA / "catalogs.json").read_text(encoding="utf-8"))
    if STORAGE.exists():
        shutil.rmtree(STORAGE)

    series_by_name: dict[str, dict] = {}
    products: list[dict] = []
    assets: dict[str, dict] = {}
    # (product_key, asset_id) / (series_id, asset_id) -> sort_order
    product_asset_links: list[tuple[str, str, int]] = []
    series_asset_links: list[tuple[str, str, int]] = []

    def resolve(catalog_id: str, page: int, ids: list[str], labels: dict) -> list[str]:
        out = []
        for asset_id in ids:
            key = f"{catalog_id}/p{page}/{asset_id}"
            if key not in assets:
                a = stage_asset(catalog_id, page, asset_id, labels)
                if a is None:
                    continue
                assets[key] = a
            out.append(key)
        return out

    def add_product(p: dict, catalog_id: str, page: int, labels: dict, status: str) -> None:
        asset_ids = resolve(catalog_id, page, p.get("asset_ids", []), labels)
        code_key = normalize_code(p["code"])
        for i, aid in enumerate(asset_ids):
            product_asset_links.append((code_key, aid, i))
        products.append({
            **{k: v for k, v in p.items() if k not in ("asset_ids", "catalog_id", "page")},
            "code_key": code_key,
            "catalog_id": catalog_id,
            "series_id": series_by_name.get(p["series"], {}).get("id"),
            "source_page": page,
            "review_status": status,
        })

    pages = load_pages(args.include_drafts)
    for d in pages:
        cid, page = d["catalog_id"], d["page"]
        labels = {a["asset_id"]: a for a in d.get("assets", [])}
        for s in d.get("series", []):
            entry = series_by_name.setdefault(s["name"], {
                "id": slug(cid, s["name"]),
                "catalog_id": cid,
                "name": s["name"],
                "category": s["category"],
                "description": s.get("description"),
                "features": [],
                "lineup": [],
                "notes": [],
            })
            entry["features"] += [f for f in s.get("features", []) if f not in entry["features"]]
            entry["lineup"] += [x for x in s.get("lineup", []) if x not in entry["lineup"]]
            entry["notes"] += [n for n in d.get("notes", []) if n not in entry["notes"]]
            for i, aid in enumerate(resolve(cid, page, s.get("asset_ids", []), labels)):
                series_asset_links.append((entry["id"], aid, i))
        for p in d.get("products", []):
            add_product(p, cid, page, labels, d["review_status"])

    if not args.no_samples:
        for f in sorted((DATA / "samples").glob("*.json")):
            for p in json.loads(f.read_text(encoding="utf-8"))["products"]:
                labels = {}
                for d in pages:
                    if (d["catalog_id"], d["page"]) == (p["catalog_id"], p["page"]):
                        labels = {a["asset_id"]: a for a in d.get("assets", [])}
                add_product(p, p["catalog_id"], p["page"], labels, "sample")

    seen: dict[str, str] = {}
    for p in products:
        if p["code_key"] in seen:
            print(f"warn: 品番の重複 {p['code']} / {seen[p['code_key']]}")
        seen[p["code_key"]] = p["code"]

    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            for c in catalogs:
                cur.execute(
                    """insert into catalogs (id, maker, title, source_file, note)
                       values (%(id)s, %(maker)s, %(title)s, %(source_file)s, %(note)s)
                       on conflict (id) do update set
                         maker = excluded.maker, title = excluded.title,
                         source_file = excluded.source_file, note = excluded.note""",
                    {**c, "note": c.get("note")},
                )

            for s in series_by_name.values():
                cur.execute(
                    """insert into series
                         (id, catalog_id, name, category, description, features, lineup, notes)
                       values
                         (%(id)s, %(catalog_id)s, %(name)s, %(category)s, %(description)s,
                          %(features)s, %(lineup)s, %(notes)s)
                       on conflict (id) do update set
                         name = excluded.name, category = excluded.category,
                         description = excluded.description, features = excluded.features,
                         lineup = excluded.lineup, notes = excluded.notes, updated_at = now()""",
                    {
                        **s,
                        "features": psycopg2.extras.Json(s["features"]),
                        "lineup": psycopg2.extras.Json(s["lineup"]),
                        "notes": psycopg2.extras.Json(s["notes"]),
                    },
                )

            for a in assets.values():
                cur.execute(
                    """insert into assets
                         (id, catalog_id, page, kind, role, caption, file_path, width, height)
                       values
                         (%(id)s, %(catalog_id)s, %(page)s, %(kind)s, %(role)s, %(caption)s,
                          %(file_path)s, %(width)s, %(height)s)
                       on conflict (id) do update set
                         role = excluded.role, caption = excluded.caption,
                         file_path = excluded.file_path, width = excluded.width, height = excluded.height""",
                    a,
                )

            product_id_by_key: dict[str, str] = {}
            for p in products:
                cur.execute(
                    """insert into products
                         (catalog_id, series_id, code, code_key, name, variant, color,
                          width_mm, height_mm, depth_mm, list_price_yen, price_note,
                          specs, source_page, review_status)
                       values
                         (%(catalog_id)s, %(series_id)s, %(code)s, %(code_key)s, %(name)s,
                          %(variant)s, %(color)s, %(width_mm)s, %(height_mm)s, %(depth_mm)s,
                          %(list_price_yen)s, %(price_note)s, %(specs)s, %(source_page)s,
                          %(review_status)s)
                       on conflict (catalog_id, code) do update set
                         series_id = excluded.series_id, name = excluded.name,
                         variant = excluded.variant, color = excluded.color,
                         width_mm = excluded.width_mm, height_mm = excluded.height_mm,
                         depth_mm = excluded.depth_mm, list_price_yen = excluded.list_price_yen,
                         price_note = excluded.price_note, specs = excluded.specs,
                         source_page = excluded.source_page, review_status = excluded.review_status,
                         updated_at = now()
                       returning id""",
                    {**p, "specs": psycopg2.extras.Json(p["specs"])},
                )
                product_id_by_key[p["code_key"]] = cur.fetchone()[0]

            cur.execute(
                "delete from product_assets where product_id = any(%s::uuid[])",
                (list(product_id_by_key.values()),),
            )
            for code_key, asset_id, order in product_asset_links:
                cur.execute(
                    """insert into product_assets (product_id, asset_id, sort_order)
                       values (%s, %s, %s) on conflict do nothing""",
                    (product_id_by_key[code_key], asset_id, order),
                )

            cur.execute(
                "delete from series_assets where series_id = any(%s)",
                (list(series_by_name.keys()),),
            )
            for series_id, asset_id, order in series_asset_links:
                cur.execute(
                    """insert into series_assets (series_id, asset_id, sort_order)
                       values (%s, %s, %s) on conflict do nothing""",
                    (series_id, asset_id, order),
                )
    finally:
        conn.close()

    print(f"取込完了: {len(series_by_name)} series, {len(products)} products, {len(assets)} assets")


if __name__ == "__main__":
    main()
