"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchEvents, fetchTopics } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EventCard } from "@/components/EventCard";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function greetingKey(): string {
  const h = new Date().getHours();
  if (h < 12) return "greet.morning";
  if (h < 18) return "greet.afternoon";
  return "greet.evening";
}

export default function DashboardPage() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", { orderBy: "opportunity_score" }],
    queryFn: () => fetchEvents({ limit: 50, orderBy: "opportunity_score" }),
  });
  const { data: topics } = useQuery({ queryKey: ["topics"], queryFn: fetchTopics });

  const highOpp = (data?.items ?? []).filter((e) => e.opportunity_score >= 50).length;
  const noTopics = topics !== undefined && topics.length === 0;

  return (
    <div className="flex flex-col gap-6">
      {data && (
        <p className="text-sm text-muted">
          {t(greetingKey())}. {t("dash.foundN", { n: data.total })}
          {highOpp > 0 ? `, ${t("dash.relevantM", { m: highOpp })}` : `, ${t("dash.allQuiet")}`}.
        </p>
      )}

      {noTopics && (
        <Panel className="p-5 border-accent/30">
          <h2 className="text-sm font-semibold text-accent">{t("onboard.title")}</h2>
          <p className="text-sm text-muted mt-2 max-w-3xl">{t("onboard.body")}</p>
          <Link
            href="/topics"
            className="inline-block mt-3 rounded-md border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 transition-colors"
          >
            {t("onboard.cta")}
          </Link>
        </Panel>
      )}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{t("dash.title")}</h1>
          <p className="text-sm text-muted mt-1">{t("dash.subtitle")}</p>
        </div>
        {data && (
          <span className="font-mono text-xs text-muted whitespace-nowrap">
            {data.total} {t("dash.tracked")}
          </span>
        )}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState label={t("dash.empty")} />
      ) : (
        <div className="grid gap-3">
          {data.items.map((event, i) => (
            <EventCard key={event.id} event={event} rank={i + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
