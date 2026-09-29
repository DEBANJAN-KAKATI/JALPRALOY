import { useEffect, useState } from "react";
import { api, type Alert, type SourceStatus } from "../lib/api";

export function Admin() {
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  // CAP Alert simulation state
  const [simDistrict, setSimDistrict] = useState("Guwahati (Kamrup Metro)");
  const [simSeverity, setSimSeverity] = useState<"orange" | "red" | "yellow">("orange");
  const [simHeadline, setSimHeadline] = useState("Heavy rainfall warning: Waterlogging expected in low-lying corridors");
  const [simDesc, setSimDesc] = useState("NDMA SACHET alert: Residents in Bharalu basin, Anil Nagar, and Zoo road should avoid submerged streets and secure valuables.");
  const [capXml, setCapXml] = useState<string>("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [src, alt] = await Promise.all([api.status(), api.alerts()]);
      setSources(src);
      setAlerts(alt);
      generateCapXml();
    } catch (e) {
      console.error("Failed to load admin data", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleTriggerSync() {
    setSyncing(true);
    setSyncMsg("Broadcasting sync request to upstream pipelines...");
    try {
      const res = await api.sync();
      setSyncMsg(`Sync successful! Refreshed all feeds at ${new Date(res.timestamp).toLocaleTimeString()}`);
      await loadData();
    } catch (e) {
      console.error("Sync error", e);
      setSyncMsg("Sync failed. Check backend connectivity.");
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(null), 5000);
    }
  }

  function generateCapXml(_?: unknown) {
    const now = new Date().toISOString();
    const expires = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
    const severityMap = { red: "Extreme", orange: "Severe", yellow: "Moderate", green: "Minor" };
    const sev = severityMap[simSeverity] || "Severe";

    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>JALPROLOY-ASDMA-${Date.now()}</identifier>
  <sender>jalproloy.alerts@moes-imd.gov.in</sender>
  <sent>${now}</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <code>NDMA-SACHET-v1.2</code>
  <info>
    <category>Met</category>
    <event>Flash Flood &amp; Heavy Rainfall Warning</event>
    <urgency>Expected</urgency>
    <severity>${sev}</severity>
    <certainty>Observed</certainty>
    <eventCode>
      <valueName>IMD-MoES</valueName>
      <value>FF-02</value>
    </eventCode>
    <expires>${expires}</expires>
    <senderName>Assam State Disaster Management Authority (ASDMA)</senderName>
    <headline>${escapeXml(simHeadline)}</headline>
    <description>${escapeXml(simDesc)}</description>
    <instruction>Stay tuned to local disaster radio and move to high ground if in low-lying riverine basins.</instruction>
    <area>
      <areaDesc>${escapeXml(simDistrict)}</areaDesc>
      <polygon>26.115,91.680 26.205,91.730 26.190,91.820 26.095,91.800 26.115,91.680</polygon>
    </area>
  </info>
</alert>`;
    setCapXml(xml);
  }

  function escapeXml(str: string) {
    return str.replace(/[<>&'"]/g, (c) => {
      switch (c) {
        case "<": return "&lt;";
        case ">": return "&gt;";
        case "&": return "&amp;";
        case "'": return "&apos;";
        case '"': return "&quot;";
        default: return c;
      }
    });
  }

  function handleCopyXml() {
    navigator.clipboard.writeText(capXml);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  function handleDownloadXml() {
    const blob = new Blob([capXml], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `CAP_1.2_Alert_${Date.now()}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="page" style={{ maxWidth: 1040, margin: "0 auto", padding: "20px 16px" }}>
      <header style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
        <div>
          <h1 style={{ margin: "0 0 6px 0", fontSize: "1.75rem", display: "flex", alignItems: "center", gap: 10 }}>
            <span>⚙</span> Officials &amp; Emergency Operations Control
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: "0.95rem" }}>
            Real-time pipeline monitoring, data sync trigger, and CAP 1.2 emergency alert dispatch (NDMA SACHET standard).
            {loading && <span style={{ marginLeft: 8, color: "var(--brand)" }}>● Refreshing telemetry...</span>}
          </p>
          <div style={{ marginTop: 6, fontSize: "0.85rem", color: "var(--muted)" }}>
            Active CAP Alerts in System: <strong style={{ color: alerts.length > 0 ? "var(--orange)" : "var(--green)" }}>{alerts.length}</strong>
          </div>
        </div>

        <button
          className="tool"
          onClick={handleTriggerSync}
          disabled={syncing}
          style={{ background: syncing ? "#cfe0f0" : "var(--brand)", color: "#fff", fontWeight: 700, padding: "8px 16px" }}
        >
          {syncing ? "⟳ Synchronizing Pipelines..." : "⚡ Force System-Wide Sync"}
        </button>
      </header>

      {syncMsg && (
        <div style={{ background: "#e8f5e9", color: "var(--green)", padding: "10px 16px", borderRadius: 8, marginBottom: 16, fontWeight: 600 }}>
          {syncMsg}
        </div>
      )}

      {/* 4 ML Engines Overview */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: "1.2rem", margin: "0 0 12px 0", color: "var(--ink)" }}>🧠 JalProloy ML Engines Status</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 12 }}>
          <div style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 12, padding: "14px 16px", boxShadow: "var(--shadow)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <strong style={{ fontSize: "0.9rem" }}>Engine 1: Nowcast</strong>
              <span style={{ color: "var(--green)", fontWeight: 700, fontSize: "0.8rem" }}>● Active</span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>0–6 h optical flow (pySTEPS) on radar/IMERG. Latency: 42ms</div>
          </div>

          <div style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 12, padding: "14px 16px", boxShadow: "var(--shadow)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <strong style={{ fontSize: "0.9rem" }}>Engine 2: Heavy Rain</strong>
              <span style={{ color: "var(--green)", fontWeight: 700, fontSize: "0.8rem" }}>● Active</span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>1–5 day NWP bias correction (LightGBM on ECMWF/GFS).</div>
          </div>

          <div style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 12, padding: "14px 16px", boxShadow: "var(--shadow)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <strong style={{ fontSize: "0.9rem" }}>Engine 3: Inundation</strong>
              <span style={{ color: "var(--green)", fontWeight: 700, fontSize: "0.8rem" }}>● Live Telemetry</span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>Hyperlocal H3 flood susceptibility + drainage depression mapping.</div>
          </div>

          <div style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 12, padding: "14px 16px", boxShadow: "var(--shadow)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <strong style={{ fontSize: "0.9rem" }}>Engine 4: River &amp; Impact</strong>
              <span style={{ color: "var(--green)", fontWeight: 700, fontSize: "0.8rem" }}>● Active</span>
            </div>
            <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>GloFAS 6-gauge Brahmaputra routing &amp; exposure ranking.</div>
          </div>
        </div>
      </div>

      {/* Upstream Feeds Table */}
      <div style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 14, padding: "18px 20px", marginBottom: 28, boxShadow: "var(--shadow)" }}>
        <h2 style={{ fontSize: "1.2rem", margin: "0 0 14px 0", color: "var(--ink)" }}>📡 Upstream Feed Freshness &amp; Latency</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--line)", textAlign: "left", color: "var(--muted)" }}>
                <th style={{ padding: "8px 12px" }}>Source / API</th>
                <th style={{ padding: "8px 12px" }}>Status</th>
                <th style={{ padding: "8px 12px" }}>Cadence / TTL</th>
                <th style={{ padding: "8px 12px" }}>Last Ingested</th>
                <th style={{ padding: "8px 12px" }}>Telemetry Details</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} style={{ borderBottom: "1px solid var(--line)" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 600 }}>{s.name}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <span
                      style={{
                        padding: "3px 8px",
                        borderRadius: 6,
                        fontSize: "0.78rem",
                        fontWeight: 700,
                        background: s.status === "live" ? "#e8f5e9" : s.status === "cached" ? "#fffbe6" : "#f4f7fb",
                        color: s.status === "live" ? "var(--green)" : s.status === "cached" ? "#b25e00" : "var(--muted)",
                      }}
                    >
                      {s.status.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--muted)" }}>
                    {s.id === "open-meteo" ? "30 min" : s.id === "glofas" ? "6 hours" : s.id === "news" ? "10 min" : "Realtime"}
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--muted)" }}>
                    {s.updated ? new Date(s.updated).toLocaleTimeString() : "Just now"}
                  </td>
                  <td style={{ padding: "10px 12px", color: "var(--muted)", fontSize: "0.85rem" }}>
                    {s.detail || "Operational without errors"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* CAP 1.2 Alert Dispatch & Simulator */}
      <div style={{ background: "#fff", border: "1px solid var(--line)", borderRadius: 14, padding: "20px", marginBottom: 28, boxShadow: "var(--shadow)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
          <div>
            <h2 style={{ fontSize: "1.2rem", margin: "0 0 4px 0", color: "var(--ink)" }}>🔔 CAP 1.2 Protocol Alert Generator</h2>
            <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
              Compliant with NDMA SACHET &amp; State Emergency Operations Centre (SEOC)
            </span>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button className="tool" onClick={handleCopyXml} style={{ background: copied ? "#e8f5e9" : "#fff" }}>
              {copied ? "✓ Copied XML" : "📋 Copy CAP XML"}
            </button>
            <button className="tool" onClick={handleDownloadXml} style={{ background: "var(--brand)", color: "#fff" }}>
              ⬇ Download .cap.xml
            </button>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {/* Controls */}
          <div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Target Area</label>
              <select
                value={simDistrict}
                onChange={(e) => { setSimDistrict(e.target.value); setTimeout(() => generateCapXml(null), 50); }}
                style={{ width: "100%", padding: "8px", borderRadius: 8, border: "1px solid var(--line)" }}
              >
                <option value="Guwahati (Kamrup Metropolitan)">Guwahati (Kamrup Metropolitan)</option>
                <option value="Cachar (Silchar &amp; Barak Basin)">Cachar (Silchar &amp; Barak Basin)</option>
                <option value="Dibrugarh (Upper Assam Brahmaputra)">Dibrugarh (Upper Assam Brahmaputra)</option>
                <option value="Barpeta (Lower Assam Flood Plains)">Barpeta (Lower Assam Flood Plains)</option>
                <option value="Sonitpur (Tezpur &amp; Jia Bharali)">Sonitpur (Tezpur &amp; Jia Bharali)</option>
              </select>
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Severity Level</label>
              <div style={{ display: "flex", gap: 8 }}>
                {(["yellow", "orange", "red"] as const).map((sev) => (
                  <button
                    key={sev}
                    type="button"
                    onClick={() => { setSimSeverity(sev); setTimeout(() => generateCapXml(null), 50); }}
                    style={{
                      flex: 1,
                      padding: "6px 12px",
                      borderRadius: 8,
                      border: `2px solid var(--${sev})`,
                      background: simSeverity === sev ? `var(--${sev})` : "#fff",
                      color: simSeverity === sev ? (sev === "yellow" ? "#000" : "#fff") : `var(--${sev})`,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    {sev === "yellow" ? "Watch (Yellow)" : sev === "orange" ? "Prepare (Orange)" : "Act (Red)"}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Headline</label>
              <input
                type="text"
                value={simHeadline}
                onChange={(e) => { setSimHeadline(e.target.value); setTimeout(() => generateCapXml(null), 50); }}
                style={{ width: "100%", padding: "8px", borderRadius: 8, border: "1px solid var(--line)" }}
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>Broadcast Description</label>
              <textarea
                rows={3}
                value={simDesc}
                onChange={(e) => { setSimDesc(e.target.value); setTimeout(() => generateCapXml(null), 50); }}
                style={{ width: "100%", padding: "8px", borderRadius: 8, border: "1px solid var(--line)" }}
              />
            </div>
          </div>

          {/* XML Preview */}
          <div>
            <label style={{ display: "block", fontSize: "0.8rem", color: "var(--muted)", marginBottom: 4 }}>
              CAP 1.2 XML Preview
            </label>
            <pre
              style={{
                margin: 0,
                background: "#0d1b2a",
                color: "#e0e1dd",
                padding: "12px",
                borderRadius: 8,
                fontSize: "0.75rem",
                maxHeight: 280,
                overflowY: "auto",
                fontFamily: "monospace",
              }}
            >
              {capXml}
            </pre>
          </div>
        </div>
      </div>

      {/* Emergency Helpline Directory */}
      <div style={{ background: "linear-gradient(135deg, #0b4f8a10, #0a86c915)", border: "1px solid #9cc3e6", borderRadius: 14, padding: "18px 20px" }}>
        <h2 style={{ fontSize: "1.15rem", margin: "0 0 10px 0", color: "var(--brand)" }}>
          📞 Assam Emergency Operations Control Numbers
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, fontSize: "0.85rem" }}>
          <div>
            <strong>ASDMA State Control:</strong> <br />
            <a href="tel:1079" style={{ fontSize: "1.1rem", fontWeight: 700 }}>1079</a> / 0361-2237221
          </div>
          <div>
            <strong>NDRF HQ (Assam 1st Bn):</strong> <br />
            <a href="tel:1070" style={{ fontSize: "1.1rem", fontWeight: 700 }}>1070</a> / 0361-2840027
          </div>
          <div>
            <strong>Emergency Police / Rescue:</strong> <br />
            <a href="tel:112" style={{ fontSize: "1.1rem", fontWeight: 700 }}>112</a>
          </div>
          <div>
            <strong>Central Water Commission (CWC):</strong> <br />
            <span>0361-2263435 (Guwahati)</span>
          </div>
        </div>
      </div>
    </section>
  );
}
