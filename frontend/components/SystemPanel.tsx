"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSystemStatus } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ErrorState, LoadingState, Panel } from "@/components/ui";

function money(v: number): string {
  return `$${v.toFixed(v < 1 ? 4 : 2)}`;
}

function num(v: number): string {
  return v.toLocaleString();
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-4">
      <p className="text-[11px] font-mono uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </Panel>
  );
}

export function SystemPanel() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["system"],
    queryFn: fetchSystemStatus,
    refetchInterval: 60_000,
  });

  return (
    <div className="flex flex-col gap-6">


      {isLoading && <LoadingState />}
      {error && <ErrorState message={(error as Error).message} onRetry={() => refetch()} />}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t("sys.costTotal")} value={money(data.cost_total_usd)} />
            <Stat label={t("sys.cost30d")} value={money(data.cost_30d_usd)} />
            <Stat label={t("sys.calls")} value={num(data.calls_total)} />
            <Stat label={t("sys.tokens")} value={num(data.tokens_total)} />
          </div>

          <Panel className="p-0 overflow-hidden">
            <h2 className="px-4 py-3 text-sm font-semibold border-b border-border">
              {t("sys.byPurpose")}
            </h2>
            {data.by_purpose.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted">—</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] font-mono uppercase tracking-widest text-muted">
                    <th className="px-4 py-2 font-normal">{t("sys.purpose")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.calls")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.tokensCol")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.costCol")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_purpose.map((b) => (
                    <tr key={b.purpose} className="border-t border-border/60">
                      <td className="px-4 py-2 font-mono">{b.purpose}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{num(b.calls)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {num(b.prompt_tokens + b.completion_tokens)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(b.cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel className="p-0 overflow-hidden">
            <h2 className="px-4 py-3 text-sm font-semibold border-b border-border">
              {t("sys.runs")}
            </h2>
            {data.recent_runs.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted">{t("sys.noRuns")}</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] font-mono uppercase tracking-widest text-muted">
                    <th className="px-4 py-2 font-normal">{t("sys.runKind")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.runItems")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.runEvents")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.runErrors")}</th>
                    <th className="px-4 py-2 font-normal text-right">{t("sys.runTime")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_runs.map((r, i) => (
                    <tr key={i} className="border-t border-border/60 align-top">
                      <td className="px-4 py-2 font-mono">{r.kind}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{num(r.items_created)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{num(r.events_created)}</td>
                      <td
                        className={`px-4 py-2 text-right tabular-nums ${r.errors.length ? "text-hot" : ""}`}
                        title={r.errors.join("\n")}
                      >
                        {num(r.errors.length)}
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-xs text-muted whitespace-nowrap">
                        {new Date(r.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}
