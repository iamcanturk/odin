"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchBenchmark, type PostRank } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

const VERDICT_STYLE: Record<PostRank["verdict"], string> = {
  top: "text-good border-good/50",
  above: "text-accent border-accent/50",
  typical: "text-muted border-border",
  below: "text-warn border-warn/50",
};

/** "3 likes" means nothing alone; it means something against the room. */
export function BenchmarkPanel() {
  const { t } = useI18n();
  const { data } = useQuery({ queryKey: ["benchmark"], queryFn: fetchBenchmark });
  if (!data) return null;

  if (!data.enough_data) {
    return (
      <Panel className="p-5">
        <h2 className="text-sm font-semibold text-text">{t("bm.title")}</h2>
        <p className="text-sm text-muted mt-2">
          {t("bm.thin", { n: data.corpus_size, m: data.min_corpus })}
        </p>
      </Panel>
    );
  }

  const likes = data.distributions.find((d) => d.metric === "likes");

  return (
    <Panel className="p-5">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-sm font-semibold text-text">{t("bm.title")}</h2>
        <span className="text-[11px] text-faint">{t("bm.subtitle")}</span>
      </div>

      <div className="grid gap-3 sm:grid-cols-3 mt-4">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted">{t("bm.you")}</div>
          <div className="font-mono text-2xl tabular-nums text-accent mt-1">
            {data.your_percentile === null ? "—" : `%${data.your_percentile.toFixed(0)}`}
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted">{t("bm.corpus")}</div>
          <div className="font-mono text-2xl tabular-nums mt-1">{data.corpus_size}</div>
        </div>
        {likes && (
          <div>
            <div className="text-[10px] uppercase tracking-widest text-muted">
              median / p75 / p90
            </div>
            <div className="font-mono text-sm tabular-nums mt-2">
              {likes.median} / {likes.p75} / {likes.p90}
            </div>
          </div>
        )}
      </div>

      {data.posts.length > 0 && (
        <ul className="mt-4 space-y-1.5 max-h-72 overflow-y-auto">
          {data.posts.map((p) => (
            <li key={p.post_id} className="flex items-start gap-2 text-sm">
              <span
                className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] tabular-nums ${VERDICT_STYLE[p.verdict]}`}
              >
                %{p.like_percentile.toFixed(0)}
              </span>
              <span className="text-text line-clamp-1 flex-1">{p.text}</span>
              <span className="shrink-0 font-mono text-[11px] text-faint tabular-nums">
                {p.likes}♥
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="text-[11px] text-faint mt-4">⚠ {data.caveat}</p>
    </Panel>
  );
}
