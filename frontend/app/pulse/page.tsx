"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { composeReply, fetchPulse, type ComposeDraft, type PulseTweet } from "@/lib/api";
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

function ReplyDrafts({ drafts, tweetUrl }: { drafts: ComposeDraft[]; tweetUrl: string | null }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState<number | null>(null);
  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-border-soft pt-3">
      {drafts.map((d, i) => (
        <div key={i} className="rounded-lg border border-border-soft bg-panel-2/50 p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
              {t(`rk.${d.angle}`)}
            </span>
            <span className="font-mono text-xs tabular-nums text-muted">
              {d.viral_score.toFixed(0)}
            </span>
          </div>
          <p className="text-sm text-text mt-1.5 whitespace-pre-wrap">{d.text}</p>
          <div className="flex gap-2 mt-2">
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(d.text);
                  setCopied(i);
                  setTimeout(() => setCopied(null), 1500);
                } catch {
                  /* clipboard blocked */
                }
              }}
              className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
            >
              {copied === i ? t("cp.copied") : t("cp.copy")}
            </button>
            {tweetUrl && (
              <a
                href={tweetUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
              >
                X ↗
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function Row({ t }: { t: PulseTweet }) {
  const { t: tr, locale } = useI18n();
  const style = TIER_STYLE[t.tier] ?? TIER_STYLE.cold;
  const reply = useMutation({
    mutationFn: () =>
      composeReply({
        text: t.text,
        author_handle: t.author_handle ?? "",
        language: locale === "en" ? "en" : "tr",
      }),
  });
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

      <div className="mt-3">
        <button
          onClick={() => reply.mutate()}
          disabled={reply.isPending}
          className="rounded-lg border border-good/50 px-3 py-1.5 text-xs text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
        >
          {reply.isPending ? tr("pl.replying") : tr("pl.reply")}
        </button>
        {reply.error && (
          <p className="text-hot text-[11px] mt-1">{(reply.error as Error).message}</p>
        )}
      </div>

      {reply.data && <ReplyDrafts drafts={reply.data} tweetUrl={t.url} />}
    </Panel>
  );
}

export default function PulsePage() {
  const { t } = useI18n();
  const [tier, setTier] = useState<"cold" | "warm" | "hot">("cold");
  // Relevance on by default: unfiltered, global viral humour drowns out your niche.
  const [relevantOnly, setRelevantOnly] = useState(true);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["pulse", tier, relevantOnly],
    queryFn: () => fetchPulse({ minTier: tier, relevantOnly }),
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
            <button
              onClick={() => setRelevantOnly((v) => !v)}
              className={`rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                relevantOnly
                  ? "border-good/60 text-good bg-good/10"
                  : "border-border text-muted hover:text-text"
              }`}
            >
              {t("pl.relevantOnly")}
            </button>
          </div>
        }
      />

      <p className="text-[11px] text-faint -mt-2">
        {relevantOnly ? t("pl.relevanceHint") : t("pl.replyHint")}
      </p>

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
