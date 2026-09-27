"""共有データベースへの接続設定。

DATABASE_URL 環境変数（postgres://...）を読む。本番では Supabase 等の
マネージドPostgresを想定。帳票作成システム（housing-spec-sheet）も
同じ DATABASE_URL を指す別のデータベースユーザー（読み取り専用）で接続する。
"""

from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL が設定されていません。"
            "例: postgres://user:pass@host:5432/housing_catalog"
        )
    conn = psycopg2.connect(url)
    psycopg2.extras.register_default_jsonb(conn_or_curs=conn)
    return conn
