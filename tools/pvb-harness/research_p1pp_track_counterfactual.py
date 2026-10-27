#!/usr/bin/env python3
"""R01 counterfactuals from inspected fixtures, not a holdout.

Tests the negative case in which a stable bass note genuinely ends as a kick
or broadband transient starts. An identity-lock algorithm must not leave an
excessive synthetic bass tail in music where that note has in fact ended.
Also checks a travelling bass line UNDER a kick (distinct from gliss alone).
Scores are predeclared energy ratios, not perceptual or distortion ground truth.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import research_p1plus as P
from research_p1pp_recovery import new_fixtures
from research_p1pp_impacts import energy,db
from p1plus_paths import default_library

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    lib=P.api(a.library.resolve());fs=48000
    inspected={x[0]:x for x in new_fixtures(fs,seed=2026102609,count=12)}
    old=os.environ.get('P1PP_V04');rows=[]
    try:
        for name in ('new_kick_2','new_kick_3','new_broadband_7'):
            _,_,t,bed,z,onset,duration,desc=inspected[name]
            for bed_mode in ('continues','ends_at_kick','travelling'):
                if bed_mode=='ends_at_kick':
                    # Controlled 10 ms fade: avoid injecting a discontinuity
                    b=bed*np.clip((onset+.01-t)/.01,0,1)
                elif bed_mode=='travelling':
                    # 65->111 Hz over 3.8 s; no known stationary identity.
                    b=.018*np.minimum(1,t/.05)*np.cos(2*np.pi*(65*t+6*t*t)+desc['bed_phase'])
                else:b=bed
                for level in (-12,-6):
                    impact=z*10**(level/20)
                    assert np.max(abs(b+impact))<1
                    output={}
                    for v04 in (0,64):
                        os.environ['P1PP_V04']=str(v04)
                        base=P.render(lib,np.r_[b,np.zeros(fs//2)],fs=fs,flags=6,impact_mode=8)
                        event=P.render(lib,np.r_[b+impact,np.zeros(fs//2)],fs=fs,flags=6,impact_mode=8)
                        d=event['latency'];assert d==base['latency']
                        gen=event['stem'][d:d+len(t),0].astype(float)-base['stem'][d:d+len(t),0].astype(float)
                        early=(t>=onset+duration)&(t<onset+duration+.08)
                        late=(t>=onset+duration+.08)&(t<onset+duration+.5)
                        # Energy of newly generated response after event;
                        # if bed ends, none of this is the original continued bed.
                        output[v04]=(db(energy(gen[early]),energy(impact)),
                                     db(energy(gen[late]),energy(impact)))
                    row=dict(name=name,kind=desc['kind'],level_db=level,bed_mode=bed_mode,
                             early_baseline_db=output[0][0],early_candidate_db=output[64][0],
                             early_delta_db=output[64][0]-output[0][0],
                             late_baseline_db=output[0][1],late_candidate_db=output[64][1],
                             late_delta_db=output[64][1]-output[0][1])
                    rows.append(row)
                    print(name,bed_mode,level,'early delta',round(row['early_delta_db'],5),
                          'late delta',round(row['late_delta_db'],5),flush=True)
    finally:
        if old is None:os.environ.pop('P1PP_V04',None)
        else:os.environ['P1PP_V04']=old
    result=dict(schema='pvb.p1pp.r01.counterfactual.v1',
                independent_source_waveforms=3, levels_per_waveform=2,
                bed_conditions_per_waveform=3,
                already_inspected_seed=2026102609,
                note='Synthetic counterfactuals; do not call increases noise without separated ground truth',
                device_validation=False,listening_validation=False,
                library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                records=rows)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('R01 counterfactual metrics saved:',len(rows),flush=True)

if __name__=='__main__':main()
