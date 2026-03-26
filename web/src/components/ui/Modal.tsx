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
      <div className="absolute inset-0 bg-[#f5f5f7] backdrop-blur-xl" onClick={onClose} />
      <div
        ref={panelRef}
        tabIndex={-1}
        className="relative mx-4 w-full max-w-xl rounded-apple-lg border border-[rgba(0,0,0,0.06)] bg-white shadow-apple-lg"
      >
        <div className="flex items-center justify-between border-b border-[rgba(0,0,0,0.06)] px-5 py-4">
          <div>
            <p className="text-xs text-muted">modal</p>
            <h2
              id={titleId}
              className="mt-1 text-sm font-semibold text-[#1d1d1f]"
            >
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full bg-surface px-3 py-1 text-sm text-muted transition hover:bg-[#e8e8ed] hover:text-[#1d1d1f]"
          >
            &times;
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
