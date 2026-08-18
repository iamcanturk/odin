"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchEvents, fetchTopics } from "@/lib/api";
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
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", { orderBy: "opportunity_score" }],
    queryFn: () => fetchEvents({ limit: 50, orderBy: "opportunity_score" }),
  });
  const { data: topics } = useQuery({ queryKey: ["topics"], queryFn: fetchTopics });

  const events = data?.items ?? [];
  const actNow = events.filter((e) => e.opportunity_score >= 50);
  const watching = events.filter((e) => e.opportunity_score < 50);
  const forYou = events.filter((e) => e.topics.length > 0).length;
  const topOpp = events.length ? Math.round(events[0].opportunity_score) : 0;
  const noTopics = topics !== undefined && topics.length === 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("dash.title")}
        subtitle={
          data
            ? `${t(greetingKey())}. ${t("dash.foundN", { n: data.total })}${
                actNow.length > 0
                  ? `, ${t("dash.relevantM", { m: actNow.length })}.`
                  : `, ${t("dash.allQuiet")}.`
              }`
            : t("dash.subtitle")
        }
      />

      {data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label={t("dash.statTracked")} value={data.total} />
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
                  <EventCard key={event.id} event={event} rank={i + 1} />
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
                  <EventCard key={event.id} event={event} rank={actNow.length + i + 1} />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
