# Notifii — Cloud-Native Notification Platform (Email, SMS, Push)

Notifii is a contract-first, cloud-native notification platform designed to reliably enqueue and deliver outbound notifications across multiple channels (email, SMS, and push). The system is built using platform engineering principles: isolated microservices, immutable infrastructure, strict API contracts, and operational visibility.

---

## Architecture (Week 1–2)

### What is deployed today

The current system provides a production-grade ingestion layer for notification requests:

- **Notification API (FastAPI)**  
  Public-facing service that validates requests and returns `202 Accepted` with a `message_id`.

- **AWS Application Load Balancer (ALB)**  
  Provides internet-facing ingress, health checks, and traffic routing.

- **ECS Fargate**  
  Runs the API as a managed, autoscalable container service in private subnets.

- **Amazon ECR**  
  Stores immutable container images used for deployment.

- **CloudWatch Logs**  
  Centralized, structured logging for API containers.

- **Terraform (modularized)**  
  Infrastructure is defined as code and split by concern:
  - `network` (VPC, subnets, NAT)
  - `iam` (task roles, execution roles)
  - `ecr` (container registry)
  - `ecs_service` (ALB, task definition, ECS service)

This gives a fully reproducible, production-style control plane for the API layer.

### What comes next (Week 3+)

- SQS request queue + Dead Letter Queue (DLQ)
- Channel workers (email / SMS / push) consuming from SQS
- Idempotency storage (DynamoDB or Postgres)
- Rate limiting, retry logic, and delivery guarantees

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
```bash
cd services/notification-api
docker build -t notifii-notification-api:dev .
docker run --rm -p 8000:8000 notifii-notification-api:dev
curl http://localhost:8000/health
```
The container runs as a non-root user and exposes port 8000.

## Deploying (dev environment)
Terraform environment:
infra/envs/dev
Typical workflow:
```bash
cd infra/envs/dev
terraform init
terraform apply
```
After deployment:
```bash 
curl http://<ALB_DNS>/health
```
If the target group is healthy, the API is live.