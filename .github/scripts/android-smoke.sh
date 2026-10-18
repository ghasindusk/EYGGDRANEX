#!/usr/bin/env bash
# Install an APK, start the app, wait, and fail if it crashed or is no longer running.
set -u
apk="$1"
package=com.eyggdranex.mobile

adb install -r "$apk"
adb logcat -c
adb shell am start -W -n "$package/.MainActivity"
sleep 30

adb logcat -d > smoke-logcat.txt
crashes=$(adb logcat -b crash -d)
pid=$(adb shell pidof "$package" | tr -d '\r')

echo "---- crash buffer ----"
echo "$crashes"
echo "---- AndroidRuntime / FATAL ----"
grep -E "AndroidRuntime|FATAL|F flutter|E/flutter" smoke-logcat.txt | head -80 || true

if [ -n "$crashes" ] || [ -z "$pid" ]; then
  echo "App crashed or is not running (pid='$pid')."
  exit 1
fi
echo "App is running (pid $pid)."
