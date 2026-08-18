"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchUnreadCount } from "@/lib/api";

const LINKS = [
  { href: "/", label: "Console" },
  { href: "/post-now", label: "Post now" },
  { href: "/topics", label: "Topics" },
  { href: "/tester", label: "Tester" },
  { href: "/profile", label: "Profile" },
  { href: "/drafts", label: "Drafts" },
  { href: "/learning", label: "Learning" },
];

export function HeaderNav() {
  const { data: unread } = useQuery({
    queryKey: ["notifications", "count"],
    queryFn: fetchUnreadCount,
    refetchInterval: 60_000,
  });

  return (
    <nav className="ml-auto flex items-center gap-4 text-sm">
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className="text-muted hover:text-text transition-colors">
          {l.label}
        </Link>
      ))}
      <Link
        href="/notifications"
        className="relative text-muted hover:text-text transition-colors"
        aria-label="Notifications"
      >
        <span aria-hidden>🔔</span>
        {!!unread && unread > 0 && (
          <span className="absolute -top-2 -right-2 rounded-full bg-hot px-1.5 text-[10px] font-mono text-bg">
            {unread}
          </span>
        )}
      </Link>
    </nav>
  );
}
