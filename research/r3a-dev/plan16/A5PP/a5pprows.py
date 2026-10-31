"""A5'' rows: label -> (library dir, algorithm, Resultant parameter dict). All rows = v1.6-a base (capRho 1.5, windowCreep 16, creepMode 2), library build_core16d (22 params).
b0 = v1.6-a base (psi .12); bb = A5' best (beta .05/.1, psi .03); s{A,B}{30,60,100} = A5'' (psi .03, sustain beta A = (.05,.1) / B = (.1,.2), betaOnsetMs 30 / 60 / 100).
P1 = build_core algo 6; v15 = build_core16d without the v1.6-a params."""
import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5PP')
import a5ppcommon as AC
CA = AC.CA
HARN = AC.HOME / 'r3-work/tools/pvb-harness'
BASE = dict(voicing=0, ampSource=0, capRho=1.5, windowCreep=16, creepMode=2)
SUS = {'A': (.05, .1), 'B': (.1, .2)}
ONSETS = [30, 60, 100]
ROWS = {'p1': ('build_core', 6, None), 'v15': ('build_core16d', 15, dict(voicing=0, ampSource=0)),
        'b0': ('build_core16d', 15, dict(BASE)),
        'bb': ('build_core16d', 15, dict(BASE, betaMin=.05, betaMax=.1, psiSlew=.03))}
NAMES = {'p1': 'P1', 'v15': 'v1.5', 'b0': 'v1.6-a base', 'bb': "A5' best .05/.1 psi.03"}
for k, (s0, s1) in SUS.items():
    for ms in ONSETS:
        ROWS[f's{k}{ms}'] = ('build_core16d', 15, dict(BASE, psiSlew=.03, betaSusMin=s0, betaSusMax=s1, betaOnsetMs=ms))
        NAMES[f's{k}{ms}'] = f"A5'' sus {s0:g}/{s1:g} onset {ms}"
NEW = [f's{k}{ms}' for k in SUS for ms in ONSETS]
GRID = ['b0', 'bb'] + NEW
BASEL = 'b0'


def engine(label):
    d, algo, prm = ROWS[label]
    return CA.load(HARN / d / 'libpvbcapi.so'), algo, prm
