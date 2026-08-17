"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchEvents } from "@/lib/api";
import { EventCard } from "@/components/EventCard";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";

export default function DashboardPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", { orderBy: "trend_score" }],
    queryFn: () => fetchEvents({ limit: 50, orderBy: "trend_score" }),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Top opportunities</h1>
          <p className="text-sm text-muted mt-1">
            Emerging events ranked by trend momentum. Updated continuously by the ingestion worker.
          </p>
        </div>
        {data && (
          <span className="font-mono text-xs text-muted whitespace-nowrap">
            {data.total} events tracked
          </span>
        )}
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState label="No events yet. Seed sources and run the ingestion worker to populate the console." />
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
