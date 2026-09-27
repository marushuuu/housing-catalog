-- housing-catalog のデータベーススキーマ
--
-- このデータベースは「データ構築システム（housing-catalog）」が書き込む唯一の場所で、
-- 「帳票作成システム（housing-spec-sheet）」はここを読み取り専用で参照する。
-- 2つのシステムはこのデータベースだけを介して連動し、互いのデプロイ・可用性には依存しない。

create extension if not exists pgcrypto;

-- 取り込んだカタログ（メーカー・版）の一覧
create table if not exists catalogs (
    id           text primary key,        -- 例: 'TE2400', 'TOTO-2026'
    maker        text not null,
    title        text not null,
    source_file  text,
    note         text,
    created_at   timestamptz not null default now()
);

-- シリーズ・品種（品番を持たない情報のまとまり。例:「リフォーム雨戸（雨戸一筋）」）
create table if not exists series (
    id           text primary key,        -- 例: 'TE2400-リフォーム雨戸（雨戸一筋）'
    catalog_id   text not null references catalogs(id) on delete cascade,
    name         text not null,
    category     text not null,
    description  text,
    features     jsonb not null default '[]',  -- text[] 相当
    lineup       jsonb not null default '[]',
    notes        jsonb not null default '[]',
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- 品番ごとの商品仕様
create table if not exists products (
    id               uuid primary key default gen_random_uuid(),
    catalog_id       text not null references catalogs(id) on delete cascade,
    series_id        text references series(id) on delete set null,
    code             text not null,        -- 紙面の表記どおりの品番
    code_key         text not null,        -- 検索用の正規化キー（全角・ハイフン等を吸収）
    name             text not null,
    variant          text,
    color            text,
    width_mm         integer,
    height_mm        integer,
    depth_mm         integer,
    list_price_yen   integer,
    price_note       text,
    specs            jsonb not null default '[]',  -- [{label, value}, ...]
    source_page      integer,
    review_status    text not null default 'draft'
                     check (review_status in ('draft', 'verified', 'sample')),
    reviewed_by      text,
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now(),
    unique (catalog_id, code)
);

-- 品番はカタログをまたいで表記が重複しうるが、検索は正規化キーで行うため索引を張る
create index if not exists idx_products_code_key on products (code_key);
create index if not exists idx_products_series on products (series_id);

-- 図・写真（1件が複数の品番・シリーズから参照されうる）
create table if not exists assets (
    id           text primary key,        -- 例: 'TE2400/p164/img_0'
    catalog_id   text not null references catalogs(id) on delete cascade,
    page         integer not null,
    kind         text not null check (kind in ('photo', 'figure')),
    role         text not null default 'other',
    caption      text not null default '',
    file_path    text not null,           -- オブジェクトストレージ上のパス（下記 storage 参照）
    width        integer,
    height       integer,
    created_at   timestamptz not null default now()
);

-- 品番・シリーズと図・写真の対応（多対多）
create table if not exists product_assets (
    product_id  uuid not null references products(id) on delete cascade,
    asset_id    text not null references assets(id) on delete cascade,
    sort_order  integer not null default 0,
    primary key (product_id, asset_id)
);

create table if not exists series_assets (
    series_id   text not null references series(id) on delete cascade,
    asset_id    text not null references assets(id) on delete cascade,
    sort_order  integer not null default 0,
    primary key (series_id, asset_id)
);

-- 帳票作成システム側は、products / series / assets / catalogs をこの形のまま読み取る。
-- 書き込みは ingest/load_db.py（データ構築システム側）だけが行う。
