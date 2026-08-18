"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchTiming, type TimeSlot } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

const DAY_TR: Record<string, string> = {
  Mon: "Pzt",
  Tue: "Sal",
  Wed: "Çar",
  Thu: "Per",
  Fri: "Cum",
  Sat: "Cmt",
  Sun: "Paz",
};

function barColor(score: number): string {
  if (score >= 80) return "var(--good)";
  if (score >= 50) return "var(--accent)";
  return "var(--border)";
}

function Bars({ slots, localize }: { slots: TimeSlot[]; localize?: boolean }) {
  const { locale } = useI18n();
  if (slots.length === 0) return null;
  return (
    <div className="flex items-end gap-1 h-24 mt-2">
      {slots.map((s) => (
        <div key={s.key} className="flex-1 flex flex-col items-center gap-1 min-w-0">
          <div
            className="w-full rounded-t transition-all"
            style={{
              height: `${Math.max(4, s.score)}%`,
              background: barColor(s.score),
            }}
            title={`${s.label}: ${s.posts} post, avg ${s.avg_engagement}`}
          />
          <span className="text-[9px] text-faint font-mono truncate w-full text-center">
            {localize && locale === "tr" ? (DAY_TR[s.label] ?? s.label) : s.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export function TimingPanel() {
  const { t, locale } = useI18n();
  const { data } = useQuery({ queryKey: ["performance", "timing"], queryFn: fetchTiming });

  if (!data) return null;

  const bestDayLabel = data.by_day.find((d) => d.key === data.best_day)?.label;
  const bestDay =
    bestDayLabel && locale === "tr" ? (DAY_TR[bestDayLabel] ?? bestDayLabel) : bestDayLabel;

  return (
    <Panel className="p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs uppercase tracking-widest text-muted">{t("tm.title")}</h2>
        <span className="font-mono text-xs text-faint tabular-nums">{data.total_posts}</span>
      </div>

      {!data.enough_data ? (
        <p className="text-sm text-muted mt-2">{t("tm.notEnough", { n: data.min_posts })}</p>
      ) : (
        <>
          <p className="text-[11px] text-faint mt-1">{t("tm.hint")}</p>

          <div className="flex flex-wrap gap-6 mt-3">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted">
                {t("tm.bestHour")}
              </p>
              <p className="text-2xl font-semibold tabular-nums text-good">
                {data.best_hour != null ? `${String(data.best_hour).padStart(2, "0")}:00` : "—"}
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-muted">{t("tm.bestDay")}</p>
              <p className="text-2xl font-semibold text-good">{bestDay ?? "—"}</p>
            </div>
          </div>

          <p className="text-[10px] uppercase tracking-widest text-muted mt-4">{t("tm.byHour")}</p>
          <Bars slots={data.by_hour} />

          <p className="text-[10px] uppercase tracking-widest text-muted mt-4">{t("tm.byDay")}</p>
          <Bars slots={data.by_day} localize />
        </>
      )}
    </Panel>
  );
}
