import { useState, type FormEvent } from "react";
import { useI18n } from "../../i18n";
import { api, type WarningColor } from "../../lib/api";
import { COLOR_HEX, COLOR_WORD_KEY } from "../../lib/imd";
import type { Place } from "../../lib/place";
import { Card } from "../Card";

const LEVELS: WarningColor[] = ["yellow", "orange", "red"];

export function AlertSignupCard({ place }: { place: Place }) {
  const { t } = useI18n();
  const [level, setLevel] = useState<WarningColor>("orange");
  const [channel, setChannel] = useState<"telegram" | "push">("telegram");
  const [contact, setContact] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.savePlace({
        name: place.name, lat: place.center[0], lon: place.center[1],
        channels: [channel], contact: channel === "telegram" ? contact || null : null, min_color: level,
      });
      setMsg(t("subscribed", { level: t(COLOR_WORD_KEY[level]) }));
    } catch {
      setMsg(t("data_unavailable"));
    }
  }

  return (
    <Card title={t("alerts_title")} icon="🔔">
      <form className="signup" onSubmit={submit}>
        <label>
          {t("place_name")}
          <input value={place.name} readOnly />
        </label>
        <fieldset>
          <legend>{t("alert_from")}</legend>
          {LEVELS.map((c) => (
            <label key={c} className={`level-pick${level === c ? " on" : ""}`} style={{ borderColor: COLOR_HEX[c] }}>
              <input type="radio" name="lvl" checked={level === c} onChange={() => setLevel(c)} />
              {t(COLOR_WORD_KEY[c])}
            </label>
          ))}
        </fieldset>
        <label>
          {t("channel")}
          <select value={channel} onChange={(e) => setChannel(e.target.value as "telegram" | "push")}>
            <option value="telegram">Telegram</option>
            <option value="push">Browser push</option>
          </select>
        </label>
        {channel === "telegram" && (
          <label>
            {t("telegram_id")}
            <input value={contact} onChange={(e) => setContact(e.target.value)} placeholder="123456789" inputMode="numeric" />
          </label>
        )}
        <button type="submit" className="primary">
          {t("subscribe")}
        </button>
        {msg && <p className="muted" role="status">{msg}</p>}
      </form>
    </Card>
  );
}
