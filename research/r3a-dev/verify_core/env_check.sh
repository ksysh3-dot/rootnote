#!/bin/bash
~/venv-rootnote/bin/python - <<'EOF'
import importlib
for m in ('mido', 'pretty_midi', 'soundfile', 'scipy', 'numpy', 'yaml'):
    try:
        mod = importlib.import_module(m); print(m, getattr(mod, '__version__', '?'))
    except Exception as e:
        print(m, 'MISSING', e)
EOF
cd ~/r3-work/tools/pvb-harness
grep -n "def midi_notes" -A 25 research_gt_bass.py | head -50
ls ~/datasets/slakh2100/train/Track00060 ~/datasets/slakh2100/train/Track00060/stems ~/datasets/slakh2100/train/Track00060/MIDI
head -30 ~/datasets/slakh2100/train/Track00060/metadata.yaml
