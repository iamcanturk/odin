"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchCadence, setWeeklyGoal } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

/** A weekly target is only useful split across the days you have left. */
export function CadencePanel({ editable = false }: { editable?: boolean }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["cadence"], queryFn: fetchCadence });
  const [goal, setGoal] = useState<string>("");

  const save = useMutation({
    mutationFn: () => setWeeklyGoal(Number(goal)),
    onSuccess: () => {
      setGoal("");
      qc.invalidateQueries({ queryKey: ["cadence"] });
    },
  });

  if (!data) return null;
  const peak = Math.max(...data.by_day.map((d) => d.posts), 1);

  return (
    <Panel className="p-5">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-sm font-semibold text-text">{t("cd.title")}</h2>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-widest ${
            data.on_track ? "border-good/50 text-good" : "border-warn/50 text-warn"
          }`}
        >
          {data.on_track ? t("cd.onTrack") : t("cd.behind")}
        </span>
        <span className="ml-auto font-mono text-[11px] text-faint">
          {t("cd.daysLeft", { n: data.days_left })}
        </span>
      </div>

      <div className="flex items-baseline gap-2 mt-3">
        <span className="font-mono text-3xl tabular-nums text-accent">{data.posted}</span>
        <span className="font-mono text-lg tabular-nums text-faint">/ {data.goal}</span>
        {data.remaining > 0 && (
          <span className="text-xs text-muted ml-2">
            {t("cd.perDay")}: <span className="text-text">{data.per_day_needed}</span>
          </span>
        )}
      </div>

      {data.quality_posts > 0 && (
        <p className="text-[11px] text-muted mt-1">
          {t("cd.quality", { n: data.quality_posts })}
        </p>
      )}

      <div className="flex items-end gap-2 mt-4 h-20">
        {data.by_day.map((d) => (
          <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
            <span className="font-mono text-[10px] tabular-nums text-faint">
              {d.posts || ""}
            </span>
            <div
              className={`w-full rounded-t transition-all ${
                d.is_today ? "bg-accent" : d.is_future ? "bg-panel-2" : "bg-good/60"
              }`}
              style={{ height: `${Math.max(2, (d.posts / peak) * 100)}%` }}
            />
            <span
              className={`text-[10px] ${d.is_today ? "text-accent font-medium" : "text-muted"}`}
            >
              {d.label}
            </span>
          </div>
        ))}
      </div>

      {editable && (
        <div className="flex items-center gap-2 mt-4 pt-4 border-t border-border-soft">
          <label className="text-xs text-muted">{t("cd.goal")}</label>
          <input
            type="number"
            min={1}
            max={200}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder={String(data.goal)}
            className="h-8 w-20 rounded-md border border-border bg-panel-2 px-2 text-sm tabular-nums outline-none focus:border-accent/60"
          />
          <button
            onClick={() => save.mutate()}
            disabled={!goal || save.isPending}
            className="h-8 rounded-md border border-accent/60 px-3 text-xs text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {t("cd.save")}
          </button>
        </div>
      )}
    </Panel>
  );
}
