# Security

## Responsibility model

File transfer design is documented in [docs/file-transfer-architecture.md](docs/file-transfer-architecture.md).

Zenoh gives you security primitives, but they are not automatically enabled. The operator must explicitly configure transport security, authentication, and access control. If these settings are left open, the deployment should be treated as unsafe.

## Required baseline for cloud or shared deployments

- Enable TLS on the router.
- Prefer mTLS for device identity.
- Assign a unique certificate or identity per device.
- Deny anonymous access.
- Restrict each agent to its own `u/<username>/fleet/<device_id>/...` namespace.
- Rotate credentials and certificates on a schedule.

## Bridge and browser access

`zfc-bridge-api` is the public control-plane entrypoint for Android and browser clients. Production deployments must expose it only through HTTPS.

- Use a real certificate or a private CA that users import manually.
- Do not serve the browser console over plain HTTP except for isolated local automation.
- Treat bridge bearer tokens as session credentials.
- Keep token TTL short and invalidate tokens after password or device revocation changes.
- Validate path parameters against the authenticated user before forwarding anything to Zenoh.
- Do not let browser clients or Android clients connect directly to the production Zenoh router unless they have their own mTLS identity and ACL profile.

The current bridge prototype reads `ZFC_BRIDGE_USERS` as a username/password JSON map. This is acceptable for local validation only. A production deployment should use password hashing, account lockout/rate limiting, audit logs, and a proper account store.

## Android client notes

The Android app stores the bridge URL, username, password, and returned token in prototype SharedPreferences so it can reconnect without forcing the user through the connection page every time. This is a prototype convenience, not a final secret-storage design.

- Replace plain SharedPreferences with Android Keystore-backed encrypted storage before real use.
- The debug build contains a local emulator-only TLS bypass for `https://10.0.2.2`.
- Do not copy that debug trust behavior into release builds or real-phone deployments.
- Real phones should use a reachable HTTPS IP/domain and an imported CA or publicly trusted certificate.

## File API identity

生产 `zfc-file-api` 不得仅信任请求体中的 `username`、`device_id` 或 `session_id`。这些字段必须与认证 token、mTLS 证书或服务端会话身份进行授权匹配。

- App and agent callers should receive user/device/session scoped file tokens.
- Presigned upload URLs should be returned only to the uploader and should not be broadcast over Zenoh.
- MinIO object keys should remain under `u/<username>/fleet/<device_id>/sessions/<session_id>/...`.
- Keep presigned URL TTL short and use bucket lifecycle cleanup for expired temporary objects.
- Do not expose the MinIO admin console to the public internet.

## Recommended secrets and config handling

- Keep production credentials out of the repository.
- Use local config files only for examples.
- Store secrets in environment variables, secret managers, or mounted files.
- Treat sample config files as templates, not deployable defaults.

## Agent-side checks

- Reject path escape attempts for cwd and file operations.
- Validate uploaded assets by size and checksum before accepting them.
- Reject unknown command types.
- Never trust app-provided local paths.
- For chat attachments, resolve `asset_id` to a validated local file path before invoking Codex, Claude, shell tools, or media processors.

## Reporting

If you find a security issue in the protocol or validation agent, report it privately and include the affected component, keyspace, and reproduction steps.
