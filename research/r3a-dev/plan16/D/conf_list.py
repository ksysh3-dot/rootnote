"""Step 1 (16.8.1 m1): confirmation-track list from MIDI metadata ONLY (no audio is read, no stem flac opened).
Exclusion union = Track numbers found (file names and text contents) under ~/r3a-dev (everything but plan16/D) plus the r3/r4 research scripts of the harness, plus V6 10 + T60.
Condition: union length of Bass-stem MIDI notes clipped to [0,30] s >= 10 s.  Ascending track number over slakh2100/train only.  Errors are recorded, never substituted."""
import re, os, sys, json, hashlib
from pathlib import Path
sys.path.insert(0, '/home/ksysh/r3a-dev/la0')
import numpy as np
from data import X, guard, TRAIN, EVAL

HOME = Path.home()
OUT = HOME / 'r3a-dev/plan16/D'
rx = re.compile(r'Track(\d{5})')
excl = {}
TEXT = {'.py', '.json', '.log', '.md', '.txt', '.sh', '.csv', '.out', '.err', '.yaml', '.yml', '.cpp', '.h', '.inc'}


def scan(root, only_prefix=None):
    for dp, dn, fn in os.walk(root):
        if str(Path(dp)).startswith(str(OUT)):
            dn[:] = []; continue
        for f in fn:
            p = Path(dp) / f
            if only_prefix and not f.startswith(only_prefix):
                continue
            for m in rx.finditer(f):
                excl.setdefault(m.group(1), set()).add(str(p))
            if p.suffix.lower() in TEXT:
                try:
                    if p.stat().st_size > 200e6:
                        continue
                    s = p.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    continue
                for m in set(rx.findall(s)):
                    excl.setdefault(m, set()).add(str(p))


scan(HOME / 'r3a-dev')
h = HOME / 'r3-work/tools/pvb-harness'
for p in sorted(h.glob('research_r[34]*.py')) + sorted(h.glob('research_resultant*.py')):
    s = p.read_text(encoding='utf-8', errors='ignore')
    for m in set(rx.findall(s)):
        excl.setdefault(m, set()).add(str(p))
for t in TRAIN + EVAL + ['Track00060']:
    excl.setdefault(t[5:], set()).add('V6/T60 list')
excl_nums = sorted(excl)
(OUT / 'conf_exclusion.json').write_text(json.dumps({k: sorted(v)[:5] for k, v in excl.items()}, indent=1))
ex_sha = hashlib.sha256(('\n'.join(excl_nums)).encode()).hexdigest()

train_dir = X.SLAKH
mid_dir = X.SLAKH_MIDI
guard(train_dir); guard(mid_dir)
names = sorted(p.name for p in train_dir.iterdir() if re.fullmatch(r'Track\d{5}', p.name))
rows, errors, chosen = [], [], []
for nm in names:
    if nm[5:] in excl:
        continue
    try:
        meta = (train_dir / nm / 'metadata.yaml').read_text(encoding='utf-8', errors='replace')   # same location as X.bass_stems_and_notes
        parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
        ids = [parts[i] for i in range(1, len(parts) - 1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i + 1])]
        iv = []
        for sid in ids:
            mp = train_dir / nm / 'MIDI' / f'{sid}.mid'
            for (s, e, pch) in X.read_midi(mp):
                s, e = max(0.0, s), min(30.0, e)
                if e > s:
                    iv.append((s, e))
        iv.sort(); tot = 0.0; cur = None
        for s, e in iv:
            if cur is None or s > cur[1]:
                if cur is not None:
                    tot += cur[1] - cur[0]
                cur = [s, e]
            else:
                cur[1] = max(cur[1], e)
        if cur is not None:
            tot += cur[1] - cur[0]
        rows.append((nm, len(ids), round(tot, 2)))
        if tot >= 10.0 and len(chosen) < 5:
            chosen.append(nm)
    except Exception as ex:
        errors.append((nm, repr(ex)))
    if len(chosen) >= 5 and False:
        break
res = dict(chosen=chosen, exclusion_count=len(excl_nums), exclusion_sha256=ex_sha, exclusion_nums=excl_nums, errors=errors,
           first_rows=rows[:25], n_examined=len(rows), note='walk ascending; every non-excluded track examined (not stopped at 5) so that skipped/error tracks are visible')
(OUT / 'conf_list.json').write_text(json.dumps(res, indent=1))
print('chosen', chosen); print('excluded', len(excl_nums), ex_sha); print('errors', errors[:10])
print('first rows', rows[:15])
