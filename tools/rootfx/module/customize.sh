# Rootnote JamesDSP module: puts librootnotefx.so (JamesDSP + Rootnote PVB) into soundfx and points the JamesDSP
# effect entry of the audio effects configuration at it. Sourced by Magisk's installer (ui_print, abort, $MODPATH,
# $ARCH, $IS64BIT, $API available).
SKIPUNZIP=0
UUID=f27317f4-c984-4de6-9a90-545759495bf2
LIB=librootnotefx.so

ui_print "- Rootnote JamesDSP (virtual bass)"
[ "$API" -lt 26 ] && abort "! Android 8.0 or later is needed"
case "$ARCH" in arm|arm64) ;; *) abort "! Only ARM phones are supported ($ARCH)";; esac

# The stock JamesDSP module installs the same effect: two copies would fight over it.
for m in /data/adb/modules/*; do
  [ -d "$m" ] || continue
  [ "$(basename "$m")" = "rootnote_jamesdsp" ] && continue
  if grep -qs "f27317f4-c984-4de6-9a90-545759495bf2" "$m"/system/etc/audio_effects* "$m"/system/vendor/etc/audio_effects* 2>/dev/null \
     || [ -f "$m/system/lib/soundfx/libjamesdsp.so" ] || [ -f "$m/system/vendor/lib/soundfx/libjamesdsp.so" ]; then
    abort "! Another JamesDSP module is installed ($(basename "$m")). Remove it in Magisk, reboot, then install this one."
  fi
done

# Libraries: 32-bit always (many Android 9 audio servers are 32-bit), 64-bit on 64-bit phones.
mkdir -p "$MODPATH/system/vendor/lib/soundfx"
cp -f "$MODPATH/libs/armeabi-v7a/$LIB" "$MODPATH/system/vendor/lib/soundfx/$LIB"
if [ "$IS64BIT" = "true" ]; then
  mkdir -p "$MODPATH/system/vendor/lib64/soundfx"
  cp -f "$MODPATH/libs/arm64-v8a/$LIB" "$MODPATH/system/vendor/lib64/soundfx/$LIB"
fi
rm -rf "$MODPATH/libs"

# Audio effects configuration: every copy in /system and /vendor (the phone uses one of them). XML (Android 8+) or
# the older .conf; the library entry "jdsp" and the effect entry "jamesdsp" are added, or replaced if present.
patched=0
for f in $(find /system/etc /vendor/etc -maxdepth 1 -type f \( -name 'audio_effects*.xml' -o -name 'audio_effects*.conf' \) 2>/dev/null); do
  case "$f" in
    /vendor/*) dest="$MODPATH/system$f" ;;
    *) dest="$MODPATH$f" ;;
  esac
  mkdir -p "$(dirname "$dest")"
  cp -f "$f" "$dest"
  case "$f" in
    *.xml)
      sed -i '/<library name="jdsp"/d; /<effect name="jamesdsp"/d' "$dest"
      sed -i "s|<libraries>|<libraries>\n        <library name=\"jdsp\" path=\"$LIB\"/>|" "$dest"
      sed -i "s|<effects>|<effects>\n        <effect name=\"jamesdsp\" library=\"jdsp\" uuid=\"$UUID\"/>|" "$dest"
      ;;
    *.conf)
      sed -i '/^ *jdsp {/,/^ *}/d; /^ *jamesdsp {/,/^ *}/d' "$dest"
      sed -i "s|^libraries {|libraries {\n  jdsp {\n    path /vendor/lib/soundfx/$LIB\n  }|" "$dest"
      sed -i "s|^effects {|effects {\n  jamesdsp {\n    library jdsp\n    uuid $UUID\n  }|" "$dest"
      ;;
  esac
  ui_print "- Patched $f"
  patched=$((patched + 1))
done
[ "$patched" -eq 0 ] && abort "! No audio effects configuration found in /system/etc or /vendor/etc"
[ -n "$(ls /odm/etc/audio_effects* 2>/dev/null)" ] && ui_print "! Note: /odm has its own audio effects file; if the effect doesn't load, report it"

set_perm_recursive "$MODPATH/system" 0 0 0755 0644
ui_print "- Done. Reboot, then open the Rootnote root app."
