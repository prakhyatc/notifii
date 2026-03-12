.PHONY: lint format test up down logs demo test-docker docker-build up-jaeger down-jaeger load-test load-test-medium load-test-heavy

# ── Local Dev ────────────────────────────────────────────────
lint:
	ruff check services/
	black --check services/

format:
	black services/
	ruff check services/ --fix

test:
	QUEUE_BACKEND=memory IDEMPOTENCY_BACKEND=memory EMAIL_PROVIDER=console OTEL_ENABLED=false \
	PYTHONPATH="$(PWD):$(PWD)/services/notification-api" \
	pytest services/notification-api/tests/ -v --tb=short

# ── Docker ───────────────────────────────────────────────────
up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

# ── Docker Tests ─────────────────────────────────────────────
test-docker:
	docker compose -f docker compose.test.yml up --build --abort-on-container-exit --exit-code-from test
	docker compose -f docker compose.test.yml down -v

# ── Individual Builds ────────────────────────────────────────
docker-build:
	docker compose build

docker-build-api:
	docker compose build api

docker-build-worker:
	docker compose build worker

# ── Quick Demo ───────────────────────────────────────────────
demo:
	@echo "Starting Notifii..."
	docker compose up --build -d
	@echo ""
	@echo "Waiting for services..."
	@sleep 5
	@echo ""
	@echo "=== Sending test notification ==="
	curl -s -X POST http://localhost:8000/v1/notifications:send \
		-H "Content-Type: application/json" \
		-H "X-Request-Id: demo-trace-001" \
		-d '{"channel":"email","recipient":"demo@example.com","message":"Hello from Notifii!"}' | python3 -m json.tool
	@echo ""
	@echo "=== Check queue depth ==="
	curl -s http://localhost:8000/v1/queue/depth | python3 -m json.tool
	@echo ""
	@echo "=== Check metrics ==="
	curl -s http://localhost:8000/metrics
	@echo ""
	@echo "Dashboard: http://localhost:5173"
	@echo "Mailhog:   http://localhost:8025"
	@echo "API:       http://localhost:8000"
	@echo "API docs:  http://localhost:8000/docs"
	@echo "Metrics:   http://localhost:8000/metrics"

# ── Tracing (Jaeger) ─────────────────────────────────────────
up-jaeger:
	docker compose -f docker compose-jaeger.yml up --build -d
	@echo ""
	@echo "Jaeger UI: http://localhost:16686"
	@echo "API:       http://localhost:8000"
	@echo "Mailhog:   http://localhost:8025"

down-jaeger:
	docker compose -f docker compose-jaeger.yml down -v

# ── Load Testing (k6) ────────────────────────────────────────
load-test:
	./load-tests/k6/run.sh light

load-test-medium:
	./load-tests/k6/run.sh medium

load-test-heavy:
	./load-tests/k6/run.sh heavy

# ── One-Click Demo ───────────────────────────────────────────
run-demo:
	./scripts/run-demo.sh

# ── Interactive Step-by-Step Demo ────────────────────────────
demo-interactive:
	./scripts/demo.sh

# ── Dashboard ────────────────────────────────────────────────
dashboard:
	cd dashboard && npm install && npm run dev

dashboard-build:
	cd dashboard && npm install && npm run build
