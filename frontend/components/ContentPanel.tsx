"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveCandidate,
  deleteCandidate,
  fetchCandidates,
  fetchStyleRefs,
  generateCandidates,
  updateCandidate,
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
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(c.text);

  const approve = useMutation<ApproveResponse, Error, void>({
    mutationFn: () => approveCandidate(eventId, c.id),
  });
  const save = useMutation({
    mutationFn: () => updateCandidate(eventId, c.id, draft),
    onSuccess: () => {
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["candidates", eventId] });
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteCandidate(eventId, c.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidates", eventId] }),
  });

  const pred = approve.data?.prediction;
  const text = c.text;
  const withSource = sourceUrl ? `${text}\n\n${sourceUrl}` : text;

  return (
    <Panel className="p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
          #{c.rank} · {c.angle}
        </span>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] text-faint tabular-nums">
            {t("cp.chars", { n: text.length })}
          </span>
          <span
            className="font-mono text-sm tabular-nums"
            style={{ color: scoreColor(c.viral_score) }}
          >
            {c.viral_score.toFixed(0)}
          </span>
        </div>
      </div>

      {editing ? (
        <div className="mt-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(12, Math.max(3, Math.ceil(draft.length / 60)))}
            className="w-full rounded-md border border-border bg-panel-2 px-3 py-2 text-sm outline-none focus:border-accent/60 resize-y"
          />
          <div className="flex items-center gap-2 mt-2">
            <button
              onClick={() => save.mutate()}
              disabled={save.isPending || !draft.trim()}
              className="rounded border border-good/50 px-2 py-1 text-[11px] text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
            >
              {t("cp.save")}
            </button>
            <button
              onClick={() => {
                setDraft(c.text);
                setEditing(false);
              }}
              className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text transition-colors"
            >
              {t("cp.cancel")}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-text mt-2 whitespace-pre-wrap">{text}</p>
      )}

      <div className="flex flex-wrap items-center gap-2 mt-3">
        <CopyButton text={text} label={t("cp.copy")} />
        {sourceUrl && <CopyButton text={withSource} label={t("cp.copySource")} />}
        {!editing && (
          <>
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
          </>
        )}
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

function SuggestedImage({ url }: { url: string }) {
  const { t } = useI18n();
  return (
    <div className="mb-4 rounded-lg border border-border overflow-hidden bg-panel-2">
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border-soft">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-widest text-muted">{t("cp.image")}</p>
          <p className="text-[11px] text-faint truncate">{t("cp.imageHint")}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <CopyButton text={url} label={t("cp.copyImage")} />
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
          >
            {t("cp.openImage")}
          </a>
        </div>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="" className="w-full max-h-64 object-cover" loading="lazy" />
    </div>
  );
}

export function ContentPanel({
  eventId,
  sourceUrl,
  imageUrl,
}: {
  eventId: string;
  sourceUrl?: string | null;
  imageUrl?: string | null;
}) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const [lang, setLang] = useState<"tr" | "en">(locale === "en" ? "en" : "tr");
  const [kind, setKind] = useState<TweetKind>("");
  const [length, setLength] = useState<TweetLength>("short");
  const [styleHandle, setStyleHandle] = useState("");

  const { data: styles } = useQuery({ queryKey: ["compose", "styles"], queryFn: fetchStyleRefs });

  const { data } = useQuery({
    queryKey: ["candidates", eventId],
    queryFn: () => fetchCandidates(eventId),
  });

  const generate = useMutation({
    mutationFn: () =>
      generateCandidates(eventId, { language: lang, kind, length, styleHandle }),
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
              <option value="story">{t("co.fmt.story")}</option>
              <option value="thread">{t("co.fmt.thread")}</option>
            </select>
          </label>
          {!!styles?.length && (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest text-muted">
                {t("co.style")}
              </span>
              <select
                value={styleHandle}
                onChange={(e) => setStyleHandle(e.target.value)}
                className={selectCls}
              >
                <option value="">{t("co.style.mine")}</option>
                {styles.map((s) => (
                  <option key={s.handle} value={s.handle}>
                    @{s.handle} ({s.samples})
                  </option>
                ))}
              </select>
            </label>
          )}

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

      {imageUrl && <SuggestedImage url={imageUrl} />}

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
