"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchProfile, rebuildProfile, type StyleProfile } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

const FEATURE_LABELS: Record<string, string> = {
  avg_length: "Avg length (chars)",
  avg_sentence_length: "Avg sentence (words)",
  question_rate: "Asks a question",
  exclaim_rate: "Uses exclamation",
  emoji_rate: "Emoji rate",
  hashtag_per_post: "Hashtags / post",
  mention_per_post: "Mentions / post",
  link_rate: "Includes a link",
  list_rate: "Uses lists",
  hook_rate: "Opens with a hook",
  allcaps_rate: "ALL-CAPS words",
};

function fmt(key: string, v: number): string {
  if (["avg_length", "avg_sentence_length", "hashtag_per_post", "mention_per_post"].includes(key))
    return v.toFixed(1);
  return `${Math.round(v * 100)}%`;
}

export default function ProfilePage() {
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery<StyleProfile | null>({
    queryKey: ["profile"],
    queryFn: fetchProfile,
  });

  const rebuild = useMutation({
    mutationFn: rebuildProfile,
    onSuccess: (p) => qc.setQueryData(["profile"], p),
  });

  const topTerms = (data?.features?.top_terms as string[] | undefined) ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Your style profile</h1>
          <p className="text-sm text-muted mt-1">
            A fingerprint of how you write, learned from your imported posts (via the X collector).
          </p>
        </div>
        <button
          onClick={() => rebuild.mutate()}
          disabled={rebuild.isPending}
          className="rounded-md border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
        >
          {rebuild.isPending ? "Rebuilding…" : "Rebuild"}
        </button>
      </div>

      {isLoading ? (
        <LoadingState label="Loading profile…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data ? (
        <EmptyState label="No style profile yet. Import posts with the X collector, then Rebuild." />
      ) : (
        <>
          <Panel className="p-5">
            <p className="text-sm text-text">{data.summary}</p>
            <p className="text-[11px] text-muted font-mono mt-2">
              {data.post_count} posts analyzed
            </p>
          </Panel>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(FEATURE_LABELS).map(([key, label]) => (
              <Panel key={key} className="p-3 flex items-center justify-between">
                <span className="text-xs text-muted">{label}</span>
                <span className="font-mono text-sm tabular-nums">
                  {fmt(key, Number(data.features?.[key] ?? 0))}
                </span>
              </Panel>
            ))}
          </div>

          {topTerms.length > 0 && (
            <Panel className="p-5">
              <h2 className="text-xs uppercase tracking-widest text-muted mb-3">Frequent terms</h2>
              <div className="flex flex-wrap gap-2">
                {topTerms.map((t) => (
                  <span
                    key={t}
                    className="rounded-md border border-border px-2 py-1 text-xs text-muted"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
