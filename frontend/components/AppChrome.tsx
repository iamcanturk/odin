"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AuthGate } from "./AuthGate";
import { Sidebar } from "./Sidebar";

export function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  if (isLogin) {
    return (
      <main className="flex-1 mx-auto w-full max-w-6xl px-6 py-8">
        <AuthGate>{children}</AuthGate>
      </main>
    );
  }

  return (
    <div className="flex-1 lg:pl-64">
      <Sidebar />
      <main className="mx-auto w-full max-w-5xl px-4 sm:px-8 py-6 sm:py-10">
        <div key={pathname} className="odin-fade-in">
          <AuthGate>{children}</AuthGate>
        </div>
      </main>
    </div>
  );
}
