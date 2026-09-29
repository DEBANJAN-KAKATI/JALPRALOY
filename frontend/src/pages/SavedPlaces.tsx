import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import { api, type RainOutlook } from "../lib/api";
import type { Place } from "../lib/place";

interface SavedPlaceItem {
  id: string;
  name: string;
  district?: string;
  lat: number;
  lon: number;
  covered: boolean;
  alertThreshold: "any" | "orange_red" | "red_only";
  notes?: string;
}

const STORAGE_KEY = "jalproloy_saved_places";

const PRESET_PLACES: SavedPlaceItem[] = [
  { id: "p1", name: "Guwahati (Dispur & Basin)", district: "Kamrup Metropolitan", lat: 26.1445, lon: 91.7362, covered: true, alertThreshold: "orange_red" },
  { id: "p2", name: "Silchar (Barak Valley)", district: "Cachar", lat: 24.833, lon: 92.779, covered: false, alertThreshold: "orange_red" },
  { id: "p3", name: "Dibrugarh (Upper Assam)", district: "Dibrugarh", lat: 27.472, lon: 94.912, covered: false, alertThreshold: "orange_red" },
  { id: "p4", name: "Tezpur (Brahmaputra North)", district: "Sonitpur", lat: 26.633, lon: 92.800, covered: false, alertThreshold: "orange_red" },
];

interface Props {
  onSelectPlace: (place: Place) => void;
  onNavigate: (page: "map" | "news" | "saved" | "admin") => void;
}

