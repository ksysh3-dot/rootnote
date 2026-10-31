"""Plan16 L: build the listening set listen/blind_core (CHOICES.md).  Run from tools/pvb-harness with PYTHONPATH=.:study
usage: ~/venv-rootnote/bin/python ~/r3a-dev/plan16/L/build.py"""
import hashlib, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
import test_engine as T
import research_core_api as CA
import research_core_xcheck as X

FS = 48000
SEED = 20261031
L = Path('/home/ksysh/r3a-dev/plan16/L')
OUT = Path('/mnt/c/Users/ksysh/rootnote-duo/listen/blind_core')
LIB = Path('build_core/libpvbcapi.so').resolve()
W = 9.0
FSC = 3000.0
R3R = 59.3507
CH = json.load(open(L / 'choices.json'))
Z = np.load(L / 'sil_series.npz')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


lib = CA.load(LIB)


def render(x, algo):
    e = T.Engine(lib, FS, vb_on=1, vb_algo=algo, ramp_ms=0)
    try:
        if algo == 15:
            CA.set_resultant(lib, e)
        y = np.stack([x, x], 1) if x.ndim == 1 else x
        y = np.ascontiguousarray(y, np.float32).copy()
        for i in range(0, len(y), 256):
            b = y[i:i + 256]
            lib.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
        lat = int(lib.pvb_latency(e.h))
    finally:
        e.close()
    return y[lat:lat + 30 * FS].astype(np.float64), lat


items = []                    # (song, start, rank_label)
for key in ('Track00025', 'Track00026'):
    for r, t in enumerate(CH[key]['tests'], 1):
        items.append(dict(track=key, start=t['start'], kind='test', rank=r))
for key in ('Track00025', 'Track00026'):
    items.append(dict(track=key, start=CH[key]['null']['start'], kind='null', rank=4))

rng = np.random.default_rng(SEED)
null_types = list(rng.permutation(['core|core', 'p1|p1']))
order = [int(i) for i in rng.permutation(len(items))]
nulls = [i for i, it in enumerate(items) if it['kind'] == 'null']
for i, nt in zip(nulls, null_types):
    items[i]['null_type'] = nt

rend = {}
for key in ('Track00025', 'Track00026'):
    x = X.read_excerpt(X.SLAKH / key / 'mix.flac', 0.0, 31.0)
    for algo in (15, 6):
        rend[(key, algo)], lat = render(x, algo)
    print(key, 'rendered, latency', lat, flush=True)

# informational: the P1 side of this build against the P1 reference build (bit identity claimed by RESULTANT_CORE.md section 1)
try:
    ref = X.open_lib(X.REF)
    key = 'Track00026'
    x = X.read_excerpt(X.SLAKH / key / 'mix.flac', 0.0, 31.0)
    e = T.Engine(ref, FS, vb_on=1, vb_algo=6, ramp_ms=0)
    y = np.ascontiguousarray(x, np.float32).copy()
    for i in range(0, len(y), 256):
        b = y[i:i + 256]
        ref.pvb_process(e.h, b.ctypes.data_as(T.FP), len(b))
    lat2 = int(ref.pvb_latency(e.h)); e.close()
    yr = y[lat2:lat2 + 30 * FS].astype(np.float64)
    print('P1(build_core) vs P1(ref build) T26 0-30 s: max abs diff', float(np.abs(yr - rend[(key, 6)]).max()), flush=True)
except Exception as ex:
    print('ref build comparison failed:', repr(ex))


def spots(key, start):
    y = Z[key + '_ysil'] ** 2
    y[:1500] = 0.0
    c = np.r_[0.0, np.cumsum(y)]
    cand = np.round(np.arange(start, start + W - 1.0 + 1e-9, 0.25), 2)
    sc = np.array([c[int(round((t + 1) * FSC))] - c[int(round(t * FSC))] for t in cand])
    pick = []
    for i in np.argsort(-sc, kind='stable'):
        if all(abs(cand[i] - cand[j]) >= 1.0 for j in pick):
            pick.append(i)
        if len(pick) == 3:
            break
    pick = sorted(pick, key=lambda i: cand[i])
    return [dict(t=float(cand[i] - start), units=float(sc[i] / R3R)) for i in pick]


