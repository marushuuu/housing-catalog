"""extract_page.py の結果とPDFページを Claude に渡し、品番・仕様を構造化データにする。

入力:  <raw>/<catalog_id>/p<page>/page.json（extract_page.py の出力）
出力:  <raw>/<catalog_id>/p<page>/extraction.json（review_status = "draft"）

抽出結果は必ず人が確認してから data/reviewed/ に置く（build_catalog.py 参照）。

使い方:
  export ANTHROPIC_API_KEY=...
  python ingest/llm_extract.py catalogs/TE2400_0166.pdf --catalog-id TE2400 --page-offset 164
  python ingest/llm_extract.py ... --dry-run   # APIを呼ばずに送信内容だけ確認
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Literal, Optional

import anthropic
import pymupdf
from pydantic import BaseModel, Field

MODEL = "claude-opus-5"

PageType = Literal[
    "product_intro",   # 商品紹介
    "price_list",      # 価格表
    "installation",    # 納まり図
    "size_range",      # 寸法特注範囲
    "survey_manual",   # 現場調査マニュアル
    "index",           # 目次・索引
    "other",
]

AssetRole = Literal[
    "product_photo",      # 商品単体の写真
    "scene_photo",        # 施工例・イメージ写真
    "exterior_drawing",   # 外観図・姿図
    "section_drawing",    # 納まり図・断面図
    "dimension_drawing",  # 寸法図
    "diagram",            # 構成図・説明図
    "other",
]


class Spec(BaseModel):
    label: str = Field(description="仕様項目名（例: 材質、枠見込、ガラス厚、重量）")
    value: str = Field(description="紙面の表記どおりの値（単位を含む）")


class Product(BaseModel):
    code: str = Field(description="品番。紙面の表記どおり（ハイフン・記号を含む）")
    name: str = Field(description="商品名・部材名")
    series: str = Field(description="シリーズ名・品種名")
    variant: Optional[str] = Field(None, description="サイズ・仕様違いの区別（例: 6090、フタ付）")
    color: Optional[str] = Field(None, description="色名・色記号。表で色ごとに品番が分かれている場合")
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    depth_mm: Optional[int] = None
    list_price_yen: Optional[int] = Field(None, description="税抜の希望小売価格（円）")
    price_note: Optional[str] = Field(None, description="価格の単位・条件（1セット、1本 等）")
    specs: list[Spec] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list, description="この品番に対応する図・写真のID")


class SeriesInfo(BaseModel):
    name: str
    category: str = Field(description="カタログ上の分類（例: シャッター/雨戸 > リフォーム雨戸）")
    description: Optional[str] = None
    features: list[str] = Field(default_factory=list, description="特長・用途（「このような時に」等）")
    lineup: list[str] = Field(default_factory=list, description="商品体系に載っている品種・部材の名前")
    asset_ids: list[str] = Field(default_factory=list)


class AssetLabel(BaseModel):
    asset_id: str
    role: AssetRole
    caption: str = Field(description="施主向け資料に載せる短い説明")


class PageExtraction(BaseModel):
    page_type: PageType
    series: list[SeriesInfo]
    products: list[Product]
    assets: list[AssetLabel]
    notes: list[str] = Field(default_factory=list, description="価格・取付の注意書きなど、品番を選ぶ際の条件")
    uncertain: list[str] = Field(
        default_factory=list,
        description="読み取りに自信がない箇所。推測で埋めずにここへ書く",
    )


SYSTEM = """あなたは工務店向けに、住宅設備メーカーの総合カタログから商品データを作る担当者です。
渡されたカタログ1ページのPDFと、そのページから機械的に切り出した図・写真の一覧をもとに、
スキーマに沿ってデータ化してください。

- 品番・寸法・価格は紙面に印刷されている値だけを使う。計算や推測で補わない。
- 価格表がサイズ×色の表になっている場合は、品番の組み合わせごとに1件ずつ products に展開する。
  品番の組み立て規則（例: 基本品番＋サイズ記号＋色記号）が紙面にあれば notes に書く。
- 品番が載っていないページ（商品紹介など）では products を空にし、series に情報をまとめる。
- 縦書きの文字は1文字ずつばらばらに抽出されていることがあるので、PDFの見た目を優先して読む。
- 図・写真の一覧のIDは、それぞれの役割と、関係する品番・シリーズに割り当てる。
  1つの切り出しに複数の図がまとまっている場合は、その旨を uncertain に書く。
- 読み取れない、または判断に迷う箇所は uncertain に書く。"""


def page_pdf_bytes(doc: pymupdf.Document, index: int) -> bytes:
    single = pymupdf.open()
    single.insert_pdf(doc, from_page=index, to_page=index)
    return single.tobytes(garbage=3, deflate=True)


def build_request(pdf_bytes: bytes, page_json: dict) -> dict:
    assets = [
        {k: a[k] for k in ("id", "kind", "bbox", "nearby_text")}
        for a in page_json["assets"]
    ]
    prompt = (
        f"カタログ {page_json['printed_page']} ページです。\n"
        "座標はPDFのpt（左上原点、ページサイズ "
        f"{page_json['size'][0]:.0f}×{page_json['size'][1]:.0f}）です。\n\n"
        "<assets>\n" + json.dumps(assets, ensure_ascii=False, indent=1) + "\n</assets>"
    )
    return {
        "model": MODEL,
        "max_tokens": 16000,
        "system": SYSTEM,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode(),
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }


def extract(client: anthropic.Anthropic, request: dict) -> PageExtraction:
    # 安全判定で断られた場合は、サーバー側で別モデルに自動で切り替える
    response = client.beta.messages.parse(
        **request,
        output_format=PageExtraction,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"抽出を断られました: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("出力が上限で途切れました。max_tokens を増やしてください")
    if response.parsed_output is None:
        raise RuntimeError("構造化データを受け取れませんでした")
    return response.parsed_output


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--catalog-id", required=True)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--page-offset", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    client = None if args.dry_run else anthropic.Anthropic()

    for i in range(doc.page_count):
        printed = args.page_offset + i
        page_dir = args.raw / args.catalog_id / f"p{printed:04d}"
        page_json = json.loads((page_dir / "page.json").read_text(encoding="utf-8"))
        request = build_request(page_pdf_bytes(doc, i), page_json)

        if args.dry_run:
            text = request["messages"][0]["content"][1]["text"]
            print(f"--- p{printed} ({len(request['messages'][0]['content'][0]['source']['data'])} bytes base64)\n{text}")
            continue

        result = extract(client, request)
        out = {
            "catalog_id": args.catalog_id,
            "page": printed,
            "model": MODEL,
            "review_status": "draft",
            **result.model_dump(),
        }
        (page_dir / "extraction.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"p{printed}: {result.page_type}, {len(result.products)} products, "
              f"{len(result.uncertain)} uncertain")


if __name__ == "__main__":
    main()
