# Changelog

## Unreleased

- Added `zfc-bridge-api` as the HTTPS entrypoint for Android and browser clients.
- Added same-origin browser console with login, terminal selection, directory browsing, command sending, cancel/end controls, and event/result polling.
- Added Android Compose MVP with bridge login, remembered connection settings, terminal/session UI, cwd switching, command sending, control actions, and attachment upload flow.
- Added bridge-side bearer token expiry checks and username/device/session identity validation before forwarding commands to Zenoh.
- Added debug-only Android emulator TLS bypass for `https://10.0.2.2`; production and real-device flows still require a trusted HTTPS certificate.
- Verified Codex execution through the Android emulator path and browser bridge path.
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
