"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchEvent } from "@/lib/api";
import { ContentPanel } from "./ContentPanel";
import { ErrorState, LoadingState, Panel, ScoreMeter, StatusBadge } from "./ui";

function VelocityRow({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted w-40 shrink-0 capitalize">
        {label.replace(/_/g, " ")}
      </span>
      <div className="h-1 flex-1 rounded-full bg-panel-2 overflow-hidden">
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-muted w-10 text-right">
        {pct.toFixed(0)}
      </span>
    </div>
  );
}

export function EventDetailView({ id }: { id: string }) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["event", id],
    queryFn: () => fetchEvent(id),
  });

  return (
    <div className="flex flex-col gap-6">
      <Link href="/" className="text-xs text-muted hover:text-accent font-mono w-fit">
        ← back to console
      </Link>

      {isLoading ? (
        <LoadingState label="Loading event…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data ? null : (
        <>
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <StatusBadge status={data.status} />
              {data.scoring_version && (
                <span className="font-mono text-[10px] text-muted">{data.scoring_version}</span>
              )}
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
            {data.summary && <p className="text-muted">{data.summary}</p>}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Panel className="p-4">
              <ScoreMeter label="Trend" score={data.trend_score} />
            </Panel>
            <Panel className="p-4">
              <ScoreMeter label="Opportunity" score={data.opportunity_score} />
            </Panel>
            <Panel className="p-4">
              <ScoreMeter label="Personal" score={data.personal_relevance} />
            </Panel>
            <Panel className="p-4">
              <ScoreMeter label="Confidence" score={data.confidence_score} />
            </Panel>
          </div>

          <ContentPanel eventId={id} />

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel className="p-5 lg:col-span-1">
              <h2 className="text-xs uppercase tracking-widest text-muted mb-3">
                Signal breakdown
              </h2>
              <div className="flex flex-col gap-2">
                {Object.keys(data.velocity).length === 0 ? (
                  <p className="text-sm text-muted">No signal data.</p>
                ) : (
                  Object.entries(data.velocity).map(([k, v]) => (
                    <VelocityRow key={k} label={k} value={Number(v)} />
                  ))
                )}
              </div>
              <h2 className="text-xs uppercase tracking-widest text-muted mt-5 mb-2">
                Sources ({data.sources.length})
              </h2>
              <div className="flex flex-wrap gap-2">
                {data.sources.map((s) => (
                  <span
                    key={s.id}
                    className="rounded-md border border-border px-2 py-1 text-xs text-muted"
                  >
                    {s.name}
                  </span>
                ))}
              </div>
            </Panel>

            <Panel className="p-5 lg:col-span-2">
              <h2 className="text-xs uppercase tracking-widest text-muted mb-3">
                What people are sharing ({data.items.length})
              </h2>
              <ul className="flex flex-col divide-y divide-border/70">
                {data.items.map((item) => (
                  <li key={item.id} className="py-2.5 first:pt-0">
                    <a
                      href={item.url ?? "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-text hover:text-accent transition-colors line-clamp-1"
                    >
                      {item.title ?? item.url ?? "Untitled"}
                    </a>
                    <span className="text-[11px] text-muted">{item.source_name}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
