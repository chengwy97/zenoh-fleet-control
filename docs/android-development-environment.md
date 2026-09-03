# Android Development Environment

The next milestone is to make `app-android` runnable before building the full mobile console.

## Target stack

- Language: Kotlin
- UI: Jetpack Compose + Material 3
- Build: Gradle wrapper committed in `app-android`
- Minimum Android version: decide during scaffold, likely API 26+
- Local backend during simulation:
  - `zenohd` on the Linux host
  - `zfc-file-api` on the Linux host
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
http://10.0.2.2:8080    -> host zfc-file-api
http://10.0.2.2:9000    -> host MinIO API, only for presigned URLs in local simulation
tcp/10.0.2.2:7447      -> host zenohd, if Android Zenoh client can dial TCP directly
```

If native Android Zenoh integration blocks the MVP, add a temporary host bridge:

```text
Android App <-> WebSocket/HTTP bridge <-> Zenoh
```

The bridge should be treated as an MVP adapter, not the final protocol.

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
- `app-android` can build from the command line.
- `app-android` can install and launch on the emulator.
