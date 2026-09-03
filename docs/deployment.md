# Deployment

详细文件传输设计见 [file-transfer-architecture.md](file-transfer-architecture.md)。

Recommended cloud layout:

```text
zenohd
zfc-file-api
MinIO
```

- `zenohd` carries commands, session state, events, and `TransferRef`.
- `zfc-file-api` authenticates App/Agent callers and generates short-lived presigned URLs.
- `MinIO` stores the real file bytes.

## Local MinIO

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

```bash
cd file-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
zfc-file-api
```

The App asks `zfc-file-api` for an upload URL, uploads bytes to MinIO, then sends the returned `TransferRef` through Zenoh. The Agent asks `zfc-file-api` for download URLs when it needs to export files back to the App.

## Security

- Put HTTPS in front of `zfc-file-api` and MinIO.
- Replace the development bearer token.
- Bind each object key to `u/<username>/fleet/<device_id>/sessions/<session_id>/...`.
- Keep presigned URL TTL short.
- Enable Zenoh TLS/mTLS and ACL separately; file API authentication does not secure Zenoh.

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
