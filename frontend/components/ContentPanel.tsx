"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveCandidate,
  fetchCandidates,
  generateCandidates,
  type ApproveResponse,
  type Candidate,
  type TweetKind,
  type TweetLength,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "./ui";

const KINDS: TweetKind[] = ["", "breaking", "contrarian", "technical", "educational", "question"];

function scoreColor(score: number): string {
  if (score >= 66) return "var(--hot)";
  if (score >= 33) return "var(--warn)";
  return "var(--accent)";
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* clipboard blocked — ignore */
        }
      }}
      className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
    >
      {done ? t("cp.copied") : label}
    </button>
  );
}

function CandidateCard({
  c,
  eventId,
  sourceUrl,
}: {
  c: Candidate;
  eventId: string;
  sourceUrl?: string | null;
}) {
  const { t } = useI18n();
  const approve = useMutation<ApproveResponse, Error, void>({
    mutationFn: () => approveCandidate(eventId, c.id),
  });
  const pred = approve.data?.prediction;
  const withSource = sourceUrl ? `${c.text}\n\n${sourceUrl}` : c.text;

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
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <CopyButton text={c.text} label={t("cp.copy")} />
        {sourceUrl && <CopyButton text={withSource} label={t("cp.copySource")} />}
        <div className="flex gap-3 text-[10px] text-muted font-mono ml-auto">
          <span>trend {c.trend_score.toFixed(0)}</span>
          <span>you {c.personal_score.toFixed(0)}</span>
          <span>risk {(c.risk_score * 100).toFixed(0)}</span>
        </div>
        {pred ? (
          <span className="text-[10px] font-mono text-good w-full text-right">
            ✓ {t("cp.approvedLikes", { n: pred.predicted_likes ?? 0 })}
          </span>
        ) : (
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            className="rounded border border-good/50 px-2 py-1 text-[11px] text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
          >
            {approve.isPending ? t("cp.approving") : t("cp.approve")}
          </button>
        )}
      </div>
    </Panel>
  );
}

export function ContentPanel({ eventId, sourceUrl }: { eventId: string; sourceUrl?: string | null }) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const [lang, setLang] = useState<"tr" | "en">(locale === "en" ? "en" : "tr");
  const [kind, setKind] = useState<TweetKind>("");
  const [length, setLength] = useState<TweetLength>("short");

  const { data } = useQuery({
    queryKey: ["candidates", eventId],
    queryFn: () => fetchCandidates(eventId),
  });

  const generate = useMutation({
    mutationFn: () => generateCandidates(eventId, { language: lang, kind, length }),
    onSuccess: (candidates) => qc.setQueryData(["candidates", eventId], candidates),
  });

  const candidates = data ?? [];
  const selectCls =
    "rounded-md border border-border bg-panel-2 px-2 py-1.5 text-sm text-text " +
    "focus:outline-none focus:border-accent/60 transition-colors";

  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
        <h2 className="text-xs uppercase tracking-widest text-muted">{t("cp.generate")}</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">{t("cp.lang")}</span>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as "tr" | "en")}
              className={selectCls}
            >
              <option value="tr">TR</option>
              <option value="en">EN</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">{t("cp.kind")}</span>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as TweetKind)}
              className={selectCls}
            >
              {KINDS.map((k) => (
                <option key={k || "all"} value={k}>
                  {t(k ? `cp.kind.${k}` : "cp.kind.all")}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">
              {t("cp.length")}
            </span>
            <select
              value={length}
              onChange={(e) => setLength(e.target.value as TweetLength)}
              className={selectCls}
            >
              <option value="short">{t("cp.length.short")}</option>
              <option value="long">{t("cp.length.long")}</option>
            </select>
          </label>
          <button
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="rounded-md border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {generate.isPending
              ? t("cp.generating")
              : candidates.length
                ? t("cp.regenerate")
                : t("cp.generateAngles")}
          </button>
        </div>
      </div>

      {generate.error && (
        <p className="text-hot text-xs mb-2">{(generate.error as Error).message}</p>
      )}

      {candidates.length === 0 ? (
        <p className="text-sm text-muted">{t("cp.none")}</p>
      ) : (
        <div className="grid gap-3">
          {candidates.map((c) => (
            <CandidateCard key={c.id} c={c} eventId={eventId} sourceUrl={sourceUrl} />
          ))}
        </div>
      )}
    </Panel>
  );
}
