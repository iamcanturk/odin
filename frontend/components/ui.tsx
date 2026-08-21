"use client";

import type { EventStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const STATUS_STYLES: Record<EventStatus, string> = {
  discovered: "text-muted border-border",
  verified: "text-accent border-accent/40",
  rising: "text-good border-good/40",
  trending: "text-hot border-hot/50",
  saturated: "text-warn border-warn/40",
  declining: "text-muted border-border",
  archived: "text-muted/60 border-border/60",
};

export function StatusBadge({ status }: { status: EventStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

function scoreColor(score: number): string {
  if (score >= 66) return "var(--hot)";
  if (score >= 33) return "var(--warn)";
  return "var(--accent)";
}

export function ScoreMeter({ label, score }: { label: string; score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex flex-col gap-1 min-w-24">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
        <span className="font-mono text-sm tabular-nums" style={{ color: scoreColor(pct) }}>
          {pct.toFixed(0)}
        </span>
      </div>
      <div className="h-1 rounded-full bg-panel-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: scoreColor(pct) }}
        />
      </div>
    </div>
  );
}

export function Panel({
  children,
  className = "",
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-[var(--radius)] border border-border bg-panel/70 backdrop-blur-sm shadow-[var(--shadow)] ${className}`}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted mt-1.5 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = "text",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "text" | "accent" | "good" | "warn" | "hot";
}) {
  const toneClass = {
    text: "text-text",
    accent: "text-accent",
    good: "text-good",
    warn: "text-warn",
    hot: "text-hot",
  }[tone];
  return (
    <Panel className="p-4">
      <p className="text-[11px] font-mono uppercase tracking-widest text-muted">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</p>
      {hint && <p className="text-[11px] text-faint mt-1">{hint}</p>}
    </Panel>
  );
}

export function LoadingState({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-20 rounded-xl border border-border bg-panel/50 animate-pulse" />
      ))}
      <p className="text-center text-xs text-muted font-mono">{label ?? t("state.scanning")}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n();
  return (
    <Panel className="p-8 text-center">
      <p className="text-hot font-mono text-sm">{t("state.signalLost")}</p>
      <p className="text-muted text-sm mt-1">{message}</p>
      <p className="text-muted/70 text-xs mt-3">
        {t("state.apiHint")} <code className="font-mono">{"/api/v1"}</code>?
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-md border border-border px-3 py-1.5 text-sm hover:border-accent/60 transition-colors"
        >
          {t("state.retry")}
        </button>
      )}
    </Panel>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <Panel className="p-10 text-center">
      <p className="text-muted text-sm">{label}</p>
    </Panel>
  );
}
