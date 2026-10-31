#!/bin/bash
cd ~/r3a-dev/plan16/B1
for f in win_88.5 win_123.5 win_52.0; do
  echo "== $f"; sed -n '2,6p' $f.txt | cut -c1-260; grep 'layer envelope stats' $f.txt | cut -c1-420
done
# cleanup of derived audio-like data later
