export default function SearchForm({ defaultValue = "" }: { defaultValue?: string }) {
  return (
    <form action="/search" className="flex gap-2">
      <input
        name="q"
        defaultValue={defaultValue}
        placeholder="品番を入力（例: SAMPLE-6090）"
        autoFocus
        className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-lg"
      />
      <button className="rounded-md bg-slate-800 px-5 py-2 text-white">検索</button>
    </form>
  );
}
