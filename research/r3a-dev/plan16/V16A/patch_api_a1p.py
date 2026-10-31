from pathlib import Path
p = Path.home() / 'r3-work/tools/pvb-harness/research_core_api.py'
t = p.read_text()
for old, new in (("'maxDfdtBirth', 'capRho', 'windowCreep')", "'maxDfdtBirth', 'capRho', 'windowCreep', 'creepMode')"),
                 ("capRho=0, windowCreep=0)", "capRho=0, windowCreep=0, creepMode=0)"),
                 ("(capRho, windowCreep: v1.6-a, creepMode: A1prime, 0 = off = v1.5)", "(capRho, windowCreep: v1.6-a; creepMode: A1', 0 = off = v1.5)")):
    assert t.count(old) == 1, old
    t = t.replace(old, new)
p.write_text(t)
