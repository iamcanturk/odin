"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  dismissEvent,
  fetchDiscover,
  fetchEvents,
  fetchImportedTweets,
  fetchPulse,
  fetchSources,
  fetchTopics,
  pollSource,
  type DiscoverItem,
  type EventList,
  type EventSummary,
  type ImportedTweet,
  type PulseTweet,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EventCard } from "@/components/EventCard";
import { CadenceStrip } from "@/components/CadenceStrip";
import { Composer, type ComposerSeed } from "@/components/Composer";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

// Ignore near-dead events — they add noise without opportunity.
const MIN_TREND = 15;

/**
 * The one screen you start on.
 *
 * Finding something, writing about it and queueing it are one continuous act, so
 * they're one surface: the stream on the left, the composer pinned on the right.
 * Clicking any card loads its subject into the composer instead of navigating away,
 * which is the whole point — you never lose the thing you were looking at.
 *
 * Four streams, because "what's worth posting about" has four honest answers:
 * clustered events, the raw incoming feed (where the images live), what's moving on
 * X right now, and your own posts worth saying again.
 */
type Stream = "events" | "raw" | "pulse" | "recycle";

const STREAMS: { key: Stream; labelKey: string }[] = [
  { key: "events", labelKey: "fl.events" },
  { key: "raw", labelKey: "fl.raw" },
  { key: "pulse", labelKey: "fl.pulse" },
  { key: "recycle", labelKey: "fl.recycle" },
];

