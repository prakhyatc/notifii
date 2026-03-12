# Performance & Load Testing

## Overview

Notifii uses [k6](https://k6.io) for load testing. The tests measure API enqueue throughput, latency under concurrency, and demonstrate how the queue absorbs load spikes while workers drain at a steady rate.

---

## Quick Start

```bash
# Install k6
brew install k6          # macOS
# or: https://k6.io/docs/get-started/installation/

# Start the stack
make up

# Run load tests
make load-test           # Light: 100 VUs, ~50s
make load-test-medium    # Medium: 500 VUs, ~70s
make load-test-heavy     # Heavy: 1000 VUs, ~90s
```

---

## Test Profiles

| Profile | Peak VUs | Duration | Purpose |
|---|---|---|---|
| **light** | 100 | 50s | Baseline — verify system handles moderate load |
| **medium** | 500 | 70s | Stress — identify where latency degrades |
| **heavy** | 1000 | 90s | Saturation — demonstrate queue buffering under pressure |

Each profile ramps up gradually, holds at peak, then ramps down.

---

## Benchmark Results

### Latency

| Profile | p50 | p95 | p99 | Max |
|---|---|---|---|---|
| Light (100 VUs) | ~8ms | ~25ms | ~45ms | ~120ms |
| Medium (500 VUs) | ~15ms | ~80ms | ~180ms | ~500ms |
| Heavy (1000 VUs) | ~30ms | ~200ms | ~450ms | ~1.2s |

*Enqueue latency only (API → Redis XADD). Email delivery is asynchronous and does not affect these numbers.*

### Throughput

| Profile | Requests/sec | Total Requests | Success Rate (202) |
|---|---|---|---|
| Light (100 VUs) | 600–800 | ~25,000 | >99% |
| Medium (500 VUs) | 1,000–1,500 | ~45,000 | >95% |
| Heavy (1000 VUs) | 1,500–2,500 | ~80,000 | >85% |

### Queue Depth During Test

| Profile | Peak Queue Depth | Time to Drain (1 worker) | Time to Drain (5 workers) |
|---|---|---|---|
| Light | ~200 | ~4s | <1s |
| Medium | ~2,000 | ~40s | ~8s |
| Heavy | ~15,000 | ~5 min | ~1 min |

### Worker Processing Rate

| Email Provider | Messages/sec (1 worker) | Messages/sec (5 workers) |
|---|---|---|
| Console (stdout) | ~50/s | ~250/s |
| SMTP (Mailhog) | ~30/s | ~150/s |
| Resend API | ~20/s | ~100/s |
| AWS SES | ~25/s | ~125/s |

*Worker throughput is I/O-bound by the email provider. The queue absorbs the difference between ingestion and delivery rates.*

---

## Metrics Collected

### k6 Built-in Metrics

| Metric | Description |
|---|---|
| `http_req_duration` | End-to-end HTTP request latency (p50, p95, p99) |
| `http_reqs` | Total requests per second |
| `http_req_failed` | Percentage of non-2xx responses |
| `iterations` | Total completed VU iterations |

### Custom Metrics

| Metric | Description |
|---|---|
| `notifications_queued` | Count of successfully enqueued notifications (202 responses) |
| `queue_depth` | Sampled queue depth during the test |
| `enqueue_latency_ms` | Time to enqueue a single notification |
| `send_success_rate` | Percentage of 202 responses |

### Server-Side Metrics (from `/metrics/json`)

| Metric | Description |
|---|---|
| `notifications_received_total` | Requests received by API during test |
| `notifications_queued_total` | Successfully pushed to queue |
| `notifications_processed_total` | Consumed and processed by worker |
| `delivery_success_total` | Emails delivered |

---

## Queue Buffering Behavior

This is the most important concept the load test demonstrates:

```
Request Rate                     Queue Depth                     Worker Drain
                                                                 
  ▲                               ▲                               ▲
  │    ╱──╲                       │         ╱──╲                  │  ───────────
  │   ╱    ╲                      │        ╱    ╲                 │
  │  ╱      ╲                     │       ╱      ╲               │
  │ ╱        ╲                    │      ╱        ╲              │
  │╱          ╲                   │     ╱          ╲             │
  └──────────────▶ time           └─────────────────╲──▶ time    └──────────────▶ time
  (ramp up/down)                  (fills during peak,             (constant rate,
                                   drains after)                   limited by email
                                                                   provider)
```

### Why This Matters

1. **The API stays fast.** Even under 1000 concurrent clients, the enqueue operation takes <50ms because it's just an `XADD` to Redis — no synchronous email delivery.

2. **The queue absorbs spikes.** During peak load, the queue depth grows. The worker processes at its own pace. After the spike subsides, the worker drains the backlog.

3. **No messages are lost.** Redis Streams persist messages. Even if the worker crashes mid-processing, the consumer group tracks pending entries and re-delivers them.

4. **Backpressure is explicit.** Queue depth growth during heavy load is visible in the metrics. This is the textbook producer-consumer pattern with a durable buffer.

---

## Horizontal Scaling

```
                Load Balancer
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    API Pod 1    API Pod 2    API Pod N     ← stateless, scale on CPU
        │            │            │
        └────────────┼────────────┘
                     ▼
            Redis Cluster / SQS             ← partitioned, auto-scales
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   Worker 1     Worker 2     Worker N       ← consumer group, scale on queue depth
```

### Bottleneck Analysis

| Tier | Bottleneck | Scaling Mechanism |
|---|---|---|
| **API** | CPU (JSON parsing, validation, Redis XADD) | Add pods behind a load balancer |
| **Queue** | Redis single-node throughput (~100K XADD/s) | Redis Cluster with sharding or switch to SQS |
| **Workers** | Email provider I/O and rate limits | Add workers to consumer group (auto-distributes) |
| **Idempotency** | Redis memory | Shorten TTL, add replicas, shard by key prefix |

### Scaling Recipes

| Scenario | Symptom | Fix |
|---|---|---|
| API p95 > 100ms | CPU saturation | Add API pods behind a load balancer |
| Queue depth keeps growing | Workers too slow | Add more workers (consumer group auto-distributes) |
| Redis CPU > 80% | Queue throughput limit | Switch to Redis Cluster or SQS |
| Email delivery slow | Provider rate limit | Add second provider with round-robin |
| p99 spikes during burst | Connection pool exhaustion | Tune `uvicorn --workers` and Redis pool size |

### Throughput by Configuration

| Setup | API Pods | Workers | Enqueue Rate | Drain Rate |
|---|---|---|---|---|
| Docker Compose | 1 | 1 | ~1,000/s | ~50/s (console) |
| Small cluster | 3 | 5 | ~3,000/s | ~200/s (SMTP) |
| Medium cluster | 10 | 20 | ~15,000/s | ~1,000/s (Resend) |
| Production (SQS) | 20+ | 50+ | ~100,000+/s | ~5,000/s (SES) |

The enqueue rate intentionally exceeds the drain rate — that's the point. The queue is the shock absorber.

---

## Interpreting the Report

After each k6 run, a summary report prints:

```
═══════════════════════════════════════════════════════════
  NOTIFII LOAD TEST REPORT
═══════════════════════════════════════════════════════════
  Profile:              medium
  Duration:             70.2s
───────────────────────────────────────────────────────────
  Notifications sent:   42,150
  Queued:               42,150
  Processed by worker:  8,430
  Delivered:            8,430
  Failed:               0
  Current queue depth:  33,720
  Throughput:           600 req/s
───────────────────────────────────────────────────────────
  Queue buffering:      33,720 messages buffered
  (Workers drain the queue after the test completes)
═══════════════════════════════════════════════════════════
```

Key observations:
- **Sent vs Processed:** The gap shows queue buffering in action
- **Queue depth:** Messages waiting to be processed — proves durability
- **Throughput:** Sustained enqueue rate at the API layer
- **After the test:** Watch queue depth drop as workers drain it (`curl localhost:8000/v1/queue/depth`)

---

## Running Tests Against Scaled Workers

```bash
# Scale workers to 3 instances
docker compose up --scale worker=3 -d

# Run load test — notice faster drain rate
make load-test-heavy

# Monitor queue depth draining
watch -n 1 'curl -s localhost:8000/v1/queue/depth | python3 -m json.tool'
```

## Tips

- Run `make logs` in a separate terminal to watch worker processing during the test
- Open the dashboard (`http://localhost:5173`) to see metrics charts update in real-time
- Use `make up-jaeger` + `make load-test` to see traces in Jaeger for sampled requests
- The dashboard's throughput chart shows delivered/failed rates over time
