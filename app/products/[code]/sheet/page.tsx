import type { Metadata } from "next";
import { notFound } from "next/navigation";
import AssetFigure from "@/components/AssetFigure";
import PrintButton from "@/components/PrintButton";
import {
  findProduct,
  formatPrice,
  formatSize,
  getAssets,
  getSeries,
  sourceLabel,
} from "@/lib/catalog";

// 施主向け「商品仕様書」の仮フォーマット（A4縦1枚）。
// 既定の出力フォーマットが決まったら、このページのレイアウトを差し替える。

type Props = {
  params: Promise<{ code: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { code } = await params;
  return { title: `商品仕様書 ${decodeURIComponent(code)}` };
}

const text = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

export default async function SheetPage({ params, searchParams }: Props) {
  const { code } = await params;
  const query = await searchParams;
  const product = findProduct(decodeURIComponent(code));
  if (!product) notFound();

  const series = getSeries(product.series_id);
  const assets = getAssets(product.assets);
  const photos = assets.filter((a) => a.kind === "photo");
  const figures = assets.filter((a) => a.kind === "figure");
  const today = new Date().toLocaleDateString("ja-JP", { timeZone: "Asia/Tokyo" });

  return (
    <div className="mx-auto max-w-[210mm] py-6 print:py-0">
      <div className="mb-4 flex items-center justify-end gap-3 px-4 print:hidden">
        <span className="text-sm text-slate-500">ブラウザの印刷から PDF に保存できます</span>
        <PrintButton />
      </div>

      <article className="space-y-5 bg-white p-[12mm] text-[10.5pt] shadow print:p-0 print:shadow-none">
        {product.is_sample && (
          <p className="border border-rose-400 p-2 text-center text-rose-700">
            ダミー品番による出力見本です（実在の品番・価格ではありません）
          </p>
        )}

        <header className="flex items-end justify-between border-b-2 border-slate-800 pb-2">
          <h1 className="text-[18pt] font-bold tracking-widest">商品仕様書</h1>
          <div className="text-right text-[9pt] text-slate-600">作成日 {today}</div>
        </header>

        <table className="w-full border-collapse text-[10pt]">
          <tbody>
            <SheetRow label="物件名" value={text(query.project)} />
            <SheetRow label="施主名" value={text(query.client) && `${text(query.client)} 様`} />
            <SheetRow label="設置場所" value={text(query.location)} />
          </tbody>
        </table>

        <section className="space-y-2">
          <h2 className="border-l-4 border-slate-800 pl-2 font-bold">商品仕様</h2>
          <table className="w-full border-collapse text-[10pt]">
            <tbody>
              <SheetRow label="品番" value={product.code} />
              <SheetRow label="商品名" value={product.name} />
              <SheetRow label="シリーズ" value={product.series} />
              {product.variant && <SheetRow label="仕様" value={product.variant} />}
              {product.color && <SheetRow label="色" value={product.color} />}
              <SheetRow label="寸法" value={formatSize(product)} />
              <SheetRow label="希望小売価格（税抜）" value={formatPrice(product)} />
              {product.specs.map((s) => (
                <SheetRow key={s.label} label={s.label} value={s.value} />
              ))}
            </tbody>
          </table>
        </section>

        {photos.length > 0 && (
          <section className="space-y-2">
            <h2 className="border-l-4 border-slate-800 pl-2 font-bold">商品画像</h2>
            <div className="grid grid-cols-2 gap-4">
              {photos.map((a) => (
                <AssetFigure key={a.id} asset={a} sizes="90mm" eager />
              ))}
            </div>
          </section>
        )}

        {figures.length > 0 && (
          <section className="space-y-3">
            {/* 見出しだけがページ末尾に残らないよう、最初の図と一緒に改ページさせる */}
            {figures.map((a, i) => (
              <div key={a.id} className="break-inside-avoid space-y-2">
                {i === 0 && (
                  <h2 className="border-l-4 border-slate-800 pl-2 font-bold">商品図</h2>
                )}
                <AssetFigure asset={a} sizes="186mm" eager />
              </div>
            ))}
          </section>
        )}

        {series && series.notes.length > 0 && (
          <section className="break-inside-avoid space-y-1 text-[8.5pt] text-slate-700">
            <h2 className="font-bold">ご注意</h2>
            <ul className="list-disc space-y-0.5 pl-5">
              {series.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </section>
        )}

        <footer className="border-t border-slate-300 pt-2 text-[8pt] text-slate-500">
          出典：{sourceLabel(product.source)}
        </footer>
      </article>
    </div>
  );
}

function SheetRow({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <th className="w-40 border border-slate-400 bg-slate-100 px-2 py-1 text-left font-normal">
        {label}
      </th>
      <td className="border border-slate-400 px-2 py-1">{value}</td>
    </tr>
  );
}
