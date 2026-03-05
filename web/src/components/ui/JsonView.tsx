export default function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="bg-black/45 border border-border rounded p-3 text-xs text-amber-100/90 overflow-auto max-h-96 whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
