import { useI18n } from "../../i18n";
import type { SourceStatus } from "../../lib/api";
import { minutesAgo } from "../../lib/format";
import type { ApiState } from "../../lib/useApi";
import { Card } from "../Card";

// Never let stale or synthetic data pass as live: every source shows its state.
export function DataStatusCard({ state }: { state: ApiState<SourceStatus[]> }) {
  const { t } = useI18n();
  const rows = state.data ?? [];
  return (
    <Card title={t("status_title")} icon="📡" loading={state.loading} error={state.error} empty={!rows.length}>
      <ul className="status-list">
        {rows.map((s) => {
          const m = minutesAgo(s.updated);
          return (
            <li key={s.id} title={s.detail}>
              <span className={`st st-${s.status}`}>{t(`st_${s.status}`)}</span>
              <span className="st-name">{s.name}</span>
              <small className="muted">
                {m == null ? s.detail : m < 1 ? t("just_now") : t("updated_ago", { m })}
              </small>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
