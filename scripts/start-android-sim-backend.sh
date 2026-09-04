#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ZENOH_BIN=${ZENOH_BIN:-/home/eame/Documents/magiclab/zenoh/zenoh/target/release/zenohd}
FILE_API_URL=${ZFC_FILE_API_URL:-http://127.0.0.1:8080}
FILE_API_TOKEN=${ZFC_FILE_API_TOKEN:-dev-token-change-me}
ZENOH_CONNECT=${ZFC_CONNECT:-tcp/127.0.0.1:7447}
USERNAME=${ZFC_USERNAME:-eame}
DEVICE_ID=${ZFC_DEVICE_ID:-dev_android_sim}
SESSION_ID=${ZFC_SESSION_ID:-sess_android_sim}
AGENT_ROOT=${AGENT_ROOT:-/home/eame}
AGENT_CWD=${AGENT_CWD:-/home/eame/Downloads}
WORK_DIR=${ZFC_SIM_WORK_DIR:-$ROOT_DIR/.zfc/android-sim}
BRIDGE_PORT=${ZFC_BRIDGE_PORT:-8443}
BRIDGE_USERS=${ZFC_BRIDGE_USERS:-'{"eame":"password"}'}
BRIDGE_HOSTNAME=${ZFC_BRIDGE_HOSTNAME:-localhost}
BRIDGE_IP=${ZFC_BRIDGE_IP:-}

API_PID=
ZENOH_PID=
AGENT_PID=
BRIDGE_PID=

cleanup() {
  if [[ -n "${AGENT_PID}" ]]; then kill "${AGENT_PID}" 2>/dev/null || true; fi
  if [[ -n "${ZENOH_PID}" ]]; then kill "${ZENOH_PID}" 2>/dev/null || true; fi
  if [[ -n "${API_PID}" ]]; then kill "${API_PID}" 2>/dev/null || true; fi
  if [[ -n "${BRIDGE_PID}" ]]; then kill "${BRIDGE_PID}" 2>/dev/null || true; fi
  docker compose -f "$ROOT_DIR/deploy/local/docker-compose.yml" down >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

wait_http() {
  local url=$1
  for _ in $(seq 1 60); do
    if curl -fksS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  echo "timed out waiting for $url" >&2
  return 1
}

if [[ "$(id -u)" == "0" ]]; then
  echo "do not run the simulation backend as root" >&2
  exit 1
fi
if [[ ! -x "$ZENOH_BIN" ]]; then
  echo "zenohd not found or not executable: $ZENOH_BIN" >&2
  exit 1
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required for the HTTPS bridge" >&2
  exit 1
fi

mkdir -p "$WORK_DIR"

echo "starting MinIO"
docker compose -f "$ROOT_DIR/deploy/local/docker-compose.yml" up -d minio

echo "starting zfc-file-api on $FILE_API_URL"
cd "$ROOT_DIR/file-api"
python3 -m venv .venv
.venv/bin/pip install -q -e .
ZFC_S3_ENDPOINT=${ZFC_S3_ENDPOINT:-http://127.0.0.1:9000} ZFC_S3_ACCESS_KEY=${ZFC_S3_ACCESS_KEY:-zfcadmin} ZFC_S3_SECRET_KEY=${ZFC_S3_SECRET_KEY:-zfcadmin123} ZFC_S3_BUCKET=${ZFC_S3_BUCKET:-zfc-transfers} ZFC_FILE_AUTH_TOKEN=${FILE_API_TOKEN} .venv/bin/uvicorn zfc_file_api.api:app --host 127.0.0.1 --port 8080 >"$WORK_DIR/file-api.log" 2>&1 &
API_PID=$!
wait_http "$FILE_API_URL/healthz"

echo "starting zenohd on $ZENOH_CONNECT"
"$ZENOH_BIN" -l "$ZENOH_CONNECT" >"$WORK_DIR/zenohd.log" 2>&1 &
ZENOH_PID=$!
sleep 1

echo "starting zfc-agent: user=$USERNAME device=$DEVICE_ID session=$SESSION_ID cwd=$AGENT_CWD"
cd "$ROOT_DIR/agent-python"
python3 -m venv .venv
.venv/bin/pip install -q -e .
.venv/bin/zfc-agent   --username "$USERNAME"   --device-id "$DEVICE_ID"   --session-id "$SESSION_ID"   --root "$AGENT_ROOT"   --cwd "$AGENT_CWD"   --connect "$ZENOH_CONNECT"   --transfer-backend s3   --transfer-store "$WORK_DIR/agent-cache"   --file-api-url "$FILE_API_URL"   --file-api-token "$FILE_API_TOKEN"   >"$WORK_DIR/agent.log" 2>&1 &
AGENT_PID=$!

echo "starting zfc-bridge-api on https://0.0.0.0:$BRIDGE_PORT"
CA_KEY="$WORK_DIR/ca.key"
CA_CRT="$WORK_DIR/ca.crt"
SERVER_KEY="$WORK_DIR/server.key"
SERVER_CSR="$WORK_DIR/server.csr"
SERVER_CRT="$WORK_DIR/server.crt"
SERVER_EXT="$WORK_DIR/server.ext"
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$CA_KEY" -out "$CA_CRT" \
  -subj "/CN=zfc-android-sim-ca" -days 365 >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout "$SERVER_KEY" -out "$SERVER_CSR" \
  -subj "/CN=$BRIDGE_HOSTNAME" >/dev/null 2>&1
SAN="DNS:$BRIDGE_HOSTNAME,DNS:localhost,IP:127.0.0.1,IP:10.0.2.2"
if [[ -n "$BRIDGE_IP" ]]; then
  SAN="$SAN,IP:$BRIDGE_IP"
fi
{
  echo "subjectAltName=$SAN"
  echo "extendedKeyUsage=serverAuth"
} >"$SERVER_EXT"
openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
  -CAcreateserial -out "$SERVER_CRT" -days 365 -sha256 -extfile "$SERVER_EXT" >/dev/null 2>&1

cd "$ROOT_DIR/bridge-api"
python3 -m venv .venv
.venv/bin/pip install -q -e .
ZFC_BRIDGE_USERS="$BRIDGE_USERS" ZFC_CONNECT="$ZENOH_CONNECT" \
  .venv/bin/zfc-bridge-api --host 0.0.0.0 --port "$BRIDGE_PORT" \
  --ssl-certfile "$SERVER_CRT" --ssl-keyfile "$SERVER_KEY" >"$WORK_DIR/bridge-api.log" 2>&1 &
BRIDGE_PID=$!
wait_http "https://127.0.0.1:$BRIDGE_PORT/healthz" || true

cat <<EOF

Android simulation backend is running.

Host endpoints:
  file-api: $FILE_API_URL
  minio:    http://127.0.0.1:9000
  zenoh:    $ZENOH_CONNECT
  bridge:   https://127.0.0.1:$BRIDGE_PORT
  bridge (emulator): https://10.0.2.2:$BRIDGE_PORT

Android emulator endpoints:
  file-api: http://10.0.2.2:8080
  minio:    http://10.0.2.2:9000
  zenoh:    tcp/10.0.2.2:7447

Bridge CA certificate for Android/browser import:
  $CA_CRT

Bridge login users:
  $BRIDGE_USERS

Namespace:
  username:   $USERNAME
  device_id:  $DEVICE_ID
  session_id: $SESSION_ID

Logs:
  $WORK_DIR/file-api.log
  $WORK_DIR/zenohd.log
  $WORK_DIR/agent.log
  $WORK_DIR/bridge-api.log

Press Ctrl+C to stop all services.
EOF

while true; do
  sleep 5
  if ! kill -0 "$API_PID" 2>/dev/null; then echo "file-api stopped" >&2; exit 1; fi
  if ! kill -0 "$ZENOH_PID" 2>/dev/null; then echo "zenohd stopped" >&2; exit 1; fi
  if ! kill -0 "$AGENT_PID" 2>/dev/null; then echo "zfc-agent stopped" >&2; exit 1; fi
  if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then echo "bridge-api stopped" >&2; exit 1; fi
done
