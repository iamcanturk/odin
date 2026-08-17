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
import { EmptyState, ErrorState, LoadingState, Panel } from "@/components/ui";

function splitCsv(v: string): string[] {
  return v.split(",").map((s) => s.trim()).filter(Boolean);
}

export default function TopicsPage() {
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
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Topics</h1>
        <p className="text-sm text-muted mt-1">
          Define what ODIN should watch for you. Keywords boost relevance; excluded terms suppress
          matches.
        </p>
      </div>

      <Panel className="p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] items-end">
          <Field label="Name" value={name} onChange={setName} placeholder="AI" />
          <Field
            label="Keywords (comma-sep)"
            value={keywords}
            onChange={setKeywords}
            placeholder="llm, openai, agents"
          />
          <Field
            label="Exclude"
            value={exclude}
            onChange={setExclude}
            placeholder="crypto, nft"
          />
          <button
            onClick={() => create.mutate()}
            disabled={!name.trim() || create.isPending}
            className="h-9 rounded-md border border-accent/50 px-4 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {create.isPending ? "Adding…" : "Add topic"}
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
        <EmptyState label="No topics yet. Add your first above." />
      ) : (
        <div className="grid gap-2">
          {data.map((t) => (
            <Panel key={t.id} className="p-3 flex items-center gap-3">
              <button
                onClick={() => toggle.mutate(t)}
                className={`size-2.5 rounded-full shrink-0 ${t.enabled ? "bg-good" : "bg-border"}`}
                title={t.enabled ? "Enabled" : "Disabled"}
              />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-sm">{t.name}</span>
                <div className="text-xs text-muted mt-0.5 truncate">
                  {t.keywords.join(", ") || "—"}
                  {t.exclude_keywords.length > 0 && (
                    <span className="text-hot/70"> · not: {t.exclude_keywords.join(", ")}</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => remove.mutate(t.id)}
                className="text-muted hover:text-hot text-xs px-2 transition-colors"
              >
                remove
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
