import { FlyToInterpolator, type PickingInfo } from "@deck.gl/core";
import { H3ClusterLayer, H3HexagonLayer } from "@deck.gl/geo-layers";
import { PathLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import DeckGL from "@deck.gl/react";
import { getResolution, latLngToCell } from "h3-js";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMemo, useState } from "react";
import MapGL, { ScaleControl } from "react-map-gl/maplibre";
import { useI18n } from "../i18n";
import type { CellRisk, Located, RiverStation, TownOutlook, WarningColor } from "../lib/api";
import { fmtNum } from "../lib/format";
import { COLOR_RGB, COLOR_WORD_KEY, pct } from "../lib/imd";
import { ASSAM_VIEW, type Place } from "../lib/place";

export type LayerKind = "flood" | "rain" | "river";

// Free, keyless basemap. Swap for self-hosted tiles (e.g. Protomaps) in production.
const BASEMAP = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const RIVER_BLUE: [number, number, number] = [30, 110, 190];
const FONT = "Noto Sans, system-ui, sans-serif";
const RIVER_WORDS = ["river_Normal", "river_Above normal", "river_High", "river_Very high"];
const LEVELS: WarningColor[] = ["green", "yellow", "orange", "red"];
/** Below this zoom, same-colour hexagons are merged into smooth zones (no cell mesh). */
const HEX_ZOOM = 12.5;

const darker = (c: [number, number, number]): [number, number, number] => [c[0] * 0.7, c[1] * 0.7, c[2] * 0.7];

interface Zone {
  color: WarningColor;
  hexagons: string[];
}

interface Props {
  place: Place;
  cells: CellRisk[];
  towns: TownOutlook[];
  rivers: RiverStation[];
  userLoc: Located | null;
  layer: LayerKind;
  onLayerChange: (l: LayerKind) => void;
  selected: string | null;
  onSelect: (h3: string) => void;
  onSelectTown: (t: TownOutlook) => void;
  onLocate: () => void;
}

