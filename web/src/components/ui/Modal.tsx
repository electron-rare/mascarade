import { ReactNode, useEffect, useId, useRef } from "react";

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
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusables = () =>
      panelRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? [];

    window.requestAnimationFrame(() => {
      const firstInteractive = focusables()[0];
      firstInteractive?.focus();
    });

    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key !== "Tab") {
        return;
      }

      const nodes = Array.from(focusables());
      if (nodes.length === 0) {
        e.preventDefault();
        panelRef.current?.focus();
        return;
      }

      const currentIndex = nodes.findIndex((node) => node === document.activeElement);
      if (e.shiftKey) {
        if (currentIndex <= 0) {
          e.preventDefault();
          nodes[nodes.length - 1]?.focus();
        }
        return;
      }

      if (currentIndex === nodes.length - 1) {
        e.preventDefault();
        nodes[0]?.focus();
      }
    };

    document.addEventListener("keydown", handler);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handler);
      restoreFocusRef.current?.focus();
    };
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
      <div
        ref={panelRef}
        tabIndex={-1}
        className="relative mx-4 w-full max-w-xl rounded-[2rem] border border-border/80 bg-[linear-gradient(180deg,rgba(9,11,10,0.98),rgba(7,7,7,0.98))] shadow-[0_28px_80px_rgba(0,0,0,0.52)]"
      >
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
            type="button"
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
