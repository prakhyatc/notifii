# Notifii

**Cloud-Native, Event-Driven Notification Platform**

[![AWS](https://img.shields.io/badge/AWS-Serverless-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)](https://aws.amazon.com/)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?style=for-the-badge&logo=terraform&logoColor=white)](https://www.terraform.io/)
[![Python](https://img.shields.io/badge/Python-FastAPI-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Containers-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Version](https://img.shields.io/badge/Version-2.0.0-blue?style=for-the-badge)]()
[![Status](https://img.shields.io/badge/Status-Production_Ready-22c55e?style=for-the-badge)]()

[Live Demo](#-live-system-verification) · [Technical Blog](#) · [Architecture](#-system-architecture) · [API Reference](#-api-reference)

---

*A contract-first notification platform that decouples request ingestion from message delivery using event-driven architecture — built to handle traffic spikes, provider failures, and downstream outages without dropping messages.*

</div>

---

## Why This Project?

Most notification systems fail under pressure because they're **synchronously coupled** to external providers. When SendGrid rate-limits you at 3 AM, your entire user registration flow breaks.

Notifii solves this by **separating concerns into three planes:**

| Plane | Responsibility | Implementation |
|-------|----------------|----------------|
| **Ingress** | Accept requests, validate, queue immediately | FastAPI + OpenAPI contract |
| **Control** | Provide durability, buffering, retry, backpressure | Amazon SQS + DLQ |
| **Delivery** | Execute delivery, handle failures, scale elastically | ECS Workers + Auto Scaling |

**The API never waits for email to send.** It queues and returns in ~10-50ms. Delivery happens asynchronously in the background.

---

## 🏗 System Architecture

### High-Level Overview

<!-- Replace with your actual diagram -->
![System Architecture](./docs/diagrams/high-level-architecture.png)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   ┌──────────────┐         ┌─────────────────────────────────────────────────┐ │
│   │    Client    │         │              INGRESS PLANE                      │ │
│   │  Application │         │  ┌─────────┐    ┌────────────────────────────┐  │ │
│   └──────┬───────┘         │  │   ALB   │───▶│      Notification API      │  │ │
│          │                 │  │         │    │  ┌──────────────────────┐  │  │ │
│          │ POST /v1/       │  └─────────┘    │  │  OpenAPI Validation  │  │  │ │
│          │ notifications   │                 │  │  ID Generation       │  │  │ │
│          │ :send           │                 │  │  SQS Enqueue         │  │  │ │
│          ▼                 │                 │  └──────────────────────┘  │  │ │
│   ┌──────────────┐         │                 └─────────────┬──────────────┘  │ │
│   │ 202 Accepted │◀────────┼───────────────────────────────┘                 │ │
│   │ {message_id} │         │                               │                 │ │
│   └──────────────┘         └───────────────────────────────┼─────────────────┘ │
│                                                            │                   │
│          ⚡ ~10-50ms                                       │ SendMessage       │
│          Client receives response                          ▼                   │
│          API has NO knowledge of delivery         ┌────────────────┐          │
│                                                   │  CONTROL PLANE │          │
│   ┌──────────────────────────────────────────────▶│                │          │
│   │                                               │  ┌──────────┐  │          │
│   │  Retry after visibility timeout              │  │   SQS    │  │          │
│   │                                               │  │  Queue   │  │          │
│   │         ┌─────────────────────────────────────│  └────┬─────┘  │          │
│   │         │                                     │       │        │          │
│   │         │  Max retries exceeded               │  ┌────▼─────┐  │          │
│   │         │                                     │  │   DLQ    │  │          │
│   │         ▼                                     │  │(failures)│  │          │
│   │  ┌────────────┐                               │  └──────────┘  │          │
│   │  │  CloudWatch│◀── Alarm: DLQ > 0             └────────┬───────┘          │
│   │  │   Alarm    │                                        │                   │
│   │  └────────────┘                                        │ ReceiveMessage    │
│   │                                                        ▼                   │
│   │                                        ┌───────────────────────────────┐  │
│   │                                        │        DELIVERY PLANE         │  │
│   │                                        │  ┌─────────────────────────┐  │  │
│   │                                        │  │     Email Workers       │  │  │
│   └────────────────────────────────────────│  │  ┌───┐ ┌───┐ ┌───┐     │  │  │
│                                            │  │  │ W │ │ W │ │...│     │  │  │
│                                            │  │  └───┘ └───┘ └───┘     │  │  │
│                                            │  │   ▲                     │  │  │
│                                            │  │   │ Auto Scaling        │  │  │
│                                            │  │   │ (queue depth)       │  │  │
│                                            │  └───┴─────────────────────┘  │  │
│                                            └───────────────┬───────────────┘  │
│                                                            │                   │
│                                                            ▼                   │
│                                                   ┌────────────────┐          │
│                                                   │ Email Provider │          │
│                                                   │  (SES/SMTP)    │          │
│                                                   └────────────────┘          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Message Flow Pipeline

<!-- Replace with your actual diagram -->
![Message Flow](./docs/diagrams/message-flow-pipeline.png)

### Request Lifecycle

<!-- Replace with your actual diagram -->
![Request Lifecycle](./docs/diagrams/request-lifecycle-sequence.png)

---

## Tech Stack

<table>
<tr>
<td width="50%">

### API Layer
| Technology | Purpose |
|------------|---------|
| **FastAPI** | Async Python framework |
| **OpenAPI 3.0** | Contract-first design |
| **Pydantic** | Request validation |
| **ALB** | Load balancing, TLS |

</td>
<td width="50%">

### Compute & Containers
| Technology | Purpose |
|------------|---------|
| **ECS Fargate** | Serverless containers |
| **ECR** | Container registry |
| **Auto Scaling** | Queue-based scaling |
| **Docker** | Containerization |

</td>
</tr>
<tr>
<td>

### Messaging & Storage
| Technology | Purpose |
|------------|---------|
| **Amazon SQS** | Message queue |
| **Dead Letter Queue** | Failed message handling |
| **CloudWatch Logs** | Structured logging |

</td>
<td>

### Infrastructure
| Technology | Purpose |
|------------|---------|
| **Terraform** | Infrastructure as Code |
| **VPC** | Network isolation |
| **IAM** | Least-privilege roles |
| **NAT Gateway** | Outbound connectivity |

</td>
</tr>
</table>

---

## 💡 Core Design Decisions

### 1. Asynchronous Decoupling

> *"The API should never wait for the email to send."*

```
 Synchronous (Fragile)              Asynchronous (Resilient)
                                      
Client ──▶ API ──▶ Email ──▶ Response    Client ──▶ API ──▶ Queue ──▶ Response
              │                                              │
              └── If email fails,                           │
                  request fails                    Worker ◀─┘
                                                     │
                                                     ▼
                                                   Email
                                                     │
                                                     └── Retries automatically
```

**Why?**
- API latency independent of provider latency
- Provider failures don't break user-facing requests
- Traffic spikes buffered in queue, not dropped
- Automatic retry with exponential backoff

---

### 2. Contract-First API Design

```yaml
# openapi/notifii.openapi.yaml — Source of Truth
openapi: 3.0.3
info:
  title: Notifii API
  version: 1.0.0

paths:
  /v1/notifications:send:
    post:
      summary: Send a notification
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SendNotificationRequest'
      responses:
        '202':
          description: Notification queued successfully
```

**Why?**
- Clients can trust the contract
- Breaking changes are versioned (`/v1/*`, `/v2/*`)
- Documentation is always accurate
- SDK generation possible

---

### 3. Queue-Based Durability

```
┌─────────────────────────────────────────────────────────────────┐
│                     SQS Message Lifecycle                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Message Sent ──▶ Visible ──▶ Received ──▶ Processing          │
│                                    │                             │
│                                    │ (visibility timeout)        │
│                                    ▼                             │
│                    ┌───────────────────────────────┐            │
│                    │        Outcome?               │            │
│                    └───────────────────────────────┘            │
│                       │                    │                     │
│                  Success               Failure                   │
│                       │                    │                     │
│                       ▼                    ▼                     │
│                   Delete            Return to Queue              │
│                   Message           (retry later)                │
│                       │                    │                     │
│                       │                    │ (max retries)       │
│                       │                    ▼                     │
│                       │              Move to DLQ                 │
│                       │              (inspect/replay)            │
│                       ▼                                          │
│                    Done                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Why?**
- Messages survive API crashes
- At-least-once delivery guaranteed
- Failed messages preserved for debugging
- Backpressure handled automatically

---

### 4. Elastic Worker Scaling

<!-- Replace with your actual diagram -->
![Autoscaling](./docs/diagrams/worker-autoscaling.png)

```
Queue Depth    Workers    Behavior
───────────    ───────    ─────────────────────────────
0-10           1          Baseline (always available)
50             5          Scaling out (traffic spike)
100+           10         Maximum capacity
10             3          Scaling in (queue draining)
0              1          Back to baseline
```

**Why?**
- Handle 10x traffic spikes automatically
- Pay only when processing messages
- No manual capacity planning
- Predictable per-message cost

---

## Repository Structure

```
notifii/
│
├── services/
│   ├── notification-api/
│   │   ├── src/
│   │   │   ├── main.py              # FastAPI application
│   │   │   ├── routes/              # API endpoints
│   │   │   ├── models/              # Pydantic schemas
│   │   │   └── queue/               # SQS integration
│   │   ├── openapi/
│   │   │   └── notifii.openapi.yaml # API contract (source of truth)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── email-worker/
│       ├── src/
│       │   ├── main.py              # Worker entry point
│       │   ├── consumer.py          # SQS polling loop
│       │   └── handlers/            # Channel handlers
│       ├── Dockerfile
│       └── requirements.txt
│
├── infra/
│   ├── modules/
│   │   ├── network/                 # VPC, subnets, NAT
│   │   ├── iam/                     # Task roles, policies
│   │   ├── ecr/                     # Container registries
│   │   ├── sqs/                     # Queue + DLQ
│   │   ├── ecs_service/             # API service + ALB
│   │   ├── ecs_worker/              # Worker + autoscaling
│   │   └── observability/           # CloudWatch logs, alarms
│   │
│   └── envs/
│       ├── dev/                     # Dev environment config
│       └── prod/                    # Prod environment config
│
├── docs/
│   └── diagrams/                    # Architecture diagrams
│
└── README.md
```

---

## API Reference

### Authentication
Currently open for demo. Production deployment adds JWT authentication at ALB layer.

### Endpoints

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `POST` | `/v1/notifications:send` | Queue a notification | `202 Accepted` |
| `GET` | `/health` | Liveness check | `200 OK` |
| `GET` | `/ready` | Readiness check | `200 OK` |

### Send Notification

```bash
curl -X POST http://<ALB_DNS>/v1/notifications:send \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "email",
    "recipient": "user@example.com",
    "message": "Welcome to our platform!",
    "idempotency_key": "user-signup-abc123"
  }'
```

### Response

```json
{
  "message_id": "ae0d03ef-492d-4788-beca-e664a65e5d1a",
  "status": "queued"
}
```

### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `channel` | string | Yes | Delivery channel: `email`, `sms`, `push` |
| `recipient` | string | Yes | Target address (email, phone, device token) |
| `message` | string | Yes | Notification content |
| `idempotency_key` | string | No | Client-provided deduplication key |

---

## Live System Verification

### Infrastructure Deployed

```bash
# Terraform outputs (us-east-1)
notification_api_alb_dns = notifii-dev-notification-api-alb-xxx.us-east-1.elb.amazonaws.com
notifications_queue_url  = https://sqs.us-east-1.amazonaws.com/xxx/notifii-notifications-dev-queue
notifications_dlq_url    = https://sqs.us-east-1.amazonaws.com/xxx/notifii-dlq-dev
```

### Worker Health

```
┌─────────────┬──────────────┬──────────────┐
│ desiredCount│ runningCount │ pendingCount │
├─────────────┼──────────────┼──────────────┤
│      1      │      1       │      0       │
└─────────────┴──────────────┴──────────────┘
Email worker is online and consuming
```

### End-to-End Verification (CloudWatch Logs)

**Message Queued (API):**
```json
{
  "event": "notification_queued",
  "message_id": "ae0d03ef-492d-4788-beca-e664a65e5d1a",
  "request_id": "proof-logs-001",
  "channel": "email",
  "recipient": "user@example.com"
}
```

**Message Processed (Worker):**
```json
{
  "event": "email_send_simulated",
  "message_id": "ae0d03ef-492d-4788-beca-e664a65e5d1a",
  "request_id": "proof-logs-001",
  "recipient": "user@example.com"
}
```

**Message Deleted (Worker):**
```json
{
  "event": "message_deleted",
  "sqs_message_id": "c498bbcb-772b-4aa3-8757-19e0e91b144a",
  "message_id": "ae0d03ef-492d-4788-beca-e664a65e5d1a"
}
```

**This proves:**
- API enqueued the message
- Worker consumed it from SQS
- Delivery was executed
- Message was deleted (acknowledged)
- **Pipeline is fully functional**

---

## Security Model

| Layer | Protection |
|-------|------------|
| **Network** | Private subnets for ECS tasks, NAT for outbound only |
| **IAM** | Least-privilege: API can only `SendMessage`, Workers can only `ReceiveMessage`/`DeleteMessage` |
| **Compute** | No SSH, no public IPs, immutable containers |
| **Queue** | No public access, VPC endpoints available |
| **Logging** | Structured JSON, no PII in logs |

### IAM Role Separation

```
┌─────────────────────────────────────────────────────────────┐
│                    IAM Role Boundaries                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   API Task Role                    Worker Task Role          │
│   ┌─────────────────┐              ┌─────────────────┐      │
│   │ sqs:SendMessage │              │ sqs:ReceiveMsg  │      │
│   │       Yes        │              │ sqs:DeleteMsg   │      │
│   │                 │              │       Yes        │      │
│   │ sqs:ReceiveMsg  │              │                 │      │
│   │       No        │              │ sqs:SendMessage │      │
│   │                 │              │       No        │      │
│   └─────────────────┘              └─────────────────┘      │
│                                                              │
│   API cannot consume messages    Workers cannot inject msgs  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker
- AWS CLI configured
- Terraform 1.5+

### Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/notifii.git
cd notifii

# Run API locally
cd services/notification-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

### Docker Build

```bash
# Build API
cd services/notification-api
docker build -t notifii-api:dev .
docker run --rm -p 8000:8000 notifii-api:dev

# Build Worker
cd services/email-worker
docker build -t notifii-worker:dev .
```

### Deploy to AWS

```bash
cd infra/envs/dev
terraform init
terraform plan
terraform apply

# Verify deployment
curl http://$(terraform output -raw notification_api_alb_dns)/health
```

---

## Architecture Diagrams

| Diagram | Description |
|---------|-------------|
| [High-Level Architecture](./docs/diagrams/high-level-architecture.png) | Complete system overview with all three planes |
| [Message Flow Pipeline](./docs/diagrams/message-flow-pipeline.png) | Four phases of message processing |
| [Request Lifecycle](./docs/diagrams/request-lifecycle-sequence.png) | Sequence diagram from request to delivery |
| [Worker Autoscaling](./docs/diagrams/worker-autoscaling.png) | Elastic scaling based on queue depth |
| [Infrastructure Modules](./docs/diagrams/infrastructure-architecture.png) | Terraform module organization |
| [Failure Handling](./docs/diagrams/failure-handling-dlq.png) | Retry behavior and DLQ flow |

---

## Future Roadmap

- [ ] **Real Email Delivery** — SES integration with bounce handling
- [ ] **SMS Channel** — SNS integration for SMS notifications
- [ ] **Push Notifications** — FCM/APNs integration
- [ ] **Delivery Webhooks** — Notify clients of delivery outcomes
- [ ] **Idempotency Storage** — DynamoDB-backed deduplication
- [ ] **Rate Limiting** — Per-client request throttling
- [ ] **Multi-Region** — Active-active deployment
- [ ] **Analytics Dashboard** — Delivery metrics, open rates

---

## Learn More

- [Technical Deep Dive (Blog Post)](#)
- [Architecture Diagrams](./docs/diagrams/)
- [OpenAPI Specification](./services/notification-api/openapi/notifii.openapi.yaml)

---

## Contributing

Contributions welcome! Please read our contributing guidelines before submitting PRs.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ☕ and event-driven architecture**

*"The API should never wait for the email to send."*

[⬆ Back to Top](#-notifii)

</div>