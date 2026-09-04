# Android Development Environment

The next milestone is to make `app-android` runnable before building the full mobile console.

## Target stack

- Java runtime used during verification: OpenJDK 21.0.11
- Python runtime used during verification: 3.13.13
- Language: Kotlin 2.0.20
- UI: Jetpack Compose + Material 3
- Build: Gradle 8.13 wrapper committed in `app-android`
- Android Gradle Plugin: 8.13.0
- Kotlin Android plugin: 2.0.20
- Compose BOM: 2025.12.00
- Minimum Android version: API 26+
- Compile / target SDK: Android 36
- Local backend during simulation:
  - `zenohd` on the Linux host
  - `zfc-file-api` on the Linux host
  - `zfc-bridge-api` on the Linux host for Android/browser access
  - MinIO on the Linux host through Docker Compose
  - Python agent on the Linux host

## Current machine status

Observed on this machine:

```text
Java: OpenJDK 21 is installed
Gradle: not installed in PATH
ANDROID_HOME: not configured
adb: not installed in PATH
emulator: not installed in PATH
```

For reproducibility, keep the verified stack aligned with [development-versions.md](development-versions.md).

This is enough to start documenting and checking prerequisites, but not enough to run an Android app yet.

## Required setup

Install Android Studio or Android SDK command-line tools, then install these SDK components:

```text
platform-tools
emulator
platforms;android-35 or newer
build-tools;35.0.0 or newer
system-images;android-35;google_apis;x86_64 or equivalent
```

Set environment variables, for example:

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

## Emulator networking

Android emulator cannot access Linux host `127.0.0.1` directly. Use:

```text
https://10.0.2.2:8443   -> host zfc-bridge-api
http://10.0.2.2:8080    -> host zfc-file-api
http://10.0.2.2:9000    -> host MinIO API, only for presigned URLs in local simulation
```

The app defaults to `https://10.0.2.2:8443`, but the Bridge URL can be changed
in the app for a real phone using a reachable HTTPS IP or domain. No APK
rebuild is needed.

For a real phone, start the backend with `ZFC_BRIDGE_IP=<host-lan-ip>` so the
temporary bridge certificate contains the same IP that the phone uses.

The Android app should talk to `zfc-bridge-api` over HTTPS. The bridge talks to Zenoh on the host side.

For private PKI, install the issuing CA certificate into the Android device or emulator manually. Do not assume the phone can auto-discover the public key or trust chain.

## Local backend for app simulation

Use the existing validation scripts as backend references:

```bash
./scripts/verify-file-api-minio.sh
./scripts/verify-chat-attachment-pdf.sh
```

The Android simulation launcher starts the same services and keeps them running while the emulator app is open:

```bash
./scripts/start-android-sim-backend.sh
```

## Acceptance criteria for environment setup

- `./scripts/check-android-env.sh` reports Java, Android SDK, `adb`, and `emulator` available.
- A test emulator can boot.
- The emulator can reach `http://10.0.2.2:8080/healthz` when file-api is running.
- The emulator can reach `https://10.0.2.2:8443/healthz` after importing the generated bridge CA.
- `app-android` can build from the command line.
- `app-android` can install and launch on the emulator.
- `zfc-bridge-api` can serve HTTPS and accept username/password login.
