"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchDiscover, fetchSources, pollSource, type DiscoverItem } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, Panel } from "@/components/ui";

function Card({ item }: { item: DiscoverItem }) {
  const { t } = useI18n();
  return (
    <Panel className="overflow-hidden flex flex-col">
      {item.image && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={item.image} alt="" className="w-full h-36 object-cover" loading="lazy" />
      )}
      <div className="p-3 flex flex-col gap-2 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
            {item.source_name}
          </span>
          {item.source_category && (
            <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-faint">
              {item.source_category}
            </span>
          )}
        </div>

        <a
          href={item.url ?? "#"}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-text hover:text-accent transition-colors line-clamp-3 flex-1"
        >
          {item.title ?? item.url}
        </a>

        <div className="flex items-center gap-3 mt-auto pt-1">
          {item.published_at && (
            <span className="text-[10px] text-faint font-mono">
              {new Date(item.published_at).toLocaleDateString()}
            </span>
          )}
          {item.event_id ? (
            <Link
              href={`/events/${item.event_id}`}
              className="ml-auto text-[11px] text-accent hover:underline"
            >
              {t("dc.toEvent")} →
            </Link>
          ) : (
            <Link
              href={`/compose?topic=${encodeURIComponent(item.title ?? "")}`}
              className="ml-auto text-[11px] text-accent hover:underline"
            >
              {t("dc.compose")} →
            </Link>
          )}
        </div>
      </div>
    </Panel>
  );
}

export default function DiscoverPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [sourceId, setSourceId] = useState("");
  const [category, setCategory] = useState("");
  const [withMedia, setWithMedia] = useState(false);

  const { data: sources } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["discover", sourceId, category, withMedia],
    queryFn: () =>
      fetchDiscover({
        sourceId: sourceId || undefined,
        category: category || undefined,
        withMedia,
      }),
  });

  // The 15-minute cron polls everything at once; this pulls one source on demand,
  // which is what you want when you're looking at Reddit or Pinterest right now.
  const poll = useMutation({
    mutationFn: () => pollSource(sourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discover"] }),
  });

  // Categories come from the sources themselves — no hardcoded list to drift.
  const categories = Array.from(
    new Set((sources ?? []).map((s) => s.category).filter((c): c is string => !!c)),
  ).sort();

  const selectCls =
    "h-9 rounded-lg border border-border bg-panel-2 px-3 text-sm text-text " +
    "outline-none focus:border-accent/60 transition-colors";

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("dc.title")}
        subtitle={t("dc.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              className={selectCls}
            >
              <option value="">{t("dc.allSources")}</option>
              {(sources ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {sourceId && (
              <button
                onClick={() => poll.mutate()}
                disabled={poll.isPending}
                className="rounded-lg border border-accent/60 bg-accent/10 px-2.5 py-1.5 text-xs text-accent hover:bg-accent/20 disabled:opacity-40 transition-colors"
              >
                {poll.isPending ? "…" : t("dc.fetch")}
              </button>
            )}
            <button
              onClick={() => setWithMedia((v) => !v)}
              className={`rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                withMedia
                  ? "border-accent/60 text-accent bg-accent/10"
                  : "border-border text-muted hover:text-text"
              }`}
            >
              {t("dc.onlyImages")}
            </button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-1.5">
        {["", ...categories].map((c) => (
          <button
            key={c || "all"}
            onClick={() => {
              setCategory(c);
              setSourceId("");
            }}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              category === c
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {c || t("dc.all")}
          </button>
        ))}
      </div>

      {poll.data && (
        <p className="text-xs text-muted">
          {poll.data.source}: {t("dc.fetched", { n: poll.data.fetched })}
          {poll.data.errors.length > 0 && ` — ${poll.data.errors.join(", ")}`}
        </p>
      )}
      {poll.error && (
        <p className="text-xs text-warn">
          {t("dc.fetchFail")}: {(poll.error as Error).message}
        </p>
      )}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState label={t("dc.empty")} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((item) => (
            <Card key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
