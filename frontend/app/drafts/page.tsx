"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deletePost, fetchPosts, markPosted, updatePost, type Post } from "@/lib/api";
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
  const posted = post.status === "posted";

  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
          {post.angle ?? "draft"}
        </span>
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
                onClick={() => setEditing(true)}
                className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
              >
                {t("cp.edit")}
              </button>
              <button
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
                className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-hot hover:border-hot/50 disabled:opacity-40 transition-colors"
              >
                {t("cp.delete")}
              </button>
            </div>
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

export default function DraftsPage() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["posts", "queue"],
    queryFn: () => fetchPosts(),
  });
  const drafts = (data ?? []).filter((p) => p.origin === "generated");

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("df.title")} subtitle={t("df.subtitle")} />

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : drafts.length === 0 ? (
        <EmptyState label={t("df.empty")} />
      ) : (
        <div className="grid gap-3">
          {drafts.map((p) => (
            <DraftRow key={p.id} post={p} />
          ))}
        </div>
      )}
    </div>
  );
}
