#!/usr/bin/env bash
# Packs the Rootnote Magisk module: tools/rootfx/module + the built libraries ($1/<abi>/librootnotefx.so) into
# $2 (default dist-root)/Rootnote-JamesDSP-module-<version>.zip. The version is the general build's.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LIBS="$1"
DIST="${2:-$HERE/../../dist-root}"
CFG="$HERE/../../buildSrc/src/main/kotlin/AndroidConfig.kt"
VER=$(sed -n 's/.*generalVersionName = "\(.*\)".*/\1/p' "$CFG")
CODE=$(sed -n 's/.*generalVersionCode = \([0-9]*\).*/\1/p' "$CFG")
TMP="$(mktemp -d)"
cp -r "$HERE/module/." "$TMP/"
sed -i "s/^version=.*/version=$VER/; s/^versionCode=.*/versionCode=$CODE/" "$TMP/module.prop"
mkdir -p "$TMP/libs/arm64-v8a" "$TMP/libs/armeabi-v7a"
cp "$LIBS/arm64-v8a/librootnotefx.so" "$TMP/libs/arm64-v8a/"
cp "$LIBS/armeabi-v7a/librootnotefx.so" "$TMP/libs/armeabi-v7a/"
mkdir -p "$DIST"
ZIP="$DIST/Rootnote-JamesDSP-module-$VER.zip"
rm -f "$ZIP"
(cd "$TMP" && zip -qr9 "$ZIP" .)
(cd "$DIST" && sha256sum "$(basename "$ZIP")" > "$(basename "$ZIP").sha256" && cat "$(basename "$ZIP").sha256")
rm -rf "$TMP"
echo "module: $ZIP"
