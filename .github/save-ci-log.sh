#!/usr/bin/env bash
# Pushes the tail of ci-build.log to the orphan branch "ci-log" (one file per job), so a failed build can be
# inspected with plain git (git fetch origin ci-log) without opening the Actions web page.
set -u
job="$1"
log="ci-build.log"
[ -f "$log" ] || echo "no log captured" > "$log"
tmp="$(mktemp -d)"
tail -c 1500000 "$log" > "$tmp/$job.log"
echo "commit: ${GITHUB_SHA:-?} run: ${GITHUB_RUN_NUMBER:-?} job: $job" > "$tmp/$job.info"
cd "$tmp"
git init -q
git config user.name "pvb-ci"
git config user.email "pvb-ci@users.noreply.github.com"
git checkout -q -b ci-log
git add "$job.log" "$job.info"
git commit -q -m "CI log: $job, run ${GITHUB_RUN_NUMBER:-?}, ${GITHUB_SHA:-?}"
git push -q -f "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" ci-log:ci-log-$job || true
