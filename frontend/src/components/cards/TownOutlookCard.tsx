import { useI18n } from "../../i18n";
import type { TownOutlook } from "../../lib/api";
import { fmtDay } from "../../lib/format";
import { COLOR_HEX } from "../../lib/imd";
import type { ApiState } from "../../lib/useApi";
import { Card } from "../Card";

export function TownOutlookCard({ state, onSelect }: { state: ApiState<TownOutlook[]>; onSelect: (t: TownOutlook) => void }) {
  const { t, lang } = useI18n();
  const rows = (state.data ?? []).slice(0, 10);
  const max = Math.max(64.5, ...rows.map((r) => r.max_mm));
  return (
    <Card title={t("towns_title")} icon="🗺" note={t("towns_note")} loading={state.loading} error={state.error} empty={!rows.length}>
      <ol className="town-list">
        {rows.map((r) => (
          <li key={r.name}>
            <button onClick={() => onSelect(r)}>
              <span className="town-name">{r.name}</span>
              <span className="town-bar">
                <i style={{ width: `${(r.max_mm / max) * 100}%`, background: r.max_mm < 2.5 ? "var(--river-soft)" : COLOR_HEX[r.color] }} />
              </span>
              <span className="town-val">
                {Math.round(r.max_mm)} mm <small>{fmtDay(r.max_date, lang)}</small>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </Card>
  );
}
