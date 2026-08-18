"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  compose,
  type ComposeAudience,
  type ComposeDraft,
  type ComposeLength,
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

  const gen = useMutation({
    mutationFn: () => compose({ topic, language: lang, length, audience, kind }),
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
    </div>
  );
}
