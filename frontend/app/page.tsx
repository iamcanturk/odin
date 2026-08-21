"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { dismissEvent, fetchEvents, fetchTopics, type EventList } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EventCard } from "@/components/EventCard";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatTile,
} from "@/components/ui";

// Ignore near-dead events on the console — they add noise without opportunity.
const MIN_TREND = 15;
const WATCHING_CAP = 24;

function greetingKey(): string {
  const h = new Date().getHours();
  if (h < 12) return "greet.morning";
  if (h < 18) return "greet.afternoon";
  return "greet.evening";
}

function SectionHeader({ title, hint, count }: { title: string; hint: string; count: number }) {
  return (
    <div className="flex items-baseline justify-between gap-3 mb-3 mt-2">
      <div className="flex items-baseline gap-3">
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        <span className="font-mono text-xs text-faint tabular-nums">{count}</span>
      </div>
      <span className="text-[11px] text-faint hidden sm:block">{hint}</span>
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const q = search.trim();
  // Searching looks across ALL events (no trend floor) so nothing is hidden from you.
  const queryKey = [
    "events",
    { orderBy: "opportunity_score", minTrend: MIN_TREND, q, category },
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
  const actNow = events
    .filter((e) => e.opportunity_score >= 50)
    .sort((a, b) => b.opportunity_score - a.opportunity_score);
  // "Watching": lower opportunity, newest-added first, capped to keep the page tight.
  const watching = events
    .filter((e) => e.opportunity_score < 50)
    .sort((a, b) => new Date(b.last_seen_at).getTime() - new Date(a.last_seen_at).getTime())
    .slice(0, WATCHING_CAP);
  const forYou = events.filter((e) => e.topics.length > 0).length;
  const topOpp = actNow.length ? Math.round(actNow[0].opportunity_score) : 0;
  const noTopics = topics !== undefined && topics.length === 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("dash.title")}
        subtitle={
          data
            ? `${t(greetingKey())}. ${t("dash.foundN", { n: events.length })}${
                actNow.length > 0
                  ? `, ${t("dash.relevantM", { m: actNow.length })}.`
                  : `, ${t("dash.allQuiet")}.`
              }`
            : t("dash.subtitle")
        }
      />

      <div className="relative">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("dash.search")}
          className="h-10 w-full rounded-lg border border-border bg-panel-2 px-3 pr-28 text-sm outline-none focus:border-accent/60 transition-colors"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-faint pointer-events-none">
          {t("dash.searchHint")}
        </span>
      </div>

      {categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setCategory("")}
            className={`rounded-lg border px-2.5 py-1 text-xs transition-colors ${
              category === ""
                ? "border-accent/60 text-accent bg-accent/10"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {t("dash.catAll")}
          </button>
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c === category ? "" : c)}
              className={`rounded-lg border px-2.5 py-1 text-xs transition-colors ${
                category === c
                  ? "border-accent/60 text-accent bg-accent/10"
                  : "border-border text-muted hover:text-text"
              }`}
            >
              {t(`cat.${c}`) === `cat.${c}` ? c : t(`cat.${c}`)}
            </button>
          ))}
        </div>
      )}

      {!q && data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label={t("dash.statTracked")} value={events.length} />
          <StatTile
            label={t("dash.statActNow")}
            value={actNow.length}
            tone={actNow.length > 0 ? "hot" : "text"}
          />
          <StatTile label={t("dash.statForYou")} value={forYou} tone={forYou > 0 ? "good" : "text"} />
          <StatTile
            label={t("dash.statTopOpp")}
            value={topOpp}
            tone={topOpp >= 66 ? "hot" : topOpp >= 33 ? "warn" : "accent"}
          />
        </div>
      )}

      {noTopics && (
        <Panel className="p-5 border-accent/30">
          <h2 className="text-sm font-semibold text-accent">{t("onboard.title")}</h2>
          <p className="text-sm text-muted mt-2 max-w-3xl">{t("onboard.body")}</p>
          <Link
            href="/topics"
            className="inline-block mt-3 rounded-lg border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 transition-colors"
          >
            {t("onboard.cta")}
          </Link>
        </Panel>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : q ? (
        events.length === 0 ? (
          <EmptyState label={t("dash.searchNone", { q })} />
        ) : (
          <section>
            <SectionHeader
              title={t("dash.searchResults")}
              hint={t("dash.searchHint")}
              count={events.length}
            />
            <div className="grid gap-3">
              {events.map((event, i) => (
                <EventCard
                  key={event.id}
                  event={event}
                  rank={i + 1}
                  onDismiss={(id) => dismiss.mutate(id)}
                />
              ))}
            </div>
          </section>
        )
      ) : events.length === 0 ? (
        <EmptyState label={t("dash.empty")} />
      ) : (
        <div className="flex flex-col gap-6">
          {actNow.length > 0 && (
            <section>
              <SectionHeader
                title={t("dash.actNow")}
                hint={t("dash.actNowHint")}
                count={actNow.length}
              />
              <div className="grid gap-3">
                {actNow.map((event, i) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    rank={i + 1}
                    onDismiss={(id) => dismiss.mutate(id)}
                  />
                ))}
              </div>
            </section>
          )}

          {watching.length > 0 && (
            <section>
              <SectionHeader
                title={t("dash.watching")}
                hint={t("dash.watchingHint")}
                count={watching.length}
              />
              <div className="grid gap-3">
                {watching.map((event, i) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    rank={actNow.length + i + 1}
                    onDismiss={(id) => dismiss.mutate(id)}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
