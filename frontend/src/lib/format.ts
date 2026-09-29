import type { Lang } from "../i18n";

const LOCALE: Record<Lang, string> = { en: "en-IN", as: "as-IN", bn: "bn-IN", hi: "hi-IN" };

/** Indian digit grouping: 13,739 / 1,23,456 */
export const fmtNum = (n: number) => Math.round(n).toLocaleString("en-IN");

export function fmtDay(iso: string, lang: Lang): string {
  const d = new Date(`${iso}T00:00:00+05:30`);
  try {
    return new Intl.DateTimeFormat(LOCALE[lang], { weekday: "short", day: "numeric", timeZone: "Asia/Kolkata" }).format(d);
  } catch {
    return iso.slice(5);
  }
}

export function fmtDate(iso: string, lang: Lang): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00+05:30` : iso);
  try {
    return new Intl.DateTimeFormat(LOCALE[lang], { day: "numeric", month: "short", timeZone: "Asia/Kolkata" }).format(d);
  } catch {
    return iso.slice(0, 10);
  }
}

export function minutesAgo(iso: string | Date | null): number | null {
  if (!iso) return null;
  const t = typeof iso === "string" ? Date.parse(iso) : iso.getTime();
  return Math.max(0, Math.round((Date.now() - t) / 60000));
}

/** "12 min ago" / "3 h ago" / "2 d ago" through i18n templates */
export function ago(iso: string | null, t: (k: string, v?: Record<string, string | number>) => string): string {
  const m = minutesAgo(iso);
  if (m == null) return "";
  if (m < 60) return t("minutes_ago", { m });
  if (m < 48 * 60) return t("hours_ago", { h: Math.round(m / 60) });
  return t("days_ago", { d: Math.round(m / 1440) });
}
