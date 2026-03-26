export default function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4 text-xs text-[#6e6e73] whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
