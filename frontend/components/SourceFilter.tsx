"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchSources, type Source } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const COLLAPSED = 8;

/**
 * Filter by the site a story came from.
 *
 * A `<select>` hid 25 sources behind a click and gave no sense of what was even
 * available, which is why "site bazlı ayırma yapamıyorum" was a fair complaint.
 * Chips show them; anything past the first few hides behind "more" so the row
 * doesn't become the page.
 */
export function SourceFilter({
  value,
  onChange,
  category,
}: {
  value: string;
  onChange: (id: string) => void;
  /** When a category is active, only offer sources that belong to it. */
  category?: string;
}) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const { data } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });

  const all = (data ?? [])
    .filter((s: Source) => s.enabled)
    .filter((s) => !category || s.category === category)
    .sort((a, b) => a.name.localeCompare(b.name));

  if (all.length === 0) return null;

  // The selected source stays visible even when the list is collapsed past it.
  const head = all.slice(0, COLLAPSED);
  const selected = all.find((s) => s.id === value);
  const visible =
    expanded || !selected || head.includes(selected) ? head : [...head, selected];
  const shown = expanded ? all : visible;

  const chip = (active: boolean) =>
    `rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
      active
        ? "border-accent/60 bg-accent/10 text-accent"
        : "border-border text-muted hover:text-text"
    }`;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button onClick={() => onChange("")} className={chip(!value)}>
        {t("dc.allSources")}
      </button>
      {shown.map((s) => (
        <button
          key={s.id}
          onClick={() => onChange(s.id === value ? "" : s.id)}
          className={chip(s.id === value)}
          title={s.url ?? s.name}
        >
          {s.name}
        </button>
      ))}
      {all.length > COLLAPSED && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-[11px] text-faint hover:text-accent transition-colors px-1"
        >
          {expanded ? t("sf.less") : t("sf.more", { n: all.length - COLLAPSED })}
        </button>
      )}
    </div>
  );
}
