import type { Horizon, WarningColor } from "./api";

// IMD's four colours and nothing else. Always paired with a word (colour-blind users).
export const COLOR_HEX: Record<WarningColor, string> = {
  green: "#2e7d32",
  yellow: "#f9d423",
  orange: "#f57c00",
  red: "#d32f2f",
};

export const COLOR_RGB: Record<WarningColor, [number, number, number]> = {
  green: [46, 125, 50],
  yellow: [249, 212, 35],
  orange: [245, 124, 0],
  red: [211, 47, 47],
};

export const COLOR_RANK: Record<WarningColor, number> = { green: 0, yellow: 1, orange: 2, red: 3 };

// i18n keys for Low / Watch / Prepare / Act
export const COLOR_WORD_KEY: Record<WarningColor, string> = {
  green: "level_green",
  yellow: "level_yellow",
  orange: "level_orange",
  red: "level_red",
};

export const HORIZONS: { key: Horizon; label: string }[] = [
  { key: "now", label: "Now" },
  { key: "6h", label: "+6h" },
  { key: "24h", label: "+24h" },
  { key: "72h", label: "+3 days" },
  { key: "120h", label: "+5 days" },
];

export const pct = (p: number) => `${Math.round(p * 100)}%`;
