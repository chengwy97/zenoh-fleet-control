# TODO

## P0: Android development and simulation environment

- [x] Decide Android project baseline: Kotlin 2.0.20, Gradle 8.13 wrapper, Android Gradle Plugin 8.13.0, Compose Material 3 BOM 2025.12.00, compile/target SDK 36, min SDK 26.
- [x] Record reproducible development versions: OpenJDK 21.0.11, Python 3.13.13, Gradle wrapper 8.13, Android Gradle Plugin 8.13.0, Kotlin 2.0.20.
- [x] Install or document Android Studio / Android SDK command-line tools.
- [x] Configure `ANDROID_HOME` and add SDK tools to `PATH`.
- [x] Install required SDK packages: platform tools, emulator, one recent Android platform, build tools, and a system image.
- [x] Create a local Android emulator profile for development.
- [x] Boot the AVD successfully and confirm adb reaches `device` state.
- [x] Verify host-to-emulator networking for local services:
  - emulator -> host `zfc-file-api`: `http://10.0.2.2:8080`
  - emulator -> host `zenohd`: TCP endpoint mapping to host router
  - emulator -> host MinIO presigned URLs
- [x] Decide Android Zenoh client strategy:
  - preferred: use an existing Zenoh Java/Kotlin-compatible binding if practical
  - fallback: add a small local HTTP/WebSocket bridge for MVP if native Android Zenoh integration blocks progress
- [x] Scaffold `app-android` as a runnable Android project.
- [x] Add one-command local backend launcher for Android simulation.
- [x] Include HTTPS bridge and temporary CA generation in the Android backend launcher.
- [x] Add one-command Android APK install/launch script for emulator verification.
- [x] Verify app can show mocked terminal/session data before real Zenoh wiring.

## P1: Android MVP features

- [x] Terminal list: online, busy, offline.
- [x] Session state: idle, running, queued, ended.
- [x] Directory browser backed by agent directory query, not app-side guessing.
- [x] Text command input and event/result stream display.
- [x] Chat attachment picker for images, PDFs, videos, audio, and ordinary files.
- [x] Attachment upload through `zfc-file-api + MinIO`; Zenoh carries only `asset_id` and `TransferRef`.
- [x] Cancel active task.
- [x] End session and start a clean session.
- [x] Read directory, event, and result snapshots through the HTTPS bridge when available.
- [x] Send `set_cwd` and `approval_response` through the correct bridge control/command endpoints.

## P1: Browser MVP features

- [x] Serve a browser console from `zfc-bridge-api`.
- [x] Browser login with bridge username/password.
- [x] Browser device list, session status, directory browsing, command send, cancel, and end session.
- [x] Browser event/result polling through the HTTPS bridge.
- [ ] Browser attachment upload through `zfc-file-api + MinIO`.
- [ ] Browser automated end-to-end test script.
- [ ] Browser SSE/WebSocket event stream to replace polling after API shape stabilizes.

## P2: Protocol and agent hardening

- [x] Durable queue storage for pending messages across agent restart.
- [x] Approval forwarding from Codex/Claude to mobile UI.
- [x] Claude adapter implementation.
- [x] Transfer progress events for large uploads/downloads.
- [x] Better file-api auth model: user/device scoped tokens instead of shared dev bearer token.
- [x] Zenoh TLS/mTLS deployment verification.
- [x] Validate URL/body identity fields before bridge forwarding and expire bearer tokens.
- [ ] Replace bridge polling with SSE or WebSocket push after the HTTP read model is stable.
- [ ] Persist bridge session/event cache for restart recovery.
- [ ] Replace prototype bridge password JSON with hashed account storage and token revocation.
- [ ] Replace Android prototype SharedPreferences secrets with Keystore-backed encrypted storage.

## Current host environment snapshot

- Java: present, OpenJDK 21.
- Verified Java runtime: OpenJDK 21.0.11.
- Verified Python runtime: 3.13.13.
- Gradle: missing from `PATH`.
- `ANDROID_HOME`: not configured.
- `adb`: missing from `PATH`.
- `emulator`: missing from `PATH`.
