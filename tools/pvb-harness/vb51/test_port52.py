"""hpv52m port gates: frozen reference, both rates, custom EQ phase, streaming, limiting and switching."""
import json
import pathlib
import sys
import time
import numpy as np
from scipy.signal import resample_poly, sosfilt, sosfreqz

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import test_engine as T
import hpv_ref as R
sys.path.insert(0, str(HERE))
import hpv51 as P

P.LAT_HPV = 6812
OPTS = dict(env='close', perc='gate', peaks='pk2', phase='pm', grid='mask', causal=True)


def reference(x, fs, eq=None, rolloff_db=0):
    dec, inter, phase = P.V.decimate, P.V.interpolate, P.path_phase
    try:
        P.V.decimate = lambda a: R.decimate(a, fs)
        P.V.interpolate = lambda a, n: R.interpolate(a, fs, n)
        if eq is not None:
            actual, baseline = T.ref_sos(fs, eq), T.ref_sos(48000, T.V11)
            def changed_phase(f):
                _, a = sosfreqz(actual, worN=np.atleast_1d(f), fs=fs)
                _, b = sosfreqz(baseline, worN=np.atleast_1d(f), fs=48000)
                delta = np.angle(a / b) + 2*np.pi*f*(7052/48000 - R.latency_frames(fs)/fs)
                return phase(f) + (float(delta[0]) if np.ndim(f) == 0 else delta)
            P.path_phase = changed_phase
        return P.layer_hpv51(x, harmonic_rolloff_db_per_octave=rolloff_db, **OPTS)[0]
    finally:
        P.V.decimate, P.V.interpolate, P.path_phase = dec, inter, phase


def run(lib):
    ref = np.load(HERE/'port/ref_hpv52m_10s.npz')
    x = ref['x']
    y, r, lat, dt = T.vb_layer(lib, 2, 48000, x, x)
    err = T.rel_db(y, ref['y'])
    T.check('hpv52m: frozen 10 s NPZ', err < -120 and np.array_equal(y, r) and lat == 7052,
            rel_db=err, max_abs=float(np.max(abs(y-ref['y']))), latency=lat, cpu_ms_per_s=100*dt)
    # Different rate, same strictly causal 3 kHz reference with rational converters.
    x44 = resample_poly(x, 147, 160)
    y44, _, lat44, _ = T.vb_layer(lib, 2, 44100, x44, x44)
    e44 = T.rel_db(y44, reference(x44, 44100))
    T.check('hpv52m: Python at 44.1 kHz', e44 < -120 and lat44 == R.latency_frames(44100),
            rel_db=e44, latency=lat44)

    for fs in (44100, 48000):
        t = np.arange(4*fs)/fs
        # Existing upper partials exercise phase matching. Nondefault EQ must affect the generated layer phase.
        mono = sum(.07/k*np.sin(2*np.pi*55*k*t+.4*k) for k in range(1, 9))
        audio = T.stereo(mono)
        eq = dict(T.V11, hp_hz=160., low_db=4.2, low_q=1.06)
        eq = {k: float(np.float32(v)) for k, v in eq.items()}
        e = T.Engine(lib, fs, vb_on=1, vb_algo=2, vb_level_db=3, ramp_ms=0, **eq)
        lib.pvb_reset(e.h)
        got = e.process(audio, blocks=[1, 17, 256, 1023])
        m = e.meters(); latency = int(m[T.M['LATENCY']]); e.close()
        d = R.latency_frames(fs); lim = latency-d
        a = audio.astype(float); delayed = np.r_[np.zeros((d, 2)), a[:-d]]
        layer = reference(a.mean(1), fs, eq)
        want = (sosfilt(T.ref_sos(fs, eq), delayed, axis=0) + 10**(3/20)*layer[:, None])*10**(-5/20)
        err = T.rel_db(got[lim+fs:], want[fs:-lim])
        T.check(f'hpv52m: full engine, custom EQ phase @ {fs}', err < -100 and m[T.M['VB']] == 3,
                rel_db=err, latency_frames=latency)

        e = T.Engine(lib, fs, vb_on=1, vb_algo=2, vb_level_db=9, flat=1)
        lib.pvb_reset(e.h)
        hot = audio * 20
        y = e.process(hot)
        tp = T.true_peak_db(y)
        T.check(f'hpv52m: +9 dB true peak @ {fs}', np.isfinite(y).all() and tp <= -.95, dbtp=tp)
        # Wet/flat keeps delay; final gate covers both. Algorithm changes use the same state machine as hpv.
        before=e.latency(); e.set(enabled=0); flat=e.process(audio)
        T.check(f'hpv52m: matched bypass keeps delay @ {fs}', e.latency()==before and np.isfinite(flat).all())
        e.set(gate_db=-90); muted=e.process(audio[:fs])
        T.check(f'hpv52m: bypass obeys mute @ {fs}', np.max(abs(muted[fs//2:])) == 0)
        e.close()
        # Continuous 1 kHz tone, no synthesised bass: isolate switch clicks and equal-delay transitions.
        tone=T.stereo(.08*np.sin(2*np.pi*1000*np.arange(fs)/fs))
        e=T.Engine(lib,fs,vb_on=1,vb_algo=0,ramp_ms=0)
        e.process(tone)
        outs=[]
        for algo in (2,0,2,1,2):
            e.set(vb_algo=algo); outs.append(e.process(tone))
        jump=float(np.max(abs(np.diff(np.concatenate(outs)[:,0]))))
        T.check(f'hpv52m: switch algorithms @ {fs}', jump < .02 and e.meters()[T.M['VB']]==3, largest_step=jump)
        e.close()
    # Audio-thread runtime includes analysis, EQ, both limiters and matching. It is a host measurement, not phone CPU.
    e=T.Engine(lib,48000,vb_on=1,vb_algo=2,flat=1)
    a=T.stereo(x); t0=time.perf_counter()
    for _ in range(3): e.process(a)
    elapsed=time.perf_counter()-t0; e.close()
    T.check('hpv52m: host CPU, full engine + match', elapsed<6, ms_per_audio_second=1000*elapsed/30)


if __name__ == '__main__':
    run(T.load_lib(str(HERE.parent/'build/libpvbcapi.so')))
    if len(sys.argv)>1:
        pathlib.Path(sys.argv[1]).write_text(json.dumps(T.RESULTS, ensure_ascii=False, indent=2)+'\n')
    raise SystemExit(any(not r['ok'] for r in T.RESULTS))
