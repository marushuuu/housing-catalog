import data from "@/data/catalog.json";

export type Spec = { label: string; value: string };

export type Asset = {
  id: string;
  src: string;
  width: number;
  height: number;
  kind: "photo" | "figure";
  role: string;
  caption: string;
  catalog_id: string;
  page: number;
};

export type Source = { catalog_id: string; page: number };

export type Product = {
  code: string;
  key: string;
  name: string;
  series: string;
  series_id: string | null;
  variant: string | null;
  color: string | null;
  width_mm: number | null;
  height_mm: number | null;
  depth_mm: number | null;
  list_price_yen: number | null;
  price_note: string | null;
  specs: Spec[];
  assets: string[];
  source: Source;
  review_status: "verified" | "draft" | "sample";
  is_sample: boolean;
};

export type Series = {
  id: string;
  name: string;
  category: string;
  description: string | null;
  features: string[];
  lineup: string[];
  notes: string[];
  assets: string[];
  sources: Source[];
};

export type Catalog = {
  id: string;
  maker: string;
  title: string;
  source_file: string;
  note?: string;
};

type CatalogData = {
  generated_at: string;
  catalogs: Catalog[];
  series: Series[];
  products: Product[];
  assets: Record<string, Asset>;
};

const catalog = data as CatalogData;

export const generatedAt = catalog.generated_at;
export const allProducts = catalog.products;
export const allSeries = catalog.series;

// ingest/build_catalog.py の normalize_code と同じ規則
export function normalizeCode(code: string): string {
  return code
    .normalize("NFKC")
    .toUpperCase()
    .replace(/[\s\-‐‑–—―ー_/・]/g, "");
}

export function findProduct(code: string): Product | undefined {
  const key = normalizeCode(code);
  return catalog.products.find((p) => p.key === key);
}

export function searchProducts(query: string): Product[] {
  const key = normalizeCode(query);
  if (!key) return [];
  const q = query.trim();
  return catalog.products.filter(
    (p) =>
      p.key.includes(key) ||
      p.name.includes(q) ||
      p.series.includes(q),
  );
}

export function getSeries(id: string | null): Series | undefined {
  return catalog.series.find((s) => s.id === id);
}

export function getAssets(ids: string[]): Asset[] {
  return ids.map((id) => catalog.assets[id]).filter(Boolean);
}

export function getCatalog(id: string): Catalog | undefined {
  return catalog.catalogs.find((c) => c.id === id);
}

export function sourceLabel(source: Source): string {
  const c = getCatalog(source.catalog_id);
  return `${c ? `${c.maker} ${c.title}` : source.catalog_id} ${source.page}ページ`;
}

export function productPath(p: Product): string {
  return `/products/${encodeURIComponent(p.code)}`;
}

export function formatPrice(p: Product): string {
  if (p.list_price_yen == null) return "—";
  const yen = `¥${p.list_price_yen.toLocaleString("ja-JP")}`;
  return p.price_note ? `${yen}（${p.price_note}）` : yen;
}

export function formatSize(p: Product): string {
  const parts = [
    p.width_mm != null && `W${p.width_mm}`,
    p.height_mm != null && `H${p.height_mm}`,
    p.depth_mm != null && `D${p.depth_mm}`,
  ].filter(Boolean);
  return parts.length ? `${parts.join(" × ")} mm` : "—";
}
