"""カタログPDFを1ページずつ解析し、文字・埋め込み画像・図（ベクター）を切り出す。

出力（ページごと）:
  <out>/<catalog_id>/p<page>/page.json   文字ブロック・アセット一覧
  <out>/<catalog_id>/p<page>/page.png    ページ全体の画像（確認・AI抽出用）
  <out>/<catalog_id>/p<page>/img_*.jpg   埋め込み写真
  <out>/<catalog_id>/p<page>/fig_*.png   ベクター図の切り出し（高解像度）

使い方:
  python ingest/extract_page.py catalogs/TE2400_0166.pdf --catalog-id TE2400 --page-offset 164
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf

PAGE_DPI = 110
FIGURE_DPI = 300
# 図としてまとめる際に、この距離(pt)以内の線は同じ図とみなす
MERGE_GAP = 6.0
# これより小さい図は装飾（罫線・アイコン等）とみなして捨てる
MIN_FIGURE_SIZE = 60.0
MIN_FIGURE_DRAWINGS = 15


def _grow(r: pymupdf.Rect, d: float) -> pymupdf.Rect:
    return pymupdf.Rect(r.x0 - d, r.y0 - d, r.x1 + d, r.y1 + d)


def _is_frame(d: dict) -> bool:
    """囲み枠・背景パネル・帯など、図の中身ではない描画かどうか。"""
    r = d["rect"]
    few_items = len(d["items"]) <= 8
    if few_items and r.width > 100 and r.height > 60:
        return True  # 角丸の囲み枠・白背景パネル
    if r.height < 20 and r.width > 150:
        return True  # 見出し帯・区切り線
    return False


def photo_frames(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """写真のトリミング枠（塗りつぶし矩形1つだけの描画）の候補。"""
    frames = []
    for d in page.get_drawings():
        if d.get("fill") and len(d["items"]) == 1 and d["items"][0][0] == "re":
            frames.append(pymupdf.Rect(d["rect"]))
    return frames


def visible_rect(image_rect: pymupdf.Rect, frames: list[pymupdf.Rect]) -> pymupdf.Rect:
    """配置画像はトリミングされていることが多いので、画像内の最大の枠を表示領域とみなす。"""
    inside = [f for f in frames
              if _grow(image_rect, 1).contains(f)
              and f.width * f.height >= image_rect.width * image_rect.height * 0.15]
    return max(inside, key=lambda f: f.width * f.height) if inside else image_rect


def cluster_drawings(page: pymupdf.Page) -> list[tuple[pymupdf.Rect, int]]:
    """近接するベクター描画をまとめて図の候補領域にする。"""
    rects: list[pymupdf.Rect] = []
    for d in page.get_drawings():
        r = pymupdf.Rect(d["rect"]) & page.rect
        if r.is_empty and not (d["rect"].width == 0 or d["rect"].height == 0):
            continue  # ページ外（版下の余白）の描画
        if not page.rect.intersects(d["rect"]) or _is_frame(d):
            continue
        rects.append(pymupdf.Rect(d["rect"]))

    clusters: list[tuple[pymupdf.Rect, int]] = []
    for r in rects:
        box, count = pymupdf.Rect(r), 1
        merged = True
        while merged:
            merged = False
            for i, (c, n) in enumerate(clusters):
                if _grow(c, MERGE_GAP).intersects(_grow(box, 0.1)):
                    box |= c
                    count += n
                    clusters.pop(i)
                    merged = True
                    break
        clusters.append((box, count))

    # 図の上下端にかかる見出し帯は切り出しに含めない
    bands = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()
             if d["rect"].height < 20 and d["rect"].width > 150 and d.get("fill")]
    trimmed = []
    for box, n in clusters:
        for b in bands:
            if not b.intersects(box):
                continue
            if b.y1 < box.y0 + box.height / 2:
                box.y0 = max(box.y0, b.y1 + 1)
            else:
                box.y1 = min(box.y1, b.y0 - 1)
        trimmed.append((box, n))

    return [
        (box & page.rect, n)
        for box, n in trimmed
        if box.width >= MIN_FIGURE_SIZE
        and box.height >= MIN_FIGURE_SIZE
        and n >= MIN_FIGURE_DRAWINGS
    ]


def text_in(page: pymupdf.Page, rect: pymupdf.Rect) -> str:
    return " ".join(page.get_textbox(rect).split())


def extract_page(doc: pymupdf.Document, index: int, out_dir: Path, printed_page: int) -> dict:
    page = doc[index]
    out_dir.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(dpi=PAGE_DPI).save(out_dir / "page.png")

    blocks = []
    for x0, y0, x1, y1, text, _no, btype in page.get_text("blocks", sort=True):
        if btype != 0 or not text.strip():
            continue
        blocks.append({"bbox": [round(v, 1) for v in (x0, y0, x1, y1)], "text": text.strip()})

    assets = []
    photo_rects: list[pymupdf.Rect] = []
    frames = photo_frames(page)
    for n, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        info = doc.extract_image(xref)
        for rect in page.get_image_rects(xref):
            rect = visible_rect(rect, frames) & page.rect
            if rect.is_empty:
                continue
            # 元画像そのもの（トリミング前）と、紙面どおりの切り出しの両方を残す
            original = f"img_{n}_original.{info['ext']}"
            (out_dir / original).write_bytes(info["image"])
            name = f"img_{n}.png"
            page.get_pixmap(dpi=FIGURE_DPI, clip=rect).save(out_dir / name)
            photo_rects.append(rect)
            assets.append({
                "id": f"img_{n}",
                "kind": "photo",
                "file": name,
                "original_file": original,
                "bbox": [round(v, 1) for v in rect],
                "original_pixels": [info["width"], info["height"]],
                "nearby_text": text_in(page, _grow(rect, 4)),
            })

    for n, (rect, count) in enumerate(sorted(cluster_drawings(page), key=lambda c: (c[0].y0, c[0].x0))):
        # 写真の枠線だけのクラスタは図ではない
        if any(p.contains(rect) or _grow(p, 2).contains(rect) for p in photo_rects):
            continue
        clip = pymupdf.Rect(rect.x0 - 2, rect.y0, rect.x1 + 2, rect.y1 + 2) & page.rect
        name = f"fig_{n}.png"
        page.get_pixmap(dpi=FIGURE_DPI, clip=clip).save(out_dir / name)
        assets.append({
            "id": f"fig_{n}",
            "kind": "figure",
            "file": name,
            "bbox": [round(v, 1) for v in clip],
            "drawings": count,
            "nearby_text": text_in(page, clip)[:300],
        })

    result = {
        "pdf_page_index": index,
        "printed_page": printed_page,
        "size": [page.rect.width, page.rect.height],
        "text": page.get_text(sort=True),
        "blocks": blocks,
        "assets": assets,
    }
    (out_dir / "page.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--catalog-id", required=True, help="カタログ識別子（例: TE2400）")
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    ap.add_argument("--page-offset", type=int, default=1,
                    help="PDF先頭ページのカタログ上のページ番号（抜粋PDF用）")
    ap.add_argument("--pages", help="対象ページ（PDF内の0始まり、例: 0-3,7）")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    indexes = range(doc.page_count)
    if args.pages:
        indexes = []
        for part in args.pages.split(","):
            a, _, b = part.partition("-")
            indexes.extend(range(int(a), int(b or a) + 1))

    for i in indexes:
        printed = args.page_offset + i
        res = extract_page(doc, i, args.out / args.catalog_id / f"p{printed:04d}", printed)
        kinds = [a["kind"] for a in res["assets"]]
        print(f"p{printed}: {len(res['blocks'])} text blocks, "
              f"{kinds.count('photo')} photos, {kinds.count('figure')} figures")


if __name__ == "__main__":
    main()
