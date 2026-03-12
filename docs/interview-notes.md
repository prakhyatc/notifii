# Interview Talking Points

Quick-reference notes for explaining Notifii during technical interviews. Each section covers a question you're likely to get, with a concise answer and the reasoning behind it.

---

## "Walk me through the architecture"

- Client sends a POST to the FastAPI API. The API validates the payload with Pydantic, checks for duplicate requests via an idempotency key stored in Redis, and enqueues the message to Redis Streams. It returns 202 immediately.
- Workers consume messages from the stream using Redis consumer groups. Each message is processed by exactly one worker. The worker delivers the email through a pluggable adapter (SMTP, Resend, SES, or console for testing).
- If delivery fails, the message stays pending in Redis. After exhausting retries, it moves to a Dead Letter Queue — a separate stream the operator can inspect and retry from.
- Everything behind an abstract interface: swap the queue (Redis/SQS/Memory), email provider, or idempotency store via environment variables. Same code runs locally with Docker Compose or on AWS with Terraform.

---

## Design Decisions

**Why async (202) instead of synchronous delivery?**
- Email providers have variable latency (50ms–5s). Synchronous delivery would make API response times unpredictable.
- The queue decouples ingestion speed from delivery speed. The API can accept thousands of requests per second even if the email provider is slow.
- During provider outages, the queue absorbs all incoming messages. Nothing is lost.

**Why Redis Streams instead of Redis Lists or Pub/Sub?**
- Streams give us consumer groups (load balancing across workers), message persistence (survives restarts), and explicit acknowledgment (XACK).
- Lists (`LPUSH/BRPOP`) don't have consumer groups or message tracking. If a worker crashes mid-processing, the message is gone.
- Pub/Sub is fire-and-forget — no persistence, no replay. Not suitable for notification delivery.

**Why the Adapter Pattern for everything?**
- Testability: unit tests use in-memory backends with zero infrastructure.
- Portability: same code runs locally (Redis + Mailhog) and in production (SQS + SES).
- Extensibility: adding a new email provider is one file and one factory case. No changes to business logic.

**Why client-side idempotency keys?**
- Server-generated deduplication (e.g., hashing the payload) is fragile — two legitimately identical notifications would be incorrectly deduplicated.
- Client-provided keys let the client decide what "duplicate" means in their context.
- Stored in Redis with 24h TTL using atomic `SET NX`. Extremely fast O(1) lookups.

---

## Tradeoffs

| Decision | Benefit | Cost |
|---|---|---|
| Async delivery (202) | Fast API, provider-independent latency | No instant delivery confirmation to client |
| Adapter pattern | Portable, testable, easy to extend | More files, extra indirection |
| Redis Streams over Lists | Durability, consumer groups, ACK | More complex, Redis-specific API |
| Client idempotency keys | Correct deduplication semantics | Requires client cooperation |
| Separate DLQ stream | Failed messages don't block live traffic | Needs monitoring; can grow if unattended |
| OpenTelemetry tracing | End-to-end visibility across async boundaries | Runtime overhead when enabled; dependency |
| Pydantic validation | Strict input contracts, auto-generated OpenAPI docs | Validation error formatting needs care |

---

## Scaling Approach

**API tier:** Stateless. Put pods behind a load balancer. Scale horizontally on CPU or request rate.

**Queue tier:** Redis handles ~100K XADD/s on a single node. For higher throughput, use Redis Cluster (sharding by channel) or swap to SQS (unlimited throughput, managed).

**Worker tier:** Add workers to the consumer group. Redis distributes messages automatically — no rebalancing required. Scale based on queue depth growth rate.

**Idempotency:** Redis with 24h TTL. For higher scale, shard by key prefix or use DynamoDB.

**Key insight:** The enqueue rate will always exceed the drain rate during bursts. That's by design — the queue is the shock absorber. The system is correct as long as workers eventually drain the backlog.

---

## What I'd Improve Next

1. **Webhook callbacks** — notify callers when delivery succeeds or fails, instead of requiring them to poll
2. **Multi-channel support** — add SMS (Twilio) and push (FCM/APNs) alongside email, using the same adapter pattern
3. **Priority queues** — separate high-priority stream for urgent notifications (e.g., OTP codes) that skip the line
4. **Scheduled delivery** — accept a `send_at` timestamp and use Redis sorted sets for delayed dispatch
5. **Circuit breaker** — automatically disable a failing provider and route to a fallback, instead of sending everything to DLQ
6. **Batch API** — accept arrays of notifications in one request for bulk operations like marketing campaigns
7. **Tenant isolation** — per-tenant rate limits, queues, and API keys for multi-tenant SaaS deployments
8. **Exactly-once delivery** — add worker-level deduplication in addition to ingress-level idempotency

---

## Questions I'd Ask the Interviewer

If they flip the question:

- "What's the expected notification volume? That determines whether Redis Streams or SQS is the right queue."
- "Do consumers need real-time delivery confirmation, or is eventual delivery acceptable?"
- "Is multi-tenancy a requirement? That changes the queue topology and rate limiting strategy."
- "What's the SLA for delivery latency? That determines how aggressively we need to scale workers."

---

## Quick Stats to Mention

- **19+ tests** — unit and integration, no Docker needed (memory backends)
- **6 abstraction layers** — queue, email, idempotency, logging, metrics, tracing
- **4 email providers** — SMTP, Resend, SES, Console
- **3 queue backends** — Redis Streams, SQS, Memory
- **Distributed tracing** — OpenTelemetry spans propagated through queue messages using W3C trace context
- **CI pipeline** — lint, test, Docker build, integration smoke test (GitHub Actions)
- **~1,000 req/s** enqueue throughput on a single Docker Compose setup
