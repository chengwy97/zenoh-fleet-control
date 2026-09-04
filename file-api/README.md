# zfc-file-api

Authenticated file transfer API for zenoh-fleet-control.

It does not replace Zenoh. Zenoh carries commands, state, and `TransferRef`; this service generates short-lived S3/MinIO presigned URLs for the actual file bytes.

## Local dependencies

```bash
cd file-api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment

```bash
export ZFC_S3_ENDPOINT=http://127.0.0.1:9000
export ZFC_S3_ACCESS_KEY=zfcadmin
export ZFC_S3_SECRET_KEY=zfcadmin123
export ZFC_S3_BUCKET=zfc-transfers
export ZFC_FILE_USER_TOKENS='{"eame":"user-token-eame"}'
export ZFC_FILE_DEVICE_TOKENS='{"eame/dev1":"device-token-dev1"}'
export ZFC_FILE_AUTH_TOKEN=dev-token-change-me
```

## Run

```bash
zfc-file-api
```

Create an upload URL:

```bash
curl -H 'Authorization: Bearer dev-token-change-me' \
  -H 'Content-Type: application/json' \
  -d '{"username":"eame","device_id":"dev1","session_id":"sess1","name":"payload.zip","archive":"zip"}' \
  http://127.0.0.1:8080/v1/transfers/uploads

For scoped tokens, use either `Bearer user-token-eame` for all `eame` requests or `Bearer device-token-dev1` for the exact `eame/dev1` device scope.
```

## Verified locally

The local flow has been verified with `minio/minio:latest`:

1. Start MinIO on `127.0.0.1:9000`.
2. Start `zfc-file-api` on `127.0.0.1:8080`.
3. Request an authenticated presigned upload URL.
4. Upload bytes directly to MinIO with the returned URL.
5. Download bytes with the returned download URL and compare content.
6. Confirm missing bearer token returns `401`.

A helper script is available at `scripts/verify-file-api-minio.sh`. It expects `zfc-file-api` to be running on port `8080` for the HTTP portion.
