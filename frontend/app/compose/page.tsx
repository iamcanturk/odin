"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import {
  compose,
  critiqueDraft,
  fetchStyleRefs,
  generateHooks,
  type ComposeAudience,
  type ComposeDraft,
  type ComposeLength,
  type Critique,
  type Hook,
  type TweetKind,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageHeader, Panel } from "@/components/ui";

const KINDS: TweetKind[] = ["", "breaking", "contrarian", "technical", "educational", "question"];
const LENGTHS: ComposeLength[] = ["short", "long", "story", "thread"];

function scoreColor(score: number): string {
  if (score >= 66) return "var(--hot)";
  if (score >= 33) return "var(--warn)";
  return "var(--accent)";
}

function CopyButton({ text }: { text: string }) {
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
          /* clipboard blocked */
        }
      }}
      className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text hover:border-accent/50 transition-colors"
    >
      {done ? t("cp.copied") : t("cp.copy")}
    </button>
  );
}

function DraftCard({ d }: { d: ComposeDraft }) {
  return (
    <Panel className="p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
          #{d.rank} · {d.angle}
        </span>
        <span
          className="font-mono text-sm tabular-nums"
          style={{ color: scoreColor(d.viral_score) }}
        >
          {d.viral_score.toFixed(0)}
        </span>
      </div>
      <p className="text-sm text-text mt-2 whitespace-pre-wrap">{d.text}</p>
      <div className="mt-3">
        <CopyButton text={d.text} />
      </div>
    </Panel>
  );
}

export default function ComposePage() {
  const { t, locale } = useI18n();
  const [topic, setTopic] = useState("");
  const [lang, setLang] = useState<"tr" | "en">(locale === "en" ? "en" : "tr");
  const [audience, setAudience] = useState<ComposeAudience>("technical");
  const [length, setLength] = useState<ComposeLength>("short");
  const [kind, setKind] = useState<TweetKind>("");
  const [styleHandle, setStyleHandle] = useState("");

  const { data: styles } = useQuery({ queryKey: ["compose", "styles"], queryFn: fetchStyleRefs });

  const gen = useMutation({
    mutationFn: () =>
      compose({ topic, language: lang, length, audience, kind, style_handle: styleHandle }),
  });

  const selectCls =
    "rounded-md border border-border bg-panel-2 px-2 py-1.5 text-sm text-text " +
    "focus:outline-none focus:border-accent/60 transition-colors";
  const drafts = gen.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("co.title")} subtitle={t("co.subtitle")} />

      <Panel className="p-5">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-widest text-muted">{t("co.topic")}</span>
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder={t("co.topicPlaceholder")}
            rows={3}
            className="rounded-md border border-border bg-panel-2 px-3 py-2 text-sm outline-none focus:border-accent/60 resize-y"
          />
        </label>

        <div className="flex flex-wrap items-end gap-3 mt-4">
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
            <span className="text-[10px] uppercase tracking-widest text-muted">
              {t("co.audience")}
            </span>
            <select
              value={audience}
              onChange={(e) => setAudience(e.target.value as ComposeAudience)}
              className={selectCls}
            >
              <option value="technical">{t("co.aud.technical")}</option>
              <option value="general">{t("co.aud.general")}</option>
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">
              {t("co.format")}
            </span>
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
            onClick={() => gen.mutate()}
            disabled={topic.trim().length < 3 || gen.isPending}
            className="rounded-md border border-accent/50 px-4 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {gen.isPending ? t("co.generating") : t("co.generate")}
          </button>
        </div>

        {gen.error && (
          <p className="text-hot text-xs mt-3">{(gen.error as Error).message}</p>
        )}
      </Panel>

      {drafts.length === 0 ? (
        <p className="text-sm text-muted">{t("co.empty")}</p>
      ) : (
        <div className="grid gap-3">
          {drafts.map((d, i) => (
            <DraftCard key={i} d={d} />
          ))}
        </div>
      )}

      <HooksPanel topic={topic} lang={lang} />
      <CritiquePanel lang={lang} />
    </div>
  );
}

