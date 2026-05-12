// HermapDashboard.jsx
// HerMap — City Planner Intelligence Dashboard
// React component. Fetches live data from your FastAPI backend every 15s.
// Usage: <HermapDashboard apiBase="http://localhost:8000" />

import { useState, useEffect, useRef } from "react";
import { Bar, Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement,
  PointElement, Filler, Tooltip, Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Filler, Tooltip, Legend);

const scoreColor = (s) => s < 40 ? "#43A047" : s < 70 ? "#FB8C00" : "#E53935";
const riskLabel  = (s) => s < 40 ? "Safe" : s < 70 ? "Caution" : "High Risk";

export default function HermapDashboard({ apiBase = "http://localhost:8000" }) {
  const [zones, setZones]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const timerRef = useRef(null);

  // ── FETCH LIVE DATA ────────────────────────────────────────────────────
  const fetchData = async () => {
    try {
      const res  = await fetch(`${apiBase}/heatmap`);
      const data = await res.json();
      setZones(data.zones || []);
      setLastUpdate(new Date().toLocaleTimeString());
      setLoading(false);
    } catch (err) {
      console.error("HerMap fetch error:", err);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, 15000);
    return () => clearInterval(timerRef.current);
  }, []);

  // ── DERIVED STATS ──────────────────────────────────────────────────────
  const highRisk   = zones.filter(z => z.risk_level === "high_risk");
  const caution    = zones.filter(z => z.risk_level === "caution");
  const totalReps  = zones.reduce((sum, z) => sum + z.report_count, 0);
  const sorted     = [...zones].sort((a, b) => b.score - a.score);

  // ── CHART DATA ─────────────────────────────────────────────────────────
  const barData = {
    labels: sorted.slice(0, 8).map(z => z.zone_id.split("_")[0]),
    datasets: [{
      label: "Risk Score",
      data: sorted.slice(0, 8).map(z => z.score.toFixed(1)),
      backgroundColor: sorted.slice(0, 8).map(z => scoreColor(z.score)),
      borderRadius: 6,
      barThickness: 32,
    }],
  };

  const barOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      y: { min: 0, max: 100, grid: { color: "rgba(0,0,0,0.05)" }, ticks: { font: { size: 11 } } },
      x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    },
  };

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "24px", background: "#F8F4F6", minHeight: "100vh" }}>

      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#D81B60" }} />
          <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>HerMap — City Intelligence</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {lastUpdate && <span style={{ fontSize: 12, color: "#888" }}>Updated {lastUpdate}</span>}
          <span style={{ fontSize: 12, padding: "4px 10px", borderRadius: 20, background: "#E8F5E9", color: "#2E7D32", fontWeight: 500 }}>
            ● Live
          </span>
          <button
            onClick={fetchData}
            style={{ fontSize: 12, padding: "5px 14px", borderRadius: 8, border: "1px solid #ddd", background: "white", cursor: "pointer" }}
          >
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: "#888" }}>Connecting to HerMap API...</div>
      ) : (
        <>
          {/* ── Metrics ── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
            {[
              { label: "Active zones", value: zones.length, sub: "monitored" },
              { label: "High risk", value: highRisk.length, sub: "score ≥ 70", color: "#E53935" },
              { label: "Caution zones", value: caution.length, sub: "score 40–69", color: "#FB8C00" },
              { label: "Total reports", value: totalReps, sub: "community inputs" },
            ].map(({ label, value, sub, color }) => (
              <div key={label} style={{ background: "white", borderRadius: 12, padding: "16px 20px", border: "1px solid #eee" }}>
                <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 26, fontWeight: 600, color: color || "#1A1A2E" }}>{value}</div>
                <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>{sub}</div>
              </div>
            ))}
          </div>

          {/* ── Alerts ── */}
          {highRisk.length > 0 && (
            <div style={{ background: "#FFEBEE", border: "1px solid #FFCDD2", borderRadius: 12, padding: "16px 20px", marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#C62828", marginBottom: 10 }}>
                ⚠ {highRisk.length} high-risk zone{highRisk.length > 1 ? "s" : ""} — PCR auto-notified
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {highRisk.map(z => (
                  <span key={z.zone_id} style={{ fontSize: 12, padding: "4px 12px", borderRadius: 16, background: "#E53935", color: "white" }}>
                    {z.zone_id} — {z.score.toFixed(0)}/100
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ── Charts ── */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 20 }}>
            <div style={{ background: "white", borderRadius: 12, padding: "20px", border: "1px solid #eee" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 16 }}>
                Top zones by risk score
              </div>
              {zones.length === 0 ? (
                <div style={{ textAlign: "center", padding: 40, color: "#bbb", fontSize: 13 }}>
                  No reports yet. Submit reports via the app to see data here.
                </div>
              ) : (
                <Bar data={barData} options={barOptions} height={180} />
              )}
            </div>

            <div style={{ background: "white", borderRadius: 12, padding: "20px", border: "1px solid #eee" }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
                Zone breakdown
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {[
                  { label: "Safe zones", count: zones.filter(z => z.risk_level === "safe").length, color: "#43A047", total: zones.length },
                  { label: "Caution zones", count: caution.length, color: "#FB8C00", total: zones.length },
                  { label: "High risk", count: highRisk.length, color: "#E53935", total: zones.length },
                ].map(({ label, count, color, total }) => (
                  <div key={label}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
                      <span style={{ color: "#555" }}>{label}</span>
                      <span style={{ fontWeight: 600 }}>{count}</span>
                    </div>
                    <div style={{ height: 6, background: "#f0f0f0", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${total ? (count / total) * 100 : 0}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.5s" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ── Zone Table ── */}
          <div style={{ background: "white", borderRadius: 12, border: "1px solid #eee", overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #f0f0f0", fontSize: 12, fontWeight: 600, color: "#888", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              All zones
            </div>
            {sorted.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: "#bbb", fontSize: 13 }}>
                No zone data yet. Start submitting reports via the Flutter app.
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#fafafa" }}>
                    {["Zone ID", "Coordinates", "Score", "Risk Level", "Reports"].map(h => (
                      <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontSize: 11, color: "#aaa", fontWeight: 500 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(z => (
                    <tr key={z.zone_id} style={{ borderTop: "1px solid #f5f5f5" }}>
                      <td style={{ padding: "12px 20px", fontFamily: "monospace", fontSize: 12, color: "#555" }}>{z.zone_id}</td>
                      <td style={{ padding: "12px 20px", color: "#888", fontSize: 12 }}>{z.latitude.toFixed(3)}, {z.longitude.toFixed(3)}</td>
                      <td style={{ padding: "12px 20px", fontWeight: 600, color: scoreColor(z.score) }}>{z.score.toFixed(1)}</td>
                      <td style={{ padding: "12px 20px" }}>
                        <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 12, background: scoreColor(z.score) + "22", color: scoreColor(z.score), fontWeight: 500 }}>
                          {riskLabel(z.score)}
                        </span>
                      </td>
                      <td style={{ padding: "12px 20px", color: "#555" }}>{z.report_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
