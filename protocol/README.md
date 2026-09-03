# protocol

Cross-platform protocol definitions for zenoh-fleet-control.

Documents:

- [keyspace.md](keyspace.md): Zenoh topic/key naming rules.
- [messages.md](messages.md): JSON message schemas for device, session, command, event, result, approval, and media.

The protocol is language-agnostic. Python agent, Android App, and future Rust/JVM agents should follow these files.

Architecture reference:

- [../docs/file-transfer-architecture.md](../docs/file-transfer-architecture.md): file API, MinIO, authentication, lifecycle, and failure handling.
