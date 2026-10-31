import re
from pathlib import Path
A = Path.home() / 'r3a-dev/plan16/A5'; P = Path.home() / 'r3a-dev/plan16/A5P'
def rd(n): return (A / n).read_text()
def common(t):
    t = t.replace('plan16/A5', 'plan16/A5P').replace('a5common', 'a5pcommon').replace('a5rows', 'a5prows')
    t = t.replace(", ('ampSlewDb', 0), ('slewOnsetMode', 0)]", "]")
    t = t.replace('VC.LIB16C', 'VC.LIB16B')
    return t
# right layer F: 16b library, trace A c sigma is the rendered value (no slew limit)
t = common(rd('right_a5.py'))
t = t.replace("lib_path = str(AR.AC.A5_DIR / 'dbgsrc/F/libpvbcapi.so')", "lib_path = str(AR.AC.LIB16B)")
t = t.replace("A5P / f'right_{label}.json'", "A5P / f'right_{label}.json'")
(P / 'right_p.py').write_text(t)
# burst
t = common(rd('burst_a5.py'))
t = t.replace("""def vec(prm):
    return VC.make_params5(prm.get('capRho', 0), prm.get('windowCreep', 0), prm.get('creepMode', 0), prm.get('ampSlewDb', 0), prm.get('slewOnsetMode', 0))""", """def vec(prm):
    return VC.make_vec(prm)""")
t = t.replace("['v15', 'base'] + AR.A5LABELS", "['v15'] + AR.GRID").replace("burst_a5.json", "burst_p.json")
(P / 'burst_p.py').write_text(t)
# rerise
t = common(rd('rerise_a5.py'))
t = t.replace("['p1', 'v15', 'base'] + AR.A5LABELS", "['p1', 'v15'] + AR.GRID").replace("rerise_a5.json", "rerise_p.json")
t = t.replace("M.Ctx(str(VC.LIB16B), 15, par)", "M.Ctx(str(VC.LIB16B), 15, par)")
(P / 'rerise_p.py').write_text(t)
# logoff45
t = common(rd('logoff45_a5.py'))
t = t.replace("['v15', 'base'] + AR.A5LABELS", "['v15'] + AR.GRID").replace("logoff45_a5.json", "logoff45_p.json")
t = t.replace("VC.make_params5(p.get('capRho', 0), p.get('windowCreep', 0), p.get('creepMode', 0), p.get('ampSlewDb', 0), p.get('slewOnsetMode', 0))", "VC.make_vec(p)")
(P / 'logoff45_p.py').write_text(t)
for n in ('right_p', 'burst_p', 'rerise_p', 'logoff45_p'):
    print(n, [l for l in (P / f'{n}.py').read_text().splitlines() if 'A5' in l or 'a5' in l or 'slew' in l.lower()])
