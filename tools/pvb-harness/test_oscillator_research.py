#!/usr/bin/env python3
"""P2-O implementation contracts, not a perceptual quality score."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path

import numpy as np
import test_engine as T
import test_modulation_research as P
from vb_quality.stage_capture import INDEX

FLAGS={'grain_c1':0,'oscillator_free':2048,'oscillator_bounded10':6144}
DP=C.POINTER(C.c_double)


def api(path):
    lib=P.api(path)
    lib.pvb_oscillator_probe_create.restype=C.c_void_p
    lib.pvb_oscillator_probe_destroy.argtypes=[C.c_void_p]
    lib.pvb_oscillator_probe_reset.argtypes=[C.c_void_p]
    lib.pvb_oscillator_probe_hop.argtypes=[C.c_void_p,C.c_double,DP,DP,C.c_double,C.c_int,DP]
    return lib


def direct(lib):
    """Independent sample-time oracle: one chirped partial with ramped amplitude."""
    h=lib.pvb_oscillator_probe_create();worst=0.;nominal_error=0.;phase=.3
    prev_f=55.;prev_a=0.;previous_target=0.;raw=[]
    try:
        for hop in range(50):
            f=55.+.3*hop;a=.12 if hop<40 else 0.
            amplitude=np.zeros(7);amplitude[1]=a
            phases=np.zeros(7);phases[1]=phase+2*np.pi*3*f*16/3000 if hop==0 else (-1)**hop*2.1
            out=np.zeros(32)
            assert lib.pvb_oscillator_probe_hop(h,f,amplitude.ctypes.data_as(DP),phases.ctypes.data_as(DP),a,0,out.ctypes.data_as(DP))==16
            t=np.arange(16)/3000;duration=16/3000
            expected=(prev_a+(a-prev_a)*t/duration)*np.cos(phase+2*np.pi*3*(prev_f*t+.5*(f-prev_f)*t*t/duration))
            expected_nominal=previous_target+(a-previous_target)*t/duration
            worst=max(worst,float(np.max(abs(expected-out[:16]))))
            nominal_error=max(nominal_error,float(np.max(abs(expected_nominal-out[16:]))))
            raw.append(out.copy());phase+=2*np.pi*3*(prev_f+f)/2*duration
            prev_f=f;prev_a=a;previous_target=a
        assert worst<2e-12 and nominal_error<1e-15,(worst,nominal_error)
        assert np.max(abs(raw[-1]))==0
        # A reset must re-establish the same birth ramp, not retain old phase.
        lib.pvb_oscillator_probe_reset(h)
        amplitude=np.zeros(7);amplitude[1]=.12;phases=np.zeros(7);phases[1]=.3+2*np.pi*3*55*16/3000
        out=np.zeros(32)
        lib.pvb_oscillator_probe_hop(h,55,amplitude.ctypes.data_as(DP),phases.ctypes.data_as(DP),.12,0,out.ctypes.data_as(DP))
        assert np.array_equal(out,raw[0])
        # Fixed frequency: a large target phase jump only adds the declared
        # 10cent correction. Its exact bound is independently synthesized here.
        lib.pvb_oscillator_probe_reset(h);phase=.3;bound=2*np.pi*3*55*(2**(10/1200)-1)*16/3000
        for hop in range(40):
            phases[1]=phase+2*np.pi*3*55*16/3000+(0 if hop==0 else 1.)
            out=np.zeros(32)
            lib.pvb_oscillator_probe_hop(h,55,amplitude.ctypes.data_as(DP),phases.ctypes.data_as(DP),.12,1,out.ctypes.data_as(DP))
            u=np.arange(16)/16
            correction=0 if hop==0 else bound
            expected=(.12*u if hop==0 else .12)*np.cos(phase+2*np.pi*3*55*np.arange(16)/3000+correction*u)
            assert np.max(abs(expected-out[:16]))<2e-12
            phase+=2*np.pi*3*55*16/3000+correction
    finally:
        lib.pvb_oscillator_probe_destroy(h)
    return dict(sample_oracle_max_abs_error=worst,nominal_ramp_max_abs_error=nominal_error,
                chirp_amplitude_birth_death_reset='passed',bounded_phase_step='passed',
                note='Known declared synthesis only. No analysis/audio quality verdict.')


def integration(lib,baseline=None):
    results=[];regressions=[]
    for fs in (44100,48000):
        t=np.arange(int(fs*3.2))/fs
        x=(.12*(1+.6*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*(55*t+3*t*t))+.04*np.cos(2*np.pi*110*t+.3))*(t<1.4)
        reference=P.render(lib,x,0,True,fs=fs,stage_flags=0)
        for name in ('oscillator_free','oscillator_bounded10'):
            flags=FLAGS[name]
            a=P.render(lib,x,0,True,fs=fs,stage_flags=flags)
            b=P.render(lib,x,0,True,fs=fs,stage_flags=flags,block=1379)
            # Existing engine dry-tail rounding can differ around1e-25 with
            # callback partitioning; require exact synthesis/stages,1e-20 audio.
            chunk_error=float(np.max(abs(a['output']-b['output'])))
            assert chunk_error<1e-20 and np.array_equal(a['stem'],b['stem'])
            assert np.array_equal(a['rows'][:,1:],b['rows'][:,1:])
            assert np.array_equal(a['stages'],b['stages'])
            prefix=x.copy();prefix[int(.85*fs):]*=-1
            c=P.render(lib,prefix,0,True,fs=fs,stage_flags=flags)
            assert np.array_equal(a['output'][:int(.85*fs)],c['output'][:int(.85*fs)])
            assert a['latency']==reference['latency'] and T.true_peak_db(a['output'])<-1
            assert np.max(abs(a['stem'][int(2.8*fs):]))<1e-7
            # The renderer must not alter measured observations/track matching.
            tracks=a['rows'][:,28:].reshape(-1,12,56)
            old=reference['rows'][:,28:].reshape(-1,12,56)
            assert np.array_equal(tracks[:,:,:14],old[:,:,:14])
            i=INDEX['raw_grain'];delta=float(np.max(abs(a['stages'][:,i]-reference['stages'][:,i])))
            assert delta>1e-7,'production oscillator dispatch not reached'
            results.append(dict(sample_rate=fs,candidate=name,chunk_prefix_termination_observations='passed',
                latency_frames=a['latency'],raw_difference_from_grain_max=delta,
                output_chunk_max_abs_error=chunk_error,stem_and_stage_chunk_bit_exact=True,
                generated_rms_dbfs=float(T.db(np.sqrt(np.mean(a['stem']**2))))))
        if baseline:
            for algo in range(6):
                a=P.render(lib,x[:fs],fs=fs,algo=algo)
                b=P.render(baseline,x[:fs],fs=fs,algo=algo)
                assert np.array_equal(a['output'],b['output']) and np.array_equal(a['stem'],b['stem'])
                regressions.append(dict(sample_rate=fs,algorithm=algo,default_bit_exact=True))
    # Correction-only is not a valid synthesizer choice.
    e=T.Engine(lib,48000)
    try:assert not lib.pvb_stage_attach(e.h,4096,10)
    finally:e.close()
    return dict(candidates=results,defaults=regressions,invalid_flag_rejected=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--lib',required=True);p.add_argument('--baseline');p.add_argument('--report',required=True);a=p.parse_args()
    lib=api(a.lib)
    report=dict(schema='pvb.phase2.oscillator.v1',library_sha256=hashlib.sha256(Path(a.lib).read_bytes()).hexdigest(),
        direct=direct(lib),integration=integration(lib,P.api(a.baseline) if a.baseline else None),
        listening_validated=False,app_adopted=False)
    Path(a.report).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('P2-O implementation checks passed; no listening quality verdict.')


if __name__=='__main__':main()
