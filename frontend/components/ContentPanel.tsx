"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveCandidate,
  fetchCandidates,
  generateCandidates,
  type ApproveResponse,
  type Candidate,
} from "@/lib/api";
import { Panel } from "./ui";

function scoreColor(score: number): string {
  if (score >= 66) return "var(--hot)";
  if (score >= 33) return "var(--warn)";
  return "var(--accent)";
}

function CandidateCard({ c, eventId }: { c: Candidate; eventId: string }) {
  const approve = useMutation<ApproveResponse, Error, void>({
    mutationFn: () => approveCandidate(eventId, c.id),
  });
  const pred = approve.data?.prediction;

  return (
    <Panel className="p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
          #{c.rank} · {c.angle}
        </span>
        <span
          className="font-mono text-sm tabular-nums"
          style={{ color: scoreColor(c.viral_score) }}
        >
          {c.viral_score.toFixed(0)}
        </span>
      </div>
      <p className="text-sm text-text mt-2 whitespace-pre-wrap">{c.text}</p>
      <div className="flex items-center justify-between gap-4 mt-3">
        <div className="flex gap-4 text-[10px] text-muted font-mono">
          <span>trend {c.trend_score.toFixed(0)}</span>
          <span>you {c.personal_score.toFixed(0)}</span>
          <span>novelty {(c.novelty_score * 100).toFixed(0)}</span>
          <span>risk {(c.risk_score * 100).toFixed(0)}</span>
        </div>
        {pred ? (
          <span className="text-[10px] font-mono text-good">
            ✓ approved · ~{pred.predicted_likes} likes predicted
          </span>
        ) : (
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            className="rounded border border-good/50 px-2 py-1 text-[11px] text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
          >
            {approve.isPending ? "Approving…" : "Approve →"}
          </button>
        )}
      </div>
    </Panel>
  );
}

export function ContentPanel({ eventId }: { eventId: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["candidates", eventId],
    queryFn: () => fetchCandidates(eventId),
  });

  const generate = useMutation({
    mutationFn: () => generateCandidates(eventId),
    onSuccess: (candidates) => qc.setQueryData(["candidates", eventId], candidates),
  });

  const candidates = data ?? [];

  return (
    <Panel className="p-5">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="text-xs uppercase tracking-widest text-muted">Generate content</h2>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="rounded-md border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
        >
          {generate.isPending
            ? "Generating…"
            : candidates.length
              ? "Regenerate"
              : "Generate angles"}
        </button>
      </div>

      {generate.error && (
        <p className="text-hot text-xs mb-2">{(generate.error as Error).message}</p>
      )}

      {candidates.length === 0 ? (
        <p className="text-sm text-muted">
          No candidates yet. Generate distinct strategic angles for this event.
        </p>
      ) : (
        <div className="grid gap-3">
          {candidates.map((c) => (
            <CandidateCard key={c.id} c={c} eventId={eventId} />
          ))}
        </div>
      )}
    </Panel>
  );
}
