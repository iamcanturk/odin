"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCadence } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/**
 * The week's target as one line above the feed.
 *
 * The full panel with the per-day breakdown lives on /you; here it only has to
 * answer "am I behind?" without taking a screen.
 */
export function CadenceStrip() {
  const { t } = useI18n();
  const { data } = useQuery({ queryKey: ["cadence"], queryFn: fetchCadence });
  if (!data) return null;

  const pct = Math.min(100, (data.posted / data.goal) * 100);

  return (
    <div className="flex items-center gap-3 rounded-[var(--radius)] border border-border bg-panel/70 px-4 py-2.5">
      <span className="text-[10px] uppercase tracking-widest text-muted shrink-0">
        {t("cd.title")}
      </span>
      <span className="font-mono text-sm tabular-nums shrink-0">
        <span className={data.on_track ? "text-good" : "text-warn"}>{data.posted}</span>
        <span className="text-faint"> / {data.goal}</span>
      </span>
      <div className="h-1.5 flex-1 min-w-[60px] rounded-full bg-panel-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${data.on_track ? "bg-good" : "bg-warn"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {data.remaining > 0 && (
        <span className="text-[11px] text-muted shrink-0 hidden sm:block">
          {t("cd.perDay")}: <span className="text-text">{data.per_day_needed}</span>
        </span>
      )}
      <span className="font-mono text-[10px] text-faint shrink-0 hidden sm:block">
        {t("cd.daysLeft", { n: data.days_left })}
      </span>
    </div>
  );
}
