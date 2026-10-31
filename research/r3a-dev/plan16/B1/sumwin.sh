#!/bin/bash
cd ~/r3a-dev/plan16/B1
for f in win_209.5 win_178.5 win_93.0 win_88.5 win_123.5 win_52.0; do
  echo "=================== $f"
  grep -E '^===|--- v15|--- v16a|voices sounding|^   [0-9]+ \||births|hops with a pair|sum\(A\)|voice [0-9]+ \(|dominant|f_osc jumps|corr\(|\(c\) test|\(d\) pitch|layer envelope stats' $f.txt | cut -c1-420
done
