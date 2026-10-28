#!/usr/bin/env python3
"""R01 predeclared developer controls, not a new holdout / not a listening test.

Checks that the opt-in track-protection candidate does not change frozen P1++
app model 13, does not change streaming/block behavior, and does not affect
ordinary steady/modulated/travelling notes without a percussive intrusion.
Writes observed differences rather than treating every difference as an
automatic quality failure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import research_p1plus as P
from p1plus_paths import default_library

def signals(fs,n=None):
    # n: sample count (default 2 s); Study 1 (#4) reuses these notes as preservation beds
    t=np.arange(round(2.0*fs) if n is None else n)/fs
    ramp=np.minimum(1.,t/.07)
    return {
        'steady_65hz':.02*ramp*np.cos(2*np.pi*65*t),
        'am_7hz_65hz':.02*ramp*(1+.35*np.cos(2*np.pi*7*t))*np.cos(2*np.pi*65*t),
        'continuous_gliss_50_to_90hz':.02*ramp*np.cos(2*np.pi*(50*t+10*t*t)),
        'two_tones_65_and_95hz':ramp*(.017*np.cos(2*np.pi*65*t)+.014*np.cos(2*np.pi*95*t)),
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--library',type=Path,default=default_library())
    ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--candidate',type=int,choices=(64,192,320,448),default=64)
    args=ap.parse_args()
    lib=P.api(args.library.resolve())
    prior=os.environ.get('P1PP_V04')
    records=[]
    try:
        for fs in (44100,48000):
            for name,sig in signals(fs).items():
                x=np.r_[sig,np.zeros(fs//3)]
                os.environ['P1PP_V04']='0'
                base=P.render(lib,x,fs=fs,flags=6,impact_mode=8,capture=False)
                baseline_blocks=P.render(lib,x,fs=fs,flags=6,impact_mode=8,capture=False,block=1379)
                os.environ['P1PP_V04']=str(args.candidate)
                guarded=P.render(lib,x,fs=fs,flags=6,impact_mode=8,capture=False)
                blocks=P.render(lib,x,fs=fs,flags=6,impact_mode=8,capture=False,block=1379)
                base_block_exact=bool(np.array_equal(base['output'],baseline_blocks['output']))
                cand_block_exact=bool(np.array_equal(guarded['output'],blocks['output']))
                assert guarded['latency']==base['latency'],(fs,name,'latency')
                assert np.isfinite(guarded['output']).all()
                diff=float(np.max(np.abs(base['stem'].astype(float)-guarded['stem'].astype(float))))
                equal=bool(np.array_equal(base['stem'],guarded['stem']))
                # Real app model 13 must ignore host R01 flags and remain bit exact.
                os.environ['P1PP_V04']='0'
                fixedbase=P.render(lib,x,fs=fs,algo=13,capture=False)
                os.environ['P1PP_V04']=str(args.candidate)
                fixedguard=P.render(lib,x,fs=fs,algo=13,capture=False)
                assert np.array_equal(fixedbase['output'],fixedguard['output']), (fs,name,'fixed app model')
                records.append(dict(fs=fs,name=name,host_output_equal=equal,
                                    host_stem_max_difference=diff,
                                    baseline_block_exact=base_block_exact,
                                    candidate_block_exact=cand_block_exact,
                                    baseline_block_max_difference=float(np.max(np.abs(base['output'].astype(float)-baseline_blocks['output'].astype(float)))),
                                    candidate_block_max_difference=float(np.max(np.abs(guarded['output'].astype(float)-blocks['output'].astype(float)))),
                                    introduced_block_failure=base_block_exact and not cand_block_exact,
                                    latency_preserved=True,app_model13_unchanged=True))
                print(fs,name,'candidate_equal',equal,'max_stem_diff',f'{diff:.3g}',
                      'base_block_exact',base_block_exact,'cand_block_exact',cand_block_exact,flush=True)
    finally:
        if prior is None:os.environ.pop('P1PP_V04',None)
        else:os.environ['P1PP_V04']=prior
    report=dict(schema='pvb.p1pp.r01.controls.v1',
                status='predeclared_negative controls; differences do not establish audible error',
                independent_synthetic_waveforms=4, rates=[44100,48000],
                candidate=f'host V04 flags {args.candidate}',device_or_listening_test=False,
                library_sha256=hashlib.sha256(args.library.read_bytes()).hexdigest(),
                records=records)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    # A failure inherited from the same engine without the R01 flag is not a
    # regression introduced by the candidate. Keep it visible in the report.
    assert not any(row['introduced_block_failure'] for row in records), 'R01 introduced block-size drift (see report)'
    print('R01 control engineering invariants PASS',len(records),'cases',flush=True)

if __name__=='__main__':main()
