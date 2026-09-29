import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useI18n } from "../i18n";
import { api, type Suggestion } from "../lib/api";

const RECENT_KEY = "recentSearches";
const POPULAR: Suggestion[] = [
  { name: "Guwahati", subtitle: "Kamrup Metropolitan", kind: "Flood map", center: [26.1445, 91.7362], covered: true, area: "Guwahati", source: "jalproloy" },
  { name: "Dibrugarh", subtitle: "Assam", kind: "Town", center: [27.472, 94.912], covered: false, area: null, source: "jalproloy" },
  { name: "Silchar", subtitle: "Cachar, Assam", kind: "Town", center: [24.833, 92.779], covered: false, area: null, source: "jalproloy" },
];
const ICON: Record<string, string> = {
  "Flood map": "⬡", Town: "🏙", City: "🏙", Village: "🏡", Locality: "🏘", District: "🗺", State: "🗺", Road: "🛣",
  Hospital: "🏥", Clinic: "🏥", Pharmacy: "💊", School: "🏫", College: "🎓", University: "🎓", River: "🌊",
  Stream: "🌊", Island: "🏝", Station: "🚉", Airport: "✈", "Bus station": "🚌", Point: "📍",
};

function loadRecent(): Suggestion[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") as Suggestion[];
  } catch {
    return [];
  }
}

function saveRecent(s: Suggestion) {
  try {
    const next = [s, ...loadRecent().filter((r) => r.name !== s.name || r.subtitle !== s.subtitle)].slice(0, 5);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable */
  }
}

/** Bold the part of the name that matches what was typed. */
function Highlight({ text, q }: { text: string; q: string }) {
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <b>{text.slice(i, i + q.length)}</b>
      {text.slice(i + q.length)}
    </>
  );
}

interface Props {
  near: [number, number];
  onSelect: (s: Suggestion) => void;
  onLocate: () => void;
}

/** Google-Maps-style search: suggestions while typing, ↑/↓/Enter/Esc, recent places,
 * "your location" when empty. Results come from /api/areas/suggest (flood-map areas,
 * Assam towns, then any OpenStreetMap place in NE India). */
export function SearchBox({ near, onSelect, onLocate }: Props) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const typed = q.trim();

  // Debounced, cancellable lookups: only the latest keystroke's request survives.
  useEffect(() => {
    if (!typed) {
      setRows([]);
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    const id = setTimeout(() => {
      api
        .suggest(typed, near, ctrl.signal)
        .then((r) => {
          setRows(r);
          setActive(0);
          setLoading(false);
        })
        .catch((e: Error) => e.name !== "AbortError" && setLoading(false));
    }, 220);
    return () => {
      clearTimeout(id);
      ctrl.abort();
    };
  }, [typed, near[0], near[1]]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const close = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const recent = loadRecent();
  const list = typed ? rows : recent.length ? recent : POPULAR;

  function choose(s: Suggestion) {
    saveRecent(s);
    setQ(s.name);
    setOpen(false);
    onSelect(s);
    (document.activeElement as HTMLElement | null)?.blur();
  }

  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, list.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (list[active]) choose(list[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className={`searchbox${open ? " open" : ""}`} ref={box} role="combobox" aria-expanded={open} aria-haspopup="listbox">
      <span className="sb-icon" aria-hidden="true">🔍</span>
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        placeholder={t("search_placeholder")}
        aria-label={t("search_placeholder")}
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
      />
      {loading && <span className="sb-spin" aria-label={t("searching")} />}
      {q && (
        <button className="sb-clear" onClick={() => { setQ(""); setOpen(true); }} aria-label={t("clear")}>
          ✕
        </button>
      )}
      {open && (
        <ul className="sb-list" role="listbox">
          {!typed && (
            <li>
              <button className="sb-row" onClick={() => { setOpen(false); onLocate(); }}>
                <span className="sb-kind">◎</span>
                <span className="sb-text"><span className="sb-name">{t("my_location")}</span></span>
              </button>
            </li>
          )}
          {!typed && <li className="sb-head">{recent.length ? t("recent_searches") : t("popular_places")}</li>}
          {list.map((s, i) => (
            <li key={`${s.name}-${s.center.join(",")}`} role="option" aria-selected={i === active}>
              <button className={`sb-row${i === active ? " active" : ""}`} onMouseEnter={() => setActive(i)} onClick={() => choose(s)}>
                <span className="sb-kind" title={s.kind}>{ICON[s.kind] ?? "📍"}</span>
                <span className="sb-text">
                  <span className="sb-name"><Highlight text={s.name} q={typed} /></span>
                  <span className="sb-sub">{[s.kind, s.subtitle].filter(Boolean).join(" · ")}</span>
                </span>
                {s.covered && <span className="sb-badge">⬡ {t("flood_map_badge")}</span>}
              </button>
            </li>
          ))}
          {typed && !loading && !rows.length && <li className="sb-empty">{t("no_results")}</li>}
          {typed && loading && !rows.length && <li className="sb-empty">{t("searching")}</li>}
        </ul>
      )}
    </div>
  );
}
