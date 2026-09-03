#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
API_DIR="$ROOT_DIR/file-api"

cd "$ROOT_DIR/deploy/local"
docker compose up -d minio

cd "$API_DIR"
python3 -m venv .venv
.venv/bin/pip install -e .

ZFC_S3_ENDPOINT=${ZFC_S3_ENDPOINT:-http://127.0.0.1:9000} \
ZFC_S3_ACCESS_KEY=${ZFC_S3_ACCESS_KEY:-zfcadmin} \
ZFC_S3_SECRET_KEY=${ZFC_S3_SECRET_KEY:-zfcadmin123} \
ZFC_S3_BUCKET=${ZFC_S3_BUCKET:-zfc-transfers} \
ZFC_FILE_AUTH_TOKEN=${ZFC_FILE_AUTH_TOKEN:-dev-token-change-me} \
.venv/bin/python - <<'PYTEST'
import hashlib
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zfc_file_api.api import create_app

# Import smoke test first; run the HTTP check against a separately started zfc-file-api.
print(create_app().title)

base = 'http://127.0.0.1:8080'
token = 'Bearer dev-token-change-me'
payload = b'zfc file api verification\n'
digest = hashlib.sha256(payload).hexdigest()
request_data = json.dumps({
    'username': 'eame',
    'device_id': 'dev-file-api',
    'session_id': 'sess-file-api',
    'name': 'payload.zip',
    'archive': 'zip',
    'size': len(payload),
    'sha256': digest,
}).encode()
try:
    urlopen(Request(base + '/v1/transfers/uploads', data=b'{}', method='POST', headers={'Content-Type': 'application/json'}), timeout=5)
except HTTPError as exc:
    assert exc.code == 401
request = Request(base + '/v1/transfers/uploads', data=request_data, method='POST', headers={'Authorization': token, 'Content-Type': 'application/json'})
with urlopen(request, timeout=10) as response:
    ref = json.load(response)
with urlopen(Request(ref['upload_url'], data=payload, method='PUT'), timeout=10) as response:
    assert response.status in (200, 204)
with urlopen(Request(ref['download_url'], method='GET'), timeout=10) as response:
    assert response.read() == payload
print(ref['transfer_id'])
print('file api minio ok')
PYTEST
