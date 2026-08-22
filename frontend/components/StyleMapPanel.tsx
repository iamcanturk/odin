"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchStyleMap, fetchStyleRefs, fetchTopics, saveStyleMap } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

// Categories worth routing. Sourced from the ones events actually carry.
const CATEGORIES = ["cve", "security", "ai", "technology", "devtools", "trends"];

/** "Write CVE posts the way @x does" — set once, applied to every future draft. */
export function StyleMapPanel() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string> | null>(null);

  const { data } = useQuery({ queryKey: ["style-map"], queryFn: fetchStyleMap });
  const { data: refs } = useQuery({ queryKey: ["compose", "styles"], queryFn: fetchStyleRefs });
  const { data: topics } = useQuery({ queryKey: ["topics"], queryFn: fetchTopics });

  const save = useMutation({
    mutationFn: (m: Record<string, string>) => saveStyleMap(m),
    onSuccess: () => {
      setDraft(null);
      qc.invalidateQueries({ queryKey: ["style-map"] });
    },
  });

  if (!data) return null;
  const current = draft ?? data.mapping;

  // Offer the built-in categories plus any the user's own topics introduce.
  const categories = Array.from(
    new Set([...CATEGORIES, ...(topics ?? []).map((x) => x.name.toLowerCase())]),
  );

  return (
    <Panel className="p-5">
      <h2 className="text-sm font-semibold text-text">{t("sm.title")}</h2>
      <p className="text-[11px] text-muted mt-1.5 leading-relaxed">{t("sm.hint")}</p>

      {!refs?.length ? (
        <p className="text-[11px] text-warn mt-4">{t("sm.noRefs")}</p>
      ) : (
        <>
          <div className="grid gap-2 mt-4 sm:grid-cols-2">
            {categories.map((c) => (
              <label key={c} className="flex items-center gap-2">
                <span className="text-xs text-muted w-24 shrink-0 truncate">{c}</span>
                <select
                  value={current[c] ?? ""}
                  onChange={(e) =>
                    setDraft({ ...current, [c]: e.target.value })
                  }
                  className="h-8 flex-1 min-w-0 rounded-md border border-border bg-panel-2 px-2 text-xs text-text outline-none focus:border-accent/60"
                >
                  <option value="">{t("sm.own")}</option>
                  {refs.map((r) => (
                    <option key={r.handle} value={r.handle}>
                      @{r.handle} ({r.samples})
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={() => save.mutate(current)}
              disabled={save.isPending || draft === null}
              className="rounded-md border border-accent/60 px-3 py-1.5 text-xs text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
            >
              {t("sm.save")}
            </button>
            {save.isSuccess && draft === null && (
              <span className="text-[11px] text-good">{t("sm.saved")}</span>
            )}
          </div>
        </>
      )}
    </Panel>
  );
}
