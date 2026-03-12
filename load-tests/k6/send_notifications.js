import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

// ─── Custom metrics ─────────────────────────────────────────
const notificationsQueued = new Counter("notifications_queued");
const queueDepthGauge     = new Trend("queue_depth");
const enqueueLatency      = new Trend("enqueue_latency_ms");
const successRate          = new Rate("send_success_rate");

// ─── Config ─────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Profiles selected via: k6 run -e PROFILE=light|medium|heavy
const PROFILES = {
  light: {
    stages: [
      { duration: "10s", target: 50 },
      { duration: "30s", target: 100 },
      { duration: "10s", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<500"],
      send_success_rate: ["rate>0.95"],
    },
  },
  medium: {
    stages: [
      { duration: "10s", target: 100 },
      { duration: "30s", target: 500 },
      { duration: "20s", target: 500 },
      { duration: "10s", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<1000"],
      send_success_rate: ["rate>0.90"],
    },
  },
  heavy: {
    stages: [
      { duration: "15s", target: 200 },
      { duration: "30s", target: 1000 },
      { duration: "30s", target: 1000 },
      { duration: "15s", target: 0 },
    ],
    thresholds: {
      http_req_duration: ["p(95)<2000"],
      send_success_rate: ["rate>0.80"],
    },
  },
};

const profile = PROFILES[__ENV.PROFILE || "light"];

export const options = {
  stages: profile.stages,
  thresholds: {
    ...profile.thresholds,
    http_req_failed: ["rate<0.20"],
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

// ─── Helpers ────────────────────────────────────────────────
const recipients = [
  "alice@loadtest.com", "bob@loadtest.com", "carol@loadtest.com",
  "dave@loadtest.com", "eve@loadtest.com", "frank@loadtest.com",
  "grace@loadtest.com", "heidi@loadtest.com", "ivan@loadtest.com",
  "judy@loadtest.com",
];

function randomRecipient() {
  return recipients[Math.floor(Math.random() * recipients.length)];
}

// ─── Setup: check API health ────────────────────────────────
export function setup() {
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, {
    "API is healthy": (r) => r.status === 200,
  });

  const metricsRes = http.get(`${BASE_URL}/metrics/json`);
  let initialMetrics = {};
  if (metricsRes.status === 200) {
    initialMetrics = JSON.parse(metricsRes.body);
  }

  return { startTime: Date.now(), initialMetrics };
}

// ─── Main VU loop ───────────────────────────────────────────
export default function () {
  const payload = JSON.stringify({
    channel: "email",
    recipient: randomRecipient(),
    message: `Load test notification at ${new Date().toISOString()} from VU ${__VU} iter ${__ITER}`,
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": `k6-${__VU}-${__ITER}-${Date.now()}`,
    },
  };

  const res = http.post(`${BASE_URL}/v1/notifications:send`, payload, params);

  const sent = check(res, {
    "status is 202": (r) => r.status === 202,
    "has message_id": (r) => {
      try { return JSON.parse(r.body).message_id !== undefined; }
      catch { return false; }
    },
    "status is queued": (r) => {
      try { return JSON.parse(r.body).status === "queued"; }
      catch { return false; }
    },
  });

  successRate.add(sent ? 1 : 0);
  if (sent) notificationsQueued.add(1);
  enqueueLatency.add(res.timings.duration);

  // Sample queue depth every ~10th request to avoid overloading the metrics endpoint
  if (__ITER % 10 === 0) {
    const depthRes = http.get(`${BASE_URL}/v1/queue/depth`);
    if (depthRes.status === 200) {
      try {
        const depth = JSON.parse(depthRes.body).queue_depth;
        queueDepthGauge.add(depth);
      } catch {}
    }
  }

  sleep(0.05 + Math.random() * 0.1);
}

// ─── Teardown: collect final metrics ────────────────────────
export function teardown(data) {
  const metricsRes = http.get(`${BASE_URL}/metrics/json`);
  const depthRes   = http.get(`${BASE_URL}/v1/queue/depth`);

  let finalMetrics = {};
  let finalDepth = "?";
  try { finalMetrics = JSON.parse(metricsRes.body); } catch {}
  try { finalDepth = JSON.parse(depthRes.body).queue_depth; } catch {}

  const elapsed = ((Date.now() - data.startTime) / 1000).toFixed(1);
  const initial = data.initialMetrics;

  const received  = (finalMetrics.notifications_received_total || 0) - (initial.notifications_received_total || 0);
  const queued    = (finalMetrics.notifications_queued_total || 0) - (initial.notifications_queued_total || 0);
  const processed = (finalMetrics.notifications_processed_total || 0) - (initial.notifications_processed_total || 0);
  const delivered = (finalMetrics.delivery_success_total || 0) - (initial.delivery_success_total || 0);
  const failed    = (finalMetrics.delivery_failures_total || 0) - (initial.delivery_failures_total || 0);

  console.log("\n═══════════════════════════════════════════════════════════");
  console.log("  NOTIFII LOAD TEST REPORT");
  console.log("═══════════════════════════════════════════════════════════");
  console.log(`  Profile:              ${__ENV.PROFILE || "light"}`);
  console.log(`  Duration:             ${elapsed}s`);
  console.log("───────────────────────────────────────────────────────────");
  console.log(`  Notifications sent:   ${received}`);
  console.log(`  Queued:               ${queued}`);
  console.log(`  Processed by worker:  ${processed}`);
  console.log(`  Delivered:            ${delivered}`);
  console.log(`  Failed:               ${failed}`);
  console.log(`  Current queue depth:  ${finalDepth}`);
  console.log(`  Throughput:           ${(received / elapsed).toFixed(0)} req/s`);
  console.log("───────────────────────────────────────────────────────────");
  console.log(`  Queue buffering:      ${queued - processed} messages buffered`);
  console.log(`  (Workers drain the queue after the test completes)`);
  console.log("═══════════════════════════════════════════════════════════\n");
}
