#!/usr/bin/env bash
# Lists the upstream RootlessJamesDSP files this fork changed (GPL-3.0 section 5(a) notice), by comparing the
# working tree's HEAD with the upstream RootlessJamesDSP commit it is based on.
#
#   tools/list_modified_upstream.sh            print the Markdown list
#   tools/list_modified_upstream.sh --write    replace the generated section of NOTICE.md
#
# UPSTREAM_BASE: the RootlessJamesDSP 1.6.14 commit this fork is based on (upstream 60d25ae). This repository does
# not contain upstream history; fetch that commit once before running the script:
#
#   git fetch https://github.com/ThePBone/RootlessJamesDSP 60d25ae8a53c6f4691c090673df290a73c6b6357
#
# Upstream's IDE file .idea/gradle.xml was never imported and is not counted as a removal.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
UPSTREAM_BASE="${UPSTREAM_BASE:-60d25ae8a53c6f4691c090673df290a73c6b6357}"
git rev-parse --verify --quiet "$UPSTREAM_BASE^{commit}" >/dev/null || {
    echo "upstream base $UPSTREAM_BASE not found; fetch it first:" >&2
    echo "  git fetch https://github.com/ThePBone/RootlessJamesDSP 60d25ae8a53c6f4691c090673df290a73c6b6357" >&2
    exit 1; }
SPEC=(-- . ':(exclude).idea')

list() {
    echo "Compared: RootlessJamesDSP 1.6.14 (upstream commit \`$(git rev-parse --short=7 "$UPSTREAM_BASE")\`) .. this commit."
    echo
    echo "Modified upstream files:"
    echo
    git diff --no-renames --name-status --diff-filter=M "$UPSTREAM_BASE" HEAD "${SPEC[@]}" | cut -f2 | sed 's/^/- `/; s/$/`/'
    echo
    local deleted
    deleted="$(git diff --no-renames --name-status --diff-filter=D "$UPSTREAM_BASE" HEAD "${SPEC[@]}" | cut -f2)"
    if [ -n "$deleted" ]; then
        echo "Removed upstream files:"
        echo
        echo "$deleted" | sed 's/^/- `/; s/$/`/'
        echo
    fi
    local added
    added="$(git diff --no-renames --name-only --diff-filter=A "$UPSTREAM_BASE" HEAD "${SPEC[@]}" | wc -l | tr -d ' ')"
    echo "Files added by this fork (not listed): $added. New source files carry their own GPL-3.0 header or are covered by this notice."
}

if [ "${1:-}" = "--write" ]; then
    out="$(list)"
    python3 - "$ROOT/NOTICE.md" "$out" <<'PY'
import sys
path, body = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
start, end = "<!-- BEGIN GENERATED: tools/list_modified_upstream.sh -->", "<!-- END GENERATED -->"
a, b = text.index(start) + len(start), text.index(end)
open(path, "w", encoding="utf-8").write(text[:a] + "\n" + body + "\n" + text[b:])
PY
    echo "NOTICE.md updated"
else
    list
fi
