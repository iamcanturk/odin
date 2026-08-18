import Link from "next/link";
import type { EventSummary } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel, ScoreMeter, StatusBadge } from "./ui";
import { IconClose } from "./icons";

const SOURCE_LABEL: Record<string, string> = {
  rss: "RSS",
  hackernews: "HN",
  github: "GitHub",
  reddit: "Reddit",
  x: "X",
};

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export function EventCard({
  event,
  rank,
  onDismiss,
}: {
  event: EventSummary;
  rank: number;
  onDismiss?: (id: string) => void;
}) {
  const { t } = useI18n();
  const forYou = event.topics.length > 0;
  return (
    <Link href={`/events/${event.id}`} className="block group">
      <Panel
        className={`relative p-4 transition-colors group-hover:border-accent/50 ${forYou ? "border-l-2 border-l-good" : ""}`}
      >
        {onDismiss && (
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onDismiss(event.id);
            }}
            className="absolute top-2.5 right-2.5 z-10 rounded-md p-1 text-faint hover:text-hot hover:bg-panel-2/80 transition-colors"
            title={t("ev.dismiss")}
            aria-label={t("ev.dismiss")}
          >
            <IconClose width={14} height={14} />
          </button>
        )}
        <div className="flex items-start gap-3 pr-6">
          <div className="font-mono text-xs text-faint w-6 pt-1 tabular-nums shrink-0">
            {String(rank).padStart(2, "0")}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <StatusBadge status={event.status} />
              {event.source_types.map((s) => (
                <span
                  key={s}
                  className="rounded border border-border px-1.5 py-0.5 text-[10px] font-mono uppercase text-muted"
                >
                  {SOURCE_LABEL[s] ?? s}
                </span>
              ))}
              {event.topics.map((tp) => (
                <span
                  key={tp}
                  className="rounded-full border border-good/40 px-2 py-0.5 text-[10px] text-good"
                >
                  {tp}
                </span>
              ))}
              <span className="text-[11px] text-faint">
                {event.source_count} · {event.item_count} · {relativeTime(event.last_seen_at)}
              </span>
            </div>
            <h3 className="mt-1.5 text-[15px] font-medium text-text truncate group-hover:text-accent transition-colors">
              {event.title}
            </h3>
            {event.summary && (
              <p className="text-sm text-muted mt-1 line-clamp-2">{event.summary}</p>
            )}
            {/* Other articles merged into this event — otherwise they're invisible. */}
            {event.headlines.filter((h) => h !== event.title).length > 0 && (
              <ul className="mt-1.5 flex flex-col gap-0.5">
                {event.headlines
                  .filter((h) => h !== event.title)
                  .slice(0, 3)
                  .map((h) => (
                    <li key={h} className="text-[11px] text-faint truncate">
                      ↳ {h}
                    </li>
                  ))}
              </ul>
            )}
            <div className="flex flex-wrap gap-x-6 gap-y-2 mt-3">
              <ScoreMeter label={t("ev.trend")} score={event.trend_score} />
              <ScoreMeter label={t("pn.opp")} score={event.opportunity_score} />
            </div>
          </div>
        </div>
      </Panel>
    </Link>
  );
}
