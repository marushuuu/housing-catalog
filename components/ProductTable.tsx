import Link from "next/link";
import { formatPrice, productPath, type Product } from "@/lib/catalog";
import StatusBadge from "@/components/StatusBadge";

export default function ProductTable({ products }: { products: Product[] }) {
  if (products.length === 0) {
    return <p className="text-sm text-slate-500">該当する品番はありません。</p>;
  }
  return (
    <table className="w-full overflow-hidden rounded-md bg-white text-sm shadow-sm">
      <thead className="bg-slate-100 text-left text-slate-600">
        <tr>
          <th className="px-3 py-2">品番</th>
          <th className="px-3 py-2">商品名</th>
          <th className="px-3 py-2">シリーズ</th>
          <th className="px-3 py-2">価格</th>
          <th className="px-3 py-2">状態</th>
        </tr>
      </thead>
      <tbody>
        {products.map((p) => (
          <tr key={p.key} className="border-t border-slate-100">
            <td className="px-3 py-2 font-mono">
              <Link href={productPath(p)} className="text-blue-700 hover:underline">
                {p.code}
              </Link>
            </td>
            <td className="px-3 py-2">{p.name}</td>
            <td className="px-3 py-2">{p.series}</td>
            <td className="px-3 py-2">{formatPrice(p)}</td>
            <td className="px-3 py-2">
              <StatusBadge product={p} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
