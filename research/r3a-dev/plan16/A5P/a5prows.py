"""A5' rows: label -> (library dir, algorithm, Resultant parameter dict). All rows = v1.6-a base (capRho 1.5, windowCreep 16, creepMode 2) with betaMin/betaMax/psiSlew varied.
label b{i}p{j}: beta set i, psiSlew j.  P1 = build_core algo 6; v15 = build_core16b without v1.6-a params."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5P')
import a5pcommon as AC
CA = AC.CA
HARN = AC.HOME / 'r3-work/tools/pvb-harness'
BASE = dict(voicing=0, ampSource=0, capRho=1.5, windowCreep=16, creepMode=2)
BETAS = [(.2, .9), (.1, .45), (.1, .2), (.05, .1)]
PSIS = [.12, .06, .03]
ROWS = {'p1': ('build_core', 6, None), 'v15': ('build_core16b', 15, dict(voicing=0, ampSource=0))}
NAMES = {'p1': 'P1', 'v15': 'v1.5'}
for i, (b0, b1) in enumerate(BETAS):
    for j, ps in enumerate(PSIS):
        ROWS[f'b{i}p{j}'] = ('build_core16b', 15, dict(BASE, betaMin=b0, betaMax=b1, psiSlew=ps))
        NAMES[f'b{i}p{j}'] = f'beta {b0:g}/{b1:g} psi {ps:g}' + (' (base)' if (i, j) == (0, 0) else '')
GRID = [k for k in ROWS if k.startswith('b')]
BASEL = 'b0p0'
# engine-run floor rows for the phase-side upper bound (existing parameters only): slower pull than the grid; f4 psi frozen after its initial value; f3/f5 open-loop phase (beta 0)
for lab, (b0, b1, ps) in (('f1', (.02, .04, .03)), ('f2', (.01, .02, .01)), ('f3', (0.0, 0.0, .03)), ('f4', (0.0, 0.0, .01))):   # psiSlew minimum accepted is .01
    ROWS[lab] = ('build_core16b', 15, dict(BASE, betaMin=b0, betaMax=b1, psiSlew=ps))
    NAMES[lab] = f'floor beta {b0:g}/{b1:g} psi {ps:g}'
FLOOR = ['f1', 'f2', 'f3', 'f4']


def engine(label):
    d, algo, prm = ROWS[label]
    return CA.load(HARN / d / 'libpvbcapi.so'), algo, prm
