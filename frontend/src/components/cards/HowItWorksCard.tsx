import { useI18n } from "../../i18n";
import { COLOR_HEX } from "../../lib/imd";
import { Card } from "../Card";

const ENGINES = [
  { n: 1, icon: "🌧", name: "Rain nowcast · 0–6 h", how: "Tracks rain cells in satellite/radar images and moves them forward (optical flow, pySTEPS).", state: "planned" },
  { n: 2, icon: "📈", name: "Heavy-rain forecast · 1–5 days", how: "Corrects weather-model (GFS/ECMWF) bias over NE India with LightGBM, trained on IMD observed rainfall.", state: "planned" },
  { n: 3, icon: "⬡", name: "Inundation per hexagon", how: "Terrain (height above drainage, slope, paving) + rain + river state → P(flood), trained on Sentinel-1 radar flood maps.", state: "demo" },
  { n: 4, icon: "🌊", name: "River propagation & impact", how: "Upstream Brahmaputra gauges → downstream levels; people affected = P(flood) × population.", state: "partial" },
];

// Transparency: say exactly what each number is and where it comes from.
export function HowItWorksCard() {
  const { t } = useI18n();
  return (
    <Card title={t("how_title")} icon="🧭" wide>
      <div className="engines">
        {ENGINES.map((e) => (
          <div key={e.n} className="engine">
            <b>
              {e.icon} Engine {e.n}: {e.name}
            </b>
            <p>{e.how}</p>
            <span className={`st st-${e.state === "demo" ? "demo" : e.state === "partial" ? "cached" : "idle"}`}>{e.state}</span>
          </div>
        ))}
      </div>
      <details>
        <summary>What each number on this page means</summary>
        <ul className="defs">
          <li><b>Flood risk %</b> — probability that a hexagon floods in the chosen window (Engine 3). Demo values until the model is trained.</li>
          <li><b>Rain mm</b> — forecast 24-hour rainfall. IMD categories: heavy ≥ 64.5 mm, very heavy ≥ 115.6 mm, extremely heavy ≥ 204.5 mm.</li>
          <li><b>River status</b> — today's modelled Brahmaputra flow ranked against the same ±15 days in the last 10 years: Normal &lt; 75th percentile, Above normal &lt; 90th, High &lt; 97th, Very high above.</li>
          <li><b>Most / least affected</b> — ranked by expected people affected (probability × population), which adds up from locality to district.</li>
        </ul>
        <div className="scale">
          {(
            [
              ["green", "Low", "No action needed"],
              ["yellow", "Watch", "Be aware, follow updates"],
              ["orange", "Prepare", "Be ready to move people and goods"],
              ["red", "Act", "Take action now"],
            ] as const
          ).map(([c, w, d]) => (
            <span key={c}>
              <i style={{ background: COLOR_HEX[c] }} />
              <b>{w}</b> {d}
            </span>
          ))}
        </div>
      </details>
    </Card>
  );
}
