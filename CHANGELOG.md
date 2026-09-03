# Changelog

## Unreleased

- Added Zenoh-based directory query support for agents.
- Added structured `set_cwd` command handling on the agent side.
- Added local CLI support for directory listing queries.
- Added initial security and contribution guidance.
- Added sample configuration files for agent and router security settings.
- Added file/directory transfer backend abstraction with a runnable local spool backend.
- Added `zfc-file-api` skeleton for authenticated MinIO/S3 presigned URL transfer flow.
- Verified MinIO presigned upload/download and unauthenticated rejection locally.
- Added file-transfer architecture guidance for zfc-file-api, MinIO, TransferRef, and production identity checks.

## 0.1.0

- Initial protocol and Python validation agent prototype.
