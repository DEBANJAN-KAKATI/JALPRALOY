# 10 · Frontend (answer in five seconds, one topic at a time)

Stack: React + TypeScript + Vite + MapLibre GL + deck.gl (`H3ClusterLayer`, `H3HexagonLayer`, `ScatterplotLayer`,
`PathLayer`, `TextLayer`) + h3-js. Offline-capable PWA. Brand: the JalProloy logo (`public/logo.png`, `emblem.png`, icons).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [logo] JalProloy   [🗺 Map | 📰 News (3) | ★ Saved]  ( 🔍 Search places… )  ⟳  EN|অস|বাং|हि │ Header
├──────────────────────────────────────────────────────────────────────────────┤
│ PREPARE · Guwahati: …                                              🔊 Read   │ AlertBanner
├──────────────────────────────────────────────┬───────────────────────────────┤
│ MapView: risk ZONES (merged hexes) → cells   │ AreaPanel: rain, flood level, │  ← first screen
│   when zoomed in · pin · ◎ locate · layers   │ river, most/least, Why?       │    (the answer)
├──────────────────────────────────────────────┴───────────────────────────────┤
│ Timeline [Now]──[+6h]──[+24h]──[+3 days]──[+5 days]   ▶ Play                  │
╞══════════════════════════════════════════════════════════════════════════════╡
│ ‹ [Overview] [Rain] [River] [Events] [Alerts & help] [How it works] ›        │  ← SlideDeck
│   one slide at a time (swipe / ← → / dots)                        ● ○ ○ 1/6  │    (the details)
├──────────────────────────────────────────────────────────────────────────────┤
│ Footer: disclaimer · sources/credits · helplines                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

## De-cluttering decisions

| Problem | Fix | Code |
|---------|-----|------|
| Long wall of cards | **SlideDeck**: six slides (Overview, Rain, River, Events, Alerts & help, How it works), only one rendered; pill tabs, arrows, dots, swipe, ←/→ keys; remembers the last slide | `components/SlideDeck.tsx`, `pages/Dashboard.tsx` |
| The "big hexagon" looked congested and artificial | 1) demo footprint follows Guwahati's south bank (river excluded) instead of a hex-shaped disk; 2) **low-risk cells hidden by default** (toggle "Show low-risk areas"); 3) at city zoom, same-colour cells merge into **smooth zones** with one outline (`H3ClusterLayer`), so no mesh of cell borders; 4) individual cells only from zoom 12.5, borderless, **opacity ∝ probability**; 5) one thin pilot-boundary line | `components/MapView.tsx`, `backend/app/services/demo.py` |
| Hexagons looked muddy / 3-D | `H3HexagonLayer` defaults to 1000 m extruded prisms, so it is set to `extruded: false` | `MapView.tsx` |
| Search only knew a few names | **Google-Maps-style SearchBox**: suggestions while typing (220 ms debounce, cancelled requests), bold match, type icons, context line, "flood map" badge, ↑/↓/Enter/Esc, recent searches, "My location" row; results from flood-map areas, Assam towns and any OSM place in NE India (Photon); picking a place drops a pin, flies there and opens its hexagon's "Why?" | `components/SearchBox.tsx`, `backend/app/api/areas.py` (`/suggest`), `services/geocode.py` |
| News was missing | **News tab**: Google News headlines containing flood/disaster (en/hi/bn; figurative uses like "floods the market" filtered out), Assam vs All-India, Flood/Disaster filter, "New" tags, unread badge on the tab, opens the publisher page; refetched on every open and every 5 min | `pages/NewsPage.tsx`, `backend/app/services/news.py` |

## Ideas taken from Flood Spaces (floodspaces.vercel.app), and what we changed

