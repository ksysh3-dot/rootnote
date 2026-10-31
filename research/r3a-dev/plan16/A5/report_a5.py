import json, sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/A5')
import a5rows as AR
from pathlib import Path
V = Path('/home/ksysh/r3a-dev/plan16/A5')
S = json.load(open(V / 'suite_values_a5.json')); SV = S['SV']; P1 = S['P1']
RR = json.load(open(V / 'rerise_a5.json')); LG = json.load(open(V / 'logoff45_a5.json')); BU = json.load(open(V / 'burst_a5.json'))
FR = {l: json.load(open(V / f'right_{l}.json'))['summary']['all10'] for l in ['v15', 'base'] + AR.A5LABELS}
print(f'{"row":18s} {"tail25 ms":>9s} {"RERISE med (n>6)":>17s} {"V6b":>7s} {"F dB":>6s} {"wrongF":>7s} {"4.12 R1":>7s} {"4.73 R1":>7s} {"45Hz ON":>7s} {"gaps":>5s} {"V3e.df4":>7s} {"V9e":>6s} {"V5a":>6s} {"V3a":>5s} {"rise90b":>7s} {"rise90_25":>9s}')
print(f'{"P1":18s} {P1["V3h.25.tail"]:9.1f} {RR["p1"]["rerise_median"]:8.2f} ({RR["p1"]["rerise_n_above6"]:2d})        {"":7s} {"":6s} {"":7s} {BU["p1|4.12"]["burst_R1"]:7.2f} {BU["p1|4.73"]["burst_R1"]:7.2f}')
for l in ['v15', 'base'] + AR.A5LABELS:
    s = SV[l]
    keys = [k for k in s if k.startswith('V6b')]
    v6b = next((s[k] for k in s if k in ('V6b', 'V6b.median', 'V6b.all')), None)
    print(f'{AR.NAMES[l]:18s} {s["V3h.25.tail"]:9.1f} {RR[l]["rerise_median"]:8.2f} ({RR[l]["rerise_n_above6"]:2d})        {str(round(v6b,2)) if v6b is not None else "-":>7s} {FR[l]["right_vs_R3_dB_sa"]:6.3f} {FR[l]["wrong_sa_F"]:7.4f} {BU[l+"|4.12"]["burst_R1"]:7.2f} {BU[l+"|4.73"]["burst_R1"]:7.2f} {LG[l]["on_frac"]:7.3f} {LG[l]["n_gaps"]:5d} {s.get("V3e.df4.beat", float("nan")):7.2f} {s.get("V9e", float("nan")):6.2f} {s.get("V5a", float("nan")):6.2f} {s["V3a"]:5.1f} {s["V3h.bare.rise90"]:7.2f} {s["V3h.25.rise90"]:9.2f}')
print('V6b-like ids:', [k for k in SV['base'] if k.startswith('V6')][:20])
print('V3e ids:', [k for k in SV['base'] if k.startswith('V3e')], ' V9/V5 ids:', [k for k in SV['base'] if k.startswith('V9') or k.startswith('V5')])
