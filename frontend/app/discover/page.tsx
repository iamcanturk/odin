"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchDiscover, fetchSources, type DiscoverItem } from "@/lib/api";
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
  const [sourceId, setSourceId] = useState("");
  const [withMedia, setWithMedia] = useState(false);

  const { data: sources } = useQuery({ queryKey: ["sources"], queryFn: fetchSources });
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["discover", sourceId, withMedia],
    queryFn: () => fetchDiscover({ sourceId: sourceId || undefined, withMedia }),
  });

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
