"use client";

import { useState } from "react";
import { login, setToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Panel } from "@/components/ui";

export default function LoginPage() {
  const { t } = useI18n();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { token } = await login(username.trim(), password);
      setToken(token);
      // Full reload so the token is picked up app-wide.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/";
    } catch {
      setError(t("login.invalid"));
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[70vh] grid place-items-center">
      <Panel className="p-8 w-full max-w-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="size-6 rounded-full border border-accent/60 grid place-items-center">
            <div className="size-1.5 rounded-full bg-accent" />
          </div>
          <span className="font-mono text-sm tracking-[0.3em]">ODIN</span>
        </div>
        <h1 className="text-lg font-semibold mb-1">{t("login.title")}</h1>
        <p className="text-sm text-muted mb-5">{t("login.subtitle")}</p>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">
              {t("login.username")}
            </span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="h-9 rounded-md border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted">
              {t("login.password")}
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="h-9 rounded-md border border-border bg-panel-2 px-3 text-sm outline-none focus:border-accent/60"
            />
          </label>
          {error && <p className="text-hot text-xs">{error}</p>}
          <button
            type="submit"
            disabled={!password || busy}
            className="mt-2 h-9 rounded-md border border-accent/50 text-sm text-accent hover:bg-accent/10 disabled:opacity-40 transition-colors"
          >
            {busy ? t("login.submitting") : t("login.submit")}
          </button>
        </form>
      </Panel>
    </div>
  );
}
