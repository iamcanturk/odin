"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchNotifications, markNotificationRead, type Notification } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

const SEVERITY: Record<string, string> = {
  high: "text-hot border-hot/50",
  warning: "text-warn border-warn/40",
  info: "text-accent border-accent/40",
};

function Row({ n }: { n: Notification }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const read = useMutation({
    mutationFn: () => markNotificationRead(n.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["notifications", "count"] });
    },
  });
  return (
    <Panel className={`p-4 ${n.read ? "opacity-60" : ""}`}>
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest ${SEVERITY[n.severity] ?? SEVERITY.info}`}
        >
          {n.type.replace(/_/g, " ")}
        </span>
        {!n.read && (
          <button
            onClick={() => read.mutate()}
            className="ml-auto text-[11px] text-muted hover:text-text transition-colors"
          >
            {t("nt.markRead")}
          </button>
        )}
      </div>
      <p className="text-sm text-text mt-2">{n.title}</p>
      {n.body && <p className="text-xs text-muted mt-1">{n.body}</p>}
    </Panel>
  );
}

export default function NotificationsPage() {
  const { t } = useI18n();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => fetchNotifications(),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("nt.title")}</h1>
        <p className="text-sm text-muted mt-1">{t("nt.subtitle")}</p>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState label={t("nt.empty")} />
      ) : (
        <div className="grid gap-2">
          {data.map((n) => (
            <Row key={n.id} n={n} />
          ))}
        </div>
      )}
    </div>
  );
}
