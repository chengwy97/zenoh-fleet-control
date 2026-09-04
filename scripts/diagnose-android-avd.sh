#!/usr/bin/env bash
set -euo pipefail

AVD_NAME=${1:-${ANDROID_AVD_NAME:-zfc-api35}}
ANDROID_HOME=${ANDROID_HOME:-/home/eame/Android/Sdk}
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
WORK_DIR=${ZFC_ANDROID_DIAG_DIR:-/tmp/zfc-android-diag}
mkdir -p "$WORK_DIR"
EMULATOR_LOG="$WORK_DIR/emulator.log"
ADB_LOG="$WORK_DIR/adb.log"
EMULATOR_PID=

cleanup() {
  if [[ -n "${EMULATOR_PID}" ]]; then
    kill "${EMULATOR_PID}" 2>/dev/null || true
    wait "${EMULATOR_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ ! -x "$ANDROID_HOME/emulator/emulator" ]]; then
  echo "missing emulator binary under $ANDROID_HOME" >&2
  exit 1
fi
if [[ ! -x "$ANDROID_HOME/platform-tools/adb" ]]; then
  echo "missing adb binary under $ANDROID_HOME" >&2
  exit 1
fi
if ! emulator -list-avds | rg -qx "$AVD_NAME"; then
  echo "missing AVD: $AVD_NAME" >&2
  exit 1
fi

pkill -f "emulator.*-avd $AVD_NAME" 2>/dev/null || true
sleep 2

emulator   -avd "$AVD_NAME"   -no-window   -no-audio   -no-boot-anim   -no-snapshot   -no-snapshot-load   -gpu swiftshader_indirect   -accel on   -verbose   >"$EMULATOR_LOG" 2>&1 &
EMULATOR_PID=$!

echo "started emulator pid=$EMULATOR_PID avd=$AVD_NAME"

adb start-server >/dev/null 2>&1 || true
adb wait-for-device || true

boot_completed=""
bootanim=""
state=""
for _ in $(seq 1 120); do
  state=$(adb devices | awk 'NR==2 {print $2}')
  if [[ "$state" == "device" ]]; then
    boot_completed=$(adb -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '')
    bootanim=$(adb -s emulator-5554 shell getprop init.svc.bootanim 2>/dev/null | tr -d '')
    if [[ "$boot_completed" == "1" && "$bootanim" == "stopped" ]]; then
      break
    fi
  fi
  sleep 5
done

{
  echo "=== adb devices ==="
  adb devices -l
  echo
  echo "=== boot props ==="
  echo "sys.boot_completed=${boot_completed:-<empty>}"
  echo "init.svc.bootanim=${bootanim:-<empty>}"
  echo "adb_state=${state:-<empty>}"
  echo
  echo "=== emulator log tail ==="
  tail -n 200 "$EMULATOR_LOG"
} | tee "$ADB_LOG"

if [[ "$boot_completed" != "1" || "$bootanim" != "stopped" ]]; then
  echo "android avd did not finish booting" >&2
  exit 1
fi

echo "android avd boot ok"
