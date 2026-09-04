# app-android

Android mobile console for zenoh-fleet-control.

Current priority: set up a runnable Android development and simulation environment before implementing the UI.

Known scaffold versions:
- Gradle 8.13
- Android Gradle Plugin 8.13.0
- Kotlin 2.0.20
- Compose BOM 2025.12.00
- compile/target SDK 36
- min SDK 26

References:

- [TODO.md](../TODO.md)
- [Android development environment](../docs/android-development-environment.md)
- [Protocol messages](../protocol/messages.md)
- [File transfer architecture](../docs/file-transfer-architecture.md)

Planned MVP screens:

- terminal list and online status
- session state and event stream
- directory browser backed by agent queries
- chat input with file/image/video/audio attachments
- cancel and end-session controls

The Bridge URL is editable in the app. Use `https://10.0.2.2:8443` for the
Android emulator, or the HTTPS IP/domain reachable by a real phone.
