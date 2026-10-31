"""Derives the A1' (b) scripts from the V16A ones (same recipes, creepMode added)."""
from pathlib import Path
V = Path.home() / 'r3a-dev/plan16/V16A'


def derive(src, dst, subs):
    t = (V / src).read_text()
    for old, new in subs:
        assert t.count(old) >= 1, (src, old)
        t = t.replace(old, new)
    (V / dst).write_text(t)


PO_OLD = "M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0)]"
PO_NEW = "M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0)]"

derive('fmetrics16.py', 'fmetrics16b.py', [(PO_OLD, PO_NEW), ('(capRho, windowCreep)', '(capRho, windowCreep, creepMode)')])

derive('right16.py', 'right16b.py', [
    (PO_OLD, PO_NEW),
    ("rho, creep = float(sys.argv[3]), float(sys.argv[4])", "rho, creep, mode = float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])"),
    ("capRho=rho, windowCreep=creep)", "capRho=rho, windowCreep=creep, creepMode=mode)"),
    ("rho=rho, creep=creep,", "rho=rho, creep=creep, mode=mode,"),
    ("usage: right16.py LABEL LIB RHO CREEP", "usage: right16b.py LABEL LIB RHO CREEP MODE"),
])

derive('rerise16.py', 'rerise16b.py', [
    (PO_OLD, PO_NEW),
    ("ROWS = [('P1', None), ('v1.5', (0, 0)), ('A1 8', (0, 8)), ('A1 16', (0, 16)), ('A1 32', (0, 32)), ('A2 1.5', (1.5, 0)), ('A1+A2 16/1.5', (1.5, 16))]",
     "ROWS = [('P1', None), ('v1.5', (0, 0, 0)), ('v1.6-a base (A2 1.5)', (1.5, 0, 0)), ('A1 8/1.5 (uncond)', (1.5, 8, 0)), ('A1p (i) 8', (1.5, 8, 1)), ('A1p (i) 16', (1.5, 16, 1)),\n"
     "        ('A1p (ii) 8', (1.5, 8, 2)), ('A1p (ii) 16', (1.5, 16, 2))]"),
    ("extra = [a for a in sys.argv[1:]]\nfor a in extra:   # extra rows as rho:creep\n    r, c = a.split(':'); ROWS.append((f'A1+A2 {c}/{r}', (float(r), float(c))))\n", ""),
    ("ctx = M.Ctx(str(VC.LIB16A), 15, dict(voicing=0, ampSource=0, capRho=par[0], windowCreep=par[1]))",
     "ctx = M.Ctx(str(VC.LIB16B), 15, dict(voicing=0, ampSource=0, capRho=par[0], windowCreep=par[1], creepMode=par[2]))"),
    ("'rerise16.json'", "'rerise16b.json'"),
])

derive('burst16.py', 'burst16b.py', [
    ("lib = VC.load(str(VC.LIB16A))", "lib = VC.load(str(VC.LIB16B))"),
    ("VC.make_params(par[0], par[1])", "VC.make_params(par[0], par[1], par[2])"),
    ("ROWS = {'v1.5': (0, 0), 'A1 8': (0, 8), 'A1 16': (0, 16), 'A1 32': (0, 32), 'A2 1.5': (1.5, 0), 'A1+A2 16/1.5': (1.5, 16)}\n"
     "for a in sys.argv[1:]:\n    r, c = a.split(':'); ROWS[f'A1+A2 {c}/{r}'] = (float(r), float(c))\n",
     "ROWS = {'v1.5': (0, 0, 0), 'v1.6-a base (A2 1.5)': (1.5, 0, 0), 'A1 8/1.5 (uncond)': (1.5, 8, 0), 'A1p (i) 8': (1.5, 8, 1), 'A1p (i) 16': (1.5, 16, 1),\n"
     "        'A1p (ii) 8': (1.5, 8, 2), 'A1p (ii) 16': (1.5, 16, 2)}\n"),
    ("'burst16.json'", "'burst16b.json'"),
])

derive('rho16.py', 'rho16b.py', [
    ("lib = VC.load(str(VC.LIB16A))", "lib = VC.load(str(VC.LIB16B))"),
    ("VC.make_params(par[0], par[1])", "VC.make_params(par[0], par[1], par[2])"),
    ("ROWS = {'v1.5': (0, 0), 'A1 8': (0, 8), 'A1 16': (0, 16), 'A1 32': (0, 32), 'A2 1.5': (1.5, 0), 'A1+A2 16/1.5': (1.5, 16)}\n"
     "for a in sys.argv[1:]:\n    r, c = a.split(':'); ROWS[f'A1+A2 {c}/{r}'] = (float(r), float(c))\n",
     "# cached layers of the first three rows come from the 084ea45 build (bit identical, v0_check16b half B); their cache names are those of rho16.py\n"
     "ROWS = {'v1.5': (0, 0, 0), 'A2 1.5': (1.5, 0, 0), 'A1+A2 8/1.5': (1.5, 8, 0), 'A1p (i) 8': (1.5, 8, 1), 'A1p (i) 16': (1.5, 16, 1),\n"
     "        'A1p (ii) 8': (1.5, 8, 2), 'A1p (ii) 16': (1.5, 16, 2)}\n"),
    ("'rho16.json'", "'rho16b.json'"),
])

derive('logoff45.py', 'logoff45b.py', [
    ("lib = VC.load(str(VC.LIB16A))", "lib = VC.load(str(VC.LIB16B))"),
    ("for name, par in (('v1.5', (0, 0)), ('A1 8', (0, 8)), ('A2 1.5', (1.5, 0)), ('A1+A2 8/1.5', (1.5, 8))):",
     "for name, par in (('v1.5', (0, 0, 0)), ('A2 1.5', (1.5, 0, 0)), ('A1+A2 8/1.5', (1.5, 8, 0)), ('A1p (i) 8', (1.5, 8, 1)), ('A1p (i) 16', (1.5, 16, 1)),\n"
     "                  ('A1p (ii) 8', (1.5, 8, 2)), ('A1p (ii) 16', (1.5, 16, 2))):"),
    ("VC.make_params(*par)", "VC.make_params(*par)"),
    ("'logoff45.json'", "'logoff45b.json'"),
])

(V / 'run_suite_b.sh').write_text('''#!/bin/bash
# A1' suite rows with the 16b library. usage: run_suite_b.sh LABEL:capRho:windowCreep:creepMode ...
V=~/r3a-dev/plan16/V16A
OUT=$V/suite
mkdir -p $OUT
REFJ=~/r3a-dev/core_results/p1_baseline/results.json
LIB=~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr mode <<< "$spec"
  ./runpy.sh $V/fmetrics16b.py --lib $LIB --algo 15 --resultant voicing=0,ampSource=0,capRho=$rho,windowCreep=$cr,creepMode=$mode --label $lab --outroot $OUT --ref-json $REFJ > $OUT/$lab.log 2>&1 &
done
wait
echo ALLDONE_B >> $OUT/done.txt
''')
(V / 'run_right_b.sh').write_text('''#!/bin/bash
# usage: run_right_b.sh LABEL:rho:creep:mode ...   (sequential rows, each uses a pool of 10)
V=~/r3a-dev/plan16/V16A
LIB=~/r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr mode <<< "$spec"
  ./runpy.sh $V/right16b.py $lab $LIB $rho $cr $mode > $V/right_$lab.log 2>&1
done
echo RIGHTDONE_B >> $V/right_done.txt
''')
print('ok')
