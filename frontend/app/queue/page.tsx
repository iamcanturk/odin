"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deletePost,
  fetchPosts,
  fetchSlot,
  markPosted,
  openInX,
  schedulePost,
  updatePost,
  type Post,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, PageHeader, Panel } from "@/components/ui";
import { RefineEditor } from "@/components/RefineEditor";

function DraftRow({ post }: { post: Post }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [xid, setXid] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(post.text);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["posts"] });

  const mark = useMutation({
    mutationFn: () => markPosted(post.id, xid.trim()),
    onSuccess: invalidate,
  });
  const save = useMutation({
    mutationFn: () => updatePost(post.id, draft),
    onSuccess: () => {
      setEditing(false);
      invalidate();
    },
  });
  const remove = useMutation({ mutationFn: () => deletePost(post.id), onSuccess: invalidate });
  const queue = useMutation({
    mutationFn: (auto: boolean) =>
      schedulePost(post.id, auto ? { auto: true } : { when: null }),
    onSuccess: invalidate,
  });
  const { data: slot } = useQuery({ queryKey: ["slot"], queryFn: fetchSlot });
  const posted = post.status === "posted";
  const queued = post.scheduled_for ? new Date(post.scheduled_for) : null;

  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2">
        {/* Only when there IS an angle — otherwise it reads "DRAFT DRAFT" beside the status. */}
        {post.angle && (
          <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
            {post.angle}
          </span>
        )}
        <span
          className={`text-[10px] font-mono uppercase tracking-widest ${posted ? "text-good" : "text-warn"}`}
        >
          {post.status}
        </span>
        <span className="ml-auto font-mono text-[10px] text-faint tabular-nums">
          {t("cp.chars", { n: post.text.length })}
        </span>
      </div>

      {editing ? (
        <RefineEditor
          value={draft}
          onChange={setDraft}
          onSave={() => save.mutate()}
          onCancel={() => {
            setDraft(post.text);
            setEditing(false);
          }}
          saving={save.isPending}
          eventId={post.event_id ?? undefined}
        />
      ) : (
        <p className="text-sm text-text mt-2 whitespace-pre-wrap">{post.text}</p>
      )}

      {!posted ? (
        <>
          {!editing && (
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() => openInX(post.text)}
                title={t("cp.openXHint")}
                className="rounded border border-accent/60 bg-accent/10 px-2 py-1 text-[11px] text-accent hover:bg-accent/20 transition-colors"
              >
                {t("cp.openX")}
              </button>
              <button
                onClick={() => setEditing(true)}
                className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
              >
                {t("cp.edit")}
              </button>
              {queued ? (
                <button
                  onClick={() => queue.mutate(false)}
                  disabled={queue.isPending}
                  title={t("qu.hint")}
                  className="rounded border border-warn/50 px-2 py-1 text-[11px] text-warn hover:bg-warn/10 disabled:opacity-40 transition-colors"
                >
                  {t("qu.unqueue")}
                </button>
              ) : (
                <button
                  onClick={() => queue.mutate(true)}
                  disabled={queue.isPending || !slot?.when}
                  title={slot?.when ? t("qu.hint") : slot?.reason}
                  className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-accent hover:border-accent/50 disabled:opacity-40 transition-colors"
                >
                  {t("qu.queue")}
                </button>
              )}
              <button
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
                className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-hot hover:border-hot/50 disabled:opacity-40 transition-colors"
              >
                {t("cp.delete")}
              </button>
            </div>
          )}
          {queued && (
            <p className="text-[11px] text-accent mt-2">
              {t("qu.queued")}: {queued.toLocaleString()} — {t("qu.hint")}
            </p>
          )}
          <p className="text-[11px] text-faint mt-2">{t("df.autoHint")}</p>
          <div className="flex items-center gap-2 mt-1">
            <input
              value={xid}
              onChange={(e) => setXid(e.target.value)}
              placeholder={t("df.pasteId")}
              className="h-8 flex-1 rounded-md border border-border bg-panel-2 px-3 text-xs outline-none focus:border-accent/60"
            />
            <button
              onClick={() => mark.mutate()}
              disabled={!xid.trim() || mark.isPending}
              className="h-8 rounded-md border border-good/50 px-3 text-xs text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
            >
              {t("df.markPosted")}
            </button>
          </div>
        </>
      ) : (
        <p className="text-[11px] text-muted font-mono mt-2">
          {t("df.posted")} {post.external_id}
        </p>
      )}
    </Panel>
  );
}

export default function QueuePage() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["posts", "queue"],
    queryFn: () => fetchPosts(),
  });

  const all = (data ?? []).filter((p) => p.origin === "generated");
  // Grouped by where a draft actually is, not by an arbitrary sort. Scheduled first
  // because those have a deadline attached.
  const scheduled = all
    .filter((p) => p.scheduled_for && p.status !== "posted")
    .sort((a, b) => (a.scheduled_for ?? "").localeCompare(b.scheduled_for ?? ""));
  const drafts = all.filter((p) => !p.scheduled_for && p.status !== "posted");
  const posted = all
    .filter((p) => p.status === "posted")
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 20);

  const groups: { key: string; items: typeof all }[] = [
    { key: "qp.scheduled", items: scheduled },
    { key: "qp.drafts", items: drafts },
    { key: "qp.posted", items: posted },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("qp.title")} subtitle={t("qp.subtitle")} />

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : all.length === 0 ? (
        <EmptyState label={t("df.empty")} />
      ) : (
        groups
          .filter((g) => g.items.length > 0)
          .map((g) => (
            <section key={g.key} className="flex flex-col gap-3">
              <div className="flex items-baseline gap-3">
                <h2 className="text-sm font-semibold tracking-tight">{t(g.key)}</h2>
                <span className="font-mono text-xs text-faint tabular-nums">
                  {g.items.length}
                </span>
              </div>
              <div className="grid gap-3">
                {g.items.map((p) => (
                  <DraftRow key={p.id} post={p} />
                ))}
              </div>
            </section>
          ))
      )}
    </div>
  );
}
