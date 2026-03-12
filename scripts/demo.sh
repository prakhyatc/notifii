#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8000"
BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

header() { echo -e "\n${BOLD}${CYAN}=== $1 ===${RESET}\n"; }
ok()     { echo -e "${GREEN}$1${RESET}"; }
warn()   { echo -e "${YELLOW}$1${RESET}"; }
fail()   { echo -e "${RED}$1${RESET}"; }
pause()  { echo -e "\n${BOLD}Press Enter to continue...${RESET}"; read -r; }

echo -e "${BOLD}"
echo "  _   _       _   _  __ _ _ "
echo " | \\ | | ___ | |_(_)/ _(_|_)"
echo " |  \\| |/ _ \\| __| | |_| | |"
echo " | |\\  | (_) | |_| |  _| | |"
echo " |_| \\_|\\___/ \\__|_|_| |_|_|"
echo ""
echo " Cloud-Agnostic Notification Platform"
echo -e "${RESET}"
echo "This demo walks through the full notification lifecycle:"
echo "  1. Send notification  ->  queue  ->  deliver"
echo "  2. Simulate failure   ->  DLQ"
echo "  3. Retry from DLQ     ->  successful delivery"
echo ""

# ─── Check if services are running ────────────────────────────
header "Checking services"
if curl -sf "$API/health" > /dev/null 2>&1; then
    ok "API is running at $API"
else
    warn "API not running. Starting with docker compose..."
    docker compose up --build -d
    echo "Waiting for services to start..."
    for i in $(seq 1 30); do
        if curl -sf "$API/health" > /dev/null 2>&1; then
            ok "Services started!"
            break
        fi
        sleep 1
        if [ "$i" -eq 30 ]; then
            fail "Services failed to start. Run 'docker compose logs' for details."
            exit 1
        fi
    done
fi

CONFIG=$(curl -sf "$API/internal/config")
echo "Config: $CONFIG" | python3 -m json.tool 2>/dev/null || echo "$CONFIG"

pause

# ─── Step 1: Send a notification ──────────────────────────────
header "Step 1: Send a notification"
echo "Sending email to demo@example.com..."
RESPONSE=$(curl -sf -X POST "$API/v1/notifications:send" \
    -H "Content-Type: application/json" \
    -H "X-Request-Id: demo-trace-001" \
    -d '{"channel":"email","recipient":"demo@example.com","message":"Hello from Notifii demo!","idempotency_key":"demo-key-001"}')
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
MESSAGE_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['message_id'])" 2>/dev/null || echo "unknown")
ok "Notification queued: $MESSAGE_ID"

echo ""
echo "Waiting for worker to process..."
sleep 3

echo ""
echo "Checking recent notifications:"
curl -sf "$API/v1/notifications/recent?count=5" | python3 -m json.tool 2>/dev/null

pause

# ─── Step 1b: Idempotency check ──────────────────────────────
header "Step 1b: Idempotency - sending duplicate"
echo "Sending same idempotency_key again..."
DUP_RESPONSE=$(curl -sf -X POST "$API/v1/notifications:send" \
    -H "Content-Type: application/json" \
    -d '{"channel":"email","recipient":"demo@example.com","message":"Duplicate!","idempotency_key":"demo-key-001"}')
echo "$DUP_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DUP_RESPONSE"
DUP_ID=$(echo "$DUP_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['message_id'])" 2>/dev/null || echo "unknown")

if [ "$MESSAGE_ID" = "$DUP_ID" ]; then
    ok "Idempotency working! Same message_id returned: $DUP_ID"
else
    warn "Got different message_id (idempotency may use memory backend)"
fi

pause

# ─── Step 2: Simulate provider failure ───────────────────────
header "Step 2: Enable provider failure simulation"
curl -sf -X POST "$API/internal/simulate/provider-failure?enable=true" | python3 -m json.tool 2>/dev/null
warn "Provider failure simulation ENABLED"

echo ""
echo "Sending notification (this will fail)..."
FAIL_RESPONSE=$(curl -sf -X POST "$API/v1/notifications:send" \
    -H "Content-Type: application/json" \
    -d '{"channel":"email","recipient":"failure-test@example.com","message":"This should fail and go to DLQ"}')
echo "$FAIL_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$FAIL_RESPONSE"

echo ""
echo "Waiting for worker to process (and fail)..."
sleep 5

pause

# ─── Step 3: Check the DLQ ───────────────────────────────────
header "Step 3: Check Dead Letter Queue"
DLQ_RESPONSE=$(curl -sf "$API/v1/queue/dlq")
echo "$DLQ_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DLQ_RESPONSE"

DLQ_COUNT=$(echo "$DLQ_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "0")
if [ "$DLQ_COUNT" -gt 0 ]; then
    ok "Found $DLQ_COUNT message(s) in DLQ"
    DLQ_ENTRY_ID=$(echo "$DLQ_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['dlq_messages'][0]['id'])" 2>/dev/null || echo "")
else
    warn "DLQ empty (worker may not have processed yet, or DLQ routing needs more retries)"
    DLQ_ENTRY_ID=""
fi

pause

# ─── Step 4: Disable failure and retry ───────────────────────
header "Step 4: Disable failure + retry from DLQ"
curl -sf -X POST "$API/internal/simulate/provider-failure?enable=false" | python3 -m json.tool 2>/dev/null
ok "Provider failure simulation DISABLED"

if [ -n "$DLQ_ENTRY_ID" ]; then
    echo ""
    echo "Retrying DLQ message: $DLQ_ENTRY_ID"
    curl -sf -X POST "$API/v1/queue/dlq/$DLQ_ENTRY_ID/retry" | python3 -m json.tool 2>/dev/null
    ok "Message re-queued for delivery!"
    
    echo ""
    echo "Waiting for worker to deliver..."
    sleep 3
else
    warn "No DLQ entry to retry (skipping)"
fi

pause

# ─── Step 5: Verify successful delivery ──────────────────────
header "Step 5: Verify delivery"
echo "Recent notifications:"
curl -sf "$API/v1/notifications/recent?count=10" | python3 -m json.tool 2>/dev/null

echo ""
echo "Queue depth:"
curl -sf "$API/v1/queue/depth" | python3 -m json.tool 2>/dev/null

echo ""
echo "Metrics:"
curl -sf "$API/metrics"

pause

# ─── Summary ─────────────────────────────────────────────────
header "Demo Complete!"
echo -e "What you just saw:"
echo -e "  ${GREEN}1.${RESET} Notification sent via API -> queued -> delivered by worker"
echo -e "  ${GREEN}2.${RESET} Idempotency prevented duplicate processing"
echo -e "  ${GREEN}3.${RESET} Simulated provider failure -> message routed to DLQ"
echo -e "  ${GREEN}4.${RESET} DLQ retry -> successful delivery"
echo -e "  ${GREEN}5.${RESET} Full observability: metrics, request IDs, structured logs"
echo ""
echo -e "Explore more:"
echo -e "  Dashboard:  ${CYAN}http://localhost:5173${RESET}"
echo -e "  Mailhog:    ${CYAN}http://localhost:8025${RESET}"
echo -e "  Metrics:    ${CYAN}http://localhost:8000/metrics${RESET}"
echo -e "  API docs:   ${CYAN}http://localhost:8000/docs${RESET}"
echo ""
