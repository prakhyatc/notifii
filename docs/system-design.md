# System Design: Notification Platform

> This document explains Notifii as a system design case study — the kind of problem discussed in backend engineering interviews at companies like Stripe, Twilio, or Datadog.

---

## Problem Statement

Design a notification delivery platform that accepts requests via HTTP, delivers messages asynchronously through pluggable providers, and guarantees no message is lost even when providers fail.

The system must handle bursty traffic (e.g., a marketing campaign sending 100K emails in minutes) without degrading API response times or dropping messages.

---

## Functional Requirements

| # | Requirement |
|---|---|
| F1 | Accept notification requests via REST API |
| F2 | Validate input (channel, recipient, message body) |
| F3 | Return 202 Accepted immediately — delivery is asynchronous |
| F4 | Deliver via pluggable email providers (SMTP, Resend, SES) |
| F5 | Retry failed deliveries with exponential backoff |
| F6 | Route permanently failed messages to a Dead Letter Queue |
| F7 | Expose DLQ contents and support manual retry |
| F8 | Prevent duplicate sends via idempotency keys |
| F9 | Provide queue depth, delivery metrics, and recent notification history |

## Non-Functional Requirements

| # | Requirement | Target |
|---|---|---|
| NF1 | API latency (p99) | < 50ms for enqueue |
| NF2 | Throughput | 1,000+ enqueues/sec per API instance |
| NF3 | Durability | Zero message loss — queue persists to disk |
| NF4 | Availability | Graceful degradation; queue absorbs provider outages |
| NF5 | Scalability | Horizontal scaling at API and worker tiers |
| NF6 | Observability | Structured logs, metrics, distributed traces |
| NF7 | Portability | Run locally with Docker or on AWS with Terraform — same code |

---

## High-Level Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │               Ingress Plane                 │
 Client ──HTTP──▶  │  FastAPI  →  Validation  →  Idempotency     │
                    │                              Check          │
                    └──────────────────┬──────────────────────────┘
                                       │ XADD
                    ┌──────────────────▼──────────────────────────┐
                    │              Message Queue                   │
                    │      Redis Streams  /  AWS SQS               │
                    │   (consumer groups, persistence, ordering)    │
                    └──────────────────┬──────────────────────────┘
                                       │ XREADGROUP
                    ┌──────────────────▼──────────────────────────┐
                    │             Delivery Plane                   │
                    │  Worker 1 ─┐                                 │
                    │  Worker 2 ─┤──▶ Email Provider (SMTP/SES)   │
                    │  Worker N ─┘                                 │
                    │              │                                │
                    │              └──▶ DLQ (after max retries)    │
                    └─────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Role |
|---|---|
| **FastAPI API** | HTTP ingress. Validates requests, checks idempotency, enqueues to the message queue. Returns 202 immediately. |
| **Message Queue** | Durable buffer between API and workers. Redis Streams (local/free) or SQS (production). Consumer groups ensure each message is processed by exactly one worker. |
| **Worker Pool** | Consumes messages, delivers via the configured email adapter, ACKs on success. On failure, messages are retried up to a max count, then moved to DLQ. |
| **Dead Letter Queue** | Stores messages that exceed retry limits. Accessible via API for inspection and manual retry. |
| **Idempotency Store** | Redis-backed (or in-memory) store keyed by client-provided idempotency keys. Prevents re-enqueuing duplicate requests. |

---

## Data Flow

### Happy Path

```
1. Client sends POST /v1/notifications:send with idempotency_key
2. API validates the payload (Pydantic schema)
3. API checks idempotency store:
   - Key exists → return original message_id (202)
   - Key absent → store key, generate message_id
4. API enqueues message to Redis Streams (XADD)
5. API returns 202 { message_id, status: "queued" }
6. Worker reads message via XREADGROUP (consumer group)
7. Worker delivers email through the configured adapter
8. Worker ACKs the message (XACK) on success
9. Worker updates idempotency status → "delivered"
```