export default function FeedPage() {
  const { t } = useI18n();
  const [stream, setStream] = useState<Stream>("events");
  const [seed, setSeed] = useState<ComposerSeed | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <CadenceStrip />

      <div className="flex flex-wrap items-center gap-1.5">
        {STREAMS.map((s) => (
          <button
            key={s.key}
            onClick={() => setStream(s.key)}
            className={`rounded-full border px-3.5 py-1.5 text-xs transition-colors ${
              stream === s.key
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {t(s.labelKey)}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] items-start">
        <div className="min-w-0">
          {stream === "events" && <EventStream onPick={setSeed} />}
          {stream === "raw" && <RawStream onPick={setSeed} />}
          {stream === "pulse" && <PulseStream onPick={setSeed} />}
          {stream === "recycle" && <RecycleStream onPick={setSeed} />}
        </div>

        {/* Sticky so the composer stays put however far you scroll the stream.
            Keyed on the seed so clicking a new card resets the draft cleanly. */}
        <div className="lg:sticky lg:top-4">
          <Composer key={seed?.topic ?? "blank"} seed={seed} />
        </div>
      </div>
    </div>
  );
}

type Picker = { onPick: (seed: ComposerSeed) => void };

function StreamHint({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] text-faint mb-3">{children}</p>;
}

/** Clustered, scored events — the original console, now a stream among others. */
function EventStream({ onPick }: Picker) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const q = search.trim();

  // Searching looks across ALL events (no trend floor) so nothing is hidden from you.
  const queryKey = ["events", { orderBy: "opportunity_score", minTrend: MIN_TREND, q, category }];
  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: () =>
      fetchEvents({
        limit: q ? 100 : 60,
        orderBy: "opportunity_score",
        minTrend: q ? 0 : MIN_TREND,
        q,
        category,
      }),
  });
  const { data: topics } = useQuery({ queryKey: ["topics"], queryFn: fetchTopics });

  const dismiss = useMutation({
    mutationFn: dismissEvent,
    onMutate: (id: string) => {
      const prev = qc.getQueryData<EventList>(queryKey);
      if (prev) {
        qc.setQueryData<EventList>(queryKey, {
          ...prev,
          total: Math.max(0, prev.total - 1),
          items: prev.items.filter((e) => e.id !== id),
        });
      }
      return { prev };
    },
    onError: (_e, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKey, ctx.prev);
    },
  });

  const events = data?.items ?? [];
  // Only offer categories that actually exist in the current result set.
  const categories = Array.from(
    new Set(events.map((e) => e.category).filter((c): c is string => !!c)),
  ).sort();
  const noTopics = topics !== undefined && topics.length === 0;

  const pick = (e: EventSummary) =>
    onPick({ topic: e.summary || e.title, eventId: e.id, source: e.title });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("dash.search")}
          className="h-9 flex-1 min-w-[180px] rounded-lg border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60 transition-colors"
        />
        {["", ...categories].map((c) => (
          <button
            key={c || "all"}
            onClick={() => setCategory(c)}
            className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
              category === c
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {c || t("dc.all")}
          </button>
        ))}
      </div>

      {noTopics && (
        <Panel className="p-4 border-warn/40">
          <p className="text-sm text-warn">
            {t("dash.noTopics")}{" "}
            <Link href="/settings" className="underline">
              {t("nav.topics")}
            </Link>
          </p>
        </Panel>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : events.length === 0 ? (
        <EmptyState label={t("dash.empty")} />
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {events.map((e, i) => (
            <EventCard
              key={e.id}
              event={e}
              rank={i + 1}
              onSelect={pick}
              onDismiss={(id) => dismiss.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** The raw incoming feed — where Pinterest images and Reddit threads actually live. */
function RawStream({ onPick }: Picker) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [sourceId, setSourceId] = useState("");
  const [category, setCategory] = useState("");
  const [withMedia, setWithMedia] = useState(false);

  const { data: sources } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["discover", sourceId, category, withMedia],
    queryFn: () =>
      fetchDiscover({
        sourceId: sourceId || undefined,
        category: category || undefined,
        withMedia,
      }),
  });

  // The 15-minute cron polls everything at once; this pulls one source on demand.
  const poll = useMutation({
    mutationFn: () => pollSource(sourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discover"] }),
  });

  const categories = Array.from(
    new Set((sources ?? []).map((s) => s.category).filter((c): c is string => !!c)),
  ).sort();

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={sourceId}
          onChange={(e) => setSourceId(e.target.value)}
          className="h-9 rounded-lg border border-border bg-panel-2 px-2 text-sm text-text outline-none focus:border-accent/60"
        >
          <option value="">{t("dc.allSources")}</option>
          {(sources ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        {sourceId && (
          <button
            onClick={() => poll.mutate()}
            disabled={poll.isPending}
            className="rounded-lg border border-accent/60 bg-accent/10 px-2.5 py-1.5 text-xs text-accent hover:bg-accent/20 disabled:opacity-40 transition-colors"
          >
            {poll.isPending ? "…" : t("dc.fetch")}
          </button>
        )}
        <button
          onClick={() => setWithMedia((v) => !v)}
          className={`rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
            withMedia
              ? "border-accent/60 text-accent bg-accent/10"
              : "border-border text-muted hover:text-text"
          }`}
        >
          {t("dc.onlyImages")}
        </button>
        {["", ...categories].map((c) => (
          <button
            key={c || "all"}
            onClick={() => {
              setCategory(c);
              setSourceId("");
            }}
            className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
              category === c
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {c || t("dc.all")}
          </button>
        ))}
      </div>

      {poll.data && (
        <p className="text-xs text-muted">
          {poll.data.source}: {t("dc.fetched", { n: poll.data.fetched })}
          {poll.data.errors.length > 0 && ` — ${poll.data.errors.join(", ")}`}
        </p>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState label={t("dc.empty")} />
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {data.map((item) => (
            <RawCard key={item.id} item={item} onPick={onPick} />
          ))}
        </div>
      )}
    </div>
  );
}

function RawCard({ item, onPick }: { item: DiscoverItem } & Picker) {
  return (
    <Panel
      onClick={() =>
        onPick({
          topic: item.title ?? item.url ?? "",
          eventId: item.event_id ?? undefined,
          source: item.source_name,
        })
      }
      className="overflow-hidden flex flex-col cursor-pointer hover:border-accent/50 transition-colors"
    >
      {item.image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.image} alt="" className="w-full h-32 object-cover" loading="lazy" />
      )}
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-accent truncate">
            {item.source_name}
          </span>
          {item.source_category && (
            <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-faint shrink-0">
              {item.source_category}
            </span>
          )}
        </div>
        <p className="text-sm text-text line-clamp-3 flex-1">{item.title ?? item.url}</p>
        {item.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-[10px] text-faint hover:text-accent transition-colors"
          >
            {new URL(item.url).hostname} ↗
          </a>
        )}
      </div>
    </Panel>
  );
}

/** What's actually moving on X right now, from the extension's sightings. */
function PulseStream({ onPick }: Picker) {
  const { t } = useI18n();
  const [relevantOnly, setRelevantOnly] = useState(true);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["pulse", relevantOnly],
    queryFn: () => fetchPulse({ relevantOnly, minTier: "warm" }),
  });

  const tierColor = (tier: PulseTweet["tier"]) =>
    tier === "hot" ? "text-hot" : tier === "warm" ? "text-warn" : "text-muted";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setRelevantOnly((v) => !v)}
          className={`rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
            relevantOnly
              ? "border-accent/60 text-accent bg-accent/10"
              : "border-border text-muted hover:text-text"
          }`}
        >
          {t("pl.relevantOnly")}
        </button>
        {data && (
          <span className="text-[11px] text-faint font-mono ml-auto">
            {data.observed} · {data.window_hours}h
          </span>
        )}
      </div>
      <StreamHint>{t("fl.pulseHint")}</StreamHint>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState label={t("pl.empty")} />
      ) : (
        <div className="grid gap-2.5">
          {data.items.map((tw) => (
            <Panel
              key={tw.external_id}
              onClick={() =>
                onPick({
                  topic: tw.text,
                  source: tw.author_handle ? `@${tw.author_handle}` : undefined,
                })
              }
              className="p-3 cursor-pointer hover:border-accent/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-muted truncate">
                  @{tw.author_handle ?? "?"}
                </span>
                <span className={`font-mono text-[11px] tabular-nums ml-auto ${tierColor(tw.tier)}`}>
                  ▲{tw.score.toFixed(0)}
                </span>
                <span className="font-mono text-[10px] text-faint tabular-nums">
                  {Math.round(tw.views_per_hour)}/h
                </span>
              </div>
              <p className="text-sm text-text mt-1.5 line-clamp-4">{tw.text}</p>
              {tw.url && (
                <a
                  href={tw.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-[10px] text-faint hover:text-accent mt-1.5 inline-block"
                >
                  X ↗
                </a>
              )}
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Your own posts, best-first.
 *
 * A point that landed once is worth making again in a new shape — and unlike the
 * corpus, this is a bar you've already cleared. The repetition guard in the composer
 * is what keeps "again in a new shape" from becoming "the same tweet twice".
 */
function RecycleStream({ onPick }: Picker) {
  const { t } = useI18n();
  const { data, isLoading, error } = useQuery({
    queryKey: ["profile", "tweets"],
    queryFn: fetchImportedTweets,
  });

  const best = (data ?? [])
    .filter((tw: ImportedTweet) => (tw.likes ?? 0) > 0)
    .sort((a, b) => (b.likes ?? 0) - (a.likes ?? 0))
    .slice(0, 30);

  return (
    <div className="flex flex-col gap-3">
      <StreamHint>{t("fl.recycleHint")}</StreamHint>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : best.length === 0 ? (
        <EmptyState label={t("fl.recycleEmpty")} />
      ) : (
        <div className="grid gap-2.5">
          {best.map((tw) => (
            <Panel
              key={tw.id}
              onClick={() => onPick({ topic: tw.text, source: t("fl.recycle") })}
              className="p-3 cursor-pointer hover:border-accent/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs tabular-nums text-good">{tw.likes}♥</span>
                {tw.impressions != null && (
                  <span className="font-mono text-[10px] tabular-nums text-faint">
                    {tw.impressions.toLocaleString()}
                  </span>
                )}
                {tw.posted_at && (
                  <span className="font-mono text-[10px] text-faint ml-auto">
                    {new Date(tw.posted_at).toLocaleDateString()}
                  </span>
                )}
              </div>
              <p className="text-sm text-text mt-1.5 line-clamp-4">{tw.text}</p>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
