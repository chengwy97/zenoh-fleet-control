#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
API_DIR="$ROOT_DIR/file-api"
AGENT_DIR="$ROOT_DIR/agent-python"
ZENOH_BIN=${ZENOH_BIN:-/home/eame/Documents/magiclab/zenoh/zenoh/target/release/zenohd}
FILE_API_URL=${ZFC_FILE_API_URL:-http://127.0.0.1:8080}
FILE_API_TOKEN=${ZFC_FILE_API_TOKEN:-dev-token-change-me}
ZENOH_CONNECT=${ZFC_CONNECT:-tcp/127.0.0.1:7447}

API_PID=
ZENOH_PID=
AGENT_PID=
WORK_DIR=$(mktemp -d)
COMPOSE_DIR="$ROOT_DIR/deploy/local"

cleanup() {
  if [[ -n "${AGENT_PID}" ]]; then kill "${AGENT_PID}" 2>/dev/null || true; fi
  if [[ -n "${ZENOH_PID}" ]]; then kill "${ZENOH_PID}" 2>/dev/null || true; fi
  if [[ -n "${API_PID}" ]]; then kill "${API_PID}" 2>/dev/null || true; fi
  docker compose -f "${COMPOSE_DIR}/docker-compose.yml" down >/dev/null 2>&1 || true
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

wait_http() {
  local url=$1
  for _ in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "timed out waiting for $url" >&2
  return 1
}

cd "$COMPOSE_DIR"
docker compose up -d minio

cd "$API_DIR"
python3 -m venv .venv
.venv/bin/pip install -q -e .
ZFC_S3_ENDPOINT=${ZFC_S3_ENDPOINT:-http://127.0.0.1:9000} \
ZFC_S3_ACCESS_KEY=${ZFC_S3_ACCESS_KEY:-zfcadmin} \
ZFC_S3_SECRET_KEY=${ZFC_S3_SECRET_KEY:-zfcadmin123} \
ZFC_S3_BUCKET=${ZFC_S3_BUCKET:-zfc-transfers} \
ZFC_FILE_AUTH_TOKEN=${FILE_API_TOKEN} \
.venv/bin/uvicorn zfc_file_api.api:app --host 127.0.0.1 --port 8080 >"$WORK_DIR/file-api.log" 2>&1 &
API_PID=$!
wait_http "$FILE_API_URL/healthz"

cd "$AGENT_DIR"
python3 -m venv .venv
.venv/bin/pip install -q -e .

if [[ ! -x "$ZENOH_BIN" ]]; then
  echo "zenohd not found or not executable: $ZENOH_BIN" >&2
  exit 1
fi
"$ZENOH_BIN" -l "$ZENOH_CONNECT" >"$WORK_DIR/zenohd.log" 2>&1 &
ZENOH_PID=$!
sleep 1

mkdir -p "$WORK_DIR/agent-root" "$WORK_DIR/app-source" "$WORK_DIR/app-output"
printf 'hello through minio\n' >"$WORK_DIR/app-source/hello.txt"

.venv/bin/zfc-agent \
  --username eame \
  --device-id dev_minio \
  --session-id sess_minio \
  --root "$WORK_DIR/agent-root" \
  --cwd "$WORK_DIR/agent-root" \
  --connect "$ZENOH_CONNECT" \
  --transfer-backend s3 \
  --transfer-store "$WORK_DIR/agent-cache" \
  --file-api-url "$FILE_API_URL" \
  --file-api-token "$FILE_API_TOKEN" \
  >"$WORK_DIR/agent.log" 2>&1 &
AGENT_PID=$!
sleep 2

.venv/bin/zfc-send-transfer \
  --username eame \
  --device-id dev_minio \
  --session-id sess_minio \
  --path "$WORK_DIR/app-source" \
  --target-path . \
  --connect "$ZENOH_CONNECT" \
  --transfer-backend s3 \
  --transfer-store "$WORK_DIR/client-cache" \
  --file-api-url "$FILE_API_URL" \
  --file-api-token "$FILE_API_TOKEN"

sleep 2
test -f "$WORK_DIR/agent-root/app-source/hello.txt"
cmp "$WORK_DIR/app-source/hello.txt" "$WORK_DIR/agent-root/app-source/hello.txt"

.venv/bin/zfc-fetch-transfer \
  --username eame \
  --device-id dev_minio \
  --session-id sess_minio \
  --path app-source \
  --output-dir "$WORK_DIR/app-output" \
  --connect "$ZENOH_CONNECT" \
  --transfer-backend s3 \
  --transfer-store "$WORK_DIR/client-cache" \
  --file-api-url "$FILE_API_URL" \
  --file-api-token "$FILE_API_TOKEN"

cmp "$WORK_DIR/app-source/hello.txt" "$WORK_DIR/app-output/app-source/hello.txt"

printf 'chat attachment through minio\n' >"$WORK_DIR/chat-attachment.txt"
ASSET_ID=$(.venv/bin/zfc-send-media \
  --username eame \
  --device-id dev_minio \
  --session-id sess_minio \
  --path "$WORK_DIR/chat-attachment.txt" \
  --description "Use this attachment in the next chat turn" \
  --connect "$ZENOH_CONNECT" \
  --transfer-backend s3 \
  --transfer-store "$WORK_DIR/client-cache" \
  --file-api-url "$FILE_API_URL" \
  --file-api-token "$FILE_API_TOKEN")
sleep 2
test -f "$WORK_DIR/agent-root/.zfc/media/$ASSET_ID/chat-attachment.txt"
cmp "$WORK_DIR/chat-attachment.txt" "$WORK_DIR/agent-root/.zfc/media/$ASSET_ID/chat-attachment.txt"

echo "file-api + minio + zenoh agent transfer ok"