fade = np.minimum(1.0, np.minimum(np.arange(int(W * FS)), np.arange(int(W * FS))[::-1]) / 480.0)[:, None]
OUT.mkdir(parents=True, exist_ok=True)
key_pairs = {}
report = []
for n, idx in enumerate(order, 1):
    it = items[idx]
    s0 = int(round(it['start'] * FS)); seg = slice(s0, s0 + int(W * FS))
    seg_core, seg_p1 = rend[(it['track'], 15)][seg], rend[(it['track'], 6)][seg]
    if it['kind'] == 'null':
        a_name, b_name = it['null_type'].split('|')
        side = None
    else:
        swap = bool(rng.integers(2))
        a_name, b_name = ('p1', 'core') if swap else ('core', 'p1')
    pick = lambda nme: seg_core if nme == 'core' else seg_p1
    A, B = pick(a_name).copy(), pick(b_name).copy()
    rms = lambda v: float(np.sqrt(np.mean(v ** 2)))
    g = rms(A) / rms(B)
    corr_db = 20 * np.log10(g)
    B *= g
    A *= fade; B *= fade
    peak = max(np.abs(A).max(), np.abs(B).max())
    scale = min(1.0, 0.95 / peak)
    A *= scale; B *= scale
    stereo = np.r_[A, np.zeros((FS, 2)), B]
    fn = f'core_{n}.wav'
    sf.write(str(OUT / fn), np.clip(stereo, -1, 1).astype(np.float32), FS, subtype='PCM_16')
    sp = spots(it['track'], it['start'])
    key_pairs[fn] = dict(pair=n, track=it['track'], window_start_s=it['start'], kind=it['kind'], rank=it['rank'],
                         A=a_name, B=b_name, loudness_correction_B_dB=round(float(corr_db), 4),
                         common_scale=round(float(scale), 5), pair_peak=round(float(peak * scale), 4), spots_in_A_s=sp)
    report.append((n, it['track'], it['start'], it['kind'], corr_db, float(peak * scale), scale, sp))
    print(f'pair {n}: {it["track"]} start {it["start"]} {it["kind"]} corr {corr_db:+.3f} dB peak {peak * scale:.3f} scale {scale:.4f}', flush=True)

blob = json.dumps(dict(seed=SEED, library=str(LIB), library_sha256=sha(LIB), order=order, pairs=key_pairs), sort_keys=True, indent=1, ensure_ascii=False).encode('utf-8')
(L / 'key.json').write_bytes(blob)
digest = hashlib.sha256(blob).hexdigest()
print('key sha256', digest)
print('lib sha256', sha(LIB))

# listening sheet (Korean; no mention of what is what)
rows = []
for n, tr, st, kind, corr, pk, sc, sp in sorted(report):
    a = ', '.join(f'{s["t"]:.2f}–{s["t"] + 1:.2f}' for s in sp)
    b = ', '.join(f'{s["t"] + 10:.2f}–{s["t"] + 11:.2f}' for s in sp)
    rows.append(f'| {n} | core_{n}.wav | {a} | {b} | 어느 쪽이 더 거슬리나 (A/B/같음) + 거슬림 1–5, 베이스가 더 좋은 쪽 (A/B/같음) |')
ans = '\n'.join(f'| {n} |  |  |  |  |' for n in range(1, 9))
md = f'''# 베이스 구간 블라인드 (해악 순위) — 청감 시트

열쇠(정답) 파일의 sha256 (듣기 전에 고정): `{digest}`

## 방법

- 파일은 `core_1.wav` ~ `core_8.wav` 8개다. 한 파일 = A (9 초) + 1 초 무음 + B (9 초)이고, A와 B는 같은 곡 구간이다.
- 쌍마다 A와 B 중 한쪽이 다를 수 있다. 둘 다 같은 쌍도 있다.
- 같은 기기, 같은 음량으로 듣는다. A/B 음량은 이미 맞춰 두었다.
- 아래 "들을 곳"은 A와 B에 똑같이 적용되는 시각이다. 그 부분을 먼저 들어 보고, 나머지는 자유롭게 들어도 된다.
- 답
  - 어느 쪽이 더 거슬리나 (A / B / 같음) + 거슬림 1–5 (1 = 거의 안 거슬림, 5 = 매우 거슬림)
  - 베이스가 더 좋은 쪽 (A / B / 같음)
  - 메모
- 이 결과는 해악 순위로만 쓰고, 채택 판정에는 쓰지 않는다.

## 들을 곳

| 쌍 | 파일 | 들을 곳 (A 안의 시각, 초) | 같은 곳 (B 안의 시각, 초 = A 시각 + 10) | 질문 |
|---|---|---|---|---|
''' + '\n'.join(rows) + f'''

## 답 적는 곳

| 쌍 | 더 거슬리는 쪽 (A/B/같음) | 거슬림 1–5 | 베이스가 더 좋은 쪽 (A/B/같음) | 메모 |
|---|---|---|---|---|
{ans}
'''
(OUT / 'listen.md').write_text(md, encoding='utf-8')
print('listen.md written')
