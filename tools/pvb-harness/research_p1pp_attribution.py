#!/usr/bin/env python3
"""First P1++ diagnostic: isolate an existing P1+ failure, with no DSP changes.

This reuses a known development condition. It is causal investigation, not a new
independent validation set or a P1++ quality claim. Each note keeps its duration,
schedule and amplitude trajectory when frequency is swept.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import check_p1hq_primary_envelopes as E
from p1plus_paths import default_library, P1PLUS_FLAGS, P1PLUS_BASELINE_ID


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,default=default_library())
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();lib=E.P.api(a.library.resolve());fs=48000
    name,mixed,mod_env,desc=list(E.fixtures(fs))[3]
    t=np.arange(len(mixed))/fs;f=desc['frequency'];rate=desc['rate']
    plain_env=mod_env/(1+.35*np.sin(2*np.pi*rate*t))
    mod_note=mod_env*np.cos(2*np.pi*f*t+.3)
    noise=mixed-mod_note
    assert np.max(abs(mixed-(mod_note+noise)))<1e-15
    rows=[]
    def run(label,source,env,freq):
        k=E.primary(freq)
        r=E.P.render(lib,np.r_[source,np.zeros(fs)],fs,P1PLUS_FLAGS)
        y=r['stem'][r['latency']:r['latency']+len(source),0]
        measured=E.envelope(y,fs,k*freq,.35*freq)[900:12000]
        result=dict(name=label,frequency=freq,harmonic=k,latency=r['latency'],
                    extracted_envelope_rms=float(np.sqrt(np.mean(measured**2))))
        if env is not None:
            ideal=env*np.cos(2*np.pi*k*freq*t)
            ref=E.envelope(ideal,fs,k*freq,.35*freq)[900:12000]
            result.update(E.score(measured,ref))
            result['relative_error_rms_percent']=100*10**(result['shape_error_db']/20)
        rows.append(result);print(label,json.dumps(result),flush=True)
    run('original_mixture',mixed,mod_env,f)
    run('note_with_am_only',mod_note,mod_env,f)
    run('note_without_am',plain_env*np.cos(2*np.pi*f*t+.3),plain_env,f)
    run('note_without_am_plus_noise',plain_env*np.cos(2*np.pi*f*t+.3)+noise,plain_env,f)
    run('noise_only',noise,None,f)
    for freq in (41.,55.,65.,81.,106.):
        run(f'same_plain_envelope_{freq:g}hz',plain_env*np.cos(2*np.pi*freq*t+.3),plain_env,freq)
    result=dict(schema='pvb.p1pp.attribution.v1',baseline_id=P1PLUS_BASELINE_ID,
                library_sha256=hashlib.sha256(a.library.read_bytes()).hexdigest(),
                flags=P1PLUS_FLAGS,fixture=name,fixture_seed=2026102606,
                input=desc,dsp_changed=False,independent_validation=False,
                definition='Same declared-latency/main-harmonic envelope metric as P1+; one fitted constant scale.',
                caveat='Frequency sweep retains the same note envelope but its input-defined harmonic order and extraction bandwidth can change. It does not isolate an internal DSP stage.',
                cases=rows)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
