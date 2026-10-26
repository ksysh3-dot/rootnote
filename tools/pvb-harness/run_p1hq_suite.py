#!/usr/bin/env python3
"""Execute the HQ evidence suite; does not require a listener's AB verdict."""
import argparse,os,subprocess,sys
from pathlib import Path
from p1plus_paths import default_library
HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[2]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,default=default_library())
    p.add_argument('--baseline',type=Path,default=default_library('baseline'))
    p.add_argument('--previous',type=Path,default=default_library('phase-v01'))
    p.add_argument('--out',type=Path,default=HERE/'build'/'p1plus-recheck')
    p.add_argument('--music-folder',type=Path,action='append',default=[])
    p.add_argument('--clips',type=Path);p.add_argument('--skip-regression',action='store_true')
    p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    for key in ('candidate','baseline','previous'):
        path=getattr(a,key).resolve()
        if not path.is_file():p.error(f'Missing library: {path}')
        setattr(a,key,path)
    out=a.out.resolve()
    if not a.dry_run:out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1')
    def run(script,*args):
        cmd=[sys.executable,str(HERE/script),*map(str,args)]
        print(subprocess.list2cmdline(cmd),flush=True)
        if not a.dry_run:subprocess.run(cmd,cwd=HERE,env=env,check=True)
    run('research_p1hq.py','--candidate',a.candidate,'--baseline',a.baseline,'--previous',a.previous,'--out',out)
    for script,name in (('check_p1hq_envelopes.py','envelopes.json'),
                        ('check_p1hq_primary_envelopes.py','primary-envelopes.json'),
                        ('check_p1hq_am.py','am.json'),
                        ('benchmark_p1hq.py','host-timing.json')):
        run(script,'--library',a.candidate,'--report',out/name)
    if not a.skip_regression:
        run('test_engine.py','--lib',a.candidate,'--report',out/'engine-regression.json')
        run('test_alpha2_profiles.py','--lib',a.candidate,'--baseline',a.baseline,'--report',out/'alpha2-regression.json')
    if a.music_folder:
        folders=[v for folder in a.music_folder for v in ('--folder',folder.resolve())]
        extra=[] if not a.clips else ['--clips',a.clips.resolve()]
        run('research_p1hq_music.py','--library',a.candidate,'--report',out/'music.json',*folders,*extra)
    print('HQ suite complete. Review measured trade-offs; no listening/phone claim is implied.',flush=True)


if __name__=='__main__':main()
