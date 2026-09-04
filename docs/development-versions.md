# Development Versions

This document records the toolchain and runtime versions used while building and verifying `zenoh-fleet-control`. The goal is reproducibility for other contributors.

## Confirmed stack

- Java: OpenJDK 21.0.11
- Python: 3.13.13
- Python binding: `eclipse-zenoh` 1.10.0
- Gradle wrapper: 8.13
- Android Gradle Plugin: 8.13.0
- Kotlin Android plugin: 2.0.20
- Jetpack Compose BOM: 2025.12.00
- Android compile SDK: 36
- Android target SDK: 36
- Android min SDK: 26
- Zenoh source checkout used for local verification: `1.10.0-5-gc5d4760e` from `/home/eame/Documents/magiclab/zenoh/zenoh`
- Docker Engine: 29.6.1
- Docker Compose: v5.2.0
- Node.js: 20.20.2
- npm: 10.8.2
- App version: 0.1.0
- Agent package version: 0.1.0
- File API package version: 0.1.0
- Bridge API package version: 0.1.0

## Source of truth

- [app-android/gradle/wrapper/gradle-wrapper.properties](../app-android/gradle/wrapper/gradle-wrapper.properties)
- [app-android/build.gradle.kts](../app-android/build.gradle.kts)
- [app-android/app/build.gradle.kts](../app-android/app/build.gradle.kts)
- [agent-python/pyproject.toml](../agent-python/pyproject.toml)
- [file-api/pyproject.toml](../file-api/pyproject.toml)

## Environment snapshot

The current host snapshot should be treated as a development reference, not a production requirement.

```text
Java: OpenJDK 21.0.11
Python: 3.13.13
Gradle: provided by wrapper inside app-android
ANDROID_HOME: not required for repository docs, but needed for local Android builds
adb/emulator: installed separately with Android SDK tools
Zenoh: local checkout at /home/eame/Documents/magiclab/zenoh/zenoh, commit c5d4760e
MinIO image used in local validation: minio/minio:latest
Node.js: 20.20.2
npm: 10.8.2
```

## Reproducibility notes

- Keep these versions aligned when updating the Android scaffold.
- Record any future SDK, plugin, or runtime bump here before changing the implementation notes.
- If local verification starts depending on a newer toolchain, add the new minimum version here and in the Android environment docs.
