#!/usr/bin/env python3
"""P1+ measurement controls and production-path regression, not an ear proxy."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import numpy as np
import research_p1plus as P
import test_engine as T


def level_delta(a,b):
    return float(20*np.log10(max(b,1e-30)/max(a,1e-30)))


def compare(a,b):
    rows=[]
    for name,x in a['cases'].items():
        y=b['cases'][name]
        row=dict(name=name,latency_equal=x['latency_frames']==y['latency_frames'],
                 output_identical=x['output_sha256']==y['output_sha256'])
        if x['support']:
            u,v=x['support'],y['support']
            row.update(residual_change_db=v['residual_db']-u['residual_db'],
                       wanted_carrier_change_db=level_delta(u['carrier_rms'],v['carrier_rms']),
                       absolute_residual_change_db=level_delta(u['residual_rms'],v['residual_rms']),
                       total_stem_change_db=level_delta(u['total_rms'],v['total_rms']))
            row['wanted_level_preserved']=abs(row['wanted_carrier_change_db'])<=.3
            row['unwanted_reduced_3db']=row['residual_change_db']<=-3
            row['no_residual_regression']=row['residual_change_db']<=1
        rows.append(row)
    return rows


def measurement_controls():
    fs=48000;t=np.arange(fs*5)/fs
    clean=.1*(1+.5*np.sin(2*np.pi*7*t))*np.cos(2*np.pi*165*t)
    def measure(x,f=(55.,),r=7.):
        return P.spectral_support(np.column_stack((x,x)),fs,f,r)
    good=measure(clean);bad=measure(clean+.005*np.sin(2*np.pi*203*t))
    quiet=measure((clean+.005*np.sin(2*np.pi*203*t))*.25)
    beating=measure(.1*np.cos(2*np.pi*165*t)+.1*np.cos(2*np.pi*174*t),(55.,58.),0.)
    assert good['residual_db'] < -120 and beating['residual_db'] < -120
    assert bad['residual_db']>-30
    assert abs(quiet['residual_db']-bad['residual_db'])<1e-9
    assert abs(level_delta(bad['carrier_rms'],quiet['carrier_rms']))>.3
    return dict(genuine_am_residual_db=good['residual_db'],
                genuine_beating_residual_db=beating['residual_db'],
                injected_203hz_residual_db=bad['residual_db'],
                gain_only_cannot_improve_normalized_score=True,
                gain_only_fails_level_preservation=True,
                no_change_cannot_pass_3db_improvement=True)


def engineering(lib,old):
    rows=[]
    for fs in (44100,48000):
        t=np.arange(fs*3)/fs
        x=.12*np.sin(2*np.pi*55*t+.2)+.0012*(1+.8*np.sin(2*np.pi*2*t))*np.sin(2*np.pi*165*t+1.7)
        a=P.render(lib,x,fs,2)
        b=P.render(lib,x,fs,2,block=1379)
        off=P.render(lib,x,fs,0)
        ref=P.render(old,x,fs,0)
        assert np.array_equal(off['output'],ref['output'])
        assert np.array_equal(off['stem'],ref['stem'])
        assert not np.array_equal(a['stem'],off['stem']), 'candidate not actually reached'
        assert np.array_equal(a['stem'],b['stem'])
        assert np.array_equal(a['stages'],b['stages'])
        chunk_error=float(np.max(abs(a['output']-b['output'])))
        assert chunk_error<1e-20
        assert a['latency']==off['latency']==(7140 if fs==48000 else 6561)
        observed_off=P.render(lib,x,fs,2,capture=False)
        assert np.array_equal(a['output'],observed_off['output'])
        future=x.copy();future[int(fs*1.7):]*=-1
        changed=P.render(lib,future,fs,2)
        assert np.array_equal(a['output'][:int(fs*1.7)],changed['output'][:int(fs*1.7)])
        # Actual analyzer observations and track lifetime are identical. Only
        # the phase-offset correction and its waveform consequence may differ.
        assert np.array_equal(a['rows'][:,28:].reshape(-1,12,56)[:,:,:14],
                              off['rows'][:,28:].reshape(-1,12,56)[:,:,:14])
        hs=a['rows'][:,28:].reshape(-1,12,56)[:,:,14:].reshape(-1,12,7,6)
        assert np.max(abs(hs[:,:,:,3]))<=.120001
        for algo in (7,8,9,10):
            no=P.render(lib,x[:fs],fs,0,algo=algo)
            yes=P.render(lib,x[:fs],fs,2,algo=algo)
            assert np.array_equal(no['output'],yes['output']),(fs,algo)
        e=T.Engine(lib,fs,vb_on=1,vb_algo=6,vb_level_db=6,out_db=-18,ramp_ms=0)
        try:
            assert lib.pvb_set_p1plus_research(e.h,2)==1
            assert lib.pvb_set_p1plus_research(e.h,16)==0
            e.process(T.stereo(x[:fs]))
            lib.pvb_reset(e.h)
            tail=e.process(np.zeros((fs,2),np.float32))
            assert np.max(abs(tail))<1e-7
        finally:e.close()
        rows.append(dict(fs=fs,default_bit_exact=True,flag_exercised=True,
                         observation_and_track_fields_bit_exact=True,
                         other_alpha_profiles_bit_exact=True,capture_bit_exact=True,
                         stem_and_stage_chunk_bit_exact=True,chunk_max_error=chunk_error,
                         prefix_unchanged=True,reset_passed=True,latency=a['latency']))
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--lib',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--results',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--require-promotion',action='store_true')
    a=p.parse_args();lib=P.api(a.lib.resolve());old=P.api(a.baseline.resolve())
    def read(name):return json.loads((a.results/name).read_text(encoding='utf-8'))
    comparisons={
        'residual_history':compare(read('baseline.json'),read('candidate-1.json')),
        'rejected_debounce':compare(read('baseline.json'),read('phase-v2.json')),
        'phase_preservation_development':compare(read('baseline.json'),read('phase-v3.json')),
    }
    for fs in (44100,48000):
        comparisons[f'phase_preservation_heldout_{fs}']=compare(
            read(f'heldout-baseline-{fs}.json'),read(f'heldout-candidate-v3-{fs}.json'))
    held=[r for fs in (44100,48000) for r in comparisons[f'phase_preservation_heldout_{fs}']]
    development=comparisons['phase_preservation_development']
    targets=[r for r in development if r['name'].startswith('anchor_')]+held
    assessed=[r for r in development+held if 'no_residual_regression' in r]
    gates=dict(target_component_reduction=all(r['unwanted_reduced_3db'] for r in targets),
               wanted_level_preservation=all(r['wanted_level_preserved'] for r in assessed),
               no_control_regression=all(r['no_residual_regression'] for r in assessed),
               latency_preservation=all(r['latency_equal'] for r in development+held))
    reasons=[k for k,v in gates.items() if not v]
    results=dict(schema='pvb.p1plus.validation.v1',measurement=measurement_controls(),
                 engineering=engineering(lib,old),comparisons=comparisons,
                 implementation_checks='pass',listening_validated=False,
                 device_validated=False,real_music_validated=False,
                 synthetic_screen='fail' if reasons else 'pass',gates=gates,
                 default_promotion='not_eligible' if reasons else 'requires_scope_review',
                 promotion_reasons=reasons,
                 candidate_sha256=hashlib.sha256(a.lib.read_bytes()).hexdigest())
    # Engineering-test success and a candidate's adoption decision are distinct.
    # New candidates may pass the frozen margins; this test never requires failure.
    a.report.write_text(json.dumps(results,indent=2,allow_nan=False),encoding='utf-8')
    print('PASS: measurement controls, actual-engine dispatch, default/other-profile invariance, chunk, prefix, reset')
    print('Synthetic screen:',results['synthetic_screen'],'failed gates:',reasons)
    if a.require_promotion and reasons:raise SystemExit(2)


if __name__=='__main__':main()
