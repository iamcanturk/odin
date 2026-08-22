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
  type EventList,
  type EventSummary,
  type ImportedTweet,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { CadenceStrip } from "@/components/CadenceStrip";
import { SourceFilter } from "@/components/SourceFilter";
import { FeedItemModal, type FeedItem } from "@/components/FeedItemModal";
import { Modal } from "@/components/Modal";
import { Composer } from "@/components/Composer";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

// Ignore near-dead events — they add noise without opportunity.
const MIN_TREND = 15;

/**
 * The one screen you start on.
 *
 * The feed gets the full width: images, summaries and merged headlines need room,
 * and a pinned side column was taking a third of it to show an empty textarea.
 * Clicking a card opens it in a modal instead — full content, then "Bunu seç" swaps
 * that same modal into a two-pane compose view so the source stays beside the draft.
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

const GRID = "grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4";

export default function FeedPage() {
  const { t } = useI18n();
  const [stream, setStream] = useState<Stream>("events");
  const [picked, setPicked] = useState<FeedItem | null>(null);
  const [blank, setBlank] = useState(false);

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
        {/* Writing without a source still has to be one click away. */}
        <button
          onClick={() => setBlank(true)}
          className="ml-auto rounded-lg border border-accent/60 bg-accent/10 px-3 py-1.5 text-xs text-accent hover:bg-accent/20 transition-colors"
        >
          + {t("fl.blank")}
        </button>
      </div>

      {stream === "events" && <EventStream onPick={setPicked} />}
      {stream === "raw" && <RawStream onPick={setPicked} />}
      {stream === "pulse" && <PulseStream onPick={setPicked} />}
      {stream === "recycle" && <RecycleStream onPick={setPicked} />}

      <FeedItemModal item={picked} onClose={() => setPicked(null)} />

      <Modal open={blank} onClose={() => setBlank(false)}>
        <div className="p-4">
          <Composer seed={null} />
        </div>
      </Modal>
    </div>
  );
}

type Picker = { onPick: (item: FeedItem) => void };

/** Shared card shell so every stream reads the same way. */
function Card({
  item,
  onPick,
  onDismiss,
  accent,
  children,
}: {
  item: FeedItem;
  onPick: (item: FeedItem) => void;
  onDismiss?: () => void;
  accent?: boolean;
  children?: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <Panel
      onClick={() => onPick(item)}
      className={`group relative overflow-hidden flex flex-col cursor-pointer hover:border-accent/50 transition-colors ${
        accent ? "border-l-2 border-l-good" : ""
      }`}
    >
      {onDismiss && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          className="absolute top-2 right-2 z-10 rounded-md px-1.5 text-faint hover:text-hot hover:bg-panel-2/90 transition-colors"
          title={t("ev.dismiss")}
          aria-label={t("ev.dismiss")}
        >
          ×
        </button>
      )}

      {item.image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.image} alt="" className="w-full h-40 object-cover" loading="lazy" />
      )}

      <div className="p-3.5 flex flex-col gap-2 flex-1">
        <div className="flex flex-wrap items-center gap-1.5 pr-5">
          {item.sourceLabel && (
            <span className="text-[10px] font-mono uppercase tracking-widest text-accent truncate max-w-[45%]">
              {item.sourceLabel}
            </span>
          )}
          {item.category && (
            <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-faint">
              {item.category}
            </span>
          )}
          {item.chips?.slice(0, 2).map((c) => (
            <span
              key={c}
              className="rounded-full border border-good/40 px-1.5 py-0.5 text-[10px] text-good"
            >
              {c}
            </span>
          ))}
          {item.meta && <span className="text-[10px] text-faint ml-auto">{item.meta}</span>}
        </div>

        <h3 className="text-[15px] font-medium text-text leading-snug line-clamp-2 group-hover:text-accent transition-colors">
          {item.title}
        </h3>

        {/* The summary is the point — it was clamped to nothing in the old layout. */}
        {item.body && <p className="text-[13px] text-muted line-clamp-4">{item.body}</p>}

        {!!item.extras?.length && (
          <ul className="flex flex-col gap-0.5">
            {item.extras.slice(0, 2).map((h) => (
              <li key={h} className="text-[11px] text-faint truncate">
                ↳ {h}
              </li>
            ))}
          </ul>
        )}

        {children && <div className="mt-auto pt-1">{children}</div>}
      </div>
    </Panel>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  const color = value >= 66 ? "bg-hot" : value >= 33 ? "bg-warn" : "bg-accent";
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] uppercase tracking-widest text-muted w-11 shrink-0">
        {label}
      </span>
      <div className="h-1 flex-1 rounded-full bg-panel-2 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="font-mono text-[10px] tabular-nums w-5 text-right">
        {value.toFixed(0)}
      </span>
    </div>
  );
}

