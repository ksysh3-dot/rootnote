#!/usr/bin/env python3
"""Reject disconnected production predictor dispatch, while API tests pass."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
SRC=HERE.parents[1]/'app/src/main/cpp/libpvb'


def main():
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args()
    original=(SRC/'pvb_vb52.cpp').read_bytes();results=[]
    for name,old,new in (
        ('linear_dispatch','(stageFlags_&StageTrackLinear)?prediction52::Linear:',
         '(stageFlags_&StageTrackLinear)?prediction52::Constant:'),
        ('burg_dispatch','(stageFlags_&StageTrackBurg)?prediction52::Burg:',
         '(stageFlags_&StageTrackBurg)?prediction52::Constant:')):
        with tempfile.TemporaryDirectory(prefix='pvb-prediction-mutation-') as tmp:
            root=Path(tmp);src=root/'libpvb';shutil.copytree(SRC,src)
            target=src/'pvb_vb52.cpp';text=target.read_text();assert text.count(old)==1
            target.write_text(text.replace(old,new));library=root/'libmutant.so'
            command=['g++','-std=c++17','-O2','-fno-fast-math','-Wall','-Wextra','-Wpedantic','-Werror','-fPIC','-shared',
                '-I'+str(src),*[str(src/n) for n in ('pvb_engine.cpp','pvb_analysis.cpp','pvb_vb.cpp','pvb_vb52.cpp')],str(HERE/'pvb_capi.cpp'),'-o',str(library)]
            subprocess.run(command,check=True)
            direct=subprocess.run([sys.executable,'-c',
                'import test_track_prediction_research as P;P.direct(P.api('+repr(str(library))+'))'],cwd=HERE,capture_output=True,text=True)
            assert direct.returncode==0,direct.stdout+direct.stderr
            native=subprocess.run([sys.executable,'-c',
                'import test_track_prediction_research as P;P.native_cases(P.api('+repr(str(library))+'))'],cwd=HERE,capture_output=True,text=True)
            log=native.stdout+native.stderr
            assert native.returncode!=0 and 'AssertionError' in log and 'native predictor dispatch not reached' in log,log
            results.append(dict(mutation=name,api_predictor_checks='pass',production_integration='rejected',
                assertion=log.strip().splitlines()[-1],library_sha256=hashlib.sha256(library.read_bytes()).hexdigest()))
            print('Detected',name,flush=True)
    assert (SRC/'pvb_vb52.cpp').read_bytes()==original
    Path(a.report).write_text(json.dumps(dict(schema='pvb.phase2.predictor_mutation.v1',mutations=results,repository_source_unchanged=True),indent=2)+'\n')


if __name__=='__main__':main()
