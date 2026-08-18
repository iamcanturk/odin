"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchProfileGrowth, type ProfilePoint } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

function Sparkline({ values }: { values: number[] }) {
  const pts = values.filter((v) => Number.isFinite(v));
  if (pts.length < 2) return null;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const span = max - min || 1;
  const w = 100;
  const h = 28;
  const d = pts
    .map((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-8" preserveAspectRatio="none">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent" />
    </svg>
  );
}

function Delta({ value }: { value: number | null }) {
  if (value == null || value === 0) return null;
  const up = value > 0;
  return (
    <span className={`font-mono text-xs ${up ? "text-good" : "text-hot"}`}>
      {up ? "▲" : "▼"} {Math.abs(value).toLocaleString()}
    </span>
  );
}

function Metric({
  label,
  value,
  delta,
  series,
}: {
  label: string;
  value: number | null;
  delta?: number | null;
  series: number[];
}) {
  return (
    <div className="flex-1 min-w-[9rem]">
      <div className="flex items-baseline gap-2">
        <span className="text-xs uppercase tracking-widest text-muted">{label}</span>
        <Delta value={delta ?? null} />
      </div>
      <p className="text-2xl font-semibold tabular-nums mt-0.5">
        {value != null ? value.toLocaleString() : "—"}
      </p>
      <div className="mt-1 text-accent">
        <Sparkline values={series} />
      </div>
    </div>
  );
}

export function GrowthPanel() {
  const { t } = useI18n();
  const { data } = useQuery({ queryKey: ["profile", "growth"], queryFn: fetchProfileGrowth });

  if (!data) return null;

  const followers = data.series.map((p: ProfilePoint) => p.followers ?? NaN);
  const following = data.series.map((p: ProfilePoint) => p.following ?? NaN);
  const tweets = data.series.map((p: ProfilePoint) => p.tweets ?? NaN);

  return (
    <Panel className="p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-xs uppercase tracking-widest text-muted">{t("pf.growth")}</h2>
        {data.handle && (
          <span className="font-mono text-xs text-muted">
            @{data.handle} · {data.snapshots} {t("pf.snapshotsN")}
          </span>
        )}
      </div>

      {data.snapshots === 0 || !data.latest ? (
        <p className="text-sm text-muted mt-2">{t("pf.noGrowth")}</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-6 mt-3">
            <Metric
              label={t("pf.followers")}
              value={data.latest.followers}
              delta={data.delta_followers}
              series={followers}
            />
            <Metric
              label={t("pf.following")}
              value={data.latest.following}
              delta={data.delta_following}
              series={following}
            />
            <Metric label={t("pf.tweets")} value={data.latest.tweets} series={tweets} />
          </div>
          <p className="text-[11px] text-muted mt-3">{t("pf.growthHint")}</p>
        </>
      )}
    </Panel>
  );
}
