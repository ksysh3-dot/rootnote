import re, sys
from pathlib import Path
root = Path.home()/'datasets/slakh2100/train'
def bass_info(d):
    meta = (d/'metadata.yaml').read_text(encoding='utf-8', errors='replace')
    parts = re.split(r'\n\s{2}(S\d+):\s*\n', meta)
    ids = [parts[i] for i in range(1, len(parts)-1, 2) if re.search(r'inst_class:\s*Bass\b', parts[i+1])]
    stems = [p for p in (next((d/'stems'/f'{i}{x}' for x in ('.wav','.flac') if (d/'stems'/f'{i}{x}').exists()), None) for i in ids) if p]
    midis = [m for m in (d/'MIDI'/f'{s.stem}.mid' for s in stems) if m.exists()]
    return ids, stems, midis
for n in list(range(1,3))+[5,12,20,40,60]+list(range(21,45)):
    name = f'Track{n:05d}'
    d = root/name
    if not d.exists(): print(name, 'MISSING'); continue
    ids, stems, midis = bass_info(d)
    nm = len(list((d/'MIDI').glob('*.mid')))
    mix = next((d/x for x in ('mix.wav','mix.flac') if (d/x).exists()), None)
    print(name, 'bass ids', ids, 'stems', len(stems), 'bass midi', len(midis), 'all midi', nm, 'mix', mix.name if mix else None)
