export default function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="bg-bg border border-border rounded p-3 text-xs text-slate-300 overflow-auto max-h-96 whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
