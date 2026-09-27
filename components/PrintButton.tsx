"use client";

export default function PrintButton() {
  return (
    <button
      onClick={() => window.print()}
      className="rounded-md bg-slate-800 px-4 py-2 text-white"
    >
      印刷 / PDFで保存
    </button>
  );
}
