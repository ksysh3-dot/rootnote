#!/usr/bin/env python3
"""Summary of a research-switch screen run with research_gt_bass (one report per candidate and dataset, models
p1, candidate, candidate + R3): paired against P1, per dataset, the per-item median tracking change (primary), the
octave-error change, and the pooled tracking change by f0 band. Usage: research_screen_summary.py <screen dir>"""
import json, sys
from pathlib import Path

rows = {}
for f in sorted(Path(sys.argv[1]).glob('*.json')):
    ds, cand = f.stem.split('_', 1); r = json.loads(f.read_text())
    for m, pr in r['paired'].items():
        b = pr['band_pooled']; pct = lambda v: f'{100 * v:+5.1f}' if v is not None else '  n/a'
        rows.setdefault(m, {})[ds] = (pct(pr['primary']), pct(pr['octave_change']),
                                      pct(b['55-82']['change']), pct(b['>=82']['change']), pr['items_used'])
print(f"{'model':28s} | {'MUSDB primary oct 55-82 >=82':32s} | {'BabySlakh primary oct 55-82 >=82':32s}")
for m in sorted(rows, key=lambda k: (('2097152' in k), k)):
    cells = [' '.join(rows[m][ds][:4]) if ds in rows[m] else ' ' * 23 for ds in ('musdb', 'slakh')]
    print(f'{m:28s} | {cells[0]:32s} | {cells[1]:32s}')
