import { useI18n } from "../../i18n";
import { Card } from "../Card";

// National numbers valid in Assam. Add district control-room numbers from ASDMA when confirmed.
const NUMBERS = [
  { n: "112", label: "Emergency (all services)" },
  { n: "1070", label: "State disaster control room" },
  { n: "1077", label: "District disaster control room" },
  { n: "108", label: "Ambulance" },
  { n: "101", label: "Fire" },
  { n: "100", label: "Police" },
];

const LINKS = [
  { href: "https://asdma.assam.gov.in", label: "ASDMA — Assam State Disaster Management Authority" },
  { href: "https://mausam.imd.gov.in", label: "IMD — official weather warnings" },
  { href: "https://ffs.india-water.gov.in", label: "CWC — official river flood forecasts" },
  { href: "https://sachet.ndma.gov.in", label: "NDMA SACHET — national alerts (CAP)" },
];

export function EmergencyCard() {
  const { t } = useI18n();
  return (
    <Card title={t("contacts_title")} icon="☎">
      <div className="phones">
        {NUMBERS.map((x) => (
          <a key={x.n} href={`tel:${x.n}`} className="phone">
            <b>{x.n}</b>
            <small>{x.label}</small>
          </a>
        ))}
      </div>
      <ul className="links">
        {LINKS.map((l) => (
          <li key={l.href}>
            <a href={l.href} target="_blank" rel="noreferrer">
              {l.label} ↗
            </a>
          </li>
        ))}
      </ul>
    </Card>
  );
}
