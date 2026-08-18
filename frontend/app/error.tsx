"use client"; // Error boundaries must be Client Components

import { useEffect } from "react";
import Link from "next/link";

/**
 * Catches render errors so one broken panel shows a recoverable message instead of
 * blanking the whole app. Deliberately free of app dependencies (i18n, API, UI kit) —
 * if one of those is what crashed, this still has to render.
 */
export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error("[ODIN] render error:", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <p className="font-mono text-sm text-hot">Bir şeyler ters gitti</p>
      <p className="mt-2 text-sm text-muted">
        Bu bölüm yüklenemedi. Tekrar denemek sorunu genelde çözer.
      </p>
      {error?.message && (
        <p className="mt-3 font-mono text-[11px] text-faint break-words">{error.message}</p>
      )}
      <div className="mt-6 flex items-center justify-center gap-2">
        <button
          onClick={() => retry()}
          className="rounded-lg border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 transition-colors"
        >
          Tekrar dene
        </button>
        <Link
          href="/"
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted hover:text-text transition-colors"
        >
          Konsola dön
        </Link>
      </div>
    </div>
  );
}
