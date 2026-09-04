#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ZENOH_BIN=${ZENOH_BIN:-/home/eame/Documents/magiclab/zenoh/zenoh/target/release/zenohd}
ZENOH_INFO_BIN=${ZENOH_INFO_BIN:-/home/eame/Documents/magiclab/zenoh/zenoh/target/release/examples/z_info}
WORK_DIR=${ZFC_ZENOH_TLS_VERIFY_DIR:-$(mktemp -d)}
ZENOH_PORT=${ZENOH_PORT:-17447}
ZENOH_PID=

cleanup() {
  if [[ -n "${ZENOH_PID}" ]]; then
    kill "${ZENOH_PID}" 2>/dev/null || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT INT TERM

if [[ ! -x "$ZENOH_BIN" ]]; then
  echo "zenohd not found or not executable: $ZENOH_BIN" >&2
  exit 1
fi
if [[ ! -x "$ZENOH_INFO_BIN" ]]; then
  echo "z_info example not found or not executable: $ZENOH_INFO_BIN" >&2
  exit 1
fi
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
CLIENT_KEY="$WORK_DIR/client.key"
CLIENT_CSR="$WORK_DIR/client.csr"
CLIENT_CRT="$WORK_DIR/client.crt"
SERVER_EXT="$WORK_DIR/server.ext"
CLIENT_EXT="$WORK_DIR/client.ext"
CLIENT_NO_CERT_CFG="$WORK_DIR/client-no-cert.json5"
CLIENT_CERT_CFG="$WORK_DIR/client-cert.json5"
CONFIG_FILE="$WORK_DIR/zenohd.json5"

openssl req -x509 -newkey rsa:2048 -nodes -keyout "$CA_KEY" -out "$CA_CRT" -subj "/CN=zfc-test-ca" -days 1 >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout "$SERVER_KEY" -out "$SERVER_CSR" -subj "/CN=localhost" >/dev/null 2>&1
openssl req -newkey rsa:2048 -nodes -keyout "$CLIENT_KEY" -out "$CLIENT_CSR" -subj "/CN=zfc-client" >/dev/null 2>&1
cat >"$SERVER_EXT" <<EOF
subjectAltName=DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth
EOF

cat >"$CLIENT_NO_CERT_CFG" <<EOF
{
  mode: "client",
  connect: { endpoints: ["tls/127.0.0.1:${ZENOH_PORT}"] },
  scouting: { multicast: { enabled: false } },
  transport: {
    link: {
      protocols: ["tls"],
      tls: {
        enable_mtls: true,
        verify_name_on_connect: false,
        root_ca_certificate: "$CA_CRT"
      }
    }
  }
}
EOF

cat >"$CLIENT_CERT_CFG" <<EOF
{
  mode: "client",
  connect: { endpoints: ["tls/127.0.0.1:${ZENOH_PORT}"] },
  scouting: { multicast: { enabled: false } },
  transport: {
    link: {
      protocols: ["tls"],
      tls: {
        enable_mtls: true,
        verify_name_on_connect: false,
        root_ca_certificate: "$CA_CRT",
        connect_private_key: "$CLIENT_KEY",
        connect_certificate: "$CLIENT_CRT"
      }
    }
  }
}
EOF
cat >"$CLIENT_EXT" <<EOF
extendedKeyUsage=clientAuth
EOF
openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" -CAcreateserial -out "$SERVER_CRT" -days 1 -sha256 -extfile "$SERVER_EXT" >/dev/null 2>&1
openssl x509 -req -in "$CLIENT_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" -CAcreateserial -out "$CLIENT_CRT" -days 1 -sha256 -extfile "$CLIENT_EXT" >/dev/null 2>&1

cat >"$CONFIG_FILE" <<EOF
{
  mode: "router",
  listen: { endpoints: { router: ["tls/127.0.0.1:${ZENOH_PORT}"] } },
  transport: {
    link: {
      protocols: ["tls"],
      tls: {
        enable_mtls: true,
        listen_certificate: "$SERVER_CRT",
        listen_private_key: "$SERVER_KEY",
        root_ca_certificate: "$CA_CRT",
        verify_name_on_connect: true
      }
    }
  }
}
EOF

"$ZENOH_BIN" -c "$CONFIG_FILE" >"$WORK_DIR/zenohd.log" 2>&1 &
ZENOH_PID=$!

for _ in $(seq 1 60); do
  if grep -q "zenohd" "$WORK_DIR/zenohd.log" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$ZENOH_PID" 2>/dev/null; then
    echo "zenohd exited early" >&2
    cat "$WORK_DIR/zenohd.log" >&2 || true
    exit 1
  fi
  sleep 0.5
done

if timeout 8s "$ZENOH_INFO_BIN" --config "$CLIENT_NO_CERT_CFG" >/dev/null 2>&1; then
  echo "unexpected success without client cert" >&2
  exit 1
fi

if ! timeout 8s "$ZENOH_INFO_BIN" --config "$CLIENT_CERT_CFG" >/dev/null 2>&1; then
  echo "mTLS session failed with client cert" >&2
  cat "$WORK_DIR/zenohd.log" >&2 || true
  exit 1
fi

echo "zenoh TLS/mTLS verification ok"
