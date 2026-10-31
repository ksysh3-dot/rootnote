import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/T')
import numpy as np
from dcommon import *
import tmeta
for k in ('Track00024', 'Track00026'):
    rf = labels.song_ref(k)
    segs, rf2 = LD.segments(k)
    print(k, 'bass notes', len(rf['ss']), 'segs', len(segs), 'nd notes', len(rf['nd_s']), 'drum hits', len(rf['drum_on']), 'drum ids', rf['drum_ids'])
    if len(rf['ss']):
        print('  bass note time range', rf['ss'].min(), rf['ss'].max(), 'pitches', np.unique(rf['ps']))
        print('  bass in 0-30:', int(((rf['es'] > 0) & (rf['ss'] < 30)).sum()))
    print('  X.bass_stems_and_notes doc:', X.bass_stems_and_notes.__doc__)
    mdir = X.SLAKH_MIDI / k / 'MIDI'
    for m in sorted(mdir.glob('*.mid')):
        nl = X.read_midi(m)
        a = np.array(nl)
        sel = a[a[:, 0] < 30] if len(a) else a
        print('  ', m.stem, len(nl), 'in0-30', len(sel), 'pitch range', (a[:, 2].min(), a[:, 2].max()) if len(a) else None, 'first start', a[:, 0].min() if len(a) else None)
