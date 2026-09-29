import { useI18n } from "../../i18n";
import type { RiverStation } from "../../lib/api";
import { fmtDate, fmtNum } from "../../lib/format";
import { COLOR_HEX } from "../../lib/imd";
import type { ApiState } from "../../lib/useApi";
import { Card } from "../Card";
import { Sparkline } from "../Sparkline";

const TREND_ICON = { rising: "▲", falling: "▼", steady: "▬" } as const;

export function RiverWatchCard({ state, highlight }: { state: ApiState<RiverStation[]>; highlight?: string | null }) {
  const { t, lang } = useI18n();
  const rows = state.data ?? [];
  return (
    <Card title={t("river_title")} icon="🌊" note={t("river_note")} wide loading={state.loading} error={state.error} empty={!rows.length}>
      <div className="flow-dir">
        ↓ {t("upstream")} → {t("downstream")}
      </div>
      <ol className="river-list">
        {[...rows].sort((a, b) => a.order - b.order).map((r) => (
          <li key={r.station} className={r.station === highlight ? "hl" : ""}>
            <span className="river-name">{r.station}</span>
            <span className="river-q">
              <b>{fmtNum(r.discharge)}</b> m³/s
              {r.season_median != null && (
                <small>
                  {t("season_median")}: {fmtNum(r.season_median)}
                </small>
              )}
            </span>
            <span className="chip" style={{ background: COLOR_HEX[r.color] }}>
              {t(`river_${r.status}`)}
            </span>
            <span className={`trend trend-${r.trend}`}>
              {TREND_ICON[r.trend]} {t(r.trend)}
            </span>
            <Sparkline series={r.series} color={COLOR_HEX[r.color]} />
            <span className="river-peak">
              {r.rise_expected ? (
                <>
                  {t("peak_on", { date: fmtDate(r.peak_date, lang) })}: {fmtNum(r.peak_discharge)}{" "}
                  <span className="chip small" style={{ background: COLOR_HEX[r.peak_color] }}>
                    {t(`river_${r.peak_status}`)}
                  </span>
                </>
              ) : (
                <span className="muted">{t("no_rise")}</span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
