cd ~/r3-work
git diff > ~/r3a-dev/plan16/V16A/a1p.diff
sha256sum ~/r3a-dev/plan16/V16A/a1p.diff tools/pvb-harness/build_core16b/libpvbcapi.so | tee ~/r3a-dev/plan16/V16A/a1p_sha256.txt
git diff --stat
git log --oneline | head -1
git status --short | grep -v '^??'
echo ---
git diff app/ | grep '^[+-]' | grep -v '^+++\|^---'
