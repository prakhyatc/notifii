#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8000"
DASHBOARD="http://localhost:5173"
MAILHOG="http://localhost:8025"

BOLD="\033[1m"
DIM="\033[2m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
MAGENTA="\033[35m"
RESET="\033[0m"

clear
echo -e "${BOLD}${CYAN}"
cat << 'ART'
  ╔══════════════════════════════════════════════════════════╗
  ║                                                          ║
  ║    _   _       _   _  __ _ _                             ║
  ║   | \ | | ___ | |_(_)/ _(_|_)                            ║
  ║   |  \| |/ _ \| __| | |_| | |                            ║
  ║   | |\  | (_) | |_| |  _| | |                            ║
  ║   |_| \_|\___/ \__|_|_| |_|_|                            ║
  ║                                                          ║
  ║   Cloud-Agnostic Notification Platform                   ║
  ║   One-Click Demo                                         ║
  ║                                                          ║
  ╚══════════════════════════════════════════════════════════╝
ART
echo -e "${RESET}"

# ─── Step 0: Ensure .env exists ──────────────────────────────
if [ ! -f .env ]; then
    echo -e "${DIM}Creating .env from .env.example...${RESET}"
    cp .env.example .env
fi

# ─── Step 1: Check Docker ────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker Desktop first.${RESET}"
    echo "  https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Docker daemon is not running. Please start Docker Desktop.${RESET}"
    exit 1
fi

# ─── Step 2: Start services ─────────────────────────────────
ALREADY_RUNNING=false
if curl -sf "$API/health" > /dev/null 2>&1; then
    echo -e "${GREEN}Services already running.${RESET}"
    ALREADY_RUNNING=true
else
    echo -e "${BOLD}Starting Notifii stack...${RESET}"
    echo -e "${DIM}(API + Worker + Redis + Mailhog)${RESET}"
    echo ""
    docker-compose up --build -d 2>&1 | tail -5

    echo ""
    echo -ne "Waiting for API to be healthy "
    for i in $(seq 1 40); do
        if curl -sf "$API/health" > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}API is ready!${RESET}"
            break
        fi
        echo -n "."
        sleep 1
        if [ "$i" -eq 40 ]; then
            echo ""
            echo -e "${RED}API failed to start in 40s.${RESET}"
            echo "Check logs: docker-compose logs api"
            exit 1
        fi
    done
fi

# ─── Step 3: Seed demo data ─────────────────────────────────
echo ""
echo -e "${BOLD}Seeding demo notifications...${RESET}"
SEED_RESULT=$(curl -sf -X POST "$API/demo/seed" 2>/dev/null || echo '{"count":0}')
SEED_COUNT=$(echo "$SEED_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo "?")
echo -e "${GREEN}Seeded ${SEED_COUNT} example notifications${RESET}"

sleep 2

# ─── Step 4: Send one live notification ──────────────────────
echo ""
echo -e "${BOLD}Sending a live notification...${RESET}"
SEND_RESULT=$(curl -sf -X POST "$API/v1/notifications:send" \
    -H "Content-Type: application/json" \
    -H "X-Request-Id: demo-onboarding-001" \
    -d '{"channel":"email","recipient":"recruiter@example.com","message":"Welcome! This notification was sent by Notifii in under 30 seconds.","idempotency_key":"demo-onboard-001"}' 2>/dev/null || echo '{}')
MSG_ID=$(echo "$SEND_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message_id','?')[:12])" 2>/dev/null || echo "?")
echo -e "${GREEN}Queued: ${MSG_ID}...${RESET}"

sleep 2

# ─── Step 5: Open dashboard ─────────────────────────────────
echo ""
echo -e "${BOLD}Opening dashboard...${RESET}"

# Detect OS and open browser
open_url() {
    local url="$1"
    if command -v xdg-open &> /dev/null; then
        xdg-open "$url" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "$url" 2>/dev/null &
    elif command -v start &> /dev/null; then
        start "$url" 2>/dev/null &
    else
        echo -e "${YELLOW}Could not auto-open browser. Open manually: ${url}${RESET}"
    fi
}

# Check if dashboard dev server is running
if curl -sf "$DASHBOARD" > /dev/null 2>&1; then
    open_url "$DASHBOARD"
    echo -e "${GREEN}Dashboard opened at ${DASHBOARD}${RESET}"
else
    echo -e "${DIM}Dashboard dev server not running. Opening API docs instead.${RESET}"
    open_url "$API/docs"
    echo -e "${GREEN}API Swagger UI opened at ${API}/docs${RESET}"
    echo -e "${DIM}To start the dashboard: cd dashboard && npm install && npm run dev${RESET}"
fi

# ─── Step 6: Print instructions ──────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ┌──────────────────────────────────────────────────────┐"
echo "  │                  DEMO READY!                         │"
echo "  └──────────────────────────────────────────────────────┘"
echo -e "${RESET}"
echo -e "  ${BOLD}Services:${RESET}"
echo -e "    API:        ${CYAN}${API}${RESET}"
echo -e "    API Docs:   ${CYAN}${API}/docs${RESET}"
echo -e "    Dashboard:  ${CYAN}${DASHBOARD}${RESET}"
echo -e "    Mailhog:    ${CYAN}${MAILHOG}${RESET}  ${DIM}(captured emails)${RESET}"
echo -e "    Metrics:    ${CYAN}${API}/metrics${RESET}"
echo ""
echo -e "  ${BOLD}Try these steps:${RESET}"
echo ""
echo -e "    ${GREEN}1.${RESET} ${BOLD}Open the Dashboard${RESET} ${DIM}(${DASHBOARD})${RESET}"
echo -e "       Go to the ${CYAN}Playground${RESET} tab."
echo ""
echo -e "    ${GREEN}2.${RESET} ${BOLD}Send a notification${RESET}"
echo -e "       Type a recipient and message, click ${CYAN}Send Notification${RESET}."
echo -e "       Watch it appear in ${CYAN}Overview${RESET} → Recent Notifications."
echo ""
echo -e "    ${GREEN}3.${RESET} ${BOLD}Simulate a failure${RESET}"
echo -e "       In Playground, click ${RED}Provider Failure: OFF${RESET} to turn it ${RED}ON${RESET}."
echo -e "       Send another notification. It will fail and move to the DLQ."
echo ""
echo -e "    ${GREEN}4.${RESET} ${BOLD}Retry from DLQ${RESET}"
echo -e "       Turn failure ${GREEN}OFF${RESET}. Go to the ${CYAN}Dead Letter Queue${RESET} tab."
echo -e "       Click ${GREEN}Retry${RESET} on the failed message. Watch it deliver."
echo ""
echo -e "    ${GREEN}5.${RESET} ${BOLD}Check Mailhog${RESET}"
echo -e "       Open ${CYAN}${MAILHOG}${RESET} to see all delivered emails."
echo ""
echo -e "  ${BOLD}Or use curl:${RESET}"
echo -e "  ${DIM}"
echo '    # Send a notification'
echo "    curl -X POST ${API}/v1/notifications:send \\"
echo '      -H "Content-Type: application/json" \\'
echo '      -d '"'"'{"channel":"email","recipient":"you@example.com","message":"Hello!"}'"'"''
echo ""
echo '    # Check queue depth'
echo "    curl ${API}/v1/queue/depth"
echo ""
echo '    # View metrics'
echo "    curl ${API}/metrics"
echo -e "  ${RESET}"
echo -e "  ${BOLD}Stop everything:${RESET}  make down"
echo ""
