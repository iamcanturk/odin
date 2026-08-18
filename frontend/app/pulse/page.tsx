"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchPulse, type PulseTweet } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, Panel, StatTile } from "@/components/ui";

const TIER_STYLE: Record<string, { badge: string; className: string }> = {
  hot: { badge: "🔥", className: "text-hot border-hot/50" },
  warm: { badge: "🚀", className: "text-warn border-warn/40" },
  cold: { badge: "🌱", className: "text-muted border-border" },
};

function compact(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(Math.round(n));
}

function Row({ t }: { t: PulseTweet }) {
  const { t: tr } = useI18n();
  const style = TIER_STYLE[t.tier] ?? TIER_STYLE.cold;
  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-mono ${style.className}`}
        >
          {style.badge} {compact(t.views_per_hour)} {tr("pl.perHour")}
        </span>
        {t.author_handle && (
          <span className="font-mono text-[11px] text-muted">@{t.author_handle}</span>
        )}
        <span className="text-[11px] text-faint">
          {tr("pl.age", { n: t.age_hours.toFixed(1) })}
        </span>
        <span className="ml-auto font-mono text-sm tabular-nums text-accent">
          {t.score.toFixed(0)}
        </span>
      </div>

      <p className="text-sm text-text mt-2 line-clamp-4 whitespace-pre-wrap">{t.text}</p>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-[11px] text-muted font-mono">
        <span>{compact(t.impressions)} 👁</span>
        <span>{compact(t.likes)} ♥</span>
        <span>{compact(t.reposts)} ⇄</span>
        <span>{compact(t.replies)} 💬</span>
        {t.url && (
          <a
            href={t.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-accent hover:underline"
          >
            X ↗
          </a>
        )}
      </div>
    </Panel>
  );
}

export default function PulsePage() {
  const { t } = useI18n();
  const [tier, setTier] = useState<"cold" | "warm" | "hot">("cold");
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["pulse", tier],
    queryFn: () => fetchPulse(tier),
    refetchInterval: 60_000,
  });

  const items = data?.items ?? [];
  const hot = items.filter((i) => i.tier === "hot").length;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("pl.title")}
        subtitle={t("pl.subtitle")}
        actions={
          <div className="flex gap-1">
            {(["cold", "warm", "hot"] as const).map((tv) => (
              <button
                key={tv}
                onClick={() => setTier(tv)}
                className={`rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                  tier === tv
                    ? "border-accent/60 text-accent bg-accent/10"
                    : "border-border text-muted hover:text-text"
                }`}
              >
                {t(tv === "cold" ? "pl.tier.all" : `pl.tier.${tv}`)}
              </button>
            ))}
          </div>
        }
      />

      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <StatTile label={t("pl.observed")} value={data.observed} />
          <StatTile label={t("pl.tier.hot")} value={hot} tone={hot > 0 ? "hot" : "text"} />
          <StatTile
            label={t("pl.perHour")}
            value={items.length ? compact(items[0].views_per_hour) : "—"}
            tone="accent"
          />
        </div>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : items.length === 0 ? (
        <EmptyState label={t("pl.empty")} />
      ) : (
        <div className="grid gap-3">
          {items.map((item) => (
            <Row key={item.external_id} t={item} />
          ))}
        </div>
      )}
    </div>
  );
}
