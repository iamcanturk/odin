"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  analyzeText,
  compose,
  createPost,
  openInX,
  schedulePost,
  type ComposeAudience,
  type ComposeLength,
  type TesterResponse,
  type TweetKind,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

/** What a feed card hands the composer when you click it. */
export interface ComposerSeed {
  topic: string;
  eventId?: string;
  source?: string;
}

const LENGTHS: ComposeLength[] = ["short", "long", "story", "thread"];
const KINDS: TweetKind[] = ["", "breaking", "contrarian", "technical", "educational", "question"];
// Long enough that you've stopped typing, short enough to feel live.
const SCORE_DEBOUNCE_MS = 700;
const MIN_TO_SCORE = 25;

function scoreColor(score: number): string {
  if (score >= 66) return "var(--good)";
  if (score >= 33) return "var(--warn)";
  return "var(--hot)";
}

/** Scoring and the repetition check, folded in from what used to be a separate page. */
function LiveScore({ text }: { text: string }) {
  const { t } = useI18n();
  // Kept together with the text it describes, so a score can never be shown against
  // a draft it wasn't computed from.
  const [scored, setScored] = useState<{ text: string; result: TesterResponse } | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const latest = useRef(text);

  useEffect(() => {
    latest.current = text;
    if (text.trim().length < MIN_TO_SCORE) return;
    const timer = setTimeout(async () => {
      setBusy(true);
      try {
        const result = await analyzeText(text);
        // A slow response for text you've since changed is stale, not an answer.
        if (latest.current === text) {
          setScored({ text, result });
          setFailed(false);
        }
      } catch {
        // Scoring is advisory and must never block writing — but saying "write more"
        // when the request actually failed sends you off fixing the wrong thing.
        if (latest.current === text) setFailed(true);
      } finally {
        setBusy(false);
      }
    }, SCORE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  const long = text.trim().length >= MIN_TO_SCORE;
  const result = long ? scored?.result ?? null : null;
  const stale = scored?.text !== text;

  if (!result) {
    if (busy) return <p className="text-[11px] text-faint">…</p>;
    if (failed && long) return <p className="text-[11px] text-warn">{t("cm.scoreFailed")}</p>;
    return (
      <p className="text-[11px] text-faint">
        {text.trim().length ? t("cm.scoreWait") : ""}
      </p>
    );
  }

  return (
    <div className={`flex flex-col gap-2 transition-opacity ${stale ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-3">
        <span className="text-[10px] uppercase tracking-widest text-muted">{t("cm.score")}</span>
        <span
          className="font-mono text-lg tabular-nums"
          style={{ color: scoreColor(result.viral_potential) }}
        >
          {result.viral_potential.toFixed(0)}
        </span>
        <span className="text-[10px] text-faint font-mono ml-auto">
          xsim {result.x_simulation.toFixed(0)} · {t("cm.fit")} {result.personal_fit.toFixed(0)}
        </span>
      </div>

      {result.repeats.length > 0 && (
        <div className="rounded border border-warn/40 bg-warn/5 p-2">
          <p className="text-[11px] text-warn font-medium">{t("ts.repeat")}</p>
          {result.repeats.slice(0, 2).map((m) => (
            <p key={m.post_id} className="text-[11px] text-muted mt-1 line-clamp-2">
              <span className="font-mono tabular-nums">%{Math.round(m.similarity * 100)}</span>{" "}
              {m.text}
            </p>
          ))}
        </div>
      )}

      {result.weaknesses.length > 0 && (
        <ul className="space-y-0.5">
          {result.weaknesses.slice(0, 2).map((w, i) => (
            <li key={i} className="text-[11px] text-muted leading-snug">
              · {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Composer({ seed }: { seed: ComposerSeed | null }) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  // Seeded from the clicked card. The parent remounts this via `key` when the seed
  // changes, which is how you reset state on a prop change without an effect.
  const [topic, setTopic] = useState(seed?.topic ?? "");
  const [text, setText] = useState("");
  const [lang, setLang] = useState<"tr" | "en">(locale === "en" ? "en" : "tr");
  const [length, setLength] = useState<ComposeLength>("short");
  const [kind, setKind] = useState<TweetKind>("");
  const [audience] = useState<ComposeAudience>("technical");
  const [saved, setSaved] = useState<string | null>(null);

  const gen = useMutation({
    mutationFn: () =>
      compose({ topic, language: lang, length, audience, kind, style_handle: "" }),
    onSuccess: (drafts) => {
      if (drafts.length) setText(drafts[0].text);
    },
  });

  const save = useMutation({
    mutationFn: () => createPost({ text, event_id: seed?.eventId }),
    onSuccess: (post) => {
      setSaved(post.id);
      qc.invalidateQueries({ queryKey: ["posts"] });
    },
  });

  const queue = useMutation({
    mutationFn: async () => {
      const post = saved ? { id: saved } : await createPost({ text, event_id: seed?.eventId });
      return schedulePost(post.id, { auto: true });
    },
    onSuccess: (post) => {
      setSaved(post.id);
      qc.invalidateQueries({ queryKey: ["posts"] });
      qc.invalidateQueries({ queryKey: ["cadence"] });
    },
  });

  const selectCls =
    "rounded-md border border-border bg-panel-2 px-2 py-1 text-xs text-text " +
    "outline-none focus:border-accent/60 transition-colors";
  const ready = text.trim().length > 0;

  return (
    <Panel className="p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-xs uppercase tracking-widest text-accent">{t("cm.title")}</h2>
        {seed?.source && (
          <span className="text-[10px] text-faint font-mono truncate">← {seed.source}</span>
        )}
      </div>

      <textarea
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        placeholder={t("cm.topicPlaceholder")}
        rows={2}
        className="rounded-md border border-border bg-panel-2 px-2.5 py-2 text-sm outline-none focus:border-accent/60 resize-y"
      />

      <div className="flex flex-wrap items-center gap-1.5">
        <select
          value={lang}
          onChange={(e) => setLang(e.target.value as "tr" | "en")}
          className={selectCls}
        >
          <option value="tr">TR</option>
          <option value="en">EN</option>
        </select>
        <select
          value={length}
          onChange={(e) => setLength(e.target.value as ComposeLength)}
          className={selectCls}
        >
          {LENGTHS.map((l) => (
            <option key={l} value={l}>
              {t(`co.fmt.${l}`)}
            </option>
          ))}
        </select>
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
        <button
          onClick={() => gen.mutate()}
          disabled={topic.trim().length < 3 || gen.isPending}
          className="ml-auto rounded-md border border-accent/50 px-3 py-1 text-xs text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
        >
          {gen.isPending ? t("co.generating") : t("co.generate")}
        </button>
      </div>

      {gen.error && <p className="text-hot text-[11px]">{(gen.error as Error).message}</p>}

      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setSaved(null);
        }}
        placeholder={t("cm.draftPlaceholder")}
        rows={8}
        className="rounded-md border border-border bg-panel-2 px-2.5 py-2 text-sm outline-none focus:border-accent/60 resize-y"
      />

      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] text-faint tabular-nums">
          {t("cp.chars", { n: text.length })}
        </span>
        {saved && <span className="text-[10px] text-good ml-auto">{t("cm.saved")}</span>}
      </div>

      <LiveScore text={text} />

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          onClick={() => openInX(text)}
          disabled={!ready}
          className="rounded border border-accent/60 bg-accent/10 px-2.5 py-1 text-[11px] text-accent hover:bg-accent/20 disabled:opacity-40 transition-colors"
        >
          {t("cp.openX")}
        </button>
        <button
          onClick={() => queue.mutate()}
          disabled={!ready || queue.isPending}
          className="rounded border border-border px-2.5 py-1 text-[11px] text-muted hover:text-accent hover:border-accent/50 disabled:opacity-40 transition-colors"
        >
          {t("qu.queue")}
        </button>
        <button
          onClick={() => save.mutate()}
          disabled={!ready || save.isPending || !!saved}
          className="rounded border border-border px-2.5 py-1 text-[11px] text-muted hover:text-text disabled:opacity-40 transition-colors"
        >
          {t("cm.saveDraft")}
        </button>
      </div>
      {queue.error && <p className="text-hot text-[11px]">{(queue.error as Error).message}</p>}
    </Panel>
  );
}
