import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import type { Horizon } from "../lib/api";
import { HORIZONS } from "../lib/imd";

// One slider controls everything: map, banner, panel.
export function Timeline({ value, onChange }: { value: Horizon; onChange: (h: Horizon) => void }) {
  const { t } = useI18n();
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const i = HORIZONS.findIndex((h) => h.key === value);
      onChange(HORIZONS[(i + 1) % HORIZONS.length].key);
    }, 1500);
    return () => clearInterval(id);
  }, [playing, value, onChange]);

  return (
    <nav className="timeline" aria-label="Forecast time">
      {HORIZONS.map((h, i) => (
        <span key={h.key} className="step">
          {i > 0 && <span className="line" />}
          <button className={h.key === value ? "active" : ""} onClick={() => onChange(h.key)} aria-pressed={h.key === value}>
            {h.label}
          </button>
        </span>
      ))}
      <button className="play" onClick={() => setPlaying((p) => !p)}>
        {playing ? `⏸ ${t("pause")}` : `▶ ${t("play")}`}
      </button>
    </nav>
  );
}
