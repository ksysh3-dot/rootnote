#!/bin/bash
cd ~/r3a-dev/plan16/A5P
sed -i '1s/^\xEF\xBB\xBF//' *.py
for f in a5_primary a5_ptable a5_song14; do
  sed -e 's#plan16/A5#plan16/A5P#g' -e 's/a5common/a5pcommon/g' -e 's/a5rows/a5prows/g' -e 's/a5primary_mod/p_primary/g' ../A5/$f.py > $f.py
done
mv a5_primary.py p_primary.py
sed -i 's/p_primary/p_primary/' a5_song14.py
sed -i "s#import p_primary as P#import p_primary as P#" a5_song14.py
grep -n "A5P\|a5p\|p_primary" p_primary.py a5_ptable.py a5_song14.py
