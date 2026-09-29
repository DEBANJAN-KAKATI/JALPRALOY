import { useI18n } from "../../i18n";
import type { RainOutlook } from "../../lib/api";
import { fmtDay } from "../../lib/format";
import { COLOR_HEX, COLOR_WORD_KEY } from "../../lib/imd";
import type { ApiState } from "../../lib/useApi";
import { Card } from "../Card";

const HEAVY = 64.5;

export function RainOutlookCard({ place, state }: { place: string; state: ApiState<RainOutlook> }) {
  const { t, lang } = useI18n();
  const d = state.data;
  // Always keep the IMD "heavy" line on the chart so small bars read as small.
  const scale = Math.max(HEAVY * 1.25, d?.max_mm ?? 0);
  return (
    <Card
      title={`${t("rain_outlook_title")} · ${place}`}
      icon="🌧"
      note={t("rain_outlook_note")}
      loading={state.loading}
      error={state.error}
      empty={!d}
    >
      {d && (
        <div className="bars" role="list">
          <div className="heavy-line" style={{ bottom: `${(HEAVY / scale) * 100}%` }}>
            <span>{t("heavy_line")}</span>
          </div>
          {d.days.map((day) => (
            <div
              key={day.date}
              className="bar-col"
              role="listitem"
              aria-label={`${day.date}: ${day.rain_mm} mm, ${t(COLOR_WORD_KEY[day.color])}`}
            >
              <span className="bar-val">{day.rain_mm < 1 ? "<1" : Math.round(day.rain_mm)}</span>
              <div className="bar-track">
                <div
                  className="bar"
                  style={{ height: `${Math.max(2, (day.rain_mm / scale) * 100)}%`, background: day.rain_mm < 2.5 ? "var(--river-soft)" : COLOR_HEX[day.color] }}
                />
              </div>
              <span className="bar-day">{fmtDay(day.date, lang)}</span>
              {day.probability != null && (
                <span className="bar-prob" title={t("chance")}>
                  {day.probability}%
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
