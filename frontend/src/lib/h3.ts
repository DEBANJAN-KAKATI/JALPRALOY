import { cellToLatLng, getResolution, isValidCell, latLngToCell } from "h3-js";

export const cellCenter = (h3: string): [number, number] => cellToLatLng(h3) as [number, number];
export const toCell = (lat: number, lon: number, res = 9) => latLngToCell(lat, lon, res);
export const isCell = (s: string) => isValidCell(s);
export const resolutionOf = (h3: string) => getResolution(h3);
