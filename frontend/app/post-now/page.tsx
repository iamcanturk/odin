"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchEvents, fetchTiming, recommendedAction } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, Panel, ScoreMeter } from "@/components/ui";

const TONE: Record<string, string> = {
  hot: "text-hot border-hot/50",
  good: "text-good border-good/40",
  warn: "text-warn border-warn/40",
  muted: "text-muted border-border",
};

const ACTION_KEY: Record<string, string> = {
  "POST NOW": "action.postNow",
  "POST WITHIN 30 MIN": "action.within30",
  CONSIDER: "action.consider",
  WAIT: "action.wait",
};

export default function PostNowPage() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["events", { orderBy: "opportunity_score" }],
    queryFn: () => fetchEvents({ limit: 25, orderBy: "opportunity_score" }),
  });
  const { data: timing } = useQuery({
    queryKey: ["performance", "timing"],
    queryFn: fetchTiming,
  });

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("pn.title")} subtitle={t("pn.subtitle")} />

      {timing?.enough_data && timing.best_hour != null && (
        <Panel className="p-4 flex items-center gap-3">
          <span className="text-[10px] uppercase tracking-widest text-muted">
            {t("tm.bestHour")}
          </span>
          <span className="font-mono text-lg tabular-nums text-good">
            {String(timing.best_hour).padStart(2, "0")}:00
          </span>
          <span className="text-[11px] text-faint">{t("tm.hint")}</span>
        </Panel>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState label={t("pn.empty")} />
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
                        {t(ACTION_KEY[action.label] ?? action.label)}
                      </span>
                      <h3 className="mt-1.5 text-[15px] font-medium truncate group-hover:text-accent transition-colors">
                        {event.title}
                      </h3>
                    </div>
                    <div className="flex gap-4 shrink-0">
                      <ScoreMeter label={t("pn.opp")} score={event.opportunity_score} />
                      <ScoreMeter label={t("pn.you")} score={event.personal_relevance} />
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
