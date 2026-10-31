from pathlib import Path
p = Path.home() / 'r3-work/tools/pvb-harness/research_core_api.py'
t = p.read_text()


def sub(old, new):
    global t
    assert t.count(old) == 1, old
    t = t.replace(old, new)


sub("'betaMax', 'kappa', 'nMin', 'nFuture', 'psiSlew', 'crest', 'maxDfdtBirth')",
    "'betaMax', 'kappa', 'nMin', 'nFuture', 'psiSlew', 'crest', 'maxDfdtBirth', 'capRho', 'windowCreep')")
sub("psiSlew=.12, crest=0, maxDfdtBirth=200)", "psiSlew=.12, crest=0, maxDfdtBirth=200, capRho=0, windowCreep=0)")
sub("# the 16 parameters of pvb_set_resultant, in the order of spec 5.8, with their defaults",
    "# the 18 parameters of pvb_set_resultant, in the order of spec 5.8 (capRho, windowCreep: v1.6-a, 0 = off = v1.5), with their defaults")
sub("library loading, the 16 parameters", "library loading, the 18 parameters")
p.write_text(t)
