import Image from "next/image";
import type { Asset } from "@/lib/catalog";

export default function AssetFigure({
  asset,
  className = "",
  sizes = "(min-width: 768px) 50vw, 100vw",
  eager = false,
}: {
  asset: Asset;
  className?: string;
  sizes?: string;
  // 印刷用ページでは遅延読込すると改ページ位置の計算がずれるため即時に読む
  eager?: boolean;
}) {
  return (
    <figure className={`break-inside-avoid ${className}`}>
      <Image
        src={asset.src}
        alt={asset.caption}
        width={asset.width}
        height={asset.height}
        sizes={sizes}
        loading={eager ? "eager" : "lazy"}
        className="h-auto w-full border border-slate-200 bg-white object-contain"
      />
      <figcaption className="mt-1 text-xs text-slate-600">{asset.caption}</figcaption>
    </figure>
  );
}
