import sys, json
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/D')
import numpy as np
import dcommon as DC
from dcommon import *
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/T')
import tmeta
print('SONGS', SONGS, 'LAG', LAG, 'R3R', r3_right(SONGS))
print('TP', {k: C.TP[k] for k in ('Track00024', 'Track00026')})
FULL = '/mnt/d/rootnote-data/slakh2100/extracted/slakh2100_flac_redux/train'
for k in ('Track00024', 'Track00026'):
    print(k)
    for sid, s in tmeta.stems_meta(k).items():
        print(' ', sid, s)
v = json.load(open('/home/ksysh/r3a-dev/plan16/V/v_raw.json'))
R3R = r3_right(SONGS)
for k in ('Track00024', 'Track00026'):
    print(k, 'E_sil/R3R', v[k]['E_sil'] / R3R, 'cause', [x / R3R for x in v[k]['E_cause']], 'nobass', v[k]['nobass'], 'nvoices', v[k]['n_voices'])
import inspect
print(inspect.getsource(X.read_midi)[:800])
print(inspect.getsource(X.read_excerpt)[:800])
