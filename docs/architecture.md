# Notifii Architecture

## System Overview

```mermaid
graph TB
    subgraph Clients
        C1[Web App]
        C2[Mobile App]
        C3[Backend Service]
    end

    subgraph "Ingress Plane"
        API[FastAPI API<br/>POST /v1/notifications:send]
        VAL[Pydantic Validation]
        IDEM[Idempotency Check]
        RL[Rate Limiter]
    end

    subgraph "Control Plane"
        Q[Message Queue<br/>Redis Streams / SQS]
        DLQ[Dead Letter Queue]
    end

    subgraph "Delivery Plane"
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker N...]
    end

    subgraph "Email Providers"
        SMTP[SMTP / Mailhog]
        RESEND[Resend]
        SES[AWS SES]
        CONSOLE[Console Logger]
    end

    subgraph "Observability"
        LOG[Structured JSON Logs]
        MET[Prometheus Metrics<br/>GET /metrics]
        RID[Request ID Tracing]
    end

    C1 & C2 & C3 -->|HTTP POST| API
    API --> VAL --> IDEM --> RL
    RL -->|Enqueue| Q
    Q -->|Consumer Group| W1 & W2 & W3
    W1 & W2 & W3 -->|Deliver| SMTP & RESEND & SES & CONSOLE
    W1 & W2 & W3 -->|On Failure| DLQ
    DLQ -->|Retry| Q
    API & W1 --> LOG & MET & RID

    style API fill:#6c63ff,stroke:#6c63ff,color:#fff
    style Q fill:#f59e0b,stroke:#f59e0b,color:#000
    style DLQ fill:#ef4444,stroke:#ef4444,color:#fff
    style W1 fill:#22c55e,stroke:#22c55e,color:#fff
    style W2 fill:#22c55e,stroke:#22c55e,color:#fff
    style W3 fill:#22c55e,stroke:#22c55e,color:#fff
```

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Idem as Idempotency Store
    participant Queue as Redis Streams
    participant Worker
    participant Email as Email Provider

    Client->>API: POST /v1/notifications:send
    API->>API: Validate (Pydantic)
    API->>Idem: Check idempotency_key
    
    alt Duplicate Request
        Idem-->>API: Return existing message_id
        API-->>Client: 202 (original message_id)
    else New Request
        Idem-->>API: No match
        API->>Queue: XADD message
        API-->>Client: 202 Accepted {message_id, status: "queued"}
    end

    Queue->>Worker: XREADGROUP (consumer group)
    Worker->>Email: Send email
    
    alt Delivery Success
        Email-->>Worker: OK
        Worker->>Queue: XACK (acknowledge)
        Worker->>Idem: Update status → delivered
    else Delivery Failure
        Email-->>Worker: Error
        Worker->>Queue: Move to DLQ after max retries
        Worker->>Idem: Update status → failed
    end
```

## Component Architecture

```mermaid
graph LR
    subgraph "services/shared/"
        subgraph "queue/"
            QB[base.py<br/>QueueAdapter ABC]
            QR[redis_adapter.py]
            QS[sqs_adapter.py]
            QM[memory_adapter.py]
            QF[factory.py]
        end
        subgraph "email/"
            EB[base.py<br/>EmailAdapter ABC]
            EC[console_adapter.py]
            ES[smtp_adapter.py]
            ER[resend_adapter.py]
            EA[ses_adapter.py]
            EF[factory.py]
        end
        subgraph "idempotency/"
            IB[base.py<br/>IdempotencyStore ABC]
            IM[memory_store.py]
            IR[redis_store.py]
            IF[factory.py]
        end
        subgraph "observability/"
            OL[logging.py]
            OM[metrics.py]
            OW[middleware.py]
        end
    end

    QF --> QB
    QB --> QR & QS & QM
    EF --> EB
    EB --> EC & ES & ER & EA
    IF --> IB
    IB --> IM & IR

    style QB fill:#6c63ff,stroke:#6c63ff,color:#fff
    style EB fill:#6c63ff,stroke:#6c63ff,color:#fff
    style IB fill:#6c63ff,stroke:#6c63ff,color:#fff
```

## Deployment Modes

```mermaid
graph TB
    subgraph "Local / Free Tier ($0/mo)"
        L_API[FastAPI<br/>Docker Container]
        L_Q[Redis Streams<br/>Docker / Upstash]
        L_W[Worker<br/>Docker Container]
        L_E[Mailhog / Resend<br/>Console]
        L_D[React Dashboard<br/>Vite Dev / Vercel]
    end

    subgraph "AWS Production (~$30-50/mo)"
        A_API[ECS Fargate + ALB]
        A_Q[SQS + DLQ]
        A_W[ECS Fargate Workers]
        A_E[AWS SES]
        A_D[CloudFront + S3]
    end

    L_API -.->|Same code| A_API
    L_Q -.->|Same interface| A_Q
    L_W -.->|Same code| A_W
    L_E -.->|Same interface| A_E
```

## Scaling to Millions

```mermaid
graph TB
    LB[Load Balancer / ALB]
    
    subgraph "API Tier (Horizontal Scale)"
        API1[API Pod 1]
        API2[API Pod 2]
        API3[API Pod N]
    end

    subgraph "Queue Tier"
        Q[Redis Cluster / SQS<br/>Partitioned by channel]
    end

    subgraph "Worker Tier (Horizontal Scale)"
        W1[Worker Pod 1<br/>Consumer Group A]
        W2[Worker Pod 2<br/>Consumer Group A]
        W3[Worker Pod N<br/>Consumer Group A]
    end

    subgraph "Storage Tier"
        R[Redis Cluster<br/>Idempotency]
    end

    LB --> API1 & API2 & API3
    API1 & API2 & API3 --> Q
    API1 & API2 & API3 --> R
    Q --> W1 & W2 & W3

    style LB fill:#6c63ff,stroke:#6c63ff,color:#fff
    style Q fill:#f59e0b,stroke:#f59e0b,color:#000
```

### Scaling Strategy

| Component | Strategy | Bottleneck | Solution |
|---|---|---|---|
| API | Horizontal pods behind LB | CPU/memory | Auto-scale on request rate |
| Queue | Redis Cluster / SQS | Throughput | Partition by channel, increase shards |
| Workers | Consumer groups | Processing rate | Add more consumers to the group |
| Idempotency | Redis Cluster | Memory | TTL expiry, key sharding |
| Email | Provider rate limits | API quotas | Multiple providers, round-robin |

### Throughput Estimates

| Setup | Notifications/sec | Latency (p99) |
|---|---|---|
| Single Docker Compose | ~100 | <50ms enqueue |
| 3 API + 5 Workers | ~2,000 | <20ms enqueue |
| 10 API + 20 Workers + Redis Cluster | ~50,000 | <10ms enqueue |
| SQS + ECS Auto-scaling | ~500,000+ | <15ms enqueue |
