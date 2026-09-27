import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "住宅設備カタログ検索",
    template: "%s | 住宅設備カタログ検索",
  },
  description: "品番から住宅設備の仕様・商品図・画像を表示し、施主向け資料として出力します。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja" className="h-full">
      <body className="min-h-full flex flex-col">
        <header className="border-b border-slate-200 bg-white print:hidden">
          <div className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
            <Link href="/" className="font-bold text-slate-900">
              住宅設備カタログ検索
            </Link>
            <form action="/search" className="ml-auto flex gap-2">
              <input
                name="q"
                placeholder="品番を入力"
                className="w-48 rounded border border-slate-300 px-2 py-1 text-sm"
              />
              <button className="rounded bg-slate-800 px-3 py-1 text-sm text-white">
                検索
              </button>
            </form>
          </div>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
