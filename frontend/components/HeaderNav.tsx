"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { clearToken, fetchUnreadCount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

function logout() {
  clearToken();
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/login";
}

const LINKS: { href: string; key: string }[] = [
  { href: "/", key: "nav.console" },
  { href: "/post-now", key: "nav.postNow" },
  { href: "/topics", key: "nav.topics" },
  { href: "/sources", key: "nav.sources" },
  { href: "/tester", key: "nav.tester" },
  { href: "/profile", key: "nav.profile" },
  { href: "/drafts", key: "nav.drafts" },
  { href: "/learning", key: "nav.learning" },
];

export function HeaderNav() {
  const { t, locale, setLocale } = useI18n();
  const pathname = usePathname();
  const { data: unread } = useQuery({
    queryKey: ["notifications", "count"],
    queryFn: fetchUnreadCount,
    refetchInterval: 60_000,
  });

  return (
    <nav className="ml-auto flex items-center gap-x-4 gap-y-1 flex-wrap justify-end text-sm">
      {LINKS.map((l) => {
        const active = pathname === l.href;
        return (
          <Link
            key={l.href}
            href={l.href}
            className={`transition-colors ${active ? "text-text" : "text-muted hover:text-text"}`}
          >
            {t(l.key)}
          </Link>
        );
      })}

      <span className="mx-1 h-4 w-px bg-border" aria-hidden />

      <button
        onClick={() => setLocale(locale === "tr" ? "en" : "tr")}
        className="font-mono text-xs uppercase text-muted hover:text-text transition-colors"
        title="TR / EN"
      >
        {locale === "tr" ? "EN" : "TR"}
      </button>

      <Link
        href="/notifications"
        className="relative text-muted hover:text-text transition-colors"
        aria-label={t("header.notifications")}
      >
        <span aria-hidden>🔔</span>
        {!!unread && unread > 0 && (
          <span className="absolute -top-2 -right-2 rounded-full bg-hot px-1.5 text-[10px] font-mono text-bg">
            {unread}
          </span>
        )}
      </Link>

      <button
        onClick={logout}
        className="text-muted hover:text-hot transition-colors"
        title={t("header.signOut")}
        aria-label={t("header.signOut")}
      >
        ⏻
      </button>
    </nav>
  );
}
