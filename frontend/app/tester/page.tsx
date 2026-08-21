"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { analyzeText, type TesterResponse } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ErrorState, PageHeader, Panel, ScoreMeter } from "@/components/ui";

function Bar({ label, value, tone }: { label: string; value: number; tone?: string }) {
  const color =
    tone === "risk" ? "var(--hot)" : value >= 66 ? "var(--good)" : value >= 33 ? "var(--warn)" : "var(--accent)";
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted w-32 shrink-0">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-panel-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="font-mono text-xs tabular-nums w-9 text-right" style={{ color }}>
        {value.toFixed(0)}
      </span>
    </div>
  );
}

export default function TesterPage() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const analyze = useMutation<TesterResponse, Error, string>({ mutationFn: analyzeText });
  const r = analyze.data;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("ts.title")} subtitle={t("ts.subtitle")} />

      <Panel className="p-4">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          maxLength={2000}
          placeholder={t("ts.placeholder")}
          className="w-full resize-y rounded-md border border-border bg-panel-2 p-3 text-sm outline-none focus:border-accent/60"
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-[11px] text-muted font-mono">{text.length}/2000</span>
          <button
            onClick={() => analyze.mutate(text.trim())}
            disabled={!text.trim() || analyze.isPending}
            className="rounded-md border border-accent/50 px-4 py-1.5 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {analyze.isPending ? t("ts.analyzing") : t("ts.analyze")}
          </button>
        </div>
      </Panel>

      {analyze.error && <ErrorState message={analyze.error.message} />}

      {r && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Panel className="p-4">
              <ScoreMeter label={t("ts.viral")} score={r.viral_potential} />
            </Panel>
            <Panel className="p-4">
              <ScoreMeter label={t("ts.xsim")} score={r.x_simulation} />
            </Panel>
            <Panel className="p-4">
              <ScoreMeter label={t("ts.personalFit")} score={r.personal_fit} />
            </Panel>
            <Panel className="p-4">
              <ScoreMeter label={t("ts.trendFit")} score={r.trend_fit} />
            </Panel>
          </div>

          <Panel className="p-5">
            <h2 className="text-xs uppercase tracking-widest text-muted mb-3">{t("ts.breakdown")}</h2>
            <div className="flex flex-col gap-2">
              <Bar label={t("ts.novelty")} value={r.novelty} />
              <Bar label={t("ts.reply")} value={r.reply_potential} />
              <Bar label={t("ts.bookmark")} value={r.bookmark_potential} />
              <Bar label={t("ts.negative")} value={r.negative_risk} tone="risk" />
            </div>
          </Panel>

          <div className="grid gap-4 sm:grid-cols-2">
            <Panel className="p-5">
              <h2 className="text-xs uppercase tracking-widest text-good mb-2">{t("ts.why")}</h2>
              <ul className="text-sm text-text list-disc pl-5 space-y-1">
                {r.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </Panel>
            <Panel className="p-5">
              <h2 className="text-xs uppercase tracking-widest text-warn mb-2">{t("ts.watch")}</h2>
              <ul className="text-sm text-text list-disc pl-5 space-y-1">
                {r.weaknesses.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </Panel>
          </div>

          {r.repeats.length > 0 && (
            <Panel className="p-5 border-warn/40">
              <h2 className="text-xs uppercase tracking-widest text-warn mb-2">
                {t("ts.repeat")}
              </h2>
              <p className="text-[11px] text-muted mb-3">{t("ts.repeatHint")}</p>
              <ul className="space-y-2">
                {r.repeats.map((m) => (
                  <li key={m.post_id} className="text-sm text-text">
                    <span className="font-mono text-[11px] text-warn mr-2 tabular-nums">
                      %{Math.round(m.similarity * 100)}
                      {m.days_ago !== null && ` · ${m.days_ago}g`}
                    </span>
                    {m.text}
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <p className="text-[11px] text-muted font-mono">⚠ {r.disclaimer}</p>
        </>
      )}
    </div>
  );
}
