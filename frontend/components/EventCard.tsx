import Link from "next/link";
import type { EventSummary } from "@/lib/api";
import { Panel, ScoreMeter, StatusBadge } from "./ui";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function EventCard({ event, rank }: { event: EventSummary; rank: number }) {
  return (
    <Link href={`/events/${event.id}`} className="block group">
      <Panel className="p-4 transition-colors group-hover:border-accent/50">
        <div className="flex items-start gap-4">
          <div className="font-mono text-xs text-muted w-6 pt-1 tabular-nums">
            {String(rank).padStart(2, "0")}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <StatusBadge status={event.status} />
              <span className="text-[11px] text-muted">
                {event.source_count} source{event.source_count === 1 ? "" : "s"} ·{" "}
                {event.item_count} item{event.item_count === 1 ? "" : "s"} ·{" "}
                {relativeTime(event.last_seen_at)}
              </span>
            </div>
            <h3 className="mt-1.5 text-[15px] font-medium text-text truncate group-hover:text-accent transition-colors">
              {event.title}
            </h3>
            {event.summary && (
              <p className="text-sm text-muted mt-1 line-clamp-2">{event.summary}</p>
            )}
          </div>
          <div className="flex gap-4 shrink-0">
            <ScoreMeter label="Trend" score={event.trend_score} />
            <ScoreMeter label="Opp." score={event.opportunity_score} />
          </div>
        </div>
      </Panel>
    </Link>
  );
}