### Failure Path

```
1. Worker attempts delivery → provider returns error
2. Worker does NOT ACK the message
3. Redis Streams marks the message as pending (PEL)
4. On next poll, the worker reclaims the pending message
5. After N retries, worker moves message to the DLQ stream
6. Operator inspects DLQ via dashboard or GET /v1/queue/dlq
7. Operator fixes the issue and triggers POST /v1/queue/dlq/{id}/retry
8. Message is re-enqueued to the main stream for reprocessing
```

---

## Key Design Decisions

### 1. Async Enqueue (202 vs 200)

**Decision:** API returns 202 immediately after enqueuing. Delivery is asynchronous.

**Why:** Email providers have variable latency (50ms–5s). Synchronous delivery would make API latency unpredictable and tie up connections during provider slowdowns. The queue decouples ingress speed from delivery speed.

**Tradeoff:** Clients don't get immediate delivery confirmation. They can poll `/v1/notifications/recent` or rely on idempotency keys.

### 2. Adapter Pattern for All External Dependencies

**Decision:** Queue, email, and idempotency each have an abstract base class (ABC). Concrete implementations are selected at startup via environment variables.

```
QueueAdapter (ABC)
├── RedisQueueAdapter     ← QUEUE_BACKEND=redis
├── SQSAdapter            ← QUEUE_BACKEND=sqs
└── MemoryQueueAdapter    ← QUEUE_BACKEND=memory

EmailAdapter (ABC)
├── ConsoleAdapter        ← EMAIL_PROVIDER=console
├── SMTPAdapter           ← EMAIL_PROVIDER=smtp
├── ResendAdapter         ← EMAIL_PROVIDER=resend
└── SESAdapter            ← EMAIL_PROVIDER=ses
```

**Why:** Same code runs locally (Redis + Mailhog) and in production (SQS + SES). Tests use memory backends with zero infrastructure. Adding a new provider is one file and one factory case.

**Tradeoff:** More files and indirection vs. a monolithic implementation. Worth it for testability and portability.

### 3. Redis Streams over Pub/Sub or Lists

**Decision:** Use Redis Streams (not Redis Lists or Pub/Sub) as the queue backend.

**Why:**
- **Consumer groups** — multiple workers get unique messages automatically
- **Persistence** — messages survive Redis restarts (AOF/RDB)
- **Acknowledgment** — XACK tracks which messages are processed; unACKed messages are reclaimed
- **Ordering** — messages are ordered by stream ID

**Tradeoff:** More complex than `LPUSH/BRPOP` but provides durability guarantees that Lists cannot.

### 4. Client-Side Idempotency Keys

**Decision:** Clients provide an `idempotency_key`. The API stores it in Redis with a 24h TTL using atomic `SET NX`.

**Why:** Network retries, load balancer replays, and client bugs can all cause duplicate requests. Server-generated deduplication (e.g., hashing the payload) is fragile — two legitimately identical notifications would be incorrectly deduplicated.

**Tradeoff:** Requires client cooperation. Not all callers will send idempotency keys. Without one, the system does not deduplicate.

### 5. DLQ as a Separate Stream

**Decision:** Failed messages are moved to a dedicated Redis Stream (`notifii:dlq`) after exhausting retries, rather than being dropped or left in the pending entries list.

**Why:**
- Failed messages don't block the main queue
- Operators can inspect failures without affecting live traffic
- Manual retry re-enqueues to the main stream, re-entering the normal processing pipeline

**Tradeoff:** Requires monitoring. An unattended DLQ can grow indefinitely.

---

## Failure Handling

