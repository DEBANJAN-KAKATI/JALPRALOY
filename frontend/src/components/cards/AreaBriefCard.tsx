import { SPEECH_LANG, useI18n } from "../../i18n";
import type { AreaSummary, RainOutlook, RiverStation } from "../../lib/api";
import { fmtDay } from "../../lib/format";
import { COLOR_WORD_KEY, HORIZONS } from "../../lib/imd";
import { nearestStation, type Place } from "../../lib/place";
import { Card } from "../Card";

interface Props {
  place: Place;
  summary: AreaSummary | null;
  rain: RainOutlook | null;
  rivers: RiverStation[] | null;
}

/** A plain-language paragraph built from the numbers on screen — deterministic,
 * translatable and works offline (no LLM needed, nothing invented). */
export function AreaBriefCard({ place, summary, rain, rivers }: Props) {
  const { t, lang } = useI18n();
  const lines: string[] = [];

  if (summary) {
    const horizon = HORIZONS.find((h) => h.key === summary.horizon)?.label ?? summary.horizon;
    lines.push(t("brief_level", { area: place.name, level: t(COLOR_WORD_KEY[summary.flood_color]), horizon }));
  } else {
    lines.push(t("not_covered"));
  }
  if (rain) {
    const wettest = rain.days.reduce((a, b) => (b.rain_mm > a.rain_mm ? b : a));
    lines.push(t("brief_rain", { mm: Math.round(rain.total_mm), day: fmtDay(wettest.date, lang), max: Math.round(wettest.rain_mm) }));
  }
  if (summary?.most_affected.length) {
    lines.push(t("brief_most", { list: summary.most_affected.map((a) => a.name).join(", ") }));
  }
  const station = nearestStation(place.center, rivers);
  if (station) {
    lines.push(t("brief_river", { station: station.station, status: t(`river_${station.status}`), trend: t(station.trend) }));
  }
  if (summary?.source === "synthetic-demo") lines.push(t("brief_demo"));

  function speak() {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(lines.join(" "));
    u.lang = SPEECH_LANG[lang];
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }

  return (
    <Card
      title={t("brief_title")}
      icon="📝"
      wide
      actions={
        <button className="link" onClick={speak}>
          🔊 {t("read_aloud")}
        </button>
      }
    >
      <div className="brief">{lines.map((l) => <p key={l}>{l}</p>)}</div>
    </Card>
  );
}
