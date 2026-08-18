"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPosts, markPosted, type Post } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function DraftRow({ post }: { post: Post }) {
  const qc = useQueryClient();
  const [xid, setXid] = useState("");
  const mark = useMutation({
    mutationFn: () => markPosted(post.id, xid.trim()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posts"] }),
  });

  return (
    <Panel className="p-4">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
          {post.angle ?? "draft"}
        </span>
        <span
          className={`text-[10px] font-mono uppercase tracking-widest ${post.status === "posted" ? "text-good" : "text-warn"}`}
        >
          {post.status}
        </span>
      </div>
      <p className="text-sm text-text mt-2 whitespace-pre-wrap">{post.text}</p>
      {post.status !== "posted" ? (
        <div className="flex items-center gap-2 mt-3">
          <input
            value={xid}
            onChange={(e) => setXid(e.target.value)}
            placeholder="Paste the X post id after posting"
            className="h-8 flex-1 rounded-md border border-border bg-panel-2 px-3 text-xs outline-none focus:border-accent/60"
          />
          <button
            onClick={() => mark.mutate()}
            disabled={!xid.trim() || mark.isPending}
            className="h-8 rounded-md border border-good/50 px-3 text-xs text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
          >
            Mark posted
          </button>
        </div>
      ) : (
        <p className="text-[11px] text-muted font-mono mt-2">posted · id {post.external_id}</p>
      )}
    </Panel>
  );
}

export default function DraftsPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["posts", "queue"],
    queryFn: () => fetchPosts(),
  });
  const drafts = (data ?? []).filter((p) => p.origin === "generated");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Drafts &amp; queue</h1>
        <p className="text-sm text-muted mt-1">
          Approved content, with its prediction stored. Post it on X yourself, then paste the post
          id so ODIN can compare prediction vs. reality.
        </p>
      </div>

      {isLoading ? (
        <LoadingState label="Loading drafts…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : drafts.length === 0 ? (
        <EmptyState label="No drafts yet. Approve a candidate from an event to queue it here." />
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
