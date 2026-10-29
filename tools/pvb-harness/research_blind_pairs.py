#!/usr/bin/env python3
"""Blind listening calibration (#4, local only): which tracking change is audible? Pairs of the full app output, P1 and a
candidate, on MUSDB 7 s excerpts chosen across the candidate's per-excerpt tracking change (from a research_gt_bass
report), plus null pairs (P1 against P1) that measure how often "different" is heard when nothing changed. Each pair is
X / Y in random order; one gain per pair (the P1 peak at -1 dBFS), so the candidate's own level change is kept.
The key (which file is which, each pair's tracking change) goes to --key, outside the listening folder; its SHA-256 is
printed into the README beforehand, so the answers can be scored against a key fixed before listening.
Listening results label a candidate (audible / measured only) and flag harm; they do not reject a measured improvement."""
import argparse, hashlib, html, json
from pathlib import Path
import numpy as np
import soundfile as sf
import research_gt_bass as G
import research_p1plus as P

TARGETS = (.30, .20, .12, .06, .02, -.06)   # per-excerpt tracking change (candidate - P1) to cover


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('report', type=Path); p.add_argument('root', type=Path); p.add_argument('out', type=Path)
    p.add_argument('--library', type=Path, required=True); p.add_argument('--key', type=Path, required=True)
    p.add_argument('--candidate', default='p1_r3a'); p.add_argument('--nulls', type=int, default=2); p.add_argument('--seed', type=int, default=20261029)
    a = p.parse_args(); rng = np.random.default_rng(a.seed); a.out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(a.report.read_text())['rows']; by = {}
    for r in rows: by.setdefault(r['item'], {})[r['model']] = r
    cand = {k: v[a.candidate]['tracked'] - v['p1']['tracked'] for k, v in by.items()
            if 'p1' in v and a.candidate in v and None not in (v['p1']['tracked'], v[a.candidate]['tracked'])
            and v['p1']['voiced_frames'] >= 300}
    chosen = []
    for t in TARGETS:
        k = min((k for k in cand if k not in chosen), key=lambda k: abs(cand[k] - t)); chosen.append(k)
    rest = [k for k in cand if k not in chosen and abs(cand[k]) < .01]
    nulls = list(rng.choice(rest, a.nulls, replace=False)) if len(rest) >= a.nulls else []
    pairs = [(k, 'test') for k in chosen] + [(int(k), 'null') for k in nulls]
    order = rng.permutation(len(pairs)); items = list(G.items(a.root)); lib = P.api(a.library.resolve())
    _, cst = G.model_spec(a.candidate); key = []
    for n, i in enumerate(order):
        idx, kind = pairs[i]; name, mix, bass, fs, _, _ = items[idx]
        x = G.to_rate(mix, fs, G.FS).astype(np.float32)
        rb = P.render(lib, x, G.FS, 0, stage_flags=0); rc = rb if kind == 'null' else P.render(lib, x, G.FS, 0, stage_flags=cst)
        lat = rb['latency']; g = 10 ** (-1 / 20) / max(float(np.max(np.abs(rb['output']))), 1e-9)
        swap = bool(rng.integers(2)); files = {}
        for side, r in zip(('X', 'Y'), ((rc, rb) if swap else (rb, rc))):
            f = a.out / f'{n + 1:02d}_{side}.wav'; sf.write(str(f), np.clip(r['output'][lat:] * g, -1, 1), G.FS, subtype='PCM_24'); files[side] = f.name
        key.append(dict(pair=n + 1, kind=kind, item=int(idx), name=name, candidate_is=('X' if swap else 'Y') if kind == 'test' else None,
                        tracking_change=None if kind == 'null' else round(float(cand[idx]), 4)))
        print(f'pair {n + 1:02d} {kind} done', flush=True)
    blob = json.dumps(dict(seed=a.seed, candidate=a.candidate, report=a.report.name, pairs=key), ensure_ascii=False, indent=1)
    a.key.write_text(blob, encoding='utf-8'); digest = hashlib.sha256(blob.encode('utf-8')).hexdigest()
    n = len(key)
    (a.out / 'README.txt').write_text(
        f'블라인드 청감 보정 1차 ({n}쌍, 약 10분). 쌍마다 X와 Y를 들어 보고 index.html에 답한다.\n'
        '어느 쪽이 무엇인지는 이 폴더에 없다. 일부 쌍은 일부러 똑같은 소리다.\n'
        '이어폰이나 평소 듣는 장치로, 같은 볼륨에서. 반복 재생해도 된다.\n'
        f'정답 키 SHA-256 (듣기 전에 고정): {digest}\n'
        '음원: MUSDB18 7 s 발췌 (CC BY 4.0), 로컬 청취 전용 — 공유·커밋하지 않는다.\n', encoding='utf-8')
    cards = '\n'.join(f'''<section><h2>{k['pair']:02d}</h2>
<div class="row"><span>X</span><audio controls preload="none" src="{k['pair']:02d}_X.wav"></audio></div>
<div class="row"><span>Y</span><audio controls preload="none" src="{k['pair']:02d}_Y.wav"></audio></div>
<fieldset data-q="d{k['pair']}"><legend>차이가 들리나요?</legend>
<label><input type="radio" name="d{k['pair']}" value="D">들린다</label><label><input type="radio" name="d{k['pair']}" value="N">모르겠다·같다</label></fieldset>
<fieldset data-q="b{k['pair']}"><legend>베이스 음높이가 더 자연스러운 쪽 (들릴 때만)</legend>
<label><input type="radio" name="b{k['pair']}" value="X">X</label><label><input type="radio" name="b{k['pair']}" value="Y">Y</label><label><input type="radio" name="b{k['pair']}" value="-">모르겠다</label></fieldset>
<fieldset data-q="c{k['pair']}"><legend>확신</legend>
<label><input type="radio" name="c{k['pair']}" value="1">약함</label><label><input type="radio" name="c{k['pair']}" value="2">보통</label><label><input type="radio" name="c{k['pair']}" value="3">강함</label></fieldset>
</section>''' for k in key)
    (a.out / 'index.html').write_text(f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>블라인드 청감 보정</title><style>
:root{{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e2dc;--accent:#2f5d8a}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151514;--fg:#ececea;--muted:#a0a09a;--card:#1f1f1d;--line:#33332f;--accent:#8fb5dc}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}} main{{max-width:720px;margin:0 auto;padding:16px}}
h1{{font-size:1.3rem}} p{{color:var(--muted)}} section{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:12px 0}}
h2{{font-size:1rem;margin:0 0 8px}} .row{{display:flex;align-items:center;gap:10px;margin:6px 0}} .row span{{width:1.5em;font-weight:600}} audio{{width:100%}}
fieldset{{border:0;padding:4px 0;margin:6px 0}} legend{{color:var(--muted);font-size:.9rem}} label{{margin-right:14px;white-space:nowrap}}
button{{background:var(--accent);color:var(--bg);border:0;border-radius:8px;padding:10px 16px;font-size:1rem}} textarea{{width:100%;height:5em;margin-top:8px;background:var(--card);color:var(--fg);border:1px solid var(--line)}}
</style></head><body><main><h1>블라인드 청감 보정 ({n}쌍)</h1>
<p>쌍마다 X와 Y를 들어 보세요. 어느 쪽이 무엇인지는 알려 드리지 않고, 일부 쌍은 일부러 똑같은 소리입니다. 같은 볼륨에서, 반복해 들어도 됩니다.</p>
{cards}
<button onclick="out()">결과 만들기</button><textarea id="r" readonly placeholder="여기 나온 한 줄을 복사해 대화창에 붙여 주세요"></textarea>
<script>function out(){{const v=q=>{{const e=document.querySelector('input[name="'+q+'"]:checked');return e?e.value:'?'}};
let s=[];for(let i=1;i<={n};i++)s.push(i+':'+v('d'+i)+v('b'+i)+v('c'+i));document.getElementById('r').value='BLIND1 '+s.join(' ');}}</script>
</main></body></html>''', encoding='utf-8')
    print('key sha256', digest)


if __name__ == '__main__':
    main()
