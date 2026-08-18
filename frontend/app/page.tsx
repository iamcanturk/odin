"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchEvents } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EventCard } from "@/components/EventCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";

export default function DashboardPage() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", { orderBy: "trend_score" }],
    queryFn: () => fetchEvents({ limit: 50, orderBy: "trend_score" }),
  });

  return (
    <div className="flex flex-col gap-6">
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
