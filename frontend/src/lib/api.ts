export type Horizon = "now" | "6h" | "24h" | "72h" | "120h";
export type WarningColor = "green" | "yellow" | "orange" | "red";
export type Source = "model" | "synthetic-demo" | "live-hydrometeo";

export interface CellRisk {
  h3: string;
  p_flood: number;
  color: WarningColor;
  rain_mm: number;
  rain_color: WarningColor;
}

export interface Driver {
  feature: string;
  text: string;
  contribution: number;
}

export interface CellDetail extends CellRisk {
  horizon: Horizon;
  locality: string | null;
  drivers: Driver[];
  source: Source;
}

export interface RankedArea {
  name: string;
  p_flood: number;
  color: WarningColor;
  expected_affected_pop: number | null;
}

export interface AreaSummary {
  name: string;
  horizon: Horizon;
  center: [number, number];
  rain_mm: number;
  rain_color: WarningColor;
  flood_color: WarningColor;
  headline: string | null;
  most_affected: RankedArea[];
  least_affected: RankedArea[];
  nearest_shelter_km: number | null;
  generated_at: string;
  valid_from: string;
  valid_to: string;
  sources: string[];
  source: Source;
}

export interface AreaCells {
  name: string;
  horizon: Horizon;
  source: Source;
  cells: CellRisk[];
}

export interface AreaHit {
  name: string;
  level: "locality" | "circle" | "district" | "state" | "town" | "point";
  center: [number, number];
  covered: boolean;
  area: string | null;
  district: string | null;
}

export interface Located {
  lat: number;
  lon: number;
  h3: string;
  covered: boolean;
  area: string | null;
  nearest_town: string;
  nearest_town_km: number;
}

export interface RainDay {
  date: string;
  rain_mm: number;
  probability: number | null;
  color: WarningColor;
}

export interface RainOutlook {
  lat: number;
  lon: number;
  days: RainDay[];
  total_mm: number;
  max_mm: number;
  source: string;
}

export interface TownOutlook {
  name: string;
  district: string;
  lat: number;
  lon: number;
  total_mm: number;
  max_mm: number;
  max_date: string;
  color: WarningColor;
}

export interface RiverStation {
  station: string;
  order: number;
  lat: number;
  lon: number;
  date: string;
  discharge: number;
  change_24h: number | null;
  trend: "rising" | "falling" | "steady";
  percentile: number;
  color: WarningColor;
  status: string;
  season_median: number | null;
  rise_expected: boolean;
  peak_date: string;
  peak_discharge: number;
  peak_color: WarningColor;
  peak_status: string;
  series: { date: string; q: number; forecast: boolean }[];
}

export interface FloodEvent {
  id: string;
  name: string;
  country: string;
  alert_level: string;
  color: WarningColor;
  from_date: string | null;
  to_date: string | null;
  is_current: boolean;
  lat: number | null;
  lon: number | null;
  url: string | null;
}

export interface SourceStatus {
  id: string;
  name: string;
  status: "idle" | "live" | "cached" | "offline" | "demo";
  updated: string | null;
  detail: string;
}

export interface SavedPlaceIn {
  name: string;
  lat: number;
  lon: number;
  channels: ("push" | "sms" | "telegram")[];
  contact: string | null;
  min_color: WarningColor;
}

export interface Suggestion {
  name: string;
  subtitle: string;
  kind: string;
  center: [number, number];
  covered: boolean;
  area: string | null;
  source: "jalproloy" | "osm";
}

export type NewsScope = "assam" | "india";

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  published: string | null;
  keywords: ("flood" | "disaster")[];
  local: boolean;
}

export interface NewsFeed {
  items: NewsItem[];
  provider: "google-news" | "gdelt";
  fetched_at: string;
  scope: NewsScope;
  lang: string;
}

export interface Alert {
  id: string;
  area: string;
  color: WarningColor;
  headline: string;
  description: string;
  issued: string;
  onset: string;
  expires: string;
  probability: number;
  source: Source;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function get<T>(path: string, params: Record<string, string> = {}, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/api${path}${qs ? `?${qs}` : ""}`, { signal });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  areaSummary: (name: string, horizon: Horizon, mode: string = "live") => get<AreaSummary>("/risk/area", { name, horizon, mode }),
  areaCells: (name: string, horizon: Horizon, mode: string = "live") => get<AreaCells>("/risk/area/cells", { name, horizon, mode }),
  cell: (h3: string, horizon: Horizon, mode: string = "live") => get<CellDetail>(`/risk/cell/${h3}`, { horizon, mode }),
  alerts: (area?: string) => get<Alert[]>("/alerts", area ? { area } : {}),
  search: (q: string) => get<AreaHit[]>("/areas/search", { q }),
  locate: (lat: number, lon: number) => get<Located>("/areas/locate", { lat: String(lat), lon: String(lon) }),
  rainOutlook: (lat: number, lon: number) =>
    get<RainOutlook>("/outlook/rain", { lat: lat.toFixed(2), lon: lon.toFixed(2) }),
  towns: () => get<TownOutlook[]>("/outlook/towns"),
  rivers: () => get<RiverStation[]>("/rivers"),
  events: () => get<{ region: FloodEvent[]; india_other: FloodEvent[] }>("/events"),
  status: () => get<SourceStatus[]>("/status"),
  suggest: (q: string, near: [number, number], signal?: AbortSignal) =>
    get<Suggestion[]>("/areas/suggest", { q, lat: near[0].toFixed(2), lon: near[1].toFixed(2) }, signal),
  news: (scope: NewsScope, lang: string) => get<NewsFeed>("/news", { scope, lang }),
  savePlace: (p: SavedPlaceIn) => post<SavedPlaceIn & { id: string; h3: string }>("/saved-places", p),
  sync: () => post<{ synced: boolean; timestamp: string; sources: SourceStatus[] }>("/sync", {}),
};
