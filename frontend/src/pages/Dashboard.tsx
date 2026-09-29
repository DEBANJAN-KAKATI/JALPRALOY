import { latLngToCell } from "h3-js";
import { useCallback, useEffect, useState } from "react";
import { AlertBanner } from "../components/AlertBanner";
import { AreaPanel } from "../components/AreaPanel";
import { AlertSignupCard } from "../components/cards/AlertSignupCard";
import { AreaBriefCard } from "../components/cards/AreaBriefCard";
import { DataStatusCard } from "../components/cards/DataStatusCard";
import { EmergencyCard } from "../components/cards/EmergencyCard";
import { FloodEventsCard } from "../components/cards/FloodEventsCard";
import { HowItWorksCard } from "../components/cards/HowItWorksCard";
import { RainOutlookCard } from "../components/cards/RainOutlookCard";
import { RiverWatchCard } from "../components/cards/RiverWatchCard";
import { TownOutlookCard } from "../components/cards/TownOutlookCard";
import { MapView, type LayerKind } from "../components/MapView";
import { SlideDeck, type Slide } from "../components/SlideDeck";
import { Timeline } from "../components/Timeline";
import { useI18n } from "../i18n";
import { api, type Horizon, type Located, type TownOutlook, type WarningColor } from "../lib/api";
import { COLOR_RANK } from "../lib/imd";
import { nearestStation, type Place } from "../lib/place";
import { useApi } from "../lib/useApi";

interface Props {
  place: Place;
  onPlace: (p: Place) => void;
  refreshKey: number;
  userLoc: Located | null;
  onLocate: () => void;
}

export function Dashboard({ place, onPlace, refreshKey, userLoc, onLocate }: Props) {
  const { t } = useI18n();
  const [horizon, setHorizon] = useState<Horizon>("24h");
  const [layer, setLayer] = useState<LayerKind>("flood");
  const [selected, setSelected] = useState<string | null>(null);
  const area = place.covered ? place.area : null;
  const [lat, lon] = place.center;

  // Model outputs (hyperlocal pilot only)
  const summary = useApi(area ? () => api.areaSummary(area, horizon) : null, [area, horizon, refreshKey]);
  const cells = useApi(area ? () => api.areaCells(area, horizon) : null, [area, horizon, refreshKey]);
  const cell = useApi(selected ? () => api.cell(selected, horizon) : null, [selected, horizon]);
  // Live public data (everywhere)
  const rain = useApi(() => api.rainOutlook(lat, lon), [lat, lon, refreshKey]);
  const towns = useApi(api.towns, [refreshKey]);
  const rivers = useApi(api.rivers, [refreshKey]);
  const events = useApi(api.events, [refreshKey]);
  const status = useApi(api.status, [refreshKey, rain.data, towns.data, rivers.data, events.data]);

  useEffect(() => {
    // A searched point inside the pilot opens its hexagon's "why" straight away.
    setSelected(place.covered && place.pinned ? latLngToCell(lat, lon, 8) : null);
    // Answer first: covered places open on flood risk; elsewhere there are no hexagons,
    // so open on the live rain layer instead of an empty map. River view is kept.
    setLayer((l) => (l === "river" ? l : place.covered ? "flood" : "rain"));
  }, [place]); // eslint-disable-line react-hooks/exhaustive-deps
  const onHorizon = useCallback((h: Horizon) => setHorizon(h), []);

  function openTown(town: TownOutlook) {
    onPlace({ name: town.name, center: [town.lat, town.lon], covered: false, area: null, district: town.district });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Banner: model answer where covered, otherwise the live rain outlook (clearly labelled raw).
  let bannerColor: WarningColor = "green";
  let bannerText = t("loading");
  if (place.covered && summary.data) {
    bannerColor = summary.data.flood_color;
    bannerText = summary.data.headline ?? `${place.name}: ${t("no_alert")}`;
  } else if (!place.covered && rain.data) {
    bannerColor = rain.data.days.reduce<WarningColor>((w, d) => (COLOR_RANK[d.color] > COLOR_RANK[w] ? d.color : w), "green");
    bannerText = t("uncovered_banner", { place: place.name, max: Math.round(rain.data.max_mm) });
  }
  const isDemo = summary.data?.source === "synthetic-demo";

  // One topic per slide keeps the page calm; the map + answer stay above.
  const slides: Slide[] = [
    {
      key: "overview", icon: "📝", title: t("slide_overview"),
      content: (
        <div className="slide-grid">
          <AreaBriefCard place={place} summary={area ? summary.data : null} rain={rain.data} rivers={rivers.data} />
          <DataStatusCard state={status} />
        </div>
      ),
    },
    {
      key: "rain", icon: "🌧", title: t("slide_rain"),
      content: (
        <div className="slide-grid">
          <RainOutlookCard place={place.name} state={rain} />
          <TownOutlookCard state={towns} onSelect={openTown} />
        </div>
      ),
    },
    {
      key: "river", icon: "🌊", title: t("slide_river"),
      content: <RiverWatchCard state={rivers} highlight={nearestStation(place.center, rivers.data)?.station} />,
    },
    { key: "events", icon: "🛰", title: t("slide_events"), content: <FloodEventsCard state={events} /> },
    {
      key: "alerts", icon: "🔔", title: t("slide_alerts"),
      content: (
        <div className="slide-grid">
          <AlertSignupCard place={place} />
          <EmergencyCard />
        </div>
      ),
    },
    { key: "how", icon: "🧭", title: t("slide_how"), content: <HowItWorksCard /> },
  ];

  return (
    <>
      <section className="hero">
        {isDemo && <div className="demo-notice">⚠ {t("demo_notice")}</div>}
        <AlertBanner color={bannerColor} text={bannerText} />
        <div className="main">
          <MapView
            place={place}
            cells={area ? cells.data?.cells ?? [] : []}
            towns={towns.data ?? []}
            rivers={rivers.data ?? []}
            userLoc={userLoc}
            layer={layer}
            onLayerChange={setLayer}
            selected={selected}
            onSelect={setSelected}
            onSelectTown={openTown}
            onLocate={onLocate}
          />
          <AreaPanel
            place={place}
            summary={area ? summary.data : null}
            cell={cell.data}
            rain={rain.data}
            rivers={rivers.data}
            userLoc={userLoc}
          />
        </div>
        {place.covered && <Timeline value={horizon} onChange={onHorizon} />}
      </section>

      <SlideDeck slides={slides} />
    </>
  );
}