export function SavedPlaces({ onSelectPlace, onNavigate }: Props) {
  const { t } = useI18n();
  const [places, setPlaces] = useState<SavedPlaceItem[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : PRESET_PLACES;
    } catch {
      return PRESET_PLACES;
    }
  });

  const [rains, setRains] = useState<Record<string, RainOutlook>>({});
  const [loadingLoc, setLoadingLoc] = useState(false);
  const [locMsg, setLocMsg] = useState<string | null>(null);
  const [customName, setCustomName] = useState("");
  const [customLat, setCustomLat] = useState("");
  const [customLon, setCustomLon] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [notifState, setNotifState] = useState<NotificationPermission>(() =>
    typeof Notification !== "undefined" ? Notification.permission : "default"
  );

  // Save to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(places));
    } catch {
      /* ignore */
    }
  }, [places]);

  // Fetch live rain for each saved place
  useEffect(() => {
    let cancelled = false;
    places.forEach((p) => {
      api.rainOutlook(p.lat, p.lon)
        .then((r) => {
          if (!cancelled) setRains((prev) => ({ ...prev, [p.id]: r }));
        })
        .catch(() => undefined);
    });
    return () => {
      cancelled = true;
    };
  }, [places]);

  function handleSaveCurrentLocation() {
    if (!("geolocation" in navigator)) {
      setLocMsg("Geolocation is not supported by your browser");
      return;
    }
    setLoadingLoc(true);
    setLocMsg(t("locating"));

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          const located = await api.locate(lat, lon);
          const newPlace: SavedPlaceItem = {
            id: `gps_${Date.now()}`,
            name: `${t("you_are_here")} (${located.nearest_town})`,
            district: located.area || "Assam",
            lat,
            lon,
            covered: located.covered,
            alertThreshold: "orange_red",
          };
          setPlaces((prev) => [newPlace, ...prev]);
          setLocMsg(null);
        } catch {
          setLocMsg("Could not resolve location address");
        } finally {
          setLoadingLoc(false);
        }
      },
      () => {
        setLocMsg(t("location_denied"));
        setLoadingLoc(false);
      },
      { timeout: 10000 }
    );
  }

  function handleAddCustom(e: React.FormEvent) {
    e.preventDefault();
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);
    if (!customName.trim() || isNaN(lat) || isNaN(lon)) return;

    const newItem: SavedPlaceItem = {
      id: `custom_${Date.now()}`,
      name: customName.trim(),
      lat,
      lon,
      covered: lat >= 26.05 && lat <= 26.25 && lon >= 91.55 && lon <= 91.90,
      alertThreshold: "orange_red",
    };
    setPlaces((prev) => [newItem, ...prev]);
    setCustomName("");
    setCustomLat("");
    setCustomLon("");
    setShowAddForm(false);
  }

  function handleDelete(id: string) {
    setPlaces((prev) => prev.filter((p) => p.id !== id));
  }

  function handleViewOnMap(p: SavedPlaceItem) {
    onSelectPlace({
      name: p.name,
      center: [p.lat, p.lon],
      covered: p.covered,
      area: p.covered ? "Guwahati" : null,
      district: p.district || null,
      pinned: true,
    });
    onNavigate("map");
  }

  async function requestNotificationPermission() {
    if (typeof Notification === "undefined") return;
    const perm = await Notification.requestPermission();
    setNotifState(perm);
    if (perm === "granted") {
      new Notification("JalProloy Alerts Active", {
        body: "You will receive flood early warnings for your saved places in Assam.",
        icon: "/icon-192.png",
      });
    }
  }

  return (
    <section className="page" style={{ maxWidth: 960, margin: "0 auto", padding: "20px 16px" }}>
      <header style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ margin: "0 0 6px 0", fontSize: "1.75rem", display: "flex", alignItems: "center", gap: 10 }}>
            <span>★</span> {t("saved")}
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: "0.95rem" }}>
            Track heavy rainfall and flood risk for your residence, family, or property in Assam with real-time telemetry.
          </p>
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button className="tool" onClick={handleSaveCurrentLocation} disabled={loadingLoc} style={{ background: "#eef5fc", borderColor: "var(--brand)" }}>
            📍 {loadingLoc ? t("locating") : "+ Save Current Location"}
          </button>
          <button className="tool" onClick={() => setShowAddForm((s) => !s)}>
            {showAddForm ? "Cancel" : "+ Custom Place"}
          </button>
        </div>
      </header>

      {locMsg && (
        <div style={{ background: "#fff3cd", color: "#664d03", padding: "10px 16px", borderRadius: 8, marginBottom: 16 }}>
          {locMsg}
        </div>
      )}

      {showAddForm && (
        <form onSubmit={handleAddCustom} style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 12, padding: 18, marginBottom: 20, boxShadow: "var(--shadow)" }}>
          <h3 style={{ margin: "0 0 12px 0", fontSize: "1.1rem" }}>Add Location in Assam</h3>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 10, alignItems: "end" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Place / Village Name</label>
              <input
                type="text"
                placeholder="e.g. Anil Nagar, Guwahati"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                required
                style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 8 }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Latitude</label>
              <input
                type="number"
                step="0.0001"
                placeholder="26.14"
                value={customLat}
                onChange={(e) => setCustomLat(e.target.value)}
                required
                style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 8 }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Longitude</label>
              <input
                type="number"
                step="0.0001"
                placeholder="91.73"
                value={customLon}
                onChange={(e) => setCustomLon(e.target.value)}
                required
                style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 8 }}
              />
            </div>
            <button type="submit" className="tool" style={{ background: "var(--brand)", color: "#fff", height: 38 }}>
              Save
            </button>
          </div>
        </form>
      )}

      {/* Alert Settings Banner */}
      <div style={{ background: "linear-gradient(135deg, #0b4f8a0d, #0a86c91a)", border: "1px solid #9cc3e6", borderRadius: 12, padding: "14px 18px", marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <strong style={{ display: "block", color: "var(--brand)" }}>🔔 Instant Flood Warning Push Alerts</strong>
          <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
            {notifState === "granted"
              ? "Browser alerts are enabled. You will be alerted when risk escalates for your saved places."
              : "Allow notifications so you receive early warnings even when the app is closed."}
          </span>
        </div>
        {notifState !== "granted" ? (
          <button className="tool" onClick={requestNotificationPermission} style={{ background: "var(--brand)", color: "#fff" }}>
            Enable Push Alerts
          </button>
        ) : (
          <span style={{ color: "var(--green)", fontWeight: 700, fontSize: "0.85rem" }}>✓ Active</span>
        )}
      </div>

      {/* Saved Places List */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 16 }}>
        {places.map((p) => {
          const rain = rains[p.id];
          const todayRain = rain?.days?.[0]?.rain_mm ?? 0;
          const maxRain = rain?.max_mm ?? 0;
          const rainColor = rain?.days?.[0]?.color ?? "green";

          return (
            <div
              key={p.id}
              style={{
                background: "#fff",
                border: "1px solid var(--line)",
                borderRadius: 14,
                padding: "16px 18px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                boxShadow: "var(--shadow)",
                position: "relative",
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 8 }}>
                  <h3 style={{ margin: 0, fontSize: "1.1rem", color: "var(--ink)" }}>{p.name}</h3>
                  <button
                    onClick={() => handleDelete(p.id)}
                    title="Remove place"
                    style={{ background: "none", border: 0, color: "var(--muted)", fontSize: "1.2rem", padding: "0 4px", cursor: "pointer" }}
                  >
                    ×
                  </button>
                </div>

                <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: 12 }}>
                  {p.district ? `${p.district} • ` : ""}
                  {p.lat.toFixed(3)}°N, {p.lon.toFixed(3)}°E
                  {p.covered && (
                    <span style={{ marginLeft: 6, padding: "2px 6px", background: "#e8f5e9", color: "var(--green)", borderRadius: 6, fontWeight: 600 }}>
                      Hyperlocal Map
                    </span>
                  )}
                </div>

                {/* Weather Telemetry Pill */}
                <div
                  style={{
                    background: rainColor === "red" ? "#fdecea" : rainColor === "orange" ? "#fff1e0" : rainColor === "yellow" ? "#fffbe6" : "#f4f7fb",
                    borderLeft: `4px solid var(--${rainColor})`,
                    padding: "8px 12px",
                    borderRadius: "0 8px 8px 0",
                    marginBottom: 14,
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 600 }}>
                    <span>Next 24h Rain:</span>
                    <span>{todayRain.toFixed(1)} mm</span>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: 2 }}>
                    7-day peak: {maxRain.toFixed(1)} mm ({rain?.source ?? "Open-Meteo"})
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button
                  className="tool"
                  onClick={() => handleViewOnMap(p)}
                  style={{ flex: 1, background: "var(--brand)", color: "#fff", textAlign: "center", fontSize: "0.85rem" }}
                >
                  🗺 View on Map
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
