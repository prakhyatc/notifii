#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${1:-light}"
BASE_URL="${BASE_URL:-http://localhost:8000}"

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   Notifii Load Test — k6              ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"

# Check k6 is installed
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}k6 is not installed.${RESET}"
    echo ""
    echo "Install it:"
    echo "  macOS:   brew install k6"
    echo "  Linux:   sudo snap install k6"
    echo "  Docker:  docker run --rm -i grafana/k6 run - <script.js"
    echo "  Other:   https://k6.io/docs/get-started/installation/"
    exit 1
fi

# Check API is running
echo -e "Checking API at ${CYAN}${BASE_URL}${RESET}..."
if ! curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${YELLOW}API not running. Start it first:${RESET}"
    echo "  make up        # Docker Compose"
    echo "  make up-jaeger # With tracing"
    exit 1
fi
echo -e "${GREEN}API is healthy${RESET}"
echo ""

# Show profile info
case "$PROFILE" in
    light)
        echo -e "Profile: ${GREEN}light${RESET} (ramp to 100 VUs over 50s)"
        ;;
    medium)
        echo -e "Profile: ${YELLOW}medium${RESET} (ramp to 500 VUs over 70s)"
        ;;
    heavy)
        echo -e "Profile: ${RED}heavy${RESET} (ramp to 1000 VUs over 90s)"
        ;;
    *)
        echo -e "${RED}Unknown profile: ${PROFILE}${RESET}"
        echo "Available: light, medium, heavy"
        exit 1
        ;;
esac
echo ""

# Run k6
k6 run \
    -e PROFILE="$PROFILE" \
    -e BASE_URL="$BASE_URL" \
    "$SCRIPT_DIR/send_notifications.js"

echo ""
echo -e "${BOLD}Post-test: waiting 10s for worker to drain queue...${RESET}"
sleep 10

echo ""
echo -e "${BOLD}Final queue state:${RESET}"
curl -sf "${BASE_URL}/v1/queue/depth" | python3 -m json.tool 2>/dev/null || echo "(could not fetch)"
echo ""
echo -e "${BOLD}Final metrics:${RESET}"
curl -sf "${BASE_URL}/metrics/json" | python3 -m json.tool 2>/dev/null || echo "(could not fetch)"
