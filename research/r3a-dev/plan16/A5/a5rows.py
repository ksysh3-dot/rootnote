"""A5 rows: label -> (library, algorithm, Resultant parameter dict). P1 = build_core algo 6 (as b12), the others = build_core16c algo 15."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import a5common as AC
CA = AC.CA
HARN = AC.HOME / 'r3-work/tools/pvb-harness'
BASE = dict(voicing=0, ampSource=0, capRho=1.5, windowCreep=16, creepMode=2)
ROWS = {'p1': ('build_core', 6, None), 'v15': ('build_core16c', 15, dict(voicing=0, ampSource=0)), 'base': ('build_core16c', 15, dict(BASE))}
for sl in (2, 4, 8):
    for on in (0, 1, 2):
        ROWS[f's{sl}m{on}'] = ('build_core16c', 15, dict(BASE, ampSlewDb=sl, slewOnsetMode=on))
NAMES = {'p1': 'P1', 'v15': 'v1.5', 'base': 'v1.6-a base'}
for sl in (2, 4, 8):
    for on in (0, 1, 2):
        NAMES[f's{sl}m{on}'] = f'A5 slew {sl} mode {on}'
A5LABELS = [k for k in ROWS if k.startswith('s')]


# oracle rows (18.9: if no row qualifies, slew alone without the guards, to see the ceiling of this mechanism): smaller limits, mode 0
for lab, sl in (('o1', 1.0), ('o05', 0.5), ('o025', 0.25), ('o01', 0.1)):
    ROWS[lab] = ('build_core16c', 15, dict(BASE, ampSlewDb=sl, slewOnsetMode=0))
    NAMES[lab] = f'oracle slew {sl:g} mode 0'

# oracle K (diagnostic library A5/dbgsrc/K, not part of the diff): the slew limit on every harmonic amplitude a_k instead of A c sigma (slewOnsetMode 3)
for lab, sl in (('k4', 4.0), ('k2', 2.0), ('k1', 1.0), ('k05', 0.5)):
    ROWS[lab] = (str(AC.A5_DIR / 'dbgsrc/K'), 15, dict(BASE, ampSlewDb=sl, slewOnsetMode=3))
    NAMES[lab] = f'oracle K a_k slew {sl:g}'

# diagnostic only (not an A5 row): slower phase pull (betaMin / betaMax, existing parameters) to test whether the 20-150 Hz skirt is phase noise
for lab, (b0, b1) in (('b1', (.05, .1)), ('b2', (.1, .2)), ('b4', (.1, .45))):
    ROWS[lab] = ('build_core16c', 15, dict(BASE, betaMin=b0, betaMax=b1))
    NAMES[lab] = f'diag beta {b0}-{b1}'


def engine(label):
    d, algo, prm = ROWS[label]
    return CA.load(HARN / d / 'libpvbcapi.so'), algo, prm
