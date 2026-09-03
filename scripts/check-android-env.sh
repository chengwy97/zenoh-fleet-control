#!/usr/bin/env bash
set -euo pipefail

failures=0

check_cmd() {
  local name=$1
  local cmd=$2
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "ok: $name -> $(command -v "$cmd")"
  else
    echo "missing: $name ($cmd)"
    failures=$((failures + 1))
  fi
}

echo "Android development environment check"
echo "user=$(id -un) uid=$(id -u)"

if java -version >/tmp/zfc-java-version.log 2>&1; then
  echo "ok: java"
  sed -n '1p' /tmp/zfc-java-version.log
else
  echo "missing: java"
  failures=$((failures + 1))
fi

if [[ -n "${ANDROID_HOME:-}" ]]; then
  echo "ok: ANDROID_HOME=$ANDROID_HOME"
  if [[ ! -d "$ANDROID_HOME" ]]; then
    echo "missing: ANDROID_HOME directory does not exist"
    failures=$((failures + 1))
  fi
else
  echo "missing: ANDROID_HOME"
  failures=$((failures + 1))
fi

check_cmd "adb" adb
check_cmd "emulator" emulator
check_cmd "sdkmanager" sdkmanager

if command -v gradle >/dev/null 2>&1; then
  echo "ok: gradle -> $(command -v gradle)"
else
  echo "info: system gradle missing; acceptable after app-android has a Gradle wrapper"
fi

if [[ "$failures" -eq 0 ]]; then
  echo "android env ok"
else
  echo "android env incomplete: $failures required item(s) missing"
  exit 1
fi
