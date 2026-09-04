#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ANDROID_HOME=${ANDROID_HOME:-/home/eame/Android/Sdk}
ADB=${ADB:-$ANDROID_HOME/platform-tools/adb}
APK_PATH=${1:-$ROOT_DIR/app-android/app/build/outputs/apk/debug/app-debug.apk}
PACKAGE_NAME=${PACKAGE_NAME:-top.chengwy97.zenohfleetcontrol}

if [[ ! -x "$ADB" ]]; then
  echo "missing adb binary: $ADB" >&2
  exit 1
fi
if [[ ! -f "$APK_PATH" ]]; then
  echo "missing APK: $APK_PATH" >&2
  exit 1
fi

$ADB start-server >/dev/null 2>&1 || true
$ADB wait-for-device

state=$($ADB devices | awk 'NR==2 {print $2}')
if [[ "$state" != "device" ]]; then
  echo "device not ready: $state" >&2
  exit 1
fi

echo "installing $APK_PATH"
$ADB install -r "$APK_PATH"

echo "launching $PACKAGE_NAME"
$ADB shell monkey -p "$PACKAGE_NAME" -c android.intent.category.LAUNCHER 1

focus=$($ADB shell dumpsys window | rg "mCurrentFocus|mFocusedApp" | head -n 2 || true)
if [[ -n "$focus" ]]; then
  echo "$focus"
fi

echo "android app launch requested"
