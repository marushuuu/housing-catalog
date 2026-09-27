import { redirect } from "next/navigation";
import SearchForm from "@/components/SearchForm";
import ProductTable from "@/components/ProductTable";
import { findProduct, productPath, searchProducts } from "@/lib/catalog";

export const metadata = { title: "検索" };

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { q } = await searchParams;
  const query = typeof q === "string" ? q : "";

  // 品番が完全一致したら商品ページへ直接移動
  const exact = query ? findProduct(query) : undefined;
  if (exact) redirect(productPath(exact));

  const results = searchProducts(query);
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-10">
      <SearchForm defaultValue={query} />
      <h1 className="text-lg font-bold">
        「{query}」の検索結果（{results.length}件）
      </h1>
      <ProductTable products={results} />
    </div>
  );
}
