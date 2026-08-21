"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchEvaluation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-4">
      <div className="text-[10px] uppercase tracking-widest text-muted">{label}</div>
      <div className="font-mono text-xl tabular-nums mt-1">{value}</div>
    </Panel>
  );
}

export function LearningPanels() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["evaluation"],
    queryFn: fetchEvaluation,
  });

  return (
    <div className="flex flex-col gap-5">
      <Panel className="p-5 border-accent/30">
        <h2 className="text-sm font-semibold text-accent">{t("ln.how")}</h2>
        <p className="text-sm text-muted mt-2 leading-relaxed">{t("ln.howBody")}</p>
        <p className="text-[11px] text-faint mt-2">{t("ln.needData")}</p>
      </Panel>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.evaluated === 0 ? (
        <EmptyState label={t("ln.empty")} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label={t("ln.evaluated")} value={String(data.evaluated)} />
            <Stat label="MAE" value={data.mae.toFixed(1)} />
            <Stat label="RMSE" value={data.rmse.toFixed(1)} />
            <Stat
              label="Precision@3"
              value={data.precision_at_3 == null ? "—" : `${(data.precision_at_3 * 100).toFixed(0)}%`}
            />
          </div>

          {!data.reliable && (
            <Panel className="p-4 border-warn/40">
              <p className="text-sm text-warn">
                {t("ln.unreliable", { n: data.evaluated, m: data.min_for_reliable })}
              </p>
            </Panel>
          )}

          {data.by_metric.length > 0 && (
            <Panel className="p-5">
              <h2 className="text-xs uppercase tracking-widest text-muted mb-3">
                {t("ln.byMetric")}
              </h2>
              <div className="grid gap-2">
                {data.by_metric.map((m) => (
                  <div key={m.metric} className="flex items-center gap-3 text-sm">
                    <span className="font-mono text-xs w-24 text-muted">{m.metric}</span>
                    <span className="tabular-nums">MAE {m.mae.toFixed(1)}</span>
                    <span
                      className={`ml-auto text-[11px] font-mono ${m.bias === "none" ? "text-good" : "text-warn"}`}
                    >
                      {t(`ln.bias.${m.bias}`)}
                    </span>
                    <span className="text-[10px] text-faint font-mono">n={m.evaluated}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          <Panel className="p-5">
            <h2 className="text-xs uppercase tracking-widest text-muted">{t("ln.calibration")}</h2>
            <div className="flex flex-wrap items-baseline gap-4 mt-2">
              <span
                className={`text-2xl font-semibold tabular-nums ${
                  data.bias === "none" ? "text-good" : "text-warn"
                }`}
              >
                {data.calibration.toFixed(2)}x
              </span>
              <span className="text-sm text-muted">{t(`ln.bias.${data.bias}`)}</span>
              {data.impressions_per_like != null && (
                <span className="text-[11px] text-faint font-mono ml-auto">
                  {t("ln.impPerLike", { n: data.impressions_per_like.toFixed(1) })}
                </span>
              )}
            </div>
            <p className="text-[11px] text-faint mt-2">{t("ln.calibrationHint")}</p>
            {data.calibration_clamped && (
              <p className="text-[11px] text-warn mt-1">{t("ln.clamped")}</p>
            )}
          </Panel>

          <Panel className="p-5">
            <h2 className="text-xs uppercase tracking-widest text-muted mb-3">{t("ln.perPost")}</h2>
            <div className="grid gap-2">
              {data.items.map((it) => (
                <div key={it.post_id} className="flex items-center gap-3 text-sm">
                  <span className="flex-1 truncate text-muted">{it.text}</span>
                  <span className="font-mono text-xs tabular-nums text-muted">
                    {t("ln.pred")} {it.predicted_likes}
                  </span>
                  <span className="font-mono text-xs tabular-nums">
                    {t("ln.act")} {it.actual_likes}
                  </span>
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
