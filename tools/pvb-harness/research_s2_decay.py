#!/usr/bin/env python3
"""Study 2 follow-up risk on real music: does C1 keep the layer alive after the music's low band has decayed?

The envelope imposition (gain = as/ps, cut only) is what lets the generated layer fall when the music's low band
falls. C1 removes most gain cuts after kicks; this checks the cost at real decays. Excerpts as in
research_s2_realmusic.py. Decay events: the input's 30-150 Hz envelope (20 ms RMS) falls at least 12 dB below its
maximum of the preceding 100 ms while that maximum is within 30 dB of the excerpt's peak; events at least 300 ms
apart. Per event, the generated layer energy in the 300 ms after the event, C1 against the unmodified model.
Development side check; not a quality score.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfiltfilt
import research_p1plus as P
import research_s1_interaction as S
from p1plus_paths import default_library
from research_s2_realmusic import FS, MODELS, C1, excerpts


def decay_events(x):
    low = sosfiltfilt(butter(4, [30, 150], btype='bandpass', fs=FS, output='sos'), x.mean(axis=1))
    w = int(.02 * FS); env = np.sqrt(np.convolve(low ** 2, np.ones(w) / w, mode='same') + 1e-30)
    db = 20 * np.log10(env); peak = db[4 * FS:].max(); hop = int(.005 * FS); look = int(.1 * FS)
    events, last = [], -10 ** 9
    for i in range(4 * FS + look, len(x) - int(.32 * FS), hop):
        prev = db[i - look:i].max()
        if prev > peak - 30 and db[i] <= prev - 12 and i - last >= int(.3 * FS):
            events.append(i); last = i
    return events


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('music', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []
    files = sorted(f for f in a.music.rglob('*') if f.suffix.lower() in ('.wav', '.flac'))
    for f in files:
        for frac, start, x in excerpts(f):
            ev = decay_events(x.astype(float))
            if not ev: continue
            for model, flags, mode in MODELS:
                r0 = P.render(lib, x, FS, flags, impact_mode=mode, capture=True)
                r1 = P.render(lib, x, FS, flags, impact_mode=mode, capture=True, stage_flags=C1)
                d = r0['latency']
                y0 = r0['stem'][d:d + len(x)].astype(float).mean(axis=1); y1 = r1['stem'][d:d + len(x)].astype(float).mean(axis=1)
                for i in ev:
                    m = slice(i, i + int(.3 * FS)); e0, e1 = S.energy(y0[m]), S.energy(y1[m])
                    if e0 <= 0: continue
                    rows.append(dict(file=f.name, fraction=frac, model=model, event_s=round(i / FS - 4 + start, 3),
                                     tail_change_db=S.db(e1, e0)))
            print(f.name, frac, 'events', len(ev), flush=True)
    summary = {}
    for model, _, _ in MODELS:
        v = np.array([r['tail_change_db'] for r in rows if r['model'] == model])
        if len(v):
            summary[model] = dict(events=int(len(v)), median_db=float(np.median(v)), p90_db=float(np.percentile(v, 90)),
                                  max_db=float(v.max()), over_1db=int((v > 1).sum()), over_3db=int((v > 3).sum()))
            print('SUMMARY', model, json.dumps(summary[model]), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study2.decay.v1', candidate='C1', summary=summary, rows=rows),
                                   indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
