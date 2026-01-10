#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

docker run --rm --platform linux/amd64 -v "${ROOT}:/local" openapitools/openapi-generator-cli generate \
  -i /local/services/notification-api/openapi/notifii.openapi.yaml \
  -g python-fastapi \
  -o /local/services/notification-api/generated