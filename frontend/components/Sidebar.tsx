"use client";

import { useState, type ComponentType, type SVGProps } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { clearToken, fetchUnreadCount } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  IconBeaker,
  IconBell,
  IconBolt,
  IconClose,
  IconDraft,
  IconFeed,
  IconGauge,
  IconGraph,
  IconHash,
  IconMenu,
  IconPower,
  IconRadar,
  IconUser,
} from "./icons";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;
type NavItem = { href: string; key: string; icon: Icon };
type NavGroup = { labelKey?: string; items: NavItem[] };

const GROUPS: NavGroup[] = [
  {
    items: [
      { href: "/", key: "nav.console", icon: IconRadar },
      { href: "/compose", key: "nav.compose", icon: IconDraft },
      { href: "/pulse", key: "nav.pulse", icon: IconGraph },
      { href: "/post-now", key: "nav.postNow", icon: IconBolt },
    ],
  },
  {
    labelKey: "nav.grp.discover",
    items: [
      { href: "/topics", key: "nav.topics", icon: IconHash },
      { href: "/sources", key: "nav.sources", icon: IconFeed },
      { href: "/tester", key: "nav.tester", icon: IconBeaker },
    ],
  },
  {
    labelKey: "nav.grp.you",
    items: [
      { href: "/profile", key: "nav.profile", icon: IconUser },
      { href: "/drafts", key: "nav.drafts", icon: IconDraft },
      { href: "/learning", key: "nav.learning", icon: IconGraph },
    ],
  },
  {
    labelKey: "nav.grp.system",
    items: [{ href: "/system", key: "nav.system", icon: IconGauge }],
  },
];

function logout() {
  clearToken();
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/login";
}

function Brand() {
  const { t } = useI18n();
  return (
    <Link href="/" className="flex items-center gap-3 px-2">
      <div className="size-7 rounded-full border border-accent/60 grid place-items-center shrink-0">
        <div className="size-2 rounded-full bg-accent" />
      </div>
      <div className="leading-tight">
        <div className="font-mono text-sm tracking-[0.3em] text-text">ODIN</div>
        <div className="text-[10px] text-faint">{t("nav.tagline")}</div>
      </div>
    </Link>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-5">
      {GROUPS.map((group, gi) => (
        <div key={gi} className="flex flex-col gap-1">
          {group.labelKey && (
            <div className="px-3 mb-1 text-[10px] font-mono uppercase tracking-widest text-faint">
              {t(group.labelKey)}
            </div>
          )}
          {group.items.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-accent/10 text-text"
                    : "text-muted hover:text-text hover:bg-panel-2/60"
                }`}
              >
                <Icon className={active ? "text-accent" : "text-faint group-hover:text-muted"} />
                <span>{t(item.key)}</span>
                {active && <span className="ml-auto size-1.5 rounded-full bg-accent" />}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function Footer({ onNavigate }: { onNavigate?: () => void }) {
  const { t, locale, setLocale } = useI18n();
  const pathname = usePathname();
  const { data: unread } = useQuery({
    queryKey: ["notifications", "count"],
    queryFn: fetchUnreadCount,
    refetchInterval: 60_000,
  });
  const notifActive = pathname.startsWith("/notifications");

  return (
    <div className="flex flex-col gap-1 border-t border-border-soft pt-3">
      <Link
        href="/notifications"
        onClick={onNavigate}
        className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
          notifActive ? "bg-accent/10 text-text" : "text-muted hover:text-text hover:bg-panel-2/60"
        }`}
      >
        <IconBell className={notifActive ? "text-accent" : "text-faint group-hover:text-muted"} />
        <span>{t("nav.notifications")}</span>
        {!!unread && unread > 0 && (
          <span className="ml-auto rounded-full bg-hot px-1.5 text-[10px] font-mono text-bg">
            {unread}
          </span>
        )}
      </Link>
      <div className="flex items-center gap-2 px-3 pt-1">
        <button
          onClick={() => setLocale(locale === "tr" ? "en" : "tr")}
          className="flex-1 rounded-lg border border-border px-2 py-1.5 font-mono text-xs uppercase text-muted hover:text-text hover:border-accent/50 transition-colors"
          title="TR / EN"
        >
          {locale === "tr" ? "EN" : "TR"}
        </button>
        <button
          onClick={logout}
          className="rounded-lg border border-border px-2.5 py-1.5 text-muted hover:text-hot hover:border-hot/50 transition-colors"
          title={t("header.signOut")}
          aria-label={t("header.signOut")}
        >
          <IconPower />
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <>
      {/* Desktop rail */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-64 flex-col gap-6 border-r border-border-soft bg-bg-2/60 backdrop-blur-sm px-3 py-5">
        <div className="pt-1">
          <Brand />
        </div>
        <div className="flex-1 overflow-y-auto">
          <NavLinks />
        </div>
        <Footer />
      </aside>

      {/* Mobile top bar */}
      <header className="lg:hidden sticky top-0 z-30 flex items-center gap-3 border-b border-border-soft bg-bg/80 backdrop-blur-sm px-4 py-3">
        <button
          onClick={() => setOpen(true)}
          className="rounded-lg border border-border p-1.5 text-muted hover:text-text transition-colors"
          aria-label={t("nav.menu")}
        >
          <IconMenu />
        </button>
        <Brand />
      </header>

      {/* Mobile drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={close} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[80%] flex flex-col gap-6 border-r border-border bg-bg-2 px-3 py-5 odin-fade-in">
            <div className="flex items-center justify-between pr-1">
              <Brand />
              <button
                onClick={close}
                className="rounded-lg border border-border p-1.5 text-muted hover:text-text transition-colors"
                aria-label={t("nav.menu")}
              >
                <IconClose />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <NavLinks onNavigate={close} />
            </div>
            <Footer onNavigate={close} />
          </div>
        </div>
      )}
    </>
  );
}
