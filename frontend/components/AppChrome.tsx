"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AuthGate } from "./AuthGate";
import { HeaderNav } from "./HeaderNav";

export function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  return (
    <>
      {!isLogin && (
        <header className="border-b border-border/80 backdrop-blur-sm sticky top-0 z-10 bg-bg/70">
          <div className="mx-auto max-w-6xl px-6 py-4 flex items-center gap-3">
            <div className="size-6 rounded-full border border-accent/60 grid place-items-center">
              <div className="size-1.5 rounded-full bg-accent" />
            </div>
            <span className="font-mono text-sm tracking-[0.3em] text-text">ODIN</span>
            <HeaderNav />
          </div>
        </header>
      )}
      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8">
        <AuthGate>{children}</AuthGate>
      </main>
    </>
  );
}
