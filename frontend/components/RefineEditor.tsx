"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { refineText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

/**
 * Edit a post by hand OR tell the AI what to change ("summarise this as if I read the
 * article"). The AI rewrites the draft in place; nothing is saved until Save is pressed.
 */
export function RefineEditor({
  value,
  onChange,
  onSave,
  onCancel,
  saving,
  eventId,
}: {
  value: string;
  onChange: (next: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving?: boolean;
  eventId?: string;
}) {
  const { t, locale } = useI18n();
  const [instruction, setInstruction] = useState("");

  const refine = useMutation({
    mutationFn: () =>
      refineText({
        text: value,
        instruction,
        language: locale === "en" ? "en" : "tr",
        event_id: eventId,
      }),
    onSuccess: (res) => {
      onChange(res.text);
      setInstruction("");
    },
  });

  return (
    <div className="mt-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={Math.min(14, Math.max(3, Math.ceil(value.length / 60)))}
        className="w-full rounded-md border border-border bg-panel-2 px-3 py-2 text-sm outline-none focus:border-accent/60 resize-y"
      />

      <div className="mt-2 rounded-md border border-border-soft bg-panel-2/50 p-2">
        <p className="text-[10px] uppercase tracking-widest text-muted mb-1">{t("cp.ai")}</p>
        <div className="flex gap-2">
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && instruction.trim() && !refine.isPending) {
                refine.mutate();
              }
            }}
            placeholder={t("cp.aiPlaceholder")}
            className="h-8 flex-1 min-w-0 rounded-md border border-border bg-panel px-3 text-xs outline-none focus:border-accent/60"
          />
          <button
            onClick={() => refine.mutate()}
            disabled={!instruction.trim() || refine.isPending}
            className="h-8 shrink-0 rounded-md border border-accent/50 px-3 text-xs text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {refine.isPending ? t("cp.aiRunning") : t("cp.aiRun")}
          </button>
        </div>
        <p className="text-[10px] text-faint mt-1">{t("cp.aiHint")}</p>
        {refine.error && (
          <p className="text-hot text-[11px] mt-1">{(refine.error as Error).message}</p>
        )}
      </div>

      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={onSave}
          disabled={saving || !value.trim()}
          className="rounded border border-good/50 px-2 py-1 text-[11px] text-good hover:bg-good/10 disabled:opacity-40 transition-colors"
        >
          {t("cp.save")}
        </button>
        <button
          onClick={onCancel}
          className="rounded border border-border px-2 py-1 text-[11px] text-muted hover:text-text transition-colors"
        >
          {t("cp.cancel")}
        </button>
      </div>
    </div>
  );
}
