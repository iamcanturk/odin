"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { IconClose } from "./icons";

/**
 * A focused overlay. Escape and backdrop close it; body scroll is locked while open
 * so the feed behind doesn't drift under the cursor.
 */
export function Modal({
  open,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKey);
    panel.current?.focus();
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  // Nothing touches `document` until `open` is true, and that only happens from a
  // click — so there's no server render to guard against.
  if (!open) return null;

  // Portalled to <body>: an ancestor with backdrop-blur becomes the containing block
  // for `position: fixed`, which silently clipped this to a third of the viewport.
  return createPortal(
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 overflow-y-auto bg-black/70 backdrop-blur-sm"
    >
      {/* min-h-full + centring: short content centres, tall content scrolls from the top. */}
      <div className="flex min-h-full items-center justify-center p-4 sm:p-6">
        <div
          ref={panel}
          tabIndex={-1}
          onClick={(e) => e.stopPropagation()}
          className={`relative w-full ${wide ? "max-w-5xl" : "max-w-2xl"} rounded-[var(--radius)] border border-border bg-panel shadow-[var(--shadow)] outline-none`}
        >
          <button
            onClick={onClose}
            className="absolute top-3 right-3 z-10 rounded-md p-1.5 text-faint hover:text-text hover:bg-panel-2 transition-colors"
            aria-label="Kapat"
          >
            <IconClose width={16} height={16} />
          </button>
          {children}
        </div>
      </div>
    </div>,
    document.body,
  );
}
