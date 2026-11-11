#!/bin/sh
# Package the existing Linux one-file executable; does not run flet pack.
set -eu

ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
PREPARE_ONLY=false
case "${1:-}" in
    --prepare-only) PREPARE_ONLY=true ;;
    '') ;;
    *) echo "Usage: bash tools/build_appimage.sh [--prepare-only]" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    echo "Usage: bash tools/build_appimage.sh [--prepare-only]" >&2
    exit 2
fi
if [ "$(uname -s)" != Linux ]; then
    echo "Run this script on Linux with a Linux executable." >&2
    exit 1
fi

BINARY="$ROOT/dist/MiBudsClient"
APPDIR="$ROOT/build/MiBudsClient.AppDir"
APP_ID=dev.mibuds.client
if [ ! -f "$BINARY" ] || [ ! -x "$BINARY" ]; then
    echo "Missing executable: $BINARY. Run the Linux flet pack command first." >&2
    exit 1
fi

APPIMAGE_TOOL="${APPIMAGETOOL:-appimagetool}"
if [ "$PREPARE_ONLY" = false ] && ! command -v "$APPIMAGE_TOOL" >/dev/null 2>&1; then
    echo "appimagetool not found. Set APPIMAGETOOL to its executable path, or use --prepare-only." >&2
    exit 1
fi

mkdir -p "$ROOT/build"
STAGING="$(mktemp -d "$ROOT/build/MiBudsClient.AppDir.XXXXXX")"
trap 'rm -rf -- "$STAGING"' EXIT
trap 'exit 1' HUP INT TERM
mkdir -p "$STAGING/usr/bin" "$STAGING/usr/share/icons/hicolor/256x256/apps"
install -m 755 "$BINARY" "$STAGING/usr/bin/mibudsclient"
install -m 755 "$ROOT/assets/linux/AppRun" "$STAGING/AppRun"
install -m 644 "$ROOT/assets/linux/$APP_ID.desktop" "$STAGING/$APP_ID.desktop"
install -m 644 "$ROOT/assets/icon.png" "$STAGING/$APP_ID.png"
install -m 644 "$ROOT/assets/icon.png" "$STAGING/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
ln -s "$APP_ID.png" "$STAGING/.DirIcon"
# This directory contains generated files only.
rm -rf -- "$APPDIR"
mv -- "$STAGING" "$APPDIR"
echo "AppDir prepared: $APPDIR"

if [ "$PREPARE_ONLY" = true ]; then
    exit 0
fi
ARCH="${ARCH:-$(uname -m)}"
export ARCH
OUTPUT="$ROOT/dist/MiBudsClient-$ARCH.AppImage"
"$APPIMAGE_TOOL" "$APPDIR" "$OUTPUT"
echo "AppImage created: $OUTPUT"
