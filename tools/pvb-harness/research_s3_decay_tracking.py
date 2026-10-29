#!/usr/bin/env python3
"""Study 3 development (#4 follow-up): at real decays, does the generated layer fall as far as the music's low band?

Study 2 side check (research_s2_decay.py): with C1 the layer energy in the 300 ms after a low-band decay is up to
+3.5 dB above the unmodified model. That alone does not say which side is right. The envelope imposition is meant to
make the layer follow the music's low band, so the reference is the input itself: per decay event (as in
research_s2_decay.py) the drop from the 100 ms before to the 300 ms after the event,
  input_drop_db = 10 log10(E_in[after] / E_in[before])     (30-150 Hz band of the input)
  layer_drop_db = 10 log10(E_layer[after] / E_layer[before]) (generated stem, latency-aligned)
  excess_db     = layer_drop_db - input_drop_db            (> 0: the layer lingers; < 0: it falls faster)
for each model unmodified and with C1. Also the applied envelope gain (median over the after window) and the
share of the after window with gain below 1. Development, real music excerpts; not a quality score.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfiltfilt
import research_p1plus as P
import research_s1_interaction as S
from p1plus_paths import default_library
from research_s2_decay import decay_events
from research_s2_realmusic import FS, MODELS, C1, GAIN, excerpts

BEFORE, AFTER = .1, .3


def drop(y, i):
    b, a = S.energy(y[i - int(BEFORE * FS):i]), S.energy(y[i:i + int(AFTER * FS)])
    return S.db(a, b) if a > 0 and b > 0 else None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('music', type=Path)
    p.add_argument('--library', type=Path, default=default_library())
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    lib = P.api(a.library.resolve()); rows = []
    sos = butter(4, [30, 150], btype='bandpass', fs=FS, output='sos')
    files = sorted(f for f in a.music.rglob('*') if f.suffix.lower() in ('.wav', '.flac'))
    for f in files:
        for frac, start, x in excerpts(f):
            x = x.astype(float); ev = decay_events(x)
            if not ev: continue
            low = sosfiltfilt(sos, x.mean(axis=1))
            for model, flags, mode in MODELS:
                for cand, stage in (('unmodified', 0), ('C1', C1)):
                    r = P.render(lib, x, FS, flags, impact_mode=mode, capture=True, stage_flags=stage)
                    d = r['latency']; y = r['stem'][d:d + len(x)].astype(float).mean(axis=1)
                    g = r['stages'][:, GAIN]; gs = len(g) / len(x)
                    for i in ev:
                        din, dl = drop(low, i), drop(y, i)
                        if din is None or dl is None: continue
                        w = g[int(i * gs):int((i + AFTER * FS) * gs)]
                        rows.append(dict(file=f.name, fraction=frac, model=model, candidate=cand,
                                         event_s=round(i / FS - 4 + start, 3), input_drop_db=din, layer_drop_db=dl,
                                         excess_db=dl - din, gain_median=float(np.median(w)) if len(w) else None,
                                         gain_below_one=float(np.mean(w < 1 - 1e-9)) if len(w) else None))
            print(f.name, frac, 'events', len(ev), flush=True)
    summary = {}
    for model, _, _ in MODELS:
        for cand in ('unmodified', 'C1'):
            sub = [r for r in rows if (r['model'], r['candidate']) == (model, cand)]
            if not sub: continue
            v = np.array([r['excess_db'] for r in sub])
            summary[f'{model}/{cand}'] = dict(events=len(sub), excess_median_db=float(np.median(v)),
                                              excess_p10_db=float(np.percentile(v, 10)),
                                              excess_p90_db=float(np.percentile(v, 90)),
                                              abs_excess_median_db=float(np.median(abs(v))),
                                              input_drop_median_db=float(np.median([r['input_drop_db'] for r in sub])),
                                              gain_below_one_median=float(np.median([r['gain_below_one'] for r in sub])))
            print('SUMMARY', model, cand, json.dumps(summary[f'{model}/{cand}']), flush=True)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(dict(schema='rootnote.study3.decay_tracking.v1', candidate='C1 (stage flag 8192)',
                                        before_s=BEFORE, after_s=AFTER, summary=summary, rows=rows),
                                   indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
