import type { ReactNode } from "react";
import { useI18n } from "../i18n";

interface Props {
  title: string;
  icon?: string;
  note?: string;
  wide?: boolean;
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  actions?: ReactNode;
  children?: ReactNode;
}

/** Every insight card: a title, a one-line source/meaning note, and honest loading/error states. */
export function Card({ title, icon, note, wide, loading, error, empty, actions, children }: Props) {
  const { t } = useI18n();
  return (
    <section className={`card${wide ? " wide" : ""}`} aria-busy={loading}>
      <header className="card-head">
        <h2>
          {icon && <span aria-hidden="true">{icon} </span>}
          {title}
        </h2>
        {actions}
      </header>
      {note && <p className="card-note">{note}</p>}
      {error && empty ? (
        <p className="card-error">⚠ {t("data_unavailable")}</p>
      ) : loading && empty ? (
        <div className="skeleton" />
      ) : (
        children
      )}
    </section>
  );
}
