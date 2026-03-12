import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { api } from "./api";

const TABS = ["Overview", "Playground", "Dead Letter Queue"];
const PIE_COLORS = ["#22c55e", "#ef4444", "#f59e0b"];

function StatusBadge({ ok }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: ok ? "var(--success)" : "var(--error)",
        marginRight: 8,
        boxShadow: ok ? "0 0 8px var(--success)" : "0 0 8px var(--error)",
      }}
    />
  );
}

function Card({ title, children, style }) {
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "20px 24px", ...style }}>
      {title && (
        <h3 style={{ fontSize: 14, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

function MetricCard({ label, value, color }) {
  return (
    <Card>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color: color || "var(--text)", fontVariantNumeric: "tabular-nums" }}>
        {value ?? "..."}
      </div>
    </Card>
  );
}

function Button({ children, onClick, variant = "primary", disabled, style }) {
  const colors = {
    primary: { bg: "var(--accent)", text: "#fff" },
    danger: { bg: "var(--error)", text: "#fff" },
    success: { bg: "var(--success)", text: "#fff" },
    ghost: { bg: "transparent", text: "var(--text-muted)" },
  };
  const c = colors[variant] || colors.primary;
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: c.bg, color: c.text,
        border: variant === "ghost" ? "1px solid var(--border)" : "none",
        borderRadius: "var(--radius-sm)", padding: "8px 16px",
        fontSize: 13, fontWeight: 500,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "all 0.15s", ...style,
      }}
    >
      {children}
    </button>
  );
}

function Tab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? "var(--accent)" : "transparent",
        color: active ? "#fff" : "var(--text-muted)",
        border: active ? "none" : "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        padding: "8px 20px", fontSize: 13, fontWeight: 500,
        cursor: "pointer", transition: "all 0.15s",
      }}
    >
      {label}
    </button>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", fontSize: 12 }}>
      <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>{p.name}: {p.value}</div>
      ))}
    </div>
  );
}

