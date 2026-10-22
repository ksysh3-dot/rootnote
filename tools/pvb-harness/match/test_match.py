"""Integration checks of actual engine output, including stereo cancellation and bypass transitions."""
import pathlib
import sys
import numpy as np
from scipy.signal import sosfilt

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import test_engine as T
from fit_weighting import proxy_db, validate


def run(lib):
    rng = np.random.default_rng(62)
    for row in validate():
        T.check('match: weighting fit '+str(row['fs']), row['rms_db'] < .7 and row['max_db'] < 2, **row)
    for fs in (44100, 48000):
        n = 2 * fs
        f = np.fft.rfftfreq(n, 1/fs)
        p = 1 / np.sqrt(np.maximum(f, 30))
        x = np.fft.irfft(np.fft.rfft(rng.normal(size=(n, 2)), axis=0) * p[:, None], n=n, axis=0)
        x *= .06 / np.max(abs(x))
        for mode in ('stereo', 'antiphase'):
            a = x.copy() if mode == 'stereo' else np.stack([x[:, 0], -x[:, 0]], axis=1)
            e = T.Engine(lib, fs, flat=1, low_db=4.2, low_q=1.06, ramp_ms=0)
            for _ in range(25): wet = e.process(a)
            gain = e.match_db()
            e.set(enabled=0)
            for _ in range(3): flat = e.process(a)
            # Exclude wrap/transition edges and compare by the independent stored speaker weighting.
            delta = proxy_db(flat[fs//2:-fs//10], fs) - proxy_db(wet[fs//2:-fs//10], fs)
            T.check(f'match: custom EQ pink {fs} {mode}', abs(delta) < .5 and e.match_measured(),
                    delta_db=delta, gain_db=gain)
            e.set(match_hold=1, out_db=-20)
            before=e.match_db(); e.process(a)
            T.check(f'match: A/B hold {fs} {mode}', abs(e.match_db()-before)<1e-6)
            e.close()

        # Reproducible musical texture (pitched bass, decaying chord and noise percussion); not an album excerpt.
        t=np.arange(3*fs)/fs
        env=np.exp(-4*(t % .5))
        bass=.05*np.sin(2*np.pi*55*t)+.025*np.sin(2*np.pi*110*t)
        chord=env*sum(.02*np.sin(2*np.pi*f*t) for f in (220,277.18,329.63,440))
        perc=.008*rng.normal(size=len(t))*np.exp(-30*(t % .25))
        music=np.stack([bass+chord+perc,bass+.8*chord-perc],1)
        e=T.Engine(lib,fs,flat=1,low_db=4.2,low_q=1.06)
        for _ in range(20): wet=e.process(music)
        e.set(enabled=0)
        for _ in range(3): flat=e.process(music)
        delta=proxy_db(flat[fs//2:-fs//10],fs)-proxy_db(wet[fs//2:-fs//10],fs)
        T.check(f'match: synthetic music {fs}', abs(delta)<.5, delta_db=delta)
        e.close()

    fs=48000; t=np.arange(4*fs)/fs
    # No high-pass or EQ in matched bypass: a 30 Hz sine retains its full flat gain.
    e=T.Engine(lib, fs, enabled=0, flat=1, match_hold=1, match_seed_db=-6, ramp_ms=0)
    x=T.stereo(.1*np.sin(2*np.pi*30*t)); y=e.process(x)
    ratio=20*np.log10(np.sqrt(np.mean(y[-fs:]**2)/np.mean(x[-fs:]**2)))
    T.check('match: flat bypass retains sub-bass', abs(ratio+6)<.02, gain_db=ratio)
    e.set(gate_db=-90); y=e.process(x[:fs])
    T.check('match: final mute still covers flat bypass', np.max(abs(y[-fs//2:]))==0)
    e.close()
    # Test a warm limiter and a continuous sine across repeated wet/flat transitions.
    e=T.Engine(lib,fs,flat=1,match_hold=1,match_seed_db=-6,ramp_ms=0)
    a=T.stereo(.1*np.sin(2*np.pi*1000*np.arange(fs)/fs)); e.process(a)
    outputs=[]
    for i in range(6):
        e.set(enabled=i%2); outputs.append(e.process(a))
    y=np.concatenate(outputs)[:,0]
    jump=float(np.max(abs(np.diff(y))))
    T.check('match: repeated transition has no discontinuity', jump<.015, largest_step=jump)
    e.close()
    # A sufficiently low output setting must not be limited by the old -15 dB match clamp.
    e=T.Engine(lib,fs,flat=1,out_db=-20)
    for _ in range(60): e.process(a)
    T.check('match: quiet output range', e.match_db() < -19, gain_db=e.match_db())
    before=e.match_db(); e.process(np.zeros_like(a)); after=e.match_db()
    T.check('match: silence preserves gain', abs(after-before)<.03, drift_db=after-before)
    e.close()


if __name__=='__main__':
    run(T.load_lib(str(HERE/'build/libpvbcapi.so')))
    raise SystemExit(any(not r['ok'] for r in T.RESULTS))
