# scripts

Development helper scripts.
- `verify-chat-attachment-pdf.sh`: starts local MinIO, file-api, zenohd, and an agent in a non-Git user directory, uploads a PDF as a chat attachment through file-api/MinIO, and verifies Codex can analyze it.
- `check-android-env.sh`: checks Java, Android SDK, adb, emulator, and sdkmanager prerequisites for Android development.
- `start-android-sim-backend.sh`: keeps MinIO, zfc-file-api, zenohd, and a Python agent running for Android emulator/manual app testing.