function OverviewTab({ metricsData, queueDepth, metricsHistory, recent }) {
  const delivered = Number(metricsData.delivery_success_total || 0);
  const failed = Number(metricsData.delivery_failures_total || 0);
  const duplicates = Number(metricsData.idempotency_duplicates_total || 0);
  const pieData = [
    { name: "Delivered", value: delivered || 0 },
    { name: "Failed", value: failed || 0 },
    { name: "Duplicates", value: duplicates || 0 },
  ].filter(d => d.value > 0);

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16, marginBottom: 32 }}>
        <MetricCard label="Queue Depth" value={queueDepth} color="var(--accent)" />
        <MetricCard label="Received" value={metricsData.notifications_received_total} />
        <MetricCard label="Queued" value={metricsData.notifications_queued_total} />
        <MetricCard label="Processed" value={metricsData.notifications_processed_total} color="var(--success)" />
        <MetricCard label="Failures" value={metricsData.delivery_failures_total} color="var(--error)" />
        <MetricCard label="Duplicates" value={metricsData.idempotency_duplicates_total} color="var(--warning)" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24, marginBottom: 32 }}>
        <Card title="Throughput (last 60 samples)">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={metricsHistory}>
              <defs>
                <linearGradient id="gSuccess" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gFail" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
              <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="delivered" stroke="#22c55e" fill="url(#gSuccess)" name="Delivered" />
              <Area type="monotone" dataKey="failed" stroke="#ef4444" fill="url(#gFail)" name="Failed" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Delivery Breakdown">
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 220, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: 13 }}>
              No data yet. Send a notification to see stats.
            </div>
          )}
          <div style={{ display: "flex", gap: 16, justifyContent: "center", marginTop: 8 }}>
            {[{ label: "Delivered", color: PIE_COLORS[0] }, { label: "Failed", color: PIE_COLORS[1] }, { label: "Duplicates", color: PIE_COLORS[2] }].map(l => (
              <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-muted)" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: l.color, display: "inline-block" }} />
                {l.label}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Queue Depth Over Time">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={metricsHistory}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
            <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} allowDecimals={false} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="queueDepth" fill="var(--accent)" radius={[4, 4, 0, 0]} name="Queue Depth" />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title={`Recent Notifications (${recent.length})`} style={{ marginTop: 24 }}>
        {recent.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No notifications processed yet.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Message ID", "Recipient", "Channel", "Status", "Time"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-muted)", fontWeight: 500, fontSize: 11, textTransform: "uppercase" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map((n, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11 }}>{n.message_id?.slice(0, 12)}...</td>
                    <td style={{ padding: "8px 12px" }}>{n.recipient}</td>
                    <td style={{ padding: "8px 12px" }}>{n.channel}</td>
                    <td style={{ padding: "8px 12px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: n.status === "delivered" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                        color: n.status === "delivered" ? "var(--success)" : "var(--error)",
                      }}>
                        {n.status}
                      </span>
                    </td>
                    <td style={{ padding: "8px 12px", color: "var(--text-muted)", fontSize: 11 }}>
                      {n.processed_at ? new Date(n.processed_at * 1000).toLocaleTimeString() : "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

function PlaygroundTab({ simFailure, simSlow, setSimFailure, setSimSlow, refresh }) {
  const [recipient, setRecipient] = useState("demo@example.com");
  const [message, setMessage] = useState("Hello from Notifii playground!");
  const [result, setResult] = useState(null);
  const [seedResult, setSeedResult] = useState(null);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(false);

  const refreshActivity = useCallback(async () => {
    try {
      const a = await api.demoActivity(30);
      setActivity(a?.activity || []);
    } catch {}
  }, []);

  useEffect(() => {
    refreshActivity();
    const id = setInterval(refreshActivity, 3000);
    return () => clearInterval(id);
  }, [refreshActivity]);

  const handleSend = async () => {
    setLoading(true);
    try {
      const r = await api.demoSendTest(recipient, message);
      setResult(r);
      setTimeout(() => { refresh(); refreshActivity(); }, 1000);
    } finally { setLoading(false); }
  };

  const handleSeed = async () => {
    setLoading(true);
    try {
      const r = await api.demoSeed();
      setSeedResult(r);
      setTimeout(() => { refresh(); refreshActivity(); }, 1000);
    } finally { setLoading(false); }
  };

  const toggleFailure = async () => {
    const next = !simFailure;
    await api.simulateFailure(next);
    setSimFailure(next);
  };

  const toggleSlow = async () => {
    const next = !simSlow;
    await api.simulateSlow(next);
    setSimSlow(next);
  };

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginBottom: 24 }}>
        <Card title="Send Notification">
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>Recipient</label>
            <input
              value={recipient} onChange={e => setRecipient(e.target.value)}
              style={{
                width: "100%", padding: "8px 12px", background: "var(--bg)",
                border: "1px solid var(--border)", borderRadius: "var(--radius-sm)",
                color: "var(--text)", fontSize: 13, outline: "none",
              }}
            />
          </div>
          <div style={{ marginBottom: 12 }}>
            <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>Message</label>
            <textarea
              value={message} onChange={e => setMessage(e.target.value)} rows={3}
              style={{
                width: "100%", padding: "8px 12px", background: "var(--bg)",
                border: "1px solid var(--border)", borderRadius: "var(--radius-sm)",
                color: "var(--text)", fontSize: 13, outline: "none", resize: "vertical",
                fontFamily: "inherit",
              }}
            />
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <Button onClick={handleSend} disabled={loading}>Send Notification</Button>
            <Button onClick={handleSeed} variant="ghost" disabled={loading}>Seed 5 Examples</Button>
          </div>
          {result && (
            <pre style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg)", padding: 12, borderRadius: "var(--radius-sm)", overflow: "auto", marginTop: 12 }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
          {seedResult && (
            <pre style={{ fontSize: 11, color: "var(--text-muted)", background: "var(--bg)", padding: 12, borderRadius: "var(--radius-sm)", overflow: "auto", marginTop: 12 }}>
              Seeded {seedResult.count} notifications
            </pre>
          )}
        </Card>

        <Card title="Failure Simulation">
          <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
            Toggle these to simulate real-world delivery failures. Watch messages move to the Dead Letter Queue and observe retry behavior.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Button onClick={toggleFailure} variant={simFailure ? "danger" : "ghost"} style={{ width: "100%", textAlign: "left" }}>
              {simFailure ? "Provider Failure: ON — messages will fail" : "Provider Failure: OFF"}
            </Button>
            <Button onClick={toggleSlow} variant={simSlow ? "danger" : "ghost"} style={{ width: "100%", textAlign: "left" }}>
              {simSlow ? "Slow Delivery: ON — 5s delay per message" : "Slow Delivery: OFF"}
            </Button>
          </div>
          <div style={{ marginTop: 16, padding: 12, background: "var(--bg)", borderRadius: "var(--radius-sm)", fontSize: 12, color: "var(--text-muted)" }}>
            <strong style={{ color: "var(--text)" }}>Try this flow:</strong><br />
            1. Enable provider failure<br />
            2. Send a notification<br />
            3. Watch it appear in the DLQ tab<br />
            4. Disable failure, then retry from DLQ<br />
            5. Watch it deliver successfully
          </div>
        </Card>
      </div>

      <Card title={`Demo Activity Log (${activity.length})`}>
        {activity.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No demo activity yet. Send a notification or seed data above.</p>
        ) : (
          <div style={{ overflowX: "auto", maxHeight: 300, overflowY: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Action", "Message ID", "Recipient", "Time"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-muted)", fontWeight: 500, fontSize: 11, textTransform: "uppercase", position: "sticky", top: 0, background: "var(--surface)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...activity].reverse().map((a, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "8px 12px" }}>
                      <span style={{
                        padding: "2px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
                        background: a.action === "seed" ? "rgba(108,99,255,0.15)" : "rgba(34,197,94,0.15)",
                        color: a.action === "seed" ? "var(--accent)" : "var(--success)",
                      }}>
                        {a.action}
                      </span>
                    </td>
                    <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11 }}>{a.message_id?.slice(0, 12)}...</td>
                    <td style={{ padding: "8px 12px" }}>{a.recipient}</td>
                    <td style={{ padding: "8px 12px", color: "var(--text-muted)", fontSize: 11 }}>{new Date(a.timestamp).toLocaleTimeString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

function DlqTab({ dlq, refresh }) {
  const handleRetry = async (entryId) => {
    await api.retryDlq(entryId);
    setTimeout(refresh, 500);
  };

  return (
    <Card title={`Dead Letter Queue (${dlq.length})`}>
      {dlq.length === 0 ? (
        <div style={{ textAlign: "center", padding: "48px 0" }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>&#10003;</div>
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>DLQ is empty. All messages processed successfully.</p>
          <p style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 8 }}>
            Enable "Provider Failure" in the Playground tab, send a notification, and watch it appear here.
          </p>
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Entry ID", "Message ID", "Recipient", "Message", "Failed At", "Action"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "var(--text-muted)", fontWeight: 500, fontSize: 11, textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dlq.map((d, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11 }}>{d.id?.slice(0, 16)}</td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11 }}>{d.body?.message_id?.slice(0, 12)}...</td>
                  <td style={{ padding: "8px 12px" }}>{d.body?.recipient}</td>
                  <td style={{ padding: "8px 12px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.body?.message}</td>
                  <td style={{ padding: "8px 12px", color: "var(--text-muted)", fontSize: 11 }}>
                    {d.failed_at ? new Date(parseFloat(d.failed_at) * 1000).toLocaleTimeString() : "\u2014"}
                  </td>
                  <td style={{ padding: "8px 12px" }}>
                    <Button onClick={() => handleRetry(d.id)} variant="success" style={{ padding: "4px 12px", fontSize: 11 }}>
                      Retry
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function App() {
  const [tab, setTab] = useState("Overview");
  const [health, setHealth] = useState(null);
  const [config, setConfig] = useState(null);
  const [metricsData, setMetrics] = useState({});
  const [queueDepth, setQueueDepth] = useState(null);
  const [dlq, setDlq] = useState([]);
  const [recent, setRecent] = useState([]);
  const [simFailure, setSimFailure] = useState(false);
  const [simSlow, setSimSlow] = useState(false);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const prevMetrics = useRef({});

  const refresh = useCallback(async () => {
    try {
      const [h, c, m, q, d, r] = await Promise.all([
        api.health().catch(() => null),
        api.config().catch(() => null),
        api.metrics().catch(() => ({})),
        api.queueDepth().catch(() => ({ queue_depth: "?" })),
        api.dlqMessages().catch(() => ({ dlq_messages: [] })),
        api.recentNotifications().catch(() => ({ notifications: [] })),
      ]);
      setHealth(h);
      setConfig(c);
      setMetrics(m);
      setQueueDepth(q?.queue_depth);
      setDlq(d?.dlq_messages || []);
      setRecent(r?.notifications || []);
      if (c) { setSimFailure(c.simulate_provider_failure); setSimSlow(c.simulate_slow_delivery); }

      const prev = prevMetrics.current;
      const newDelivered = Number(m.delivery_success_total || 0) - Number(prev.delivery_success_total || 0);
      const newFailed = Number(m.delivery_failures_total || 0) - Number(prev.delivery_failures_total || 0);
      prevMetrics.current = m;

      setMetricsHistory(hist => {
        const next = [...hist, {
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          delivered: Math.max(0, newDelivered),
          failed: Math.max(0, newFailed),
          queueDepth: Number(q?.queue_depth || 0),
        }];
        return next.slice(-60);
      });
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "32px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 28, marginBottom: 4 }}>
            Notifii <span style={{ fontSize: 14, color: "var(--text-muted)", fontWeight: 400 }}>Dashboard</span>
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
            <StatusBadge ok={health?.status === "ok"} />
            {health?.status === "ok" ? "System Operational" : "Connecting..."}
            {config && (
              <span style={{ marginLeft: 16, opacity: 0.7 }}>
                Queue: {config.queue_backend} &middot; Email: {config.email_provider} &middot; Demo: {config.demo_mode ? "on" : "off"}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={refresh} variant="ghost">Refresh</Button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        {TABS.map(t => (
          <Tab key={t} label={t} active={tab === t} onClick={() => setTab(t)} />
        ))}
      </div>

      {tab === "Overview" && (
        <OverviewTab metricsData={metricsData} queueDepth={queueDepth} metricsHistory={metricsHistory} recent={recent} />
      )}
      {tab === "Playground" && (
        <PlaygroundTab simFailure={simFailure} simSlow={simSlow} setSimFailure={setSimFailure} setSimSlow={setSimSlow} refresh={refresh} />
      )}
      {tab === "Dead Letter Queue" && (
        <DlqTab dlq={dlq} refresh={refresh} />
      )}

      <div style={{ textAlign: "center", marginTop: 48, paddingBottom: 32, color: "var(--text-muted)", fontSize: 12 }}>
        Notifii &mdash; Cloud-Agnostic Notification Platform &middot; Event-Driven &middot; Queue-Backed &middot; Idempotent
      </div>
    </div>
  );
}
