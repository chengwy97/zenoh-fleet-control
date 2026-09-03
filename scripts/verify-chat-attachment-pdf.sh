#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
AGENT_DIR="$ROOT_DIR/agent-python"
FILE_API_DIR="$ROOT_DIR/file-api"
COMPOSE_FILE="$ROOT_DIR/deploy/local/docker-compose.yml"
ZENOH_BIN=${ZENOH_BIN:-/home/eame/Documents/magiclab/zenoh/zenoh/target/release/zenohd}
FILE_API_URL=${ZFC_FILE_API_URL:-http://127.0.0.1:8080}
FILE_API_TOKEN=${ZFC_FILE_API_TOKEN:-dev-token-change-me}
ZENOH_CONNECT=${ZFC_CONNECT:-tcp/127.0.0.1:7447}
PDF_PATH=${1:-${PDF_PATH:-/home/eame/Downloads/机会成本：做出高效决策的策略思维（人人需要了解的经济学概念、MBA决策思维工具，查理·芒格的关键思维模型：机会成本是投资决策的过滤器，聪... (z-library.sk, 1lib.sk, z-lib.sk).pdf}}
AGENT_ROOT=${AGENT_ROOT:-/home/eame}
AGENT_CWD=${AGENT_CWD:-/home/eame/Downloads}
USERNAME=${ZFC_USERNAME:-eame}
DEVICE_ID=${ZFC_DEVICE_ID:-dev_pdf_attachment}
SESSION_ID=${ZFC_SESSION_ID:-sess_pdf_attachment}
WORK_DIR=$(mktemp -d)

API_PID=
ZENOH_PID=
AGENT_PID=
WATCH_PID=
ASSET_ID=

cleanup() {
  if [[ -n "${WATCH_PID}" ]]; then kill "${WATCH_PID}" 2>/dev/null || true; fi
  if [[ -n "${AGENT_PID}" ]]; then kill "${AGENT_PID}" 2>/dev/null || true; fi
  if [[ -n "${ZENOH_PID}" ]]; then kill "${ZENOH_PID}" 2>/dev/null || true; fi
  if [[ -n "${API_PID}" ]]; then kill "${API_PID}" 2>/dev/null || true; fi
  docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
  if [[ -n "${ASSET_ID}" ]]; then
    rm -rf "$AGENT_CWD/.zfc/media/$ASSET_ID"
  fi
  rm -f "$AGENT_CWD/.zfc/sessions/$SESSION_ID.json"
  rmdir "$AGENT_CWD/.zfc/media" "$AGENT_CWD/.zfc/sessions" "$AGENT_CWD/.zfc" 2>/dev/null || true
  rm -rf "$WORK_DIR"
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

wait_for_log() {
  local pattern=$1
  local file=$2
  local seconds=$3
  for _ in $(seq 1 "$seconds"); do
    if grep -q "$pattern" "$file" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "timed out waiting for pattern: $pattern" >&2
  tail -n 160 "$file" >&2 || true
  return 1
}

if [[ "$(id -u)" == "0" ]]; then
  echo "do not run this verification as root" >&2
  exit 1
fi
if [[ ! -f "$PDF_PATH" ]]; then
  echo "PDF not found: $PDF_PATH" >&2
  exit 1
fi
if [[ ! -d "$AGENT_CWD" ]]; then
  echo "agent cwd not found: $AGENT_CWD" >&2
  exit 1
fi
if [[ ! -x "$ZENOH_BIN" ]]; then
  echo "zenohd not found or not executable: $ZENOH_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
agent-python/.venv/bin/python -m compileall -q agent-python/src
bash -n scripts/verify-chat-attachment-pdf.sh

docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
docker compose -f "$COMPOSE_FILE" up -d minio

cd "$FILE_API_DIR"
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

"$ZENOH_BIN" -l "$ZENOH_CONNECT" >"$WORK_DIR/zenohd.log" 2>&1 &
ZENOH_PID=$!
sleep 1

cd "$AGENT_DIR"
python3 -m venv .venv
.venv/bin/pip install -q -e .
.venv/bin/zfc-agent \
  --username "$USERNAME" \
  --device-id "$DEVICE_ID" \
  --session-id "$SESSION_ID" \
  --root "$AGENT_ROOT" \
  --cwd "$AGENT_CWD" \
  --connect "$ZENOH_CONNECT" \
  --transfer-backend s3 \
  --transfer-store "$WORK_DIR/agent-cache" \
  --file-api-url "$FILE_API_URL" \
  --file-api-token "$FILE_API_TOKEN" \
  >"$WORK_DIR/agent.log" 2>&1 &
AGENT_PID=$!
sleep 2

.venv/bin/zfc-watch-session \
  --username "$USERNAME" \
  --device-id "$DEVICE_ID" \
  --session-id "$SESSION_ID" \
  --connect "$ZENOH_CONNECT" \
  >"$WORK_DIR/watch.log" 2>&1 &
WATCH_PID=$!
sleep 1

ASSET_ID=$(.venv/bin/zfc-send-media \
  --username "$USERNAME" \
  --device-id "$DEVICE_ID" \
  --session-id "$SESSION_ID" \
  --path "$PDF_PATH" \
  --description "请分析这个 PDF 是否正常可读，并概括书名、作者、目录结构和主要内容。用户只关心分析结果，不关心文件存储位置。" \
  --connect "$ZENOH_CONNECT" \
  --transfer-backend s3 \
  --transfer-store "$WORK_DIR/client-cache" \
  --file-api-url "$FILE_API_URL" \
  --file-api-token "$FILE_API_TOKEN")

echo "asset_id=$ASSET_ID"
wait_for_log "media_ref" "$WORK_DIR/watch.log" 60
if [[ ! -f "$AGENT_CWD/.zfc/media/$ASSET_ID/$(basename "$PDF_PATH")" ]]; then
  echo "agent did not materialize PDF attachment" >&2
  exit 1
fi

CMD_ID=$(.venv/bin/zfc-send-command \
  --username "$USERNAME" \
  --device-id "$DEVICE_ID" \
  --session-id "$SESSION_ID" \
  --tool codex \
  --prompt "请分析刚刚上传的 PDF 附件。你需要读取 agent 本地已校验的附件路径，使用 pdfinfo、pdftotext 等工具判断 PDF 是否正常，并输出书名、作者、出版社、页数、目录结构、主题摘要和明显问题。不要只告诉我路径。" \
  --media "$ASSET_ID=这是用户上传的 PDF，请读取它并完成分析。" \
  --connect "$ZENOH_CONNECT")

echo "cmd_id=$CMD_ID"
wait_for_log "results/$CMD_ID" "$WORK_DIR/watch.log" 300
if ! grep -q '"status":"succeeded"' "$WORK_DIR/watch.log"; then
  echo "Codex PDF analysis did not succeed" >&2
  tail -n 180 "$WORK_DIR/watch.log" >&2
  exit 1
fi
if ! grep -q 'PDF 状态\|PDF' "$WORK_DIR/watch.log"; then
  echo "Codex result did not include a PDF analysis message" >&2
  tail -n 180 "$WORK_DIR/watch.log" >&2
  exit 1
fi

echo "uid=$(id -u) user=$(id -un) agent_cwd=$AGENT_CWD"
echo "chat attachment PDF verification ok"
