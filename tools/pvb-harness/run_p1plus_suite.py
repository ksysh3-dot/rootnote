#!/usr/bin/env python3
"""Reproduce the P1+ study. Test execution success is not promotion approval."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, default=PACKAGE/'windows-x64/baseline/pvbcapi.dll')
    p.add_argument('--candidate', type=Path, default=PACKAGE/'windows-x64/candidate-v3/pvbcapi.dll')
    p.add_argument('--debounce', type=Path, default=PACKAGE/'windows-x64/candidate-v2/pvbcapi.dll')
    p.add_argument('--out', type=Path, default=PACKAGE/'recheck')
    p.add_argument('--music-folder', type=Path, action='append', default=[])
    p.add_argument('--skip-regression', action='store_true')
    p.add_argument('--require-promotion', action='store_true',
                   help='Exit 2 if the frozen synthetic screen fails; never approves a release.')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    for name in ('baseline', 'candidate', 'debounce'):
        path = getattr(a, name).resolve()
        if not path.is_file(): p.error(f'Missing {name} library: {path}')
        setattr(a, name, path)
    for folder in a.music_folder:
        if not folder.is_dir(): p.error(f'Missing music folder: {folder}')
    out = a.out.resolve()
    if not a.dry_run: out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1')

    def run(script, *args):
        cmd = [sys.executable, str(HERE/script), *map(str, args)]
        print(subprocess.list2cmdline(cmd), flush=True)
        if not a.dry_run: subprocess.run(cmd, env=env, cwd=HERE, check=True)

    for lib, flags, filename in (
        (a.baseline, 0, 'baseline.json'), (a.candidate, 0, 'candidate-0.json'),
        (a.candidate, 1, 'candidate-1.json'), (a.debounce, 2, 'phase-v2.json'),
        (a.candidate, 2, 'phase-v3.json')):
        run('research_p1plus.py', '--library', lib, '--flags', flags, '--report', out/filename)
    for fs in (44100, 48000):
        for lib, flags, prefix in ((a.baseline, 0, 'heldout-baseline'),
                                   (a.candidate, 2, 'heldout-candidate-v3')):
            run('research_p1plus.py', '--library', lib, '--flags', flags, '--fs', fs,
                '--heldout', '--report', out/f'{prefix}-{fs}.json')
    run('test_p1plus.py', '--lib', a.candidate, '--baseline', a.baseline,
        '--results', out, '--report', out/'p1plus-validation.json')
    if not a.skip_regression:
        for script, filename in (('test_engine.py', 'engine-regression.json'),
                                  ('test_native_renderer.py', 'native-renderer.json'),
                                  ('test_native_stream.py', 'native-stream.json')):
            run(script, '--lib', a.candidate, '--report', out/filename)
        run('test_alpha2_profiles.py', '--lib', a.candidate, '--baseline', a.baseline,
            '--report', out/'alpha2-regression.json')
    if a.music_folder:
        folders = [value for folder in a.music_folder for value in ('--folder', folder.resolve())]
        run('research_p1plus_music.py', '--baseline', a.baseline, '--candidate', a.candidate,
            '--report', out/'music.json', *folders)
    if not a.dry_run:
        verdict = json.loads((out/'p1plus-validation.json').read_text(encoding='utf-8'))
        print('Study execution complete. Synthetic screen:', verdict['synthetic_screen'], flush=True)
        print('Real-music quality, phone playback and preference remain separate judgments.', flush=True)
        if a.require_promotion and verdict['synthetic_screen'] != 'pass': raise SystemExit(2)


if __name__ == '__main__': main()
