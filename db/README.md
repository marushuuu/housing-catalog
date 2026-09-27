# db/

`schema.sql` が、データ構築システム（housing-catalog）と帳票作成システム（housing-spec-sheet）が
共有するデータベースの唯一の定義です。書き込みはこのリポジトリの `ingest/load_db.py` だけが行います。

housing-spec-sheet 側でスキーマを変更したい場合は、このリポジトリの `db/schema.sql` を更新し、
housing-spec-sheet はそれに追従する形にしてください（スキーマの発生源をここに一本化するため）。
