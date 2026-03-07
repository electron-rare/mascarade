import { useMemo, useState } from "react";
import Button from "./Button";

function displayModelName(name: string): string {
  const withoutPrefix = name.replace(/^hf\.co\//, "");
  return withoutPrefix;
}

export default function CompactModelList({
  items,
  title = "local ollama models",
  previewCount = 6,
}: {
  items: string[];
  title?: string;
  previewCount?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const orderedItems = useMemo(() => items.filter(Boolean), [items]);
  const visibleItems = expanded ? orderedItems : orderedItems.slice(0, previewCount);
  const hiddenCount = Math.max(0, orderedItems.length - visibleItems.length);

  if (orderedItems.length === 0) {
    return null;
  }

  return (
    <div className="rounded-3xl border border-[#214e31] bg-[#0c170f]/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-[#8cffb7]">{title}</p>
          <p className="mt-2 text-[12px] leading-5 text-amber-100/52">
            {orderedItems.length} modele(s) detecte(s) dans le runtime local.
          </p>
        </div>
        {orderedItems.length > previewCount ? (
          <Button
            type="button"
            variant="ghost"
            className="min-h-0 px-3 py-2 text-[10px]"
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "collapse" : `show all ${orderedItems.length}`}
          </Button>
        ) : null}
      </div>

      <div className={expanded ? "mt-3 max-h-56 overflow-y-auto pr-1" : "mt-3"}>
        <div className="flex flex-wrap gap-2">
          {visibleItems.map((item) => (
            <span
              key={item}
              title={item}
              className="inline-flex max-w-full items-center rounded-full border border-accent/35 bg-accent/10 px-3 py-1 text-[11px] font-medium tracking-[0.03em] text-accent"
            >
              <span className="max-w-[20rem] truncate">{displayModelName(item)}</span>
            </span>
          ))}
          {!expanded && hiddenCount > 0 ? (
            <span className="inline-flex items-center rounded-full border border-border/80 bg-black/25 px-3 py-1 text-[11px] font-medium tracking-[0.03em] text-muted">
              +{hiddenCount} more
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
