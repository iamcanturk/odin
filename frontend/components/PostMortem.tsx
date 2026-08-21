"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchPostMortem, type Comparison } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const VERDICT_COLOR: Record<Comparison["verdict"], string> = {
  better: "text-good",
  similar: "text-muted",
  worse: "text-warn",
  unknown: "text-faint",
};

/** The four reference points that turn a bare number into an explanation. */
export function PostMortem({ postId }: { postId: string }) {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["postmortem", postId],
    queryFn: () => fetchPostMortem(postId),
  });

  if (isLoading) return <p className="text-[11px] text-faint mt-2">…</p>;
  if (!data) return null;

  return (
    <div className="mt-3 rounded-lg border border-border-soft bg-panel-2 p-3">
      <div className="flex items-baseline gap-2">
        <h3 className="text-[11px] uppercase tracking-widest text-accent">{t("pm.title")}</h3>
        {data.first_hour_likes !== null && (
          <span className="text-[10px] text-faint font-mono">
            {t("pm.firstHour")}: {data.first_hour_likes}♥
          </span>
        )}
      </div>

      {data.comparisons.length > 0 && (
        <ul className="mt-2 space-y-1">
          {data.comparisons.map((c) => (
            <li key={c.label} className="text-xs">
              <span className={`font-mono tabular-nums mr-2 ${VERDICT_COLOR[c.verdict]}`}>
                {c.actual.toFixed(0)}
                {c.reference !== null && ` / ${c.reference.toFixed(0)}`}
              </span>
              <span className="text-muted">{c.note}</span>
            </li>
          ))}
        </ul>
      )}

      {data.lessons.length > 0 && (
        <>
          <div className="text-[10px] uppercase tracking-widest text-muted mt-3">
            {t("pm.lessons")}
          </div>
          <ul className="mt-1 space-y-1 list-disc pl-4">
            {data.lessons.map((lesson, i) => (
              <li key={i} className="text-xs text-text leading-relaxed">
                {lesson}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
