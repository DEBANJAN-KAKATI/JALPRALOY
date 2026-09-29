import type { RiverStation } from "./api";

/** What the dashboard is looking at. `area` is set only where the hyperlocal flood
 * model has hexagons (pilot: Guwahati); elsewhere we show live rain + river data. */
export interface Place {
  name: string;
  center: [number, number]; // (lat, lon)
  covered: boolean;
  area: string | null;
  district?: string | null;
  /** dropped by search / my location: show a pin and select the hexagon under it */
  pinned?: boolean;
}

export const DEFAULT_PLACE: Place = {
  name: "Guwahati",
  center: [26.1445, 91.7362],
  covered: true,
  area: "Guwahati",
  district: "Kamrup Metropolitan",
};

export const ASSAM_VIEW = { latitude: 26.35, longitude: 92.7, zoom: 6.3 };

export function distanceKm(a: [number, number], b: [number, number]): number {
  const p = Math.PI / 180;
  const h =
    Math.sin(((b[0] - a[0]) * p) / 2) ** 2 +
    Math.cos(a[0] * p) * Math.cos(b[0] * p) * Math.sin(((b[1] - a[1]) * p) / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

export function nearestStation(center: [number, number], rivers: RiverStation[] | null): RiverStation | null {
  if (!rivers?.length) return null;
  return rivers.reduce((best, r) =>
    distanceKm(center, [r.lat, r.lon]) < distanceKm(center, [best.lat, best.lon]) ? r : best,
  );
}
