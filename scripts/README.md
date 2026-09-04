# scripts

Development helper scripts.
- `verify-chat-attachment-pdf.sh`: starts local MinIO, file-api, zenohd, and an agent in a non-Git user directory, uploads a PDF as a chat attachment through file-api/MinIO, and verifies Codex can analyze it.
- `check-android-env.sh`: checks Java, Android SDK, adb, emulator, and sdkmanager prerequisites for Android development.
- `start-android-sim-backend.sh`: keeps MinIO, zfc-file-api, zenohd, a Python agent, and the HTTPS bridge running for Android emulator/manual app testing.
- `start-bridge-api.sh`: starts `zfc-bridge-api` behind HTTPS with a local CA and prints the CA certificate path for Android/browser import.
- `diagnose-android-avd.sh`: boots an AVD, polls adb boot state, and captures emulator logs for troubleshooting.
- `install-launch-android-app.sh`: installs the Android debug APK into the emulator and launches the app.
- `verify-zenoh-tls-mtls.sh`: generates temporary CA/server/client certificates and verifies zenohd accepts mTLS and rejects unauthenticated TLS clients. Override `ZENOH_PORT` if the default test port is busy.

For a real phone, include the host LAN IP in the generated bridge certificate:

```bash
ZFC_BRIDGE_IP=192.168.1.20 ./scripts/start-android-sim-backend.sh
```
