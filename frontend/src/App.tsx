import { useCallback, useEffect, useRef, useState } from "react";
import { Footer } from "./components/Footer";
import { Header, type Page } from "./components/Header";
import { useI18n } from "./i18n";
import { api, type Located, type Suggestion } from "./lib/api";
import { DEFAULT_PLACE, type Place } from "./lib/place";
import { Admin } from "./pages/Admin";
import { Dashboard } from "./pages/Dashboard";
import { NewsPage, newsLang, newsSeenAt } from "./pages/NewsPage";
import { SavedPlaces } from "./pages/SavedPlaces";

const AUTO_REFRESH_MS = 5 * 60 * 1000;
const STALE_ON_RETURN_MS = 60 * 1000;

export default function App() {
  const { t, lang } = useI18n();
  const [page, setPage] = useState<Page>(() => (location.hash === "#admin" ? "admin" : location.hash === "#news" ? "news" : "map"));
  const [place, setPlace] = useState<Place>(DEFAULT_PLACE);
  const [refreshKey, setRefreshKey] = useState(0);
  const [updatedAt, setUpdatedAt] = useState(new Date());
  const [userLoc, setUserLoc] = useState<Located | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [newsBadge, setNewsBadge] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const lastRefresh = useRef(Date.now());

  const refresh = useCallback(async () => {
    setIsSyncing(true);
    try {
      await api.sync();
    } catch (e) {
      console.warn("Live sync check:", e);
    } finally {
      setIsSyncing(false);
      lastRefresh.current = Date.now();
      setRefreshKey((k) => k + 1);
      setUpdatedAt(new Date());
    }
  }, []);

  // Initial sync on mount: ensures anyone opening the platform receives updated live data immediately
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Sync: every 5 min, and immediately when the user comes back to the tab/app or
  // the network returns — so whoever opens the app sees current data.
  useEffect(() => {
    const id = setInterval(refresh, AUTO_REFRESH_MS);
    const wake = () => {
      if (document.visibilityState === "visible" && Date.now() - lastRefresh.current > STALE_ON_RETURN_MS) refresh();
    };
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", refresh);
    window.addEventListener("focus", wake);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", refresh);
      window.removeEventListener("focus", wake);
    };
  }, [refresh]);

  // News badge: count headlines newer than the last one the user saw.
  useEffect(() => {
    if (page === "news") return setNewsBadge(0);
    let cancelled = false;
    api
      .news("assam", newsLang(lang))
      .then((f) => {
        const seen = newsSeenAt();
        if (!cancelled) setNewsBadge(f.items.filter((i) => i.published && Date.parse(i.published) > seen).length);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [page, lang, refreshKey]);

  useEffect(() => {
    history.replaceState(null, "", page === "map" ? location.pathname : `#${page}`);
  }, [page]);

  function selectSuggestion(s: Suggestion) {
    setPlace({ name: s.name, center: s.center, covered: s.covered, area: s.area, district: s.subtitle || null, pinned: s.kind !== "Flood map" });
  }

  function locate() {
    if (!("geolocation" in navigator)) return setToast(t("location_denied"));
    setToast(t("locating"));
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const loc = await api.locate(pos.coords.latitude, pos.coords.longitude);
          setUserLoc(loc);
          setPlace({ name: t("you_are_here"), center: [loc.lat, loc.lon], covered: loc.covered, area: loc.area, pinned: true });
          setPage("map");
          setToast(null);
        } catch {
          setToast(t("data_unavailable"));
        }
      },
      () => setToast(t("location_denied")),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    );
  }

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(id);
  }, [toast]);

  return (
    <div className="app">
      <Header
        page={page}
        onNavigate={setPage}
        newsBadge={newsBadge}
        near={place.center}
        onSelect={selectSuggestion}
        onLocate={locate}
        onRefresh={refresh}
        updatedAt={updatedAt}
        isSyncing={isSyncing}
      />
      {page === "map" && <Dashboard place={place} onPlace={setPlace} refreshKey={refreshKey} userLoc={userLoc} onLocate={locate} />}
      {page === "news" && <NewsPage refreshKey={refreshKey} />}
      {page === "saved" && <SavedPlaces onSelectPlace={setPlace} onNavigate={setPage} />}
      {page === "admin" && <Admin />}
      <Footer />
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
