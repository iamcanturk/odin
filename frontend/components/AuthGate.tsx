"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { fetchAuthConfig, getToken } from "@/lib/api";

/**
 * Gates the app: when auth is required and there's no token, redirect to /login.
 * The /login route itself is always allowed. Invalid tokens are handled by the API
 * client (401 → redirect). When auth is disabled server-side, everything passes.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (pathname === "/login") return; // handled by the direct render below
    let active = true;
    (async () => {
      try {
        const cfg = await fetchAuthConfig();
        if (active && cfg.auth_required && !getToken()) {
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.href = "/login";
          return;
        }
      } catch {
        // If the config call fails, fail open so the app is still usable.
      }
      if (active) setReady(true);
    })();
    return () => {
      active = false;
    };
  }, [pathname]);

  if (pathname === "/login") return <>{children}</>;
  if (!ready) return null;
  return <>{children}</>;
}
