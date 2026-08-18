"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchEvaluation } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-4">
      <div className="text-[10px] uppercase tracking-widest text-muted">{label}</div>
      <div className="font-mono text-xl tabular-nums mt-1">{value}</div>
    </Panel>
  );
}

export default function LearningPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["evaluation"],
    queryFn: fetchEvaluation,
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Learning</h1>
        <p className="text-sm text-muted mt-1">
          Prediction vs. actual. Once you post approved drafts and their metrics come back (via the
          X collector), ODIN measures how accurate its predictions were.
        </p>
      </div>

      {isLoading ? (
        <LoadingState label="Evaluating…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.evaluated === 0 ? (
        <EmptyState label="Nothing to evaluate yet. Post an approved draft, then import its metrics." />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label="Evaluated" value={String(data.evaluated)} />
            <Stat label="MAE (likes)" value={data.mae.toFixed(1)} />
            <Stat label="RMSE (likes)" value={data.rmse.toFixed(1)} />
            <Stat
              label="Precision@3"
              value={data.precision_at_3 == null ? "—" : `${(data.precision_at_3 * 100).toFixed(0)}%`}
            />
          </div>

          <Panel className="p-5">
            <h2 className="text-xs uppercase tracking-widest text-muted mb-3">Per post</h2>
            <div className="grid gap-2">
              {data.items.map((it) => (
                <div key={it.post_id} className="flex items-center gap-3 text-sm">
                  <span className="flex-1 truncate text-muted">{it.text}</span>
                  <span className="font-mono text-xs tabular-nums text-muted">
                    pred {it.predicted_likes}
                  </span>
                  <span className="font-mono text-xs tabular-nums">act {it.actual_likes}</span>
                  <span
                    className="font-mono text-xs tabular-nums w-14 text-right"
                    style={{ color: it.error_pct > 50 ? "var(--hot)" : "var(--good)" }}
                  >
                    {it.error_pct.toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