export function MapView(props: Props) {
  const { place, cells, towns, rivers, userLoc, layer, onLayerChange, selected, onSelect, onSelectTown, onLocate } = props;
  const { t } = useI18n();
  const [zoom, setZoom] = useState(10.5);
  const [showLow, setShowLow] = useState(false);

  // Changing initialViewState moves the camera: river layer = whole Assam,
  // searched pin = street zoom, covered area = city zoom, other places = regional.
  const initialViewState = useMemo(() => {
    const zoomTo = place.pinned ? (place.covered ? 13 : 11) : place.covered ? 11 : 8;
    const view = layer === "river" ? ASSAM_VIEW : { latitude: place.center[0], longitude: place.center[1], zoom: zoomTo };
    return { ...view, pitch: 0, bearing: 0, transitionDuration: 800, transitionInterpolator: new FlyToInterpolator() };
  }, [place.center, place.covered, place.pinned, layer === "river"]); // eslint-disable-line react-hooks/exhaustive-deps

  const colorOf = (c: CellRisk): WarningColor => (layer === "rain" ? c.rain_color : c.color);
  const byId = useMemo(() => new Map(cells.map((c) => [c.h3, c])), [cells]);
  const res = cells.length ? getResolution(cells[0].h3) : 8;
  const cellAt = (coord?: number[]) => (coord ? byId.get(latLngToCell(coord[1], coord[0], res)) : undefined);

  const zones = useMemo<Zone[]>(() => {
    const groups: Record<WarningColor, string[]> = { green: [], yellow: [], orange: [], red: [] };
    for (const c of cells) groups[colorOf(c)].push(c.h3);
    return LEVELS.filter((k) => groups[k].length && (showLow || k !== "green")).map((k) => ({ color: k, hexagons: groups[k] }));
  }, [cells, layer, showLow]); // eslint-disable-line react-hooks/exhaustive-deps

  const showCells = layer !== "river" && cells.length > 0;
  const hexMode = zoom >= HEX_ZOOM;
  const gauges = [...rivers].sort((a, b) => a.order - b.order);

  const layers = [
    // Pilot footprint: one thin outline instead of hundreds of cell borders.
    showCells &&
      new H3ClusterLayer<{ hexagons: string[] }>({
        id: "coverage",
        data: [{ hexagons: cells.map((c) => c.h3) }],
        getHexagons: (d) => d.hexagons,
        filled: false,
        stroked: true,
        getLineColor: [70, 90, 120, 170],
        lineWidthMinPixels: 1.2,
      }),
    showCells &&
      !hexMode &&
      new H3ClusterLayer<Zone>({
        id: "zones",
        data: zones,
        getHexagons: (d) => d.hexagons,
        getFillColor: (d) => [...COLOR_RGB[d.color], d.color === "green" ? 55 : 115],
        getLineColor: (d) => [...darker(COLOR_RGB[d.color]), 200],
        lineWidthMinPixels: 1.4,
        stroked: true,
        filled: true,
        pickable: true,
        onClick: (info) => {
          const c = cellAt(info.coordinate);
          if (c) onSelect(c.h3);
        },
      }),
    showCells &&
      hexMode &&
      new H3HexagonLayer<CellRisk>({
        id: "cells",
        data: showLow ? cells : cells.filter((c) => colorOf(c) !== "green"),
        getHexagon: (d) => d.h3,
        // Opacity follows probability: faint = unlikely, solid = likely.
        getFillColor: (d) => [...COLOR_RGB[colorOf(d)], layer === "rain" ? 140 : 60 + 170 * d.p_flood],
        stroked: false,
        extruded: false, // H3HexagonLayer defaults to 1000 m-tall 3D prisms
        pickable: true,
        onClick: (info) => info.object && onSelect(info.object.h3),
        updateTriggers: { getFillColor: [layer] },
      }),
    showCells &&
      !!selected &&
      new H3HexagonLayer<string>({
        id: "selected",
        data: [selected],
        getHexagon: (d) => d,
        getFillColor: [255, 255, 255, 60],
        getLineColor: [15, 23, 42, 255],
        lineWidthMinPixels: 3,
        stroked: true,
        extruded: false,
      }),
    layer === "rain" &&
      new ScatterplotLayer<TownOutlook>({
        id: "towns",
        data: towns,
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: (d) => (d.max_mm < 2.5 ? [140, 180, 220, 220] : [...COLOR_RGB[d.color], 230]),
        getLineColor: [255, 255, 255],
        stroked: true,
        lineWidthMinPixels: 1.5,
        getRadius: (d) => 6 + Math.min(10, d.max_mm / 12),
        radiusUnits: "pixels",
        pickable: true,
        onClick: (info) => info.object && onSelectTown(info.object),
      }),
    layer === "rain" &&
      new TextLayer<TownOutlook>({
        id: "town-labels",
        data: towns,
        getPosition: (d) => [d.lon, d.lat],
        getText: (d) => `${d.name} · ${Math.round(d.max_mm)} mm`,
        getSize: 11,
        getPixelOffset: [0, -16],
        getColor: [40, 40, 40],
        outlineWidth: 2,
        outlineColor: [255, 255, 255],
        fontSettings: { sdf: true },
        characterSet: "auto",
        fontFamily: FONT,
      }),
    layer === "river" &&
      new PathLayer<{ path: [number, number][] }>({
        id: "river-line",
        data: [{ path: gauges.map((g) => [g.lon, g.lat] as [number, number]) }],
        getPath: (d) => d.path,
        getColor: [...RIVER_BLUE, 120],
        getWidth: 4,
        widthUnits: "pixels",
      }),
    layer === "river" &&
      new ScatterplotLayer<RiverStation>({
        id: "gauges",
        data: gauges,
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: (d) => [...COLOR_RGB[d.color], 240],
        getLineColor: [...RIVER_BLUE],
        stroked: true,
        lineWidthMinPixels: 2,
        getRadius: 9,
        radiusUnits: "pixels",
        pickable: true,
      }),
    layer === "river" &&
      new TextLayer<RiverStation>({
        id: "gauge-labels",
        data: gauges,
        getPosition: (d) => [d.lon, d.lat],
        getText: (d) => `${d.station}\n${fmtNum(d.discharge)} m³/s`,
        getSize: 12,
        getPixelOffset: [0, -24],
        getColor: [20, 40, 70],
        outlineWidth: 2,
        outlineColor: [255, 255, 255],
        fontSettings: { sdf: true },
        characterSet: "auto",
        fontFamily: FONT,
      }),
    place.pinned &&
      new ScatterplotLayer<Place>({
        id: "pin",
        data: [place],
        getPosition: (d) => [d.center[1], d.center[0]],
        getFillColor: [219, 68, 55],
        getLineColor: [255, 255, 255],
        stroked: true,
        lineWidthMinPixels: 2.5,
        getRadius: 8,
        radiusUnits: "pixels",
      }),
    place.pinned &&
      new TextLayer<Place>({
        id: "pin-label",
        data: [place],
        getPosition: (d) => [d.center[1], d.center[0]],
        getText: (d) => d.name,
        getSize: 13,
        getPixelOffset: [0, -20],
        getColor: [20, 20, 20],
        outlineWidth: 3,
        outlineColor: [255, 255, 255],
        fontSettings: { sdf: true },
        characterSet: "auto",
        fontFamily: FONT,
      }),
    userLoc &&
      new ScatterplotLayer<Located>({
        id: "me",
        data: [userLoc],
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: [26, 115, 232],
        getLineColor: [255, 255, 255],
        stroked: true,
        lineWidthMinPixels: 3,
        getRadius: 8,
        radiusUnits: "pixels",
      }),
  ].filter(Boolean);

  function tooltip({ object, layer: l, coordinate }: PickingInfo) {
    if (!l) return null;
    if (l.id === "zones" || l.id === "cells") {
      const c = l.id === "cells" ? (object as CellRisk) : cellAt(coordinate);
      if (!c) return null;
      return `${t(COLOR_WORD_KEY[colorOf(c)])} · ${t("flood_risk")} ${pct(c.p_flood)}\n${t("rain_expected")}: ${c.rain_mm} mm`;
    }
    if (!object) return null;
    if (l.id === "towns") {
      const c = object as TownOutlook;
      return `${c.name} (${c.district})\n${Math.round(c.max_mm)} mm / day max · ${Math.round(c.total_mm)} mm in 5 days`;
    }
    if (l.id === "gauges") {
      const g = object as RiverStation;
      return `${g.station}: ${fmtNum(g.discharge)} m³/s\n${t(`river_${g.status}`)} · ${t(g.trend)}`;
    }
    return null;
  }

  return (
    <div className="map">
      <DeckGL
        initialViewState={initialViewState}
        controller
        layers={layers}
        getTooltip={tooltip}
        onViewStateChange={({ viewState }) => {
          const z = Math.round((viewState as { zoom: number }).zoom * 4) / 4;
          if (z !== zoom) setZoom(z);
        }}
      >
        <MapGL mapStyle={BASEMAP}>
          <ScaleControl position="top-left" />
        </MapGL>
      </DeckGL>
      {layer === "flood" && !place.covered && <div className="map-chip">⬡ {t("flood_pilot_only")}</div>}
      <button className="locate-btn" onClick={onLocate} title={t("my_location")} aria-label={t("my_location")}>◎</button>
      <fieldset className="layers">
        <legend className="sr-only">Layers</legend>
        {(["flood", "rain", "river"] as LayerKind[]).map((l) => (
          <label key={l}>
            <input type="radio" name="layer" checked={layer === l} onChange={() => onLayerChange(l)} />
            {t(`layer_${l}`)}
          </label>
        ))}
      </fieldset>
      <div className="legend" aria-label="Legend">
        <div className="legend-row">
          {LEVELS.map((c, i) => (
            <span key={c} className={!showLow && c === "green" && layer !== "river" ? "dim" : ""}>
              <i style={{ background: `rgb(${COLOR_RGB[c].join(",")})` }} />
              {layer === "river" ? t(RIVER_WORDS[i]) : t(COLOR_WORD_KEY[c])}
            </span>
          ))}
        </div>
        {showCells && (
          <label className="legend-toggle">
            <input type="checkbox" checked={showLow} onChange={(e) => setShowLow(e.target.checked)} />
            {t("show_low")}
          </label>
        )}
        {showCells && !hexMode && <small className="muted">{t("zoom_for_cells")}</small>}
      </div>
    </div>
  );
}
