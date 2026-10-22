#!/usr/bin/env bash
# Reproducible host-only compiler, no Android or Gradle dependency. Requires Java 17 and curl.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../build/kotlin"
mkdir -p "$OUT"
fetch() {
    local path="$1" name="$2" version="$3" hash="$4"
    curl --fail --location --retry 3 --silent --show-error "https://repo.maven.apache.org/maven2/$path/$name/$version/$name-$version.jar" -o "$OUT/$name.jar"
    echo "$hash  $OUT/$name.jar" | sha256sum --check --status
}
fetch org/jetbrains/kotlin kotlin-compiler-embeddable 1.9.24 e71ff19e6b141ab85a9328fd010941531a302543026bd4244c95adc208d501f6
fetch org/jetbrains/kotlin kotlin-stdlib 1.9.24 858b902696da9cf585ab9d98ffc1c2712269828354dfe9107e3711b084a36468
fetch org/jetbrains/kotlin kotlin-script-runtime 1.9.24 314c7d308fe750654365bac6144780613c9169cf3d9e1dafbab91cf80bdc357c
fetch org/jetbrains/kotlin kotlin-daemon-embeddable 1.9.24 177bc8b2a4076dcce7878ad0d8fd07163af3178e3fa90ee63d4f733bb47bfdc9
fetch org/jetbrains/kotlin kotlin-reflect 1.6.10 3277ac102ae17aad10a55abec75ff5696c8d109790396434b496e75087854203
fetch org/jetbrains/intellij/deps trove4j 1.0.20200330 c5fd725bffab51846bf3c77db1383c60aaaebfe1b7fe2f00d23fe1b7df0a439d
fetch org/jetbrains annotations 13.0 ace2a10dc8e2d5fd34925ecac03e4988b2c0f851650c94b8cef49ba1bd111478
cat > "$OUT/kotlinc" <<'EOF'
#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"
exec java -cp "$HERE/*" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect "$@"
EOF
chmod +x "$OUT/kotlinc"
echo "KOTLINC=$OUT/kotlinc"
echo "KOTLIN_STDLIB=$OUT/kotlin-stdlib.jar"
if [ -n "${GITHUB_ENV:-}" ]; then
    echo "KOTLINC=$OUT/kotlinc" >> "$GITHUB_ENV"
    echo "KOTLIN_STDLIB=$OUT/kotlin-stdlib.jar" >> "$GITHUB_ENV"
fi
