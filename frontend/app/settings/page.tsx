"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { PageHeader } from "@/components/ui";
import { CadencePanel } from "@/components/CadencePanel";
import { SourcesPanel } from "@/components/SourcesPanel";
import { StyleMapPanel } from "@/components/StyleMapPanel";
import { SystemPanel } from "@/components/SystemPanel";
import { TopicsPanel } from "@/components/TopicsPanel";

type Tab = "sources" | "topics" | "goal" | "style" | "system";

const TABS: { key: Tab; labelKey: string }[] = [
  { key: "sources", labelKey: "nav.sources" },
  { key: "topics", labelKey: "nav.topics" },
  { key: "goal", labelKey: "st.goal" },
  { key: "style", labelKey: "st.style" },
  { key: "system", labelKey: "nav.system" },
];

/** Everything you configure, in one place — what comes in, what you care about,
 *  what you're aiming for, and what it costs. */
export default function SettingsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("sources");

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("st.title")} subtitle={t("st.subtitle")} />

      <div className="flex flex-wrap items-center gap-1.5">
        {TABS.map((x) => (
          <button
            key={x.key}
            onClick={() => setTab(x.key)}
            className={`rounded-full border px-3.5 py-1.5 text-xs transition-colors ${
              tab === x.key
                ? "border-accent/60 bg-accent/10 text-accent"
                : "border-border text-muted hover:text-text"
            }`}
          >
            {t(x.labelKey)}
          </button>
        ))}
      </div>

      {tab === "sources" && <SourcesPanel />}
      {tab === "topics" && <TopicsPanel />}
      {tab === "goal" && <CadencePanel editable />}
      {tab === "style" && <StyleMapPanel />}
      {tab === "system" && <SystemPanel />}
    </div>
  );
}
