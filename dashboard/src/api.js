const BASE = "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  return res.json();
}

export const api = {
  health: () => request("/health"),
  config: () => request("/internal/config"),
  metrics: () => request("/metrics/json"),
  queueDepth: () => request("/v1/queue/depth"),
  dlqMessages: (count = 20) => request(`/v1/queue/dlq?count=${count}`),
  recentNotifications: (count = 20) => request(`/v1/notifications/recent?count=${count}`),
  retryDlq: (entryId) => request(`/v1/queue/dlq/${entryId}/retry`, { method: "POST" }),
  sendNotification: (payload) =>
    request("/v1/notifications:send", { method: "POST", body: JSON.stringify(payload) }),
  simulateFailure: (enable) =>
    request(`/internal/simulate/provider-failure?enable=${enable}`, { method: "POST" }),
  simulateSlow: (enable) =>
    request(`/internal/simulate/slow-delivery?enable=${enable}`, { method: "POST" }),
  demoSeed: () => request("/demo/seed", { method: "POST" }),
  demoSendTest: (recipient, message) =>
    request(`/demo/send-test?recipient=${encodeURIComponent(recipient)}&message=${encodeURIComponent(message)}`, { method: "POST" }),
  demoActivity: (limit = 50) => request(`/demo/activity?limit=${limit}`),
};