| Flood Spaces has | JalProloy does it as | Why ours is better for IMD/ASDMA |
|------------------|----------------------|----------------------------------|
| Long single scroll: map, then many cards | **Answer-first hero** (banner + map + ranking fit one screen); cards below | A farmer or official gets the answer without scrolling |
| River watch in m³/s with NORMAL labels | **Brahmaputra main stem, upstream → downstream**, status vs the **same season over 10 years**, 30-day sparkline plus a 7-day forecast peak | Their points snap to tributaries (e.g. "Brahmaputra – Jamalpur 93 m³/s"); we snap to the highest-flow GloFAS cell, and "high" is relative to the season, not a fixed number |
| Risk score = hand-tuned formula (Rain₁ₕ×6 + …), "Confidence 100 %" | Calibrated probabilities from trained models; **"How is this calculated?"** card with exact definitions | Transparent and honest; no fake confidence |
| Live global GDACS list | **Regional GDACS filter** (NE India + neighbours), "elsewhere in India" collapsed | Relevant to Assam, not a world feed |
| Data-pipeline status (LIVE/FALLBACK) | **Data sources card**: live / cached / offline / **demo** per source, with "updated x min ago" | Stale or synthetic data can never pass as live |
| Monthly outlook ranking of districts | **Assam towns ranked by wettest day in 5 days**, tap to open | Uses IMD rain colours; directly navigable |
| 7-day weather cards | **7-day rain bars with the IMD "heavy" line** and chance of rain | Shows at a glance how far from "heavy" each day is |
| Telegram alert (threshold, radius) | **Get alerts** with IMD levels (Watch/Prepare/Act) and a channel | Same language as the warnings |
| AI chat brief (OpenRouter LLM) | **Area brief** generated from the on-screen numbers, translated, read aloud | Deterministic, works offline, can't invent facts (an LLM can be added later, grounded on the same data) |
| Search + My Location + Refresh | Same, plus auto-refresh every 5 min, H3/"lat,lon" search, town search, "outside pilot" handling | |
| Bangladesh emergency numbers | **Assam/India numbers** (112, 1070, 1077, 108, 101, 100) + ASDMA, IMD, CWC, SACHET links | |
| English only; basemap needs an API key | **4 languages**; keyless Carto basemap; offline PWA | |
| Splash screen | None: skeleton loading instead | Every second counts during a flood |

## Principles (and where they live in code)

| Principle | Implementation |
|-----------|----------------|
| Only IMD's four colours, always with a word | `lib/imd.ts`, legend in `MapView` (river layer uses Normal/Above normal/High/Very high) |
| Answer first | `Dashboard` hero section; cards only below the fold |
| One timeline controls everything | `Dashboard` owns `horizon` (covered areas only) |
| Local languages + read aloud | `i18n/` with `t(key, vars)` templates; `speechSynthesis` in the banner and brief |
| Offline PWA | `public/sw.js`: app shell cache-first, `/api` network-first with cached fallback |
| Explainability | "Why?" panel (`drivers`), "How is this calculated?" card |
| Never mislead | demo notice; source labels on every card; the Data sources card |
| Pilot honesty | outside Guwahati: "hyperlocal map not available here yet", Rain layer by default, live rain and river data still shown |

## Code map

```
src/
  App.tsx                 place, refresh (5 min), my-location, toast
  pages/Dashboard.tsx     fetches everything via useApi(); hero + insight cards
  components/
    Header, AlertBanner, MapView, AreaPanel, Timeline, Footer, Card, Sparkline
    cards/  AreaBrief, DataStatus, RainOutlook, RiverWatch, TownOutlook,
            FloodEvents, AlertSignup, Emergency, HowItWorks
  lib/    api.ts (types + client), useApi.ts, place.ts, imd.ts, format.ts, h3.ts
  i18n/   en/as/bn/hi.json + index.tsx
```

Backend endpoints used by the cards: `/api/outlook/rain`, `/api/outlook/towns`, `/api/rivers`, `/api/events`,
`/api/status`, `/api/areas/locate` (see `backend/app/api/live.py`, `areas.py`).

## TODO list (frontend owner)

1. **Rain-motion arrows:** deck.gl `IconLayer` fed by an `/api/nowcast/arrows` endpoint (Engine 1 `motion_arrows`).
2. **River layer:** switch from GloFAS discharge to CWC levels with warning/danger lines once available.
3. **Saved places page:** list/delete; push permission + VAPID subscription.
4. **Admin page:** engine run status, alert queue (approve/cancel), CAP preview, hindcast selector.
5. **Hindcast mode:** load a stored hindcast run and animate T−72 h → T+0 (your demo).
6. **Accessibility:** keyboard access to hexagons (list fallback), contrast check, font scaling.
7. **Performance:** at state scale (100k hexes) request cells by viewport or aggregate to res 7 when zoomed out; code-split maplibre/deck.gl.
8. **Translations reviewed** by native Assamese, Bengali and Hindi speakers (card notes, emergency labels and the How-it-works text are still English).

## Commands
```bash
npm run dev       # http://localhost:5173, proxies /api to :8000
npm run build     # type-check + production bundle (service worker active only here)
npm run preview   # serve the production build to test offline mode
```

Deploy: Vercel/Netlify (static) with the API on Render/Railway. The app calls relative `/api/...` URLs, so add a
rewrite rule on the static host that forwards `/api/*` to the backend (or serve both behind one reverse proxy).
