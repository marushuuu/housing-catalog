import type { Product } from "@/lib/catalog";

const styles = {
  verified: "bg-emerald-100 text-emerald-800",
  draft: "bg-amber-100 text-amber-800",
  sample: "bg-rose-100 text-rose-800",
};

const labels = {
  verified: "確認済み",
  draft: "未確認（AI抽出）",
  sample: "ダミー",
};

export default function StatusBadge({ product }: { product: Product }) {
  const s = product.review_status;
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${styles[s]}`}>{labels[s]}</span>
  );
}
