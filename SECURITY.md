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

## Reporting

If you find a security issue in the protocol or validation agent, report it privately and include the affected component, keyspace, and reproduction steps.

## File API identity

生产 `zfc-file-api` 不得仅信任请求体中的 `username`、`device_id` 或 `session_id`。这些字段必须与认证 token、mTLS 证书或服务端会话身份进行授权匹配。