/** The first line does nearly all the work, so explore it densely and score it. */
function HooksPanel({ topic, lang }: { topic: string; lang: "tr" | "en" }) {
  const { t } = useI18n();
  const gen = useMutation({ mutationFn: () => generateHooks({ topic, language: lang }) });
  const hooks: Hook[] = gen.data ?? [];

  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-xs uppercase tracking-widest text-muted">{t("co.hooks")}</h2>
          <p className="text-[11px] text-faint mt-1">{t("co.hooksHint")}</p>
        </div>
        <button
          onClick={() => gen.mutate()}
          disabled={topic.trim().length < 3 || gen.isPending}
          className="rounded-md border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
        >
          {gen.isPending ? t("co.generating") : t("co.hooks")}
        </button>
      </div>
      {gen.error && <p className="text-hot text-xs mt-2">{(gen.error as Error).message}</p>}
      {hooks.length > 0 && (
        <div className="flex flex-col gap-1.5 mt-3">
          {hooks.map((h) => (
            <div
              key={h.rank}
              className="flex items-start gap-3 rounded-md border border-border-soft bg-panel-2/50 px-3 py-2"
            >
              <span className="font-mono text-[10px] text-faint tabular-nums pt-0.5">
                {String(h.rank).padStart(2, "0")}
              </span>
              <p className="text-sm text-text flex-1">{h.text}</p>
              <span className="font-mono text-xs tabular-nums text-accent">
                {h.xsim_score.toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/** Ordered adversarial critique: value first, polish last. */
function CritiquePanel({ lang }: { lang: "tr" | "en" }) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const run = useMutation({ mutationFn: () => critiqueDraft({ text, language: lang }) });
  const r: Critique | undefined = run.data;

  return (
    <Panel className="p-5">
      <h2 className="text-xs uppercase tracking-widest text-muted">{t("co.critique")}</h2>
      <p className="text-[11px] text-faint mt-1">{t("co.critiqueHint")}</p>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        className="w-full mt-3 rounded-md border border-border bg-panel-2 px-3 py-2 text-sm outline-none focus:border-accent/60 resize-y"
      />
      <button
        onClick={() => run.mutate()}
        disabled={text.trim().length < 3 || run.isPending}
        className="mt-2 rounded-md border border-accent/50 px-3 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
      >
        {run.isPending ? t("co.generating") : t("co.critique")}
      </button>
      {run.error && <p className="text-hot text-xs mt-2">{(run.error as Error).message}</p>}

      {r && (
        <div className="mt-4 flex flex-col gap-2">
          {r.stopped_at && (
            <p className="text-xs text-warn">{t("co.stopped", { n: r.stopped_at })}</p>
          )}
          <div className="flex items-center gap-3 text-[11px] font-mono text-muted">
            <span>
              {t("co.before")} {r.xsim_before.toFixed(0)}
            </span>
            <span>→</span>
            <span className={r.xsim_after >= r.xsim_before ? "text-good" : "text-hot"}>
              {t("co.after")} {r.xsim_after.toFixed(0)}
            </span>
          </div>
          {r.passes.map((p) => (
            <div key={p.name} className="rounded-md border border-border-soft bg-panel-2/50 p-3">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase tracking-widest text-accent">
                  {p.name}
                </span>
                <span
                  className={`text-[10px] font-mono uppercase ${p.verdict === "pass" ? "text-good" : "text-warn"}`}
                >
                  {p.verdict}
                </span>
              </div>
              {p.rationale && <p className="text-[11px] text-muted mt-1">{p.rationale}</p>}
            </div>
          ))}
          <div className="rounded-md border border-good/40 bg-good/5 p-3">
            <p className="text-[10px] uppercase tracking-widest text-good mb-1">final</p>
            <p className="text-sm text-text whitespace-pre-wrap">{r.final}</p>
          </div>
        </div>
      )}
    </Panel>
  );
}
