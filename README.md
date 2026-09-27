# 住宅設備カタログ検索（housing-catalog）

工務店向けのシステムです。メーカーのカタログPDFから品番・商品仕様・商品図・商品画像を取り込みます。
品番を指定すると仕様を表示し、施主向けの「商品仕様書」（A4）として出力します。

## 全体の流れ

```
カタログPDF
  │ 1. ingest/extract_page.py   文字・写真・図（ベクター）を機械的に切り出す → data/raw/
  │ 2. ingest/llm_extract.py    Claude がページを読み、品番・仕様を構造化 → data/raw/.../extraction.json（未確認）
  │ 3. 人が確認・修正            → data/reviewed/<カタログ>/p<ページ>.json（review_status: "verified"）
  │ 4. ingest/build_catalog.py  確認済みデータをまとめる → data/catalog.json, public/catalog-assets/
  ▼
Webアプリ（Next.js）
  /                        品番検索・登録済み一覧
  /search?q=品番           完全一致なら商品ページへ移動（全角・小文字・ハイフンの違いは吸収）
  /products/[品番]          仕様・商品図・画像・シリーズ情報・注意事項
  /products/[品番]/sheet    施主向け「商品仕様書」（印刷 / PDF保存）
```

## セットアップ

```bash
# 取込（Python 3.10+）
pip install -r ingest/requirements.txt

# Webアプリ
npm install
npm run dev   # http://localhost:3000
```

## カタログの取込手順

```bash
# 1. 切り出し（--page-offset は抜粋PDFの先頭ページのカタログ上のページ番号）
python ingest/extract_page.py catalogs/TE2400_0166.pdf --catalog-id TE2400 --page-offset 164

# 2. AI抽出（ANTHROPIC_API_KEY が必要。--dry-run で送信内容だけ確認できる）
python ingest/llm_extract.py catalogs/TE2400_0166.pdf --catalog-id TE2400 --page-offset 164

# 3. data/raw/TE2400/p0164/extraction.json を確認・修正し、
#    review_status を "verified" にして data/reviewed/TE2400/p0164.json に置く

# 4. Webアプリ用データを生成
python ingest/build_catalog.py
```

カタログを追加するときは `data/catalogs.json` にも登録します。

## データの扱い

- **品番・寸法・価格は人の確認を通ったものだけを表示します**。AIの抽出結果（`draft`）は、確認用に
  `build_catalog.py --include-drafts` で表示できます。画面には「未確認」の表示が付きます。
- 図・写真は `data/raw/.../page.json` の `assets` に ID 付きで切り出されます。AI がそれぞれに役割
  （商品写真・納まり図など）と対応する品番を割り当てます。
- 写真は紙面のトリミングどおりの切り出し（`img_N.png`）と、元の埋め込み画像（`img_N_original.*`）の両方を保存します。
- 図はベクター描画を近接でまとめて切り出すため、隣り合う図が1枚にまとまることがあります。確認時に直します。

## 現状（試作）

- 検証に使ったのは、TE2400 の164ページ（リフォーム雨戸の商品紹介）1ページだけです。このページには
  品番の記載がないため、`data/reviewed/TE2400/p0164.json` はシリーズ情報だけを手入力で作っています。
- `data/samples/demo.json` の `SAMPLE-6090` は、画面と出力の動作確認用のダミー品番です。価格表ページを
  取り込んだら削除します（`build_catalog.py --no-samples` で除外できます）。
- 出力フォーマット（`app/products/[code]/sheet/page.tsx`）は仮のものです。既定のフォーマットが決まったら差し替えます。

## 今後の課題

- 価格表ページ（サイズ×色の表）から品番を展開する精度の検証
- 確認・修正用の画面（現状はJSONを直接編集）
- 複数品番をまとめた資料の出力、Excel形式での出力
- カタログ改訂時の差分確認
- データ量が増えたらJSONファイルからデータベースへ移行
