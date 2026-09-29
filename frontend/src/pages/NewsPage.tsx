import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import { api, type NewsFeed, type NewsScope } from "../lib/api";
import { ago } from "../lib/format";
import { useApi } from "../lib/useApi";

type KeywordFilter = "all" | "flood" | "disaster";
const SEEN_KEY = "newsSeenAt";

export function newsLang(lang: string): string {
  return lang === "hi" || lang === "bn" ? lang : "en"; // Google News has no Assamese edition
}

/** Timestamp of the newest item the user has already seen (drives the tab badge). */
export function newsSeenAt(): number {
  try {
    return Number(localStorage.getItem(SEEN_KEY) ?? 0);
  } catch {
    return 0;
  }
}

function markSeen(feed: NewsFeed | null) {
  const newest = Math.max(0, ...(feed?.items ?? []).map((i) => (i.published ? Date.parse(i.published) : 0)));
  try {
    if (newest) localStorage.setItem(SEEN_KEY, String(newest));
  } catch {
    /* ignore */
  }
}

/** Flood & disaster headlines. Fetched every time the tab opens and every 5 minutes
 * while open (the server shares one cached copy between all visitors for 10 min). */
export function NewsPage({ refreshKey }: { refreshKey: number }) {
  const { t, lang } = useI18n();
  const [scope, setScope] = useState<NewsScope>("assam");
  const [kw, setKw] = useState<KeywordFilter>("all");
  const [poll, setPoll] = useState(0);
  const [seenBefore] = useState(newsSeenAt); // snapshot: highlight what was new when the tab opened
  const feed = useApi(() => api.news(scope, newsLang(lang)), [scope, lang, refreshKey, poll]);

  useEffect(() => {
    const id = setInterval(() => setPoll((p) => p + 1), 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => markSeen(feed.data), [feed.data]);

  const items = (feed.data?.items ?? []).filter((i) => kw === "all" || i.keywords.includes(kw));

  return (
    <section className="page news">
      <header className="news-head">
        <div>
          <h1>📰 {t("news_title")}</h1>
          <p className="muted">{t("news_note")}</p>
          {lang === "as" && <p className="muted small">{t("news_lang_note")}</p>}
        </div>
        <div className="news-meta">
          {feed.data && (
            <small className="muted">
              {t("news_via", { provider: feed.data.provider === "gdelt" ? "GDELT" : "Google News" })} · {ago(feed.data.fetched_at, t)} ·{" "}
              {t("news_auto")}
            </small>
          )}
          <button className="tool light" onClick={() => setPoll((p) => p + 1)} disabled={feed.loading}>
            ⟳ {t("refresh")}
          </button>
        </div>
      </header>

      <div className="news-filters">
        <div className="seg" role="group">
          {(["assam", "india"] as NewsScope[]).map((s) => (
            <button key={s} className={scope === s ? "on" : ""} onClick={() => setScope(s)}>
              {t(`news_scope_${s}`)}
            </button>
          ))}
        </div>
        <div className="seg" role="group">
          {(["all", "flood", "disaster"] as KeywordFilter[]).map((k) => (
            <button key={k} className={kw === k ? "on" : ""} onClick={() => setKw(k)}>
              {k === "all" ? t("news_all") : t(`kw_${k}`)}
            </button>
          ))}
        </div>
      </div>

      {feed.error && !feed.data && <p className="card-error">⚠ {t("data_unavailable")}</p>}
      {feed.loading && !feed.data && <div className="skeleton tall" />}
      {feed.data && !items.length && <p className="muted">{t("news_empty")}</p>}

      <ul className="news-list">
        {items.map((n) => {
          const fresh = n.published && Date.parse(n.published) > seenBefore && seenBefore > 0;
          return (
            <li key={n.id}>
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="news-item">
                <span className="news-tags">
                  {n.keywords.map((k) => (
                    <span key={k} className={`tag tag-${k}`}>{t(`kw_${k}`)}</span>
                  ))}
                  {n.local && <span className="tag tag-local">📍 {t("local_badge")}</span>}
                  {fresh && <span className="tag tag-new">{t("new_tag")}</span>}
                </span>
                <span className="news-title">{n.title}</span>
                <span className="news-foot">
                  <b>{n.source}</b> · {ago(n.published, t)}
                  <span className="news-go">{t("read_more")} ↗</span>
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