/** Clustered, scored events. */
function EventStream({ onPick }: Picker) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sourceId, setSourceId] = useState("");
  const q = search.trim();

  // Searching looks across ALL events (no trend floor) so nothing is hidden from you.
  const queryKey = [
    "events",
    { orderBy: "opportunity_score", minTrend: MIN_TREND, q, category, sourceId },
  ];
  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: () =>
      fetchEvents({
        limit: q ? 100 : 60,
        orderBy: "opportunity_score",
        minTrend: q ? 0 : MIN_TREND,
        q,
        category,
        sourceId: sourceId || undefined,
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
  const categories = Array.from(
    new Set(events.map((e) => e.category).filter((c): c is string => !!c)),
  ).sort();
  const noTopics = topics !== undefined && topics.length === 0;

  const toItem = (e: EventSummary): FeedItem => ({
    id: e.id,
    title: e.title_local || e.title,
    // Only 1 of 1229 events has a written summary, so fall back to the source
    // article's lede rather than showing a bare headline.
    body: e.summary || e.excerpt,
    image: e.image,
    category: e.category,
    chips: e.topics,
    extras: e.headlines.filter((h) => h !== e.title),
    meta: `${e.source_count} · ${e.item_count}`,
    scores: [
      { label: t("ev.trend"), value: e.trend_score },
      { label: t("pn.opp"), value: e.opportunity_score },
    ],
    eventId: e.id,
    seedText: e.summary || e.title,
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("dash.search")}
          className="h-9 flex-1 min-w-[200px] max-w-md rounded-lg border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60 transition-colors"
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

      <SourceFilter value={sourceId} onChange={setSourceId} category={category} />

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
        <div className={GRID}>
          {events.map((e) => (
            <Card
              key={e.id}
              item={toItem(e)}
              onPick={onPick}
              onDismiss={() => dismiss.mutate(e.id)}
              accent={e.topics.length > 0}
            >
              <div className="flex flex-col gap-1">
                <Bar label={t("ev.trend")} value={e.trend_score} />
                <Bar label={t("pn.opp")} value={e.opportunity_score} />
              </div>
            </Card>
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

      <SourceFilter value={sourceId} onChange={setSourceId} category={category} />

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
        <div className={GRID}>
          {data.map((it) => (
            <Card
              key={it.id}
              onPick={onPick}
              item={{
                id: it.id,
                title: it.title ?? it.url ?? "",
                body: it.summary,
                image: it.image,
                url: it.url,
                sourceLabel: it.source_name,
                category: it.source_category,
                meta: it.published_at ? new Date(it.published_at).toLocaleDateString() : null,
                eventId: it.event_id,
                seedText: it.title ?? "",
              }}
            />
          ))}
        </div>
      )}
    </div>
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

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
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
        <span className="text-[11px] text-faint">{t("fl.pulseHint")}</span>
        {data && (
          <span className="text-[11px] text-faint font-mono ml-auto">
            {data.observed} · {data.window_hours}h
          </span>
        )}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState label={t("pl.empty")} />
      ) : (
        <div className={GRID}>
          {data.items.map((tw) => (
            <Card
              key={tw.external_id}
              onPick={onPick}
              item={{
                id: tw.external_id,
                title: `@${tw.author_handle ?? "?"}`,
                body: tw.text,
                url: tw.url,
                sourceLabel: tw.tier.toUpperCase(),
                meta: `${Math.round(tw.views_per_hour)}/h`,
                seedText: tw.text,
              }}
            >
              <div className="flex items-center gap-3 font-mono text-[10px] tabular-nums text-faint">
                <span className={tw.tier === "hot" ? "text-hot" : "text-warn"}>
                  ▲{tw.score.toFixed(0)}
                </span>
                <span>{tw.likes ?? 0}♥</span>
                <span>{tw.reposts ?? 0}⇄</span>
                {tw.impressions != null && <span>{tw.impressions.toLocaleString()}</span>}
              </div>
            </Card>
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
    .slice(0, 40);

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[11px] text-faint">{t("fl.recycleHint")}</p>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : best.length === 0 ? (
        <EmptyState label={t("fl.recycleEmpty")} />
      ) : (
        <div className={GRID}>
          {best.map((tw) => (
            <Card
              key={tw.id}
              onPick={onPick}
              item={{
                id: tw.id,
                title: tw.text.slice(0, 80),
                body: tw.text,
                url: tw.url,
                sourceLabel: t("fl.recycle"),
                meta: tw.posted_at ? new Date(tw.posted_at).toLocaleDateString() : null,
                seedText: tw.text,
              }}
            >
              <div className="flex items-center gap-3 font-mono text-[10px] tabular-nums text-faint">
                <span className="text-good">{tw.likes}♥</span>
                <span>{tw.reposts ?? 0}⇄</span>
                {tw.impressions != null && <span>{tw.impressions.toLocaleString()}</span>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
