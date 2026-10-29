#!/usr/bin/env python3
"""Resultant R3-b (#4): offline frame balance of one added condition on R3-a's halving, from research_r3a_diagnose
--dump files of the development sets (no engine change, decides nothing). A halving is allowed only when
cue > threshold (frames without the cue keep R3-a's decision). Per set and threshold: share of R3-a's correct
restorations (good) that would be lost, share of its wrong halvings (bad) removed, and the frame balance
(bad removed - good lost, scaled from the sampled frames to the set's frame totals)."""
import argparse
import json
from pathlib import Path
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dumps', type=Path, nargs='+'); p.add_argument('--cue', default='reg')
    p.add_argument('--grid', default='-0.6,-0.5,-0.4,-0.3,-0.2,-0.1,0')
    a = p.parse_args(); sets = {d.stem: json.loads(d.read_text(encoding='utf-8')) for d in a.dumps}
    print(f'cue {a.cue}: halving allowed when cue > threshold')
    print('threshold ' + '  '.join(f'{n:>34s}' for n in sets))
    for th in (float(x) for x in a.grid.split(',')):
        cols = []
        for d in sets.values():
            g = np.array([x[a.cue] for x in d['frames']['good']], float); b = np.array([x[a.cue] for x in d['frames']['bad']], float)
            lost = np.mean(np.isfinite(g) & (g <= th)); rem = np.mean(np.isfinite(b) & (b <= th))
            bal = rem * d['totals']['bad'] - lost * d['totals']['good']
            cols.append(f'good lost {100 * lost:4.1f} % bad removed {100 * rem:4.1f} % net {bal:+6.0f}')
        print(f'{th:9.2f} ' + '  '.join(cols))
    for n, d in sets.items(): print(n, 'totals', {k: d['totals'][k] for k in ('good', 'bad', 'hi_voiced')})


if __name__ == '__main__':
    main()
