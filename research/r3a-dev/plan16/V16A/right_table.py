import json, sys
from pathlib import Path
V = Path('/home/ksysh/r3a-dev/plan16/V16A')
labs = sys.argv[1:] or ['v15', 'c8', 'c16', 'c32', 'a2', 'c16a2']
base = json.load(open(V / 'right_v15.json'))['summary']
print('label | right vs R3 dB (all10 sa) | delta vs v1.5 dB | right vs R3 dB (noT40) | delta | wrong_sa_F all10 | noT40 | v6b right dB')
for l in labs:
    s = json.load(open(V / f'right_{l}.json'))['summary']
    a, b = s['all10'], s['noT40']
    print(f"{l} | {a['right_vs_R3_dB_sa']:+.3f} | {a['right_vs_R3_dB_sa'] - base['all10']['right_vs_R3_dB_sa']:+.3f} | {b['right_vs_R3_dB_sa']:+.3f} | {b['right_vs_R3_dB_sa'] - base['noT40']['right_vs_R3_dB_sa']:+.3f} | {a['wrong_sa_F']:.4f} | {b['wrong_sa_F']:.4f} | {a['right_vs_R3_dB_v6b']:+.3f}")
