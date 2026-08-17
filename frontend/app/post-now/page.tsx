"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchEvents, recommendedAction } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState, Panel, ScoreMeter } from "@/components/ui";

const TONE: Record<string, string> = {
  hot: "text-hot border-hot/50",
  good: "text-good border-good/40",
  warn: "text-warn border-warn/40",
  muted: "text-muted border-border",
};

export default function PostNowPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", { orderBy: "opportunity_score" }],
    queryFn: () => fetchEvents({ limit: 25, orderBy: "opportunity_score" }),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">What should I post now?</h1>
        <p className="text-sm text-muted mt-1">
          Events ranked by opportunity — trend momentum weighted by your personal relevance,
          timing and source confidence.
        </p>
      </div>

      {isLoading ? (
        <LoadingState label="Weighing opportunities…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState label="No opportunities yet. Add topics and run ingestion." />
      ) : (
        <div className="grid gap-3">
          {data.items.map((event, i) => {
            const action = recommendedAction(event.opportunity_score);
            return (
              <Link key={event.id} href={`/events/${event.id}`} className="block group">
                <Panel className="p-4 transition-colors group-hover:border-accent/50">
                  <div className="flex items-start gap-4">
                    <div className="font-mono text-xs text-muted w-6 pt-1 tabular-nums">
                      {String(i + 1).padStart(2, "0")}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span
                        className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest ${TONE[action.tone]}`}
                      >
                        {action.label}
                      </span>
                      <h3 className="mt-1.5 text-[15px] font-medium truncate group-hover:text-accent transition-colors">
                        {event.title}
                      </h3>
                    </div>
                    <div className="flex gap-4 shrink-0">
                      <ScoreMeter label="Opp." score={event.opportunity_score} />
                      <ScoreMeter label="You" score={event.personal_relevance} />
                    </div>
                  </div>
                </Panel>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
