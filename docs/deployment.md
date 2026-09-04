# Deployment

详细文件传输设计见 [file-transfer-architecture.md](file-transfer-architecture.md)。

Recommended cloud layout:

```text
zenohd
zfc-bridge-api
zfc-file-api
MinIO
```

- `zenohd` carries commands, session state, events, and `TransferRef`.
- `zfc-bridge-api` exposes HTTPS login/session/device APIs for Android and browser clients, then forwards control messages to Zenoh.
- `zfc-file-api` authenticates App/Agent callers and generates short-lived presigned URLs.
- `MinIO` stores the real file bytes.

## Local MinIO

Local validation has been done with Docker Engine 29.6.1, Docker Compose v5.2.0, and the `minio/minio:latest` image currently referenced by the scripts.

```bash
docker pull minio/minio:latest
cd deploy/local
docker compose up -d minio
```

MinIO API: `http://127.0.0.1:9000`
MinIO console: `http://127.0.0.1:9001`

Development credentials:

```text
MINIO_ROOT_USER=zfcadmin
MINIO_ROOT_PASSWORD=zfcadmin123
```

Do not use these credentials in production.

## File API

The Python service was validated in a Python 3.13.13 virtual environment with the `eclipse-zenoh` 1.10.0 binding available in `file-api` and `agent-python`.

```bash
cd file-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
zfc-file-api
```

The App asks `zfc-file-api` for an upload URL, uploads bytes to MinIO, then sends the returned `TransferRef` through Zenoh. The Agent asks `zfc-file-api` for download URLs when it needs to export files back to the App.

## Bridge API

The mobile and browser entrypoint is `zfc-bridge-api`.

It should run behind HTTPS with a server certificate and key. For private CA deployments, export the CA certificate and import it into Android devices or browsers explicitly.

Example local run:

```bash
cd bridge-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ZFC_BRIDGE_USERS='{"eame":"password"}' ZFC_CONNECT=tcp/127.0.0.1:7447 zfc-bridge-api --host 0.0.0.0 --port 8443
```

The bridge handles login, token issuance, session reads, directory queries, and command/control publishing. It does not replace Zenoh for the agent side.

For a local developer setup, `scripts/start-bridge-api.sh` starts the bridge with a temporary CA and prints the generated CA certificate path. Import that CA into Android or browser trust stores manually before connecting.

The bridge also serves the browser console from the same origin:

```text
https://127.0.0.1:8443/
```

The browser console uses the same login endpoint and bearer token as the Android app. It should be used over HTTPS in real deployments. A plain HTTP bridge can be useful for local automated browser tests when the test runner cannot accept a private CA, but that mode should bind to loopback only.

For the complete Android simulation stack, use `scripts/start-android-sim-backend.sh`.
It starts MinIO, file-api, zenohd, the Python agent, and the HTTPS bridge. Set
`ZFC_BRIDGE_IP` to the server's LAN address when a real phone connects, so the
generated certificate contains the correct IP in its SAN.

## Security

- Put HTTPS in front of `zfc-file-api` and MinIO.
- Put HTTPS in front of `zfc-bridge-api`.
- Prefer user-scoped or device-scoped bearer tokens over a shared development token.
- The legacy shared bearer token is only for local prototyping.
- Bind each object key to `u/<username>/fleet/<device_id>/sessions/<session_id>/...`.
- Keep presigned URL TTL short.
- Enable Zenoh TLS/mTLS and ACL separately; file API authentication does not secure Zenoh.
- Import private CA certificates manually on Android and browser clients; do not assume the client can discover the CA automatically.
- Replace prototype SharedPreferences password/token storage with platform encrypted storage before real phone use.
- Replace `ZFC_BRIDGE_USERS` plaintext credentials with a hashed account store before shared deployment.

## Verified command

During local validation, `zfc-file-api` returned an S3 `TransferRef` like:

```text
s3://zfc-transfers/u/eame/fleet/dev-minio-test/sessions/sess-minio-test/transfers/<transfer_id>/payload.zip
```

Uploading through the presigned PUT URL and downloading through the presigned GET URL both succeeded. Requests without `Authorization: Bearer <token>` returned `401`.

生产环境不要把 MinIO 管理端口直接暴露给公网；App 和 Agent 应通过 file-api 获取受限的短期 URL。


## Local Transfer Verification

Run the local end-to-end check after Docker and Python dependencies are available:

```bash
./scripts/verify-file-api-minio.sh
```

It starts MinIO, zfc-file-api, zenohd, and a Python agent, then verifies S3-backed import/export through Zenoh commands.

For a full chat-attachment simulation with a PDF and Codex running from a normal user directory:

```bash
PDF_PATH=/path/to/book.pdf ./scripts/verify-chat-attachment-pdf.sh
```

The script intentionally rejects root execution and defaults the agent cwd to `/home/eame/Downloads` to cover non-Git working directories.
