# housing-catalog（データ構築システム）

工務店向けシステムの一部です。全体は2つのシステムに分かれています。

- **housing-catalog（このリポジトリ）**：データ構築システム。メーカーのカタログPDFから
  品番・商品仕様・商品図・商品画像を取り込み、共有データベースへ書き込む。
- **housing-spec-sheet（別リポジトリ）**：帳票作成システム。品番を入力すると仕様データを
  引いて、見積り・仕様図として表示・出力する。このリポジトリのデータベースを読み取り専用で参照する。

2つは別々にリポジトリ・デプロイ先を分け、共有データベースだけを介して連動する。
データベースへの書き込みは、このリポジトリの `ingest/load_db.py` だけが行う。

## 全体の流れ

```
カタログPDF
  │ 1. ingest/extract_page.py   文字・写真・図（ベクター）を機械的に切り出す → data/raw/
  │ 2. ingest/llm_extract.py    Claude がページを読み、品番・仕様を構造化 → data/raw/.../extraction.json（未確認）
  │ 3. 人が確認・修正            → data/reviewed/<カタログ>/p<ページ>.json（review_status: "verified"）
  │ 4. ingest/load_db.py        確認済みデータをデータベースへ書き込む → storage/（図・写真の実ファイル）
  ▼
共有データベース（db/schema.sql）
  catalogs / series / products / assets / product_assets / series_assets
  ▼
housing-spec-sheet（別リポジトリ）が読み取り専用で参照
```

## セットアップ

```bash
pip install -r ingest/requirements.txt

# ローカルでの動作確認用（本番はSupabase等マネージドPostgresを想定）
createdb housing_catalog
cp .env.example .env   # DATABASE_URL を編集
export $(cat .env | xargs)
psql "$DATABASE_URL" -f db/schema.sql
```

## カタログの取込手順

```bash
# 1. 切り出し（--page-offset は抜粋PDFの先頭ページのカタログ上のページ番号）
python ingest/extract_page.py catalogs/TE2400_0166.pdf --catalog-id TE2400 --page-offset 164

# 2. AI抽出（ANTHROPIC_API_KEY が必要。--dry-run で送信内容だけ確認できる）
python ingest/llm_extract.py catalogs/TE2400_0166.pdf --catalog-id TE2400 --page-offset 164

# 3. data/raw/TE2400/p0164/extraction.json を確認・修正し、
#    review_status を "verified" にして data/reviewed/TE2400/p0164.json に置く

# 4. データベースへ書き込み（再実行しても安全。既存行は上書きされる）
python ingest/load_db.py
```

カタログを追加するときは `data/catalogs.json` にも登録する。

## データベース（db/schema.sql）

- `catalogs`：取り込んだカタログ（メーカー・版）の一覧
- `series`：品番を持たないシリーズ・品種の情報（特長、注意事項など）
- `products`：品番ごとの商品仕様。`code_key` は全角・ハイフン等を吸収した検索キー
  （`housing-spec-sheet` 側の検索も同じ正規化規則を使う）
- `assets`：図・写真。`file_path` はオブジェクトストレージ上の相対パス
- `product_assets` / `series_assets`：品番・シリーズと図・写真の対応（多対多）

`ingest/load_db.py` が書き込む図・写真の実ファイルは `storage/` に配置される
（gitには含めない）。本番では、ここをオブジェクトストレージ（S3 / Supabase Storage 等）へ
同期し、`housing-spec-sheet` はそこから配信する。

## データの扱い

- **品番・寸法・価格は人の確認を通ったものだけをデータベースへ入れます**（`review_status = "verified"`）。
  `data/samples/demo.json` はダミー品番（`review_status = "sample"`）で、
  帳票作成システム側の動作確認用。実データが揃ったら削除する。
- AIの抽出結果（`draft`）は `load_db.py --include-drafts` で取り込める（確認用。本番投入の前提ではない）。
- 写真は紙面のトリミングどおりの切り出しを保存する。図はベクター描画を近接でまとめて切り出すため、
  隣り合う図が1枚にまとまることがある。確認時に直す。

## 現状（試作）

- 検証に使ったのは、LIXIL「TE2400」の164ページ（リフォーム雨戸の商品紹介）1ページのみ。
  品番の記載がないページのため、`data/reviewed/TE2400/p0164.json` はシリーズ情報だけを手入力している。
- `toto/` に TOTO 総合カタログ（18分割PDF、計1028ページ、品番索引あり）を配置済み。
  こちらの取込はこれから。
- `data/samples/demo.json` の `SAMPLE-6090` は動作確認用のダミー品番。

## 今後の課題

- TOTOカタログの取込（品番索引からの品番一覧化、価格表ページの読み取り精度）
- 価格表ページ（サイズ×色の表）から品番を展開する精度の検証
- 確認・修正用の画面（現状はJSONを直接編集）
- `storage/` からオブジェクトストレージへの同期の自動化
- カタログ改訂時の差分確認
