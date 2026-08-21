"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSource,
  deleteSource,
  fetchSourceItems,
  fetchSources,
  updateSource,
  type Source,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function health(s: Source, t: (k: string) => string): { label: string; color: string } {
  if (!s.enabled) return { label: "off", color: "var(--muted)" };
  if (s.failure_count >= 3) return { label: t("src.failing"), color: "var(--hot)" };
  if (!s.last_success_at) return { label: t("src.never"), color: "var(--warn)" };
  return { label: t("src.healthy"), color: "var(--good)" };
}

function SourceRow({ s }: { s: Source }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["sources"] });
  const toggle = useMutation({
    mutationFn: () => updateSource(s.id, { enabled: !s.enabled }),
    onSuccess: invalidate,
  });
  const remove = useMutation({ mutationFn: () => deleteSource(s.id), onSuccess: invalidate });
  const [open, setOpen] = useState(false);
  const h = health(s, t);

  return (
    <Panel className="p-3">
      <div className="flex items-center gap-3">
        <button
          onClick={() => toggle.mutate()}
          className="size-2.5 rounded-full shrink-0"
          style={{ background: s.enabled ? "var(--good)" : "var(--border)" }}
          title={s.enabled ? "on" : "off"}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{s.name}</span>
            <span className="text-[10px] font-mono uppercase text-muted">{s.type}</span>
            {s.category && (
              <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase text-faint">
                {s.category}
              </span>
            )}
          </div>
          {s.url && <div className="text-xs text-muted mt-0.5 truncate">{s.url}</div>}
        </div>
        <span className="font-mono text-[11px]" style={{ color: h.color }}>
          {h.label}
        </span>
        <button
          onClick={() => setOpen((v) => !v)}
          className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
        >
          {open ? t("src.hideItems") : t("src.showItems")}
        </button>
        <button
          onClick={() => remove.mutate()}
          className="text-muted hover:text-hot text-xs px-2 transition-colors"
        >
          {t("src.remove")}
        </button>
      </div>

      {open && <SourceItems id={s.id} />}
    </Panel>
  );
}

/** What this source actually brought in — the page showed health but never content. */
function SourceItems({ id }: { id: string }) {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["sources", id, "items"],
    queryFn: () => fetchSourceItems(id),
  });

  if (isLoading) return <p className="text-xs text-faint mt-3">…</p>;
  if (!data || data.length === 0) {
    return <p className="text-xs text-muted mt-3">{t("src.noItems")}</p>;
  }
  return (
    <ul className="mt-3 flex flex-col gap-1.5 border-t border-border-soft pt-3">
      {data.map((item) => (
        <li key={item.id} className="flex items-start gap-2">
          {item.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.image} alt="" className="size-8 rounded object-cover shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <a
              href={item.url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-text hover:text-accent transition-colors line-clamp-2"
            >
              {item.title ?? item.url}
            </a>
            {item.published_at && (
              <span className="text-[10px] text-faint font-mono">
                {new Date(item.published_at).toLocaleDateString()}
              </span>
            )}
          </div>
          {item.event_id && (
            <a
              href={`/events/${item.event_id}`}
              className="text-[10px] text-accent hover:underline shrink-0"
            >
              →
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

export function SourcesPanel() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["sources"],
    queryFn: fetchSources,
  });

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const create = useMutation({
    mutationFn: () => createSource({ name: name.trim(), type: "rss", url: url.trim() }),
    onSuccess: () => {
      setName("");
      setUrl("");
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  return (
    <div className="flex flex-col gap-6">

      <Panel className="p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_2fr_auto] items-end">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">{t("src.name")}</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="TechCrunch"
              className="h-9 rounded-md border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">{t("src.url")}</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/feed"
              className="h-9 rounded-md border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60"
            />
          </label>
          <button
            onClick={() => create.mutate()}
            disabled={!name.trim() || !url.trim() || create.isPending}
            className="h-9 rounded-md border border-accent/50 px-4 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {create.isPending ? t("src.adding") : t("src.add")}
          </button>
        </div>
        {create.error && <p className="text-hot text-xs mt-2">{(create.error as Error).message}</p>}
      </Panel>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState label={t("src.empty")} />
      ) : (
        <div className="grid gap-2">
          {data.map((s) => (
            <SourceRow key={s.id} s={s} />
          ))}
        </div>
      )}
    </div>
  );
}
