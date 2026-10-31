"""S19-NF rows: label -> (library dir, algorithm, Resultant parameter dict). All Resultant rows = capRho 1.5, windowCreep 16, creepMode 2.
References (nFuture 24 default): p1 (build_core algo 6), b0p0 (= v1.6-a: beta .2/.9, psiSlew .12), b3p2 (= v1.6-b: beta .05/.1, psiSlew .03).
New rows nfaNN = v1.6-a with nFuture NN; nfbNN = v1.6-b with nFuture NN."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/NF')
import a5pcommon as AC
CA = AC.CA
HARN = AC.HOME / 'r3-work/tools/pvb-harness'
BASE = dict(voicing=0, ampSource=0, capRho=1.5, windowCreep=16, creepMode=2)
VA = dict(BASE, betaMin=.2, betaMax=.9, psiSlew=.12)
VB = dict(BASE, betaMin=.05, betaMax=.1, psiSlew=.03)
ROWS = {'p1': ('build_core', 6, None), 'b0p0': ('build_core16b', 15, dict(VA)), 'b3p2': ('build_core16b', 15, dict(VB))}
NAMES = {'p1': 'P1', 'b0p0': 'v1.6-a', 'b3p2': 'v1.6-b'}
NEW = []
for tag, base in (('a', VA), ('b', VB)):
    for nf in ((48, 72, 96) if tag == 'a' else (48, 96)):
        lab = f'nf{tag}{nf}'
        ROWS[lab] = ('build_core16b', 15, dict(base, nFuture=nf))
        NAMES[lab] = f'v1.6-{tag} nF{nf}'
        NEW.append(lab)
REFN = ['b0p0', 'b3p2']          # reference rows that are re-rendered here where a per-row cache is needed (12-song, 14-song)
NFUT = {l: ROWS[l][2].get('nFuture', 24) for l in ROWS if ROWS[l][2]}
GRID = NEW


def engine(label):
    d, algo, prm = ROWS[label]
    return CA.load(HARN / d / 'libpvbcapi.so'), algo, prm
