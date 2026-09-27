import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import AssetFigure from "@/components/AssetFigure";
import StatusBadge from "@/components/StatusBadge";
import {
  findProduct,
  formatPrice,
  formatSize,
  getAssets,
  getSeries,
  productPath,
  sourceLabel,
} from "@/lib/catalog";

type Props = { params: Promise<{ code: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { code } = await params;
  const product = findProduct(decodeURIComponent(code));
  return { title: product ? `${product.code} ${product.name}` : "品番が見つかりません" };
}

export default async function ProductPage({ params }: Props) {
  const { code } = await params;
  const product = findProduct(decodeURIComponent(code));
  if (!product) notFound();

  const series = getSeries(product.series_id);
  const assets = getAssets(product.assets);
  const seriesAssets = getAssets(series?.assets ?? []).filter(
    (a) => !product.assets.includes(a.id),
  );

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-10">
      {product.is_sample && (
        <p className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">
          これは画面確認用のダミー品番です。実在の品番・価格ではありません。
        </p>
      )}

      <section className="flex flex-wrap items-start gap-4">
        <div className="flex-1 space-y-1">
          <div className="text-sm text-slate-500">{product.series}</div>
          <h1 className="text-2xl font-bold">{product.name}</h1>
          <div className="font-mono text-lg">{product.code}</div>
          <StatusBadge product={product} />
        </div>
        <form action={`${productPath(product)}/sheet`} className="w-full space-y-2 rounded-md bg-white p-4 shadow-sm sm:w-80">
          <div className="text-sm font-bold">施主向け資料を出力</div>
          <input name="project" placeholder="物件名" className="w-full rounded border border-slate-300 px-2 py-1 text-sm" />
          <input name="client" placeholder="施主名" className="w-full rounded border border-slate-300 px-2 py-1 text-sm" />
          <input name="location" placeholder="設置場所（例: 1階 リビング南面）" className="w-full rounded border border-slate-300 px-2 py-1 text-sm" />
          <button className="w-full rounded-md bg-slate-800 px-3 py-2 text-sm text-white">
            出力プレビュー
          </button>
        </form>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold">商品仕様</h2>
        <table className="w-full rounded-md bg-white text-sm shadow-sm">
          <tbody>
            <Row label="品番" value={product.code} />
            <Row label="商品名" value={product.name} />
            <Row label="シリーズ" value={product.series} />
            {product.variant && <Row label="仕様" value={product.variant} />}
            {product.color && <Row label="色" value={product.color} />}
            <Row label="寸法" value={formatSize(product)} />
            <Row label="希望小売価格（税抜）" value={formatPrice(product)} />
            {product.specs.map((s) => (
              <Row key={s.label} label={s.label} value={s.value} />
            ))}
            <Row label="出典" value={sourceLabel(product.source)} />
          </tbody>
        </table>
      </section>

      {assets.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">商品図・画像</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {assets.map((a) => (
              <AssetFigure key={a.id} asset={a} />
            ))}
          </div>
        </section>
      )}

      {series && (
        <section className="space-y-3">
          <h2 className="text-lg font-bold">シリーズ情報：{series.name}</h2>
          {series.description && <p className="text-sm">{series.description}</p>}
          {series.features.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {series.features.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          )}
          {series.notes.length > 0 && (
            <div className="rounded-md bg-amber-50 p-3 text-sm">
              <div className="mb-1 font-bold">注意事項</div>
              <ul className="list-disc space-y-1 pl-5">
                {series.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          )}
          {seriesAssets.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2">
              {seriesAssets.map((a) => (
                <AssetFigure key={a.id} asset={a} />
              ))}
            </div>
          )}
        </section>
      )}

      <Link href="/" className="inline-block text-sm text-blue-700 hover:underline">
        ← 品番一覧へ
      </Link>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr className="border-t border-slate-100 first:border-t-0">
      <th className="w-48 bg-slate-50 px-3 py-2 text-left font-normal text-slate-600">{label}</th>
      <td className="px-3 py-2">{value}</td>
    </tr>
  );
}