| Failure Mode | Behavior |
|---|---|
| **Email provider timeout** | Worker retries with backoff. After max retries → DLQ. |
| **Email provider down** | Queue absorbs all incoming messages. Workers retry on each poll cycle. No messages are lost. |
| **Worker crash mid-processing** | Consumer group tracks the message as pending. Next healthy worker reclaims it. |
| **API crash after enqueue** | Client already received 202. Message is in the queue. Worker delivers it. |
| **Redis crash** | AOF persistence recovers messages. In production, use Redis Cluster or switch to SQS. |
| **Duplicate request** | Idempotency key returns original message_id. No re-enqueue. |
| **Invalid payload** | Pydantic validation returns 400 before any enqueue. |
| **Rate limit exceeded** | API returns 429. Client retries with backoff. |

---

## Scaling Strategy

### Horizontal Scaling Points

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

| Tier | Scaling Trigger | Mechanism |
|---|---|---|
| API | p99 latency > 50ms or CPU > 70% | Add pods behind load balancer |
| Queue | Approaching single-node throughput limit | Redis Cluster (shard by channel) or SQS (unlimited) |
| Workers | Queue depth growing faster than drain rate | Add workers to consumer group — messages auto-distribute |
| Idempotency | Memory pressure on Redis | Shorten TTL, add Redis replicas, shard by key prefix |

### Throughput Estimates

| Configuration | Enqueue Rate | Drain Rate | Queue Steady-State |
|---|---|---|---|
| 1 API + 1 Worker (Docker Compose) | ~1,000/s | ~50/s | Queue grows during bursts, drains after |
| 3 API + 5 Workers | ~3,000/s | ~250/s | Handles sustained traffic |
| 10 API + 20 Workers + Redis Cluster | ~15,000/s | ~1,000/s | Production-grade |
| SQS + ECS Auto-scaling | ~100,000+/s | ~5,000/s | Enterprise-scale |

The enqueue rate intentionally exceeds the drain rate. The queue is the shock absorber — this is the fundamental design principle.

---

## Cost Considerations

### Local Development: $0

Docker Compose runs everything locally. No cloud accounts required. Memory backends available for testing.

### Free-Tier Cloud: $0

| Component | Free Option |
|---|---|
| Redis | Upstash (10K commands/day free) |
| Email | Resend (3,000 emails/month free) |
| Compute | Fly.io (3 shared VMs free with credit card) |
| Dashboard | Vercel (free for static sites) |

### Production Estimate: ~$50–150/month

| Component | Service | Cost |
|---|---|---|
| 3 API pods | ECS Fargate | ~$30/mo |
| 5 Worker pods | ECS Fargate | ~$50/mo |
| Redis Cluster | ElastiCache | ~$30/mo |
| SES | Pay per email | ~$0.10/1K emails |
| Monitoring | CloudWatch + Jaeger | ~$10/mo |

---

## Tradeoffs Summary

| Decision | Benefit | Cost |
|---|---|---|
| Async (202) over sync (200) | Fast API, decoupled delivery | No instant delivery confirmation |
| Adapter pattern | Portable, testable, extensible | More files, indirection |
| Redis Streams over Lists | Durability, consumer groups, ACK | Complexity, Redis-specific API |
| Client-side idempotency | Prevents duplicate sends | Requires client cooperation |
| Separate DLQ stream | Failures don't block main queue | Needs monitoring, manual retry |
| OpenTelemetry tracing | End-to-end visibility across services | Dependency, overhead when enabled |
| Pydantic validation | Strict contracts, auto-generated docs | Validation errors need careful formatting |

---

## What I'd Improve Next

1. **Webhook delivery status** — notify callers when delivery succeeds/fails via callback URL
2. **Multi-channel support** — SMS (Twilio), push (FCM/APNs) alongside email
3. **Priority queues** — urgent notifications skip the line (separate high-priority stream)
4. **Scheduled delivery** — accept `send_at` timestamp, use Redis sorted sets for scheduling
5. **Tenant isolation** — per-tenant rate limits, queues, and API keys for multi-tenant SaaS
6. **Exactly-once delivery** — use message deduplication at the worker level (not just ingress)
7. **Batch API** — accept arrays of notifications in a single request for bulk operations
8. **Circuit breaker** — auto-disable a failing email provider and route to a backup
