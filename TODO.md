# TODO

## P0: Android development and simulation environment

- [ ] Decide Android project baseline: Kotlin, Gradle wrapper, Android Gradle Plugin, Compose Material 3.
- [ ] Install or document Android Studio / Android SDK command-line tools.
- [ ] Configure `ANDROID_HOME` and add SDK tools to `PATH`.
- [ ] Install required SDK packages: platform tools, emulator, one recent Android platform, build tools, and a system image.
- [ ] Create a local Android emulator profile for development.
- [ ] Verify host-to-emulator networking for local services:
  - emulator -> host `zfc-file-api`: `http://10.0.2.2:8080`
  - emulator -> host `zenohd`: TCP endpoint mapping to host router
  - emulator -> host MinIO presigned URLs
- [ ] Decide Android Zenoh client strategy:
  - preferred: use an existing Zenoh Java/Kotlin-compatible binding if practical
  - fallback: add a small local HTTP/WebSocket bridge for MVP if native Android Zenoh integration blocks progress
- [ ] Scaffold `app-android` as a runnable Android project.
- [ ] Add one-command local backend launcher for Android simulation.
- [ ] Verify app can show mocked terminal/session data before real Zenoh wiring.

## P1: Android MVP features

- [ ] Terminal list: online, busy, offline.
- [ ] Session state: idle, running, queued, ended.
- [ ] Directory browser backed by agent directory query, not app-side guessing.
- [ ] Text command input and event/result stream display.
- [ ] Chat attachment picker for images, PDFs, videos, audio, and ordinary files.
- [ ] Attachment upload through `zfc-file-api + MinIO`; Zenoh carries only `asset_id` and `TransferRef`.
- [ ] Cancel active task.
- [ ] End session and start a clean session.

## P2: Protocol and agent hardening

- [ ] Durable queue storage for pending messages across agent restart.
- [ ] Approval forwarding from Codex/Claude to mobile UI.
- [ ] Claude adapter implementation.
- [ ] Transfer progress events for large uploads/downloads.
- [ ] Better file-api auth model: user/device scoped tokens instead of shared dev bearer token.
- [ ] Zenoh TLS/mTLS deployment verification.

## Current host environment snapshot

- Java: present, OpenJDK 21.
- Gradle: missing from `PATH`.
- `ANDROID_HOME`: not configured.
- `adb`: missing from `PATH`.
- `emulator`: missing from `PATH`.
