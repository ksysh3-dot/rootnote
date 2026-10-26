#!/usr/bin/env python3
"""Build the unchanged host C API on Windows using an explicitly supplied Zig.

Only the generated C API copy receives DLL export annotations. DSP sources are
compiled in place. Caches and temporary files stay under the output directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zig', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--source-root', type=Path,
                        help='Optional repository/control checkout to compile, keeping this builder.')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = args.source_root.resolve() if args.source_root else here.parents[1]
    src = root / 'app/src/main/cpp/libpvb'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key, folder in [('TEMP', 'tmp'), ('TMP', 'tmp'),
                        ('ZIG_GLOBAL_CACHE_DIR', 'global-cache'),
                        ('ZIG_LOCAL_CACHE_DIR', 'local-cache')]:
        p = (args.cache.resolve() if args.cache else out.parent) / folder
        p.mkdir(parents=True, exist_ok=True)
        env[key] = str(p)
    capi = root / 'tools/pvb-harness/pvb_capi.cpp'
    generated = out / 'pvb_capi_windows.cpp'
    source = capi.read_text(encoding='utf-8')
    source = re.sub(r'^(?=(?:int|void\*?|float|double)\s+pvb_\w+\()',
                    '__declspec(dllexport) ', source, flags=re.M)
    generated.write_text(source, encoding='utf-8')
    inputs = [src / n for n in ('pvb_engine.cpp', 'pvb_analysis.cpp',
                                'pvb_vb.cpp', 'pvb_vb52.cpp')]
    cmd = [str(args.zig.resolve()), 'c++', '-std=c++17', '-O2',
           '-fno-fast-math', '-Wall', '-Wextra', '-Wpedantic', '-Werror',
           '-pthread', '-shared', '-I' + str(src), *map(str, inputs),
           str(generated), '-o', str(out / 'pvbcapi.dll')]
    subprocess.run(cmd, env=env, check=True)
    files = sorted(src.glob('*.h')) + inputs + [capi]
    manifest = {p.relative_to(root).as_posix():
                hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (out / 'source_hashes.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(out / 'pvbcapi.dll', flush=True)


if __name__ == '__main__':
    main()
