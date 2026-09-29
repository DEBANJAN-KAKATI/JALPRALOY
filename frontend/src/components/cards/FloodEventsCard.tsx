import { useI18n } from "../../i18n";
import type { FloodEvent } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import { COLOR_HEX } from "../../lib/imd";
import type { ApiState } from "../../lib/useApi";
import { Card } from "../Card";

function EventRow({ e }: { e: FloodEvent }) {
  const { t, lang } = useI18n();
  return (
    <li>
      <span className="chip" style={{ background: COLOR_HEX[e.color] }}>
        {e.alert_level}
      </span>
      <span className="ev-body">
        <b>{e.name}</b>
        <small>
          {e.from_date && fmtDate(e.from_date, lang)} – {e.is_current ? t("ongoing") : e.to_date && fmtDate(e.to_date, lang)}
        </small>
      </span>
      {e.url && (
        <a href={e.url} target="_blank" rel="noreferrer">
          {t("report")} ↗
        </a>
      )}
    </li>
  );
}

export function FloodEventsCard({ state }: { state: ApiState<{ region: FloodEvent[]; india_other: FloodEvent[] }> }) {
  const { t } = useI18n();
  const d = state.data;
  return (
    <Card title={t("events_title")} icon="🛰" note={t("events_note")} loading={state.loading} error={state.error} empty={!d}>
      {d && (
        <>
          {d.region.length ? (
            <ul className="event-list">{d.region.map((e) => <EventRow key={e.id} e={e} />)}</ul>
          ) : (
            <p className="muted">{t("no_events")}</p>
          )}
          {d.india_other.length > 0 && (
            <details>
              <summary>
                {t("elsewhere_india")} ({d.india_other.length})
              </summary>
              <ul className="event-list">{d.india_other.map((e) => <EventRow key={e.id} e={e} />)}</ul>
            </details>
          )}
        </>
      )}
    </Card>
  );
}
