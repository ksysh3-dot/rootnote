from pathlib import Path
t = Path("/home/ksysh/r3a-dev/plan16/F/f_right.py").read_text()


def sub(a, b):
    global t
    assert t.count(a) == 1, a
    t = t.replace(a, b)


sub("sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F')", "sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/F'); sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/V16A')")
sub("label, lib_path = sys.argv[1], sys.argv[2]\nrho = float(sys.argv[3]) if len(sys.argv) > 3 else None\n",
    "label, lib_path = sys.argv[1], sys.argv[2]\nrho, creep = float(sys.argv[3]), float(sys.argv[4])\n")
sub("CDIR = Path('/home/ksysh/r3a-dev/plan16/F/cache')", "CDIR = Path('/home/ksysh/r3a-dev/plan16/V16A/cache')")
sub("""if rho is not None:
    M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0)]
    CA.PARAMS = CA.PARAMS + ('capRho',)
    CA.DEFAULTS = dict(CA.DEFAULTS, capRho=0)
""", "M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0)]\n")
sub("""    res = dict(voicing=0, ampSource=0)
    if rho is not None:
        res['capRho'] = rho
""", "    res = dict(voicing=0, ampSource=0, capRho=rho, windowCreep=creep)\n")
sub("rho=rho, summary", "rho=rho, creep=creep, summary")
sub("Path('/home/ksysh/r3a-dev/plan16/F') / f'f_right_{label}.json'", "Path('/home/ksysh/r3a-dev/plan16/V16A') / f'right_{label}.json'")
sub("usage: f_right.py LABEL LIB [rho]    (rho given -> 17-parameter call, new lib)",
    "usage: right16.py LABEL LIB RHO CREEP   (v1.6-a lib, 18 parameters). Copy of plan16/F/f_right.py with the extra parameter.")
Path("/home/ksysh/r3a-dev/plan16/V16A/right16.py").write_text(t)
Path("/home/ksysh/r3a-dev/plan16/V16A/run_right.sh").write_text("""#!/bin/bash
# usage: run_right.sh LABEL:rho:creep ...   (sequential rows, each uses a pool of 10)
V=~/r3a-dev/plan16/V16A
LIB=~/r3-work/tools/pvb-harness/build_core16a/libpvbcapi.so
cd $V
for spec in "$@"; do
  IFS=: read lab rho cr <<< "$spec"
  ./runpy.sh $V/right16.py $lab $LIB $rho $cr > $V/right_$lab.log 2>&1
done
echo RIGHTDONE >> $V/right_done.txt
""")
