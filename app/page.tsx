import SearchForm from "@/components/SearchForm";
import ProductTable from "@/components/ProductTable";
import { allProducts, allSeries, generatedAt } from "@/lib/catalog";

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-10">
      <section className="space-y-3">
        <h1 className="text-2xl font-bold">品番から商品仕様を表示</h1>
        <p className="text-sm text-slate-600">
          カタログから取り込んだ品番を入力すると、仕様・商品図・画像を表示し、施主向け資料として出力できます。
        </p>
        <SearchForm />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">登録済みの品番（{allProducts.length}件）</h2>
        <ProductTable products={allProducts} />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">取り込み済みのシリーズ（{allSeries.length}件）</h2>
        <ul className="space-y-2 text-sm">
          {allSeries.map((s) => (
            <li key={s.id} className="rounded-md bg-white p-3 shadow-sm">
              <div className="font-bold">{s.name}</div>
              <div className="text-slate-500">{s.category}</div>
            </li>
          ))}
        </ul>
        <p className="text-xs text-slate-400">データ生成日時: {generatedAt}</p>
      </section>
    </div>
  );
}
