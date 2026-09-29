import { useEffect, useState } from "react";
import { LANG_LABEL, useI18n, type Lang } from "../i18n";
import type { Suggestion } from "../lib/api";
import { minutesAgo } from "../lib/format";
import { SearchBox } from "./SearchBox";

export type Page = "map" | "news" | "saved" | "admin";

interface Props {
  page: Page;
  onNavigate: (page: Page) => void;
  newsBadge: number;
  near: [number, number];
  onSelect: (s: Suggestion) => void;
  onLocate: () => void;
  onRefresh: () => void;
  updatedAt: Date;
  isSyncing?: boolean;
}

export function Header({ page, onNavigate, newsBadge, near, onSelect, onLocate, onRefresh, updatedAt, isSyncing }: Props) {
  const { t, lang, setLang } = useI18n();
  const [, tick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 30_000); // keep "updated x min ago" honest
    return () => clearInterval(id);
  }, []);

  const m = minutesAgo(updatedAt) ?? 0;
  const tabs: { key: Page; label: string; badge?: number }[] = [
    { key: "map", label: `🗺 ${t("tab_map")}` },
    { key: "news", label: `📰 ${t("tab_news")}`, badge: newsBadge },
    { key: "saved", label: `★ ${t("saved")}` },
    { key: "admin", label: `⚙ ${t("admin") || "Admin"}` },
  ];

  return (
    <header className="header">
      <button className="brand" onClick={() => onNavigate("map")} aria-label="JalProloy home">
        <img src="/emblem.png" alt="" width={40} height={40} />
        <span className="wordmark">
          <span className="wm-name">
            <span className="wm-jal">Jal</span>
            <span className="wm-proloy">Proloy</span>
          </span>
          <span className="wm-tag">{t("tagline")}</span>
        </span>
      </button>

      <nav className="tabs" aria-label="Sections">
        {tabs.map((tab) => (
          <button key={tab.key} className={page === tab.key ? "active" : ""} onClick={() => onNavigate(tab.key)} aria-current={page === tab.key}>
            {tab.label}
            {!!tab.badge && <span className="badge-dot">{tab.badge > 9 ? "9+" : tab.badge}</span>}
          </button>
        ))}
      </nav>

      <SearchBox near={near} onLocate={onLocate} onSelect={(s) => { onSelect(s); onNavigate("map"); }} />

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: "0.78rem", fontWeight: 700, color: "var(--green)", background: "#e8f5e9", padding: "4px 8px", borderRadius: 8 }}>
          <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: "var(--green)", animation: "pulse 1.5s infinite" }}></span>
          <span>LIVE</span>
        </div>

        <button
          className="tool"
          onClick={onRefresh}
          disabled={isSyncing}
          title={m < 1 ? t("just_now") : t("updated_ago", { m })}
          style={{ display: "flex", alignItems: "center", gap: 5 }}
        >
          <span style={{ display: "inline-block", animation: isSyncing ? "spin 0.8s linear infinite" : "none" }}>⟳</span>
          <span className="tool-label">{isSyncing ? "Syncing..." : t("refresh")}</span>
          {!isSyncing && m >= 1 && <small className="muted"> {m}′</small>}
        </button>
      </div>
      <div className="langs" role="group" aria-label="Language">
        {(Object.keys(LANG_LABEL) as Lang[]).map((l) => (
          <button key={l} className={l === lang ? "active" : ""} onClick={() => setLang(l)} aria-pressed={l === lang}>
            {LANG_LABEL[l]}
          </button>
        ))}
      </div>
    </header>
  );
}
