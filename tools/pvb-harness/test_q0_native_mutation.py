#!/usr/bin/env python3
"""Build an isolated native ratio=0 fault and require waveform-gate rejection.

Never patches the repository sources. A nonzero exit alone is insufficient:
the child must reach the production-waveform assertion. Compile/import errors
are infrastructure failures, not successful fault detection.
"""
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
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',default='native-mutation-q0.json')
    a=p.parse_args()
    rows=[]
    original_sources={name:(SRC/name).read_bytes() for name in ('pvb_vb_modulation.h','pvb_vb52.cpp')}
    capi_original=(HERE/'pvb_capi.cpp').read_bytes()
    defects=('ratio_zero','freeze_am','reverse_curvature','phase_reset','sample_offset','uncleared_ring','minus12db','future_read')
    for defect in defects:
        with tempfile.TemporaryDirectory(prefix='pvb-q0-mutation-') as directory:
            root=Path(directory);src=root/'libpvb';shutil.copytree(SRC,src)
            capi=root/'pvb_capi.cpp';capi.write_bytes(capi_original)
            target=src/'pvb_vb_modulation.h'
            text=target.read_text()
            if defect=='ratio_zero':
                start=text.index('inline void local(');stop=text.index('\n}',start)+2
                text=text[:start]+'inline void local(const ModulationFit& m,double t,double& ratio,double& phase) {\n (void)m;(void)t;ratio=0;phase=0;\n}'+text[stop:]
            elif defect=='freeze_am':
                start=text.index('    ratio=',text.index('inline void local('));stop=text.index('\n',start)
                text=text[:start]+'    ratio=1.;'+text[stop:]
            elif defect=='reverse_curvature':
                text=text.replace('Pi*m.slope*t*t','-Pi*m.slope*t*t')
            else:
                target=capi if defect=='future_read' else src/'pvb_vb52.cpp'
                text=target.read_text()
                old,new={
                    'phase_reset':('k*(tr.phi+phase)','k*phase'),
                    'sample_offset':('(centre-16+g)','(centre-15+g)'),
                    'uncleared_ring':('pvOut_[slot]=pvApv_[slot]=0;','/* fault: stale ring retained */'),
                    'minus12db':('pvOut_[slot]+=grain[g]*gw_[g];','pvOut_[slot]+=.25*grain[g]*gw_[g];'),
                    'future_read':('if(count>s.finalized-s.readPosition) return -2;','/* fault: unfinalized read allowed */')
                }[defect]
                assert text.count(old)==1,(defect,text.count(old));text=text.replace(old,new)
            target.write_text(text)
            library=root/'libmutant.so'
            command=['g++','-std=c++17','-O2','-fno-fast-math','-Wall','-Wextra','-Wpedantic','-Werror','-fPIC','-shared',
                     '-I'+str(src),*[str(src/n) for n in ('pvb_engine.cpp','pvb_analysis.cpp','pvb_vb.cpp','pvb_vb52.cpp')],
                     str(capi),'-o',str(library)]
            subprocess.run(command,check=True)
            tests=[]
            for script,extra in [('test_native_stream.py',[]),('test_modulation_research.py',['--direct-only'])]:
                result=subprocess.run([sys.executable,str(HERE/script),'--lib',str(library),
                                       '--report',str(root/(script+'.json')),*extra],text=True,capture_output=True)
                log=result.stdout+result.stderr
                valid_tag=any(tag in log for tag in ('native_renderer_waveform','native_ola_waveform','native_ola_tail','unfinalized future exposed'))
                detected=result.returncode!=0 and 'AssertionError' in log and valid_tag
                if not detected:raise AssertionError((defect,script,result.returncode,log[-3000:]))
                tests.append(dict(script=script,exit_code=result.returncode,assertion=log.strip().splitlines()[-1]))
            rows.append(dict(defect=defect,scope='host API guard' if defect=='future_read' else 'production native code',
                             mutant_library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),tests=tests))
            print('Detected',defect,flush=True)
    unchanged=all((SRC/n).read_bytes()==data for n,data in original_sources.items()) and (HERE/'pvb_capi.cpp').read_bytes()==capi_original
    assert unchanged
    report=dict(schema='pvb.q0.native_mutation.v2',status='pass',source_repository_unchanged=unchanged,defects=rows,
                scope='Production waveform/OLA and host future-read fault detection; not listening results')
    Path(a.report).write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:8 isolated native/API faults rejected by stream and P1 gates')

if __name__=='__main__':
    main()
