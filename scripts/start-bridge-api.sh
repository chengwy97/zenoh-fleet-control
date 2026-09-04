#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BRIDGE_DIR="$ROOT_DIR/bridge-api"
WORK_DIR=${ZFC_BRIDGE_WORK_DIR:-$ROOT_DIR/.zfc/bridge}
BRIDGE_HOST=${ZFC_BRIDGE_HOST:-0.0.0.0}
BRIDGE_PORT=${ZFC_BRIDGE_PORT:-8443}
ZENOH_CONNECT=${ZFC_CONNECT:-tcp/127.0.0.1:7447}
BRIDGE_USERS=${ZFC_BRIDGE_USERS:-'{"eame":"password"}'}
BRIDGE_HOSTNAME=${ZFC_BRIDGE_HOSTNAME:-localhost}
BRIDGE_IP=${ZFC_BRIDGE_IP:-}

BRIDGE_PID=

cleanup() {
  if [[ -n "${BRIDGE_PID:-}" ]]; then
    kill "$BRIDGE_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

mkdir -p "$WORK_DIR"

CA_KEY="$WORK_DIR/ca.key"
CA_CRT="$WORK_DIR/ca.crt"
SERVER_KEY="$WORK_DIR/server.key"
SERVER_CSR="$WORK_DIR/server.csr"
SERVER_CRT="$WORK_DIR/server.crt"
SERVER_EXT="$WORK_DIR/server.ext"

openssl req -x509 -newkey rsa:2048 -nodes -keyout "$CA_KEY" -out "$CA_CRT" -subj "/CN=zfc-bridge-ca" -days 365 >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout "$SERVER_KEY" -out "$SERVER_CSR" -subj "/CN=$BRIDGE_HOSTNAME" >/dev/null 2>&1
SAN="DNS:$BRIDGE_HOSTNAME,DNS:localhost,IP:127.0.0.1,IP:10.0.2.2"
if [[ -n "$BRIDGE_IP" ]]; then
  SAN="$SAN,IP:$BRIDGE_IP"
fi
cat >"$SERVER_EXT" <<EOF
subjectAltName=$SAN
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" -CAcreateserial -out "$SERVER_CRT" -days 365 -sha256 -extfile "$SERVER_EXT" >/dev/null 2>&1

cd "$BRIDGE_DIR"
python3 -m venv .venv
.venv/bin/pip install -q -e .

ZFC_BRIDGE_USERS="$BRIDGE_USERS" ZFC_CONNECT="$ZENOH_CONNECT" \
  .venv/bin/zfc-bridge-api --host "$BRIDGE_HOST" --port "$BRIDGE_PORT" \
  --ssl-certfile "$SERVER_CRT" --ssl-keyfile "$SERVER_KEY" >"$WORK_DIR/bridge-api.log" 2>&1 &
BRIDGE_PID=$!

cat <<EOF

zfc-bridge-api is running.

HTTPS endpoint:
  https://127.0.0.1:${BRIDGE_PORT}

Certificate SAN:
  $SAN

CA certificate for Android/browser import:
  $CA_CRT

Login users:
  $BRIDGE_USERS

Log:
  $WORK_DIR/bridge-api.log

Press Ctrl+C to stop.
EOF

while true; do
  sleep 5
  if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
    echo "bridge-api stopped" >&2
    exit 1
  fi
done
