import json, os
import research_core_xcheck as X
print(X.CAND, os.path.exists(X.CAND), os.path.exists(X.REF))
s = json.load(open(os.path.expanduser('~/r3a-dev/core_results/verify_A/results.json')))['metrics']['V6']
print([(t['name'], t['tp']) for t in s['per_track']])
print(sorted(os.listdir(os.path.expanduser('~/datasets/slakh2100_midi/train/Track00060/MIDI')))[:20])
print(os.cpu_count())
print(open(os.path.expanduser('~/datasets/slakh2100_midi/train/Track00060/metadata.yaml')).read()[:1500])
