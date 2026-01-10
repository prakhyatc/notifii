# Notifii — Cloud-Native Notification Platform (Email, SMS, Push)

Notifii is a contract-first, cloud-native notification platform designed to reliably enqueue and deliver outbound notifications across multiple channels (email, SMS, and push). The system is built using platform engineering principles: isolated microservices, immutable infrastructure, strict API contracts, and operational visibility.

![Version](https://img.shields.io/badge/version-v2.0.0-blue)
![AWS](https://img.shields.io/badge/AWS-Serverless-orange)
![Status](https://img.shields.io/badge/status-production--ready-green)
---

## Architecture (Week 1–4)

### What is deployed today

Notifii now runs a **full asynchronous delivery pipeline** in AWS:

- **Notification API (FastAPI)**  
  Public-facing service that validates requests against the OpenAPI contract and returns `202 Accepted` with a `message_id`.

- **AWS Application Load Balancer (ALB)**  
  Provides internet-facing ingress, health checks, and traffic routing.

- **Amazon SQS + DLQ**  
  All notification requests are enqueued to a durable SQS queue.  
  Failed messages are automatically routed to a Dead Letter Queue for inspection and replay.

- **ECS Fargate (API + Workers)**  
  - `notification-api` runs as a managed service behind ALB  
  - `email-worker` runs as an autoscaled background service consuming from SQS

- **Auto Scaling (Application Auto Scaling)**  
  Email workers scale up automatically based on queue depth and scale down when idle, allowing the system to absorb traffic bursts cost-efficiently.

- **Amazon ECR**  
  Stores immutable container images used for deployment.

- **CloudWatch Logs**  
  Centralized, structured logs for both API and workers.

- **Terraform (modularized)**  
  Infrastructure is defined as code and split by concern:
  - `network` (VPC, subnets, NAT)
  - `iam` (task roles, execution roles)
  - `ecr` (container registries)
  - `sqs` (queue + DLQ)
  - `ecs_service` (ALB + API service)
  - `ecs_worker` (email worker service + autoscaling)

This forms a **production-grade event-driven notification system**:  
API → Queue → Workers → Delivery.

---
## Architecture Diagrams (Mermaid)
![Autoscaling Concept](docs/Autoscaling%20Concept.png)
![Request Lifecycle Sequence](docs/Request%20Lifecycle%20Sequence%20(Contract-first+async).png)
---
## Live System Verification (v2.0.0)

### Infrastructure Outputs (Terraform)
```text
notification_api_alb_dns = notifii-dev-notification-api-alb-763396971.us-east-1.elb.amazonaws.com
notification_api_repo_url = 062373232751.dkr.ecr.us-east-1.amazonaws.com/notifii-notification-api
notifications_queue_arn = arn:aws:sqs:us-east-1:062373232751:notifii-notifications-dev-queue
notifications_queue_url = https://sqs.us-east-1.amazonaws.com/062373232751/notifii-notifications-dev-queue
```

### Worker Service Health
```text
| desiredCount | runningCount | pendingCount |
|-------------|--------------|--------------|
| 1           | 1            | 0            |
```
This confirms the email worker is online and consuming.

### Verified End-to-End Processing
The following CloudWatch logs show real messages being processed:
```json
{
  "event": "email_send_simulated",
  "message_id": "ae0d03ef-492d-4788-beca-e664a65e5d1a",
  "request_id": "proof-logs-001",
  "recipient": "user@example.com",
  "idempotency_key": "proof-logs-001"
}
```
```json
{
  "event": "message_deleted",
  "sqs_message_id": "c498bbcb-772b-4aa3-8757-19e0e91b144a",
  "message_id": "ae0d03ef-492d-4788-beca-e664a65e5d1a",
  "request_id": "proof-logs-001"
}
```
This proves:
	•	The API enqueued the message
	•	The worker consumed it
	•	The message was deleted from SQS
	•	The pipeline is fully functional

### Verified Idempotency Metadata Flow
Requests contain an idempotency_key that is propagated end-to-end:
```json
{
  "request_id": "proof-logs-002",
  "idempotency_key": "proof-logs-002"
}
```  
Future versions will enforce deduplication using this key.
---

## What happens when you send a notification

1. Client sends `POST /v1/notifications:send`
2. API validates the request using OpenAPI
3. Message is written to SQS with metadata (channel, request_id, idempotency_key)
4. API returns `202 Accepted` with a `message_id`
5. Workers poll SQS
6. Worker processes the message (email in v2)
7. On success, worker deletes the message from SQS
8. On failure, SQS moves the message to the DLQ after retries

This decouples request ingestion from delivery and makes the system resilient to spikes and downstream failures.

---

## OpenAPI as the Contract

The API contract is defined and versioned independently of the implementation.

**Source of truth:**  
`services/notification-api/openapi/notifii.openapi.yaml`

All business endpoints are versioned under `/v1/*`.  
Infrastructure endpoints (`/health`, `/ready`) remain unversioned.

### Versioning rules

- **Patch** – Documentation fixes, bug fixes, no contract changes  
- **Minor** – Backward-compatible changes (new optional fields, new endpoints)  
- **Major** – Breaking changes (field removal, semantic changes, renames)

This ensures API consumers can depend on stable contracts even as the platform evolves.

---

## Running Locally

### FastAPI (without Docker)

```bash
cd services/notification-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Health checks:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Docker
### Notification API
```bash
cd services/notification-api
docker build -t notifii-notification-api:dev .
docker run --rm -p 8000:8000 notifii-notification-api:dev
curl http://localhost:8000/health
```
### Email Worker
```bash
cd services/email-worker
docker build -t notifii-email-worker:dev .
docker run --rm notifii-email-worker:dev
``` 


## Deploying (dev environment)
### Terraform environment:
infra/envs/dev
### Typical workflow:
```bash
cd infra/envs/dev
terraform init
terraform apply
```
### After deployment:
```bash 
curl http://<ALB_DNS>/health
```
If the target group is healthy, the API is live.