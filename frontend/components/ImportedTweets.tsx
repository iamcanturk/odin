"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchImportedTweets, type ImportedTweet, type MetricPoint } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function Metric({ value, label }: { value: number | null; label: string }) {
  if (value == null) return null;
  return (
    <span className="text-[11px] text-muted tabular-nums">
      <span className="text-text font-medium">{compact(value)}</span> {label}
    </span>
  );
}

/** The first-hour view curve — where most of a tweet's reach is decided. */
function FirstHour({ history }: { history: MetricPoint[] }) {
  const { t } = useI18n();
  const pts = history.filter(
    (h) => h.minutes_after_post != null && h.minutes_after_post <= 60 && h.impressions != null,
  );
  if (pts.length < 2) return null;
  const max = Math.max(...pts.map((p) => p.impressions ?? 0)) || 1;
  return (
    <div className="mt-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-widest text-muted">
          {t("pf.firstHour")}
        </span>
        <span className="text-[10px] text-faint font-mono">
          {t("pf.samples", { n: pts.length })}
        </span>
      </div>
      <div className="flex items-end gap-0.5 h-8 mt-1">
        {pts.map((p, i) => (
          <div
            key={i}
            className="flex-1 rounded-t bg-accent/70 min-w-[2px]"
            style={{ height: `${Math.max(6, (100 * (p.impressions ?? 0)) / max)}%` }}
            title={`+${p.minutes_after_post}m: ${compact(p.impressions ?? 0)} views`}
          />
        ))}
      </div>
    </div>
  );
}

function Row({ tw }: { tw: ImportedTweet }) {
  const { t } = useI18n();
  const when = tw.posted_at ? new Date(tw.posted_at).toLocaleDateString() : "";
  return (
    <div className="py-3 first:pt-0 last:pb-0 border-b border-border-soft last:border-0">
      <p className="text-sm text-text whitespace-pre-wrap">{tw.text}</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2">
        <Metric value={tw.likes} label={t("pf.mLikes")} />
        <Metric value={tw.reposts} label={t("pf.mReposts")} />
        <Metric value={tw.replies} label={t("pf.mReplies")} />
        <Metric value={tw.impressions} label={t("pf.mViews")} />
        {when && <span className="text-[11px] text-faint ml-auto font-mono">{when}</span>}
        {tw.url && (
          <a
            href={tw.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-accent hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            X ↗
          </a>
        )}
      </div>
      <FirstHour history={tw.history} />
    </div>
  );
}

export function ImportedTweets() {
  const { t } = useI18n();
  const { data } = useQuery({ queryKey: ["profile", "tweets"], queryFn: fetchImportedTweets });

  if (!data) return null;

  return (
    <Panel className="p-5">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-xs uppercase tracking-widest text-muted">{t("pf.myTweets")}</h2>
        {data.length > 0 && (
          <span className="font-mono text-xs text-faint tabular-nums">{data.length}</span>
        )}
      </div>
      {data.length === 0 ? (
        <p className="text-sm text-muted mt-2">{t("pf.noTweets")}</p>
      ) : (
        <>
          <p className="text-[11px] text-faint mb-2">
            {t("pf.myTweetsHint")} {t("pf.tracking")}
          </p>
          <div className="flex flex-col">
            {data.map((tw) => (
              <Row key={tw.id} tw={tw} />
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
