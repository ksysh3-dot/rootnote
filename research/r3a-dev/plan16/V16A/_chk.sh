cd ~/r3a-dev/plan16/V16A
grep -E 'ALL BIT|^creepMode|^windowCreep' v0_check16b.log
echo A-rows: $(grep -c "^('A'" v0_check16b.log) false: $(grep "^('A'" v0_check16b.log | grep -c False)
echo B-rows: $(grep -c "^('B'" v0_check16b.log) false: $(grep "^('B'" v0_check16b.log | grep -c False)
for f in suite/i8a2.log right_i8a2.log; do echo == $f; tail -n 3 $f; done
