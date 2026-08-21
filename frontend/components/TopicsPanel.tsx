"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTopic,
  deleteTopic,
  fetchTopics,
  updateTopic,
  type Topic,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function splitCsv(v: string): string[] {
  return v.split(",").map((s) => s.trim()).filter(Boolean);
}

export function TopicsPanel() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["topics"],
    queryFn: fetchTopics,
  });

  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const [exclude, setExclude] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["topics"] });

  const create = useMutation({
    mutationFn: () =>
      createTopic({
        name: name.trim(),
        keywords: splitCsv(keywords),
        exclude_keywords: splitCsv(exclude),
      }),
    onSuccess: () => {
      setName("");
      setKeywords("");
      setExclude("");
      invalidate();
    },
  });

  const toggle = useMutation({
    mutationFn: (t: Topic) => updateTopic(t.id, { enabled: !t.enabled }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => deleteTopic(id),
    onSuccess: invalidate,
  });

  return (
    <div className="flex flex-col gap-6">

      <Panel className="p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] items-end">
          <Field label={t("tp.name")} value={name} onChange={setName} placeholder="AI" />
          <Field
            label={t("tp.keywords")}
            value={keywords}
            onChange={setKeywords}
            placeholder="llm, openai, agents"
          />
          <Field
            label={t("tp.exclude")}
            value={exclude}
            onChange={setExclude}
            placeholder="crypto, nft"
          />
          <button
            onClick={() => create.mutate()}
            disabled={!name.trim() || create.isPending}
            className="h-9 rounded-md border border-accent/50 px-4 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {create.isPending ? t("tp.adding") : t("tp.add")}
          </button>
        </div>
        {create.error && (
          <p className="text-hot text-xs mt-2">{(create.error as Error).message}</p>
        )}
      </Panel>

      {isLoading ? (
        <LoadingState label="Loading topics…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState label={t("tp.empty")} />
      ) : (
        <div className="grid gap-2">
          {data.map((topic) => (
            <Panel key={topic.id} className="p-3 flex items-center gap-3">
              <button
                onClick={() => toggle.mutate(topic)}
                className={`size-2.5 rounded-full shrink-0 ${topic.enabled ? "bg-good" : "bg-border"}`}
                title={topic.enabled ? "on" : "off"}
              />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-sm">{topic.name}</span>
                <div className="text-xs text-muted mt-0.5 truncate">
                  {topic.keywords.join(", ") || "—"}
                  {topic.exclude_keywords.length > 0 && (
                    <span className="text-hot/70">
                      {" "}
                      · {t("tp.not")} {topic.exclude_keywords.join(", ")}
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => remove.mutate(topic.id)}
                className="text-muted hover:text-hot text-xs px-2 transition-colors"
              >
                {t("tp.remove")}
              </button>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-widest text-muted">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 rounded-md border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60"
      />
    </label>
  );
}
