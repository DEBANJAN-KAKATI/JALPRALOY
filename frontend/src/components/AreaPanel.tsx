import { useI18n } from "../i18n";
import type { AreaSummary, CellDetail, Located, RainOutlook, RankedArea, RiverStation } from "../lib/api";
import { fmtNum } from "../lib/format";
import { COLOR_HEX, COLOR_WORD_KEY, HORIZONS, pct } from "../lib/imd";
import { nearestStation, type Place } from "../lib/place";

function Row({ a, i }: { a: RankedArea; i?: number }) {
  return (
    <li>
      <span className="dot" style={{ background: COLOR_HEX[a.color] }} />
      <span className="name">{i !== undefined ? `${i + 1}. ` : ""}{a.name}</span>
      <span className="val">{pct(a.p_flood)}</span>
    </li>
  );
}

function RiverLine({ station }: { station: RiverStation | null }) {
  const { t } = useI18n();
  if (!station) return null;
  return (
    <>
      <dt>🌊 {station.station}</dt>
      <dd>
        {fmtNum(station.discharge)} m³/s{" "}
        <span className="chip" style={{ background: COLOR_HEX[station.color] }}>
          {t(`river_${station.status}`)}
        </span>{" "}
        <small className="muted">{t(station.trend)}</small>
      </dd>
    </>
  );
}

interface Props {
  place: Place;
  summary: AreaSummary | null;
  cell: CellDetail | null;
  rain: RainOutlook | null;
  rivers: RiverStation[] | null;
  userLoc: Located | null;
}

export function AreaPanel({ place, summary, cell, rain, rivers, userLoc }: Props) {
  const { t } = useI18n();
  const station = nearestStation(place.center, rivers);

  if (!place.covered) {
    const worst = rain?.days.reduce((a, b) => (b.rain_mm > a.rain_mm ? b : a));
    return (
      <aside className="panel">
        <h2>{place.name}</h2>
        {place.district && place.district !== place.name && <p className="muted">{place.district}</p>}
        <p className="note-box">{t("not_covered")}</p>
        <dl className="kv">
          {rain && worst && (
            <>
              <dt>{t("rain_expected")}</dt>
              <dd>
                {Math.round(rain.total_mm)} mm / 7d{" "}
                <span className="chip" style={{ background: COLOR_HEX[worst.color] }}>
                  {t(COLOR_WORD_KEY[worst.color])}
                </span>
              </dd>
            </>
          )}
          <RiverLine station={station} />
        </dl>
        {userLoc && !userLoc.covered && (
          <p className="muted">{t("nearest_town", { town: userLoc.nearest_town, km: userLoc.nearest_town_km })}</p>
        )}
      </aside>
    );
  }

  if (!summary) return <aside className="panel">{t("loading")}</aside>;
  const horizonLabel = HORIZONS.find((h) => h.key === summary.horizon)?.label ?? summary.horizon;

  return (
    <aside className="panel">
      <h2>
        {place.name} · {horizonLabel}
      </h2>
      <dl className="kv">
        <dt>{t("rain_expected")}</dt>
        <dd>
          {Math.round(summary.rain_mm)} mm{" "}
          <span className="chip" style={{ background: COLOR_HEX[summary.rain_color] }}>
            {t(COLOR_WORD_KEY[summary.rain_color])}
          </span>
        </dd>
        <dt>{t("flood_risk")}</dt>
        <dd>
          <span className="chip" style={{ background: COLOR_HEX[summary.flood_color] }}>
            {t(COLOR_WORD_KEY[summary.flood_color])}
          </span>
        </dd>
        <RiverLine station={station} />
      </dl>

      <h3>{t("most_affected")}</h3>
      <ol className="ranked">{summary.most_affected.map((a, i) => <Row key={a.name} a={a} i={i} />)}</ol>
      <h3>{t("least_affected")}</h3>
      <ul className="ranked">{summary.least_affected.map((a) => <Row key={a.name} a={a} />)}</ul>
      {summary.nearest_shelter_km != null && (
        <p>
          {t("nearest_shelter")}: {summary.nearest_shelter_km.toFixed(1)} km
        </p>
      )}

      <section className="why">
        <h3>{t("why")}</h3>
        {cell ? (
          <>
            <p>
              <b>{cell.locality ?? cell.h3}</b> — {t("flood_risk")} {pct(cell.p_flood)}
            </p>
            <ul>{cell.drivers.map((d) => <li key={d.feature}>{d.text}</li>)}</ul>
          </>
        ) : (
          <p className="muted">{t("select_cell")}</p>
        )}
      </section>
    </aside>
  );
}
