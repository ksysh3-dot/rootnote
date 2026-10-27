#!/usr/bin/env python3
"""R01 development-only comparison across the *already inspected* 2026102609 impact corpus.

No held-out claims. Compares P1++ v0.3 vs host bit64 (existing model 13
unaffected) on twelve distinct waveforms and two input levels each. Differences
are paired per waveform; levels are not independent samples. Outputs diagnostic
metrics, not listening scores or instrument attribution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np

import research_p1plus as P
from research_p1pp_recovery import new_fixtures
from research_p1pp_impacts import score
from research_p1pp_track_identity import track_identity
from p1plus_paths import default_library

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--candidate',type=int,choices=(64,192,320,448),default=64)
    a=p.parse_args()
    lib=P.api(a.library.resolve());fs=48000
    old=os.environ.get('P1PP_V04')
    rows=[]
    try:
        for name,_,t,bed,z,onset,duration,desc in new_fixtures(fs,seed=2026102609,count=12):
            ref={}
            for flag in (0,a.candidate):
                os.environ['P1PP_V04']=str(flag)
                ref[flag]=P.render(lib,np.r_[bed,np.zeros(fs//2)],fs=fs,flags=6,impact_mode=8)
            for level in (-12,-6):
                impact=z*10**(level/20)
                source=bed+impact
                assert np.max(abs(source))<1
                x=np.r_[source,np.zeros(fs//2)]
                variant={}
                for flag in (0,a.candidate):
                    os.environ['P1PP_V04']=str(flag)
                    render=P.render(lib,x,fs=fs,flags=6,impact_mode=8)
                    measured,_=score(render,ref[flag],source,impact,t,onset,duration,fs)
                    ident=track_identity(render['rows'],fs,onset,duration,desc['bed_frequency'])
                    flags=render['rows'][:,27].astype(np.int64)//65536
                    variant[flag]=dict(metrics=measured,ident=ident,
                                       armed=int(np.count_nonzero(flags&8)),
                                       stem=render['stem'],
                                       latency=int(render['latency']))
                baseline=variant[0];candidate=variant[a.candidate]
                assert baseline['latency']==candidate['latency']
                assert np.isfinite(candidate['stem']).all()
                paired={}
                for metric in ('early_tail_energy_per_input_db','early_tail_stationary_residual_per_input_db',
                               'early_tail_nonbed_per_input_db','late_tail_energy_per_input_db',
                               'late_tail_stationary_residual_per_input_db','generated_peak_per_input_peak_db'):
                    paired[metric]=dict(baseline=baseline['metrics'][metric],candidate=candidate['metrics'][metric],
                                        difference=candidate['metrics'][metric]-baseline['metrics'][metric])
                row=dict(name=name,kind=desc['kind'],level_db=level,bed_frequency=desc['bed_frequency'],
                         armed_hops=candidate['armed'],output_bit_identical=bool(np.array_equal(baseline['stem'],candidate['stem'])),
                         max_stem_difference=float(np.max(abs(baseline['stem'].astype(float)-candidate['stem'].astype(float)))),
                         stolen_hops_baseline=baseline['ident']['original_id_stolen_hops_over_5_percent'],
                         stolen_hops_candidate=candidate['ident']['original_id_stolen_hops_over_5_percent'],
                         bed_missing_hops_baseline=baseline['ident']['missing_confirmed_near_bed_hops'],
                         bed_missing_hops_candidate=candidate['ident']['missing_confirmed_near_bed_hops'],
                         metrics=paired)
                rows.append(row)
                print(name,level,'armed',row['armed_hops'],
                      'stolen',row['stolen_hops_baseline'],'to',row['stolen_hops_candidate'],
                      'missing',row['bed_missing_hops_baseline'],'to',row['bed_missing_hops_candidate'],
                      'early dB',round(paired['early_tail_energy_per_input_db']['difference'],5),flush=True)
    finally:
        if old is None:os.environ.pop('P1PP_V04',None)
        else:os.environ['P1PP_V04']=old
    changed=[r for r in rows if not r['output_bit_identical']]
    worse=sorted(rows,key=lambda z:z['metrics']['early_tail_energy_per_input_db']['difference'],reverse=True)
    summary=dict(schema='pvb.p1pp.r01.devcohort.v1',
                 seed=2026102609,candidate_flags=a.candidate,independent_waveforms=12,
                 repeated_levels_per_waveform=2,
                 total_settings=len(rows),changed_settings=len(changed),
                 armed_settings=sum(x['armed_hops']>0 for x in rows),
                 worst_early_tail_changes=[dict(name=x['name'],level_db=x['level_db'],
                                               delta_db=x['metrics']['early_tail_energy_per_input_db']['difference'])
                                           for x in worse[:5]],
                 note='Development set already seen before candidate; numbers do not establish holdout success',
                 device_validation=False,listening_validation=False,
                 source_library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),cases=rows)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('R01 development cohort measured',len(rows),'settings;',len(changed),'changed;',
          summary['armed_settings'],'armed',flush=True)

if __name__=='__main__':main()
