import os
os.chdir(os.path.expanduser('~/r3-app'))
def rw(p, a, b):
    s = open(p, encoding='utf-8', newline='').read()
    assert a in s, p
    open(p, 'w', encoding='utf-8', newline='').write(s.replace(a, b))
rw('app/src/main/cpp/libpvb/pvb_vb.h',
   'sustained-layer path; vbAlpha2_ with resultantOn_ (experimental app model 15, defaults of pvb_resultant.h; research params only via the host API)',
   'sustained-layer path; vbAlpha2_ with resultantOn_ (experimental app model 15, defaults of pvb_resultant.h;\n                   // research params only via the host API)')
rw('tools/pvb-harness/jvm/Alpha3SettingsTest.kt',
   'P1 + C1 (14, research branch), Resultant core v1.5 (15, experimental), P1+ / P1++ / P1++ v0.3 (11-13), and the\n    // re-exposed gentle12 (ID 3); P1 is the default.',
   'P1 + C1 (14, research branch), Resultant core v1.5 (15, experimental),\n    // P1+ / P1++ / P1++ v0.3 (11-13), and the re-exposed gentle12 (ID 3); P1 is the default.')
