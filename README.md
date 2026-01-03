# Notifii — Cloud-Native Notification Platform (Email/SMS/Push)

Notifii is a contract-first, cloud-native notification platform built to enqueue and deliver notifications via independent channel workers (Email/SMS/Push). The system is designed for scale, cost efficiency, and operational clarity (metrics/logs/health checks).

## Architecture: Week 1–2

**Current (Week 1–2):**
- **notification-api** (FastAPI): accepts requests and returns `202 Accepted` with a `message_id`
- **ECS Fargate + ALB**: runs the API behind a load balancer in private subnets
- **CloudWatch Logs**: centralized logging
- **Terraform**: reproducible infra, modularized by concern (network, IAM, ECR, ECS)

**Next (Week 3+):**
- SQS queue + DLQ
- Channel workers (email/sms/push) consuming from SQS
- Idempotency persistence (DynamoDB/Postgres) + rate limiting

## OpenAPI as Contract

The OpenAPI spec is the source of truth for the public API contract:

- Spec: `services/notification-api/openapi/notifii.openapi.yaml`
- All business endpoints are versioned under `/v1/*`.
- Versioning rules:
  - **Patch**: docs/typos, non-breaking internal changes
  - **Minor**: backward-compatible additions (new optional fields, new endpoints)
  - **Major**: breaking changes (removed/renamed fields, changed semantics)

## How to run locally

### Notification API (FastAPI)
```bash
cd services/notification-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Health checks:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Container(Docker)
```bash
cd services/notification-api
docker build -t notifii-notification-api:dev .
docker run --rm -p 8000:8000 notifii-notification-api:dev
curl http://localhost:8000/health
```

## Terraform environment:

- infra/envs/dev

Typical flow:

```bash
cd infra/envs/dev
terraform init
terraform apply
```

After deployment, hit the ALB:

```bash 
curl http://<ALB_DNS>/health
```

## Terraform state + locking

Use a remote backend for state storage and locking (S3 + DynamoDB) to prevent concurrent applies. Keep terraform.tfstate out of git and treat state as sensitive infrastructure metadata.

## CI

GitHub Actions runs on push/PR:

- Ruff + Black
- Pytest
- Docker build (no push)