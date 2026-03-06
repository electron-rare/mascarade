import { ReactNode, useEffect, useId } from "react";

export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const titleId = useId();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (open) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative mx-4 w-full max-w-xl rounded-[2rem] border border-border/80 bg-[linear-gradient(180deg,rgba(9,11,10,0.98),rgba(7,7,7,0.98))] shadow-[0_28px_80px_rgba(0,0,0,0.52)]">
        <div className="flex items-center justify-between border-b border-border/80 bg-black/25 px-5 py-4">
          <div>
            <p className="screen-label">modal</p>
            <h2
              id={titleId}
              className="mt-2 text-sm font-semibold uppercase tracking-[0.18em] text-accent glow-text"
            >
              {title}
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-full border border-border/80 bg-black/25 px-3 py-1 text-sm text-muted transition hover:border-accent/40 hover:text-accent"
          >
            ×
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
