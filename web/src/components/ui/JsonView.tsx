export default function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-[1.5rem] border border-border/80 bg-black/35 p-4 text-xs text-amber-100/88 whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
