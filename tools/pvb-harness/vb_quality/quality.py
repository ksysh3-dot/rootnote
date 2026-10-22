"""Reproducible 48 kHz research candidates; these are NOT shipped quality modes.

Reuse the build-14 Python reference with opt-in changes, explicit alignment and
stage outputs. No downloaded model, gain matching, or perceptual claim is hidden
in this module. Processing is file-based but each generator uses causal placement.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import sys

import numpy as np
from scipy.signal import lfilter, sosfilt, upfirdn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'vb51'))
import hpv51 as P

C, V = P.C, P.V
FS = 48000
BASE_LATENCY = 7052
LIMITER_LATENCY = 88


@dataclass(frozen=True)
class Candidate:
    name: str
    window: int = 384
    mask_ms: float = 0.0
    existing: bool = False
    percussion: bool = True
    phase_match: bool = True
    adaptive: bool = False
    continuous_phase: bool = False
    follow_partials: bool = False
    harmonic_rolloff_db_per_octave: float = 0.0

    @property
    def latency(self):
        # Preserve the base nominal alignment; a longer PV window adds N/2 delay.
        # This is not a newly measured acoustic group delay or end-to-end latency.
        return BASE_LATENCY + (self.window - 384) // 2 * V.DEC

    def metadata(self):
        return dict(**asdict(self), window_ms=1000*self.window/V.FSD,
                    nominal_layer_latency_frames=self.latency,
                    nominal_engine_latency_ms=1000*(self.latency+LIMITER_LATENCY)/FS,
                    fft_points=V.PV_NFFT, implemented_in_app=False)


CANDIDATES = {c.name: c for c in (
    Candidate('baseline'),
    Candidate('smooth128', mask_ms=20),
    Candidate('long256', window=768),
    Candidate('long512', window=1536),
    Candidate('smooth256', window=768, mask_ms=20),
    Candidate('smooth512', window=1536, mask_ms=20),
    Candidate('existing128', existing=True),
    Candidate('existing256', window=768, mask_ms=20, existing=True),
    Candidate('existing512', window=1536, mask_ms=20, existing=True),
    Candidate('no_percussion', percussion=False),
    Candidate('no_phase_match', phase_match=False),
    Candidate('multi512', window=1536, mask_ms=20, adaptive=True),
    Candidate('continuous128', continuous_phase=True),
    Candidate('continuous_smooth128', mask_ms=20, continuous_phase=True),
    Candidate('follow128', mask_ms=20, continuous_phase=True, follow_partials=True),
    Candidate('gentle128', harmonic_rolloff_db_per_octave=12.0),
)}


def layer(x, candidate='baseline', frame_trace=None):
    """Float64 mono layer, stage outputs, and analysis events at fixed 48 kHz.

    Inputs must include any desired tail flush. The reference's process-global
    options are restored; concurrent threads must use separate Python processes.
    """
    c = CANDIDATES[candidate] if isinstance(candidate, str) else candidate
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError('expected finite mono audio at 48 kHz')
    if c.window not in (384, 768, 1536) or c.mask_ms < 0:
        raise ValueError('unsupported analysis configuration')
    if c.adaptive:
        return multiresolution(x, c)
    old_lat, old_placement = P.LAT_HPV, V.PLACEMENT
    old_decimate, old_interpolate = V.decimate, V.interpolate
    stats = {}
    # Empty/short files still get well-defined output without changing reference code.
    n = len(x)
    padded = np.pad(x, (0, max(0, 2*FS-n)))
    try:
        P.LAT_HPV = 6812
        # FFT convolution can leave roundoff in an exactly silent source. The
        # relative-only source-peak classifier can promote it to a valid grid
        # while the bass filter is still ringing. A causal FIR, like the app's,
        # preserves exact silence and avoids file-length-dependent decisions.
        V.decimate = lambda a: upfirdn(V._AA, a, down=V.DEC)[:(len(a)+V.DEC-1)//V.DEC]
        V.interpolate = lambda a, n: upfirdn(V._AA*V.DEC, a, up=V.DEC)[:n]
        out, parts = P.layer_hpv51(
            padded, phase='pm' if c.phase_match else 'k',
            harm='ex' if c.existing else 'add', peaks='pk2', env='close',
            perc='gate' if c.percussion else 'none', grid='mask', causal=True,
            pv_n=c.window, render_lat=c.latency - 240,
            mask_smooth_s=c.mask_ms/1000, return_parts=True, stats=stats, frame_trace=frame_trace,
            continuous_phase=c.continuous_phase, follow_partials=c.follow_partials,
            harmonic_rolloff_db_per_octave=c.harmonic_rolloff_db_per_octave)
    finally:
        P.LAT_HPV, V.PLACEMENT = old_lat, old_placement
        V.decimate, V.interpolate = old_decimate, old_interpolate
    return out[:n], dict(pv=parts['pv'][:n], perc=parts['perc'][:n],
                         stats=stats, candidate=c.metadata())


def multiresolution(x, candidate):
    """Experimental glide-aware 128/512 ms blend, with a fixed long-path delay.

    A coherent, resolved single-note trajectory may use the short path. This is
    a heuristic under evaluation, not a source separator or a certified HQ mode.
    All controls are timestamped; stale/absent tracks revert to the long path.
    """
    trace = []
    short = CANDIDATES['smooth128']
    long = CANDIDATES['smooth512']
    _, a = layer(x, short, frame_trace=trace)
    _, b = layer(x, long)
    delta = long.latency-short.latency
    def delayed(v):
        return np.pad(v, (delta, 0))[:len(x)]
    target = np.zeros(len(x))
    history = []
    previous = None
    for centre, peaks in trace:
        strongest = max((p[1] for p in peaks), default=0)
        strong = [p for p in peaks if p[1] >= strongest*.25]
        valid = len(strong) == 1 and strong[0][2] <= P.PK_RES_DB
        if previous is not None and centre-previous != V.PV_H:
            history = []
        previous = centre
        if valid:
            f = strong[0][0]
            if history and abs(f-history[-1]) > .03*f:
                history = []
            history = (history+[f])[-6:]
        else:
            history = []
        use_short = False
        if len(history) == 6:
            times = np.arange(6)*V.PV_H/V.FSD
            slope, intercept = np.polyfit(times, history, 1)
            residual = float(np.sqrt(np.mean((np.asarray(history)-(intercept+slope*times))**2)))
            use_short = 4 < abs(slope) < 120 and residual < .15
        # Trace controls are pre-interpolation; the output FIR adds AA_DELAY.
        pos = centre*V.DEC + V.AA_DELAY + delta
        target[pos:min(pos+V.PV_H*V.DEC, len(x))] = float(use_short)
    # Causal control smoothing prevents a hard waveform switch; no extra delay.
    alpha = np.exp(-1/(.02*FS))
    weight = lfilter([1-alpha], [1, -alpha], target)
    pv = weight*delayed(a['pv']) + (1-weight)*b['pv']
    # Preserve the short transient path at the same nominal time. It is already
    # energy-gated and polyphony-suppressed; it still needs listening validation.
    perc = delayed(a['perc'])
    stats = dict(b['stats'], short_path_mean_weight=float(weight.mean()) if len(weight) else 0.0,
                 short_path_peak_weight=float(weight.max()) if len(weight) else 0.0)
    return pv+perc, dict(pv=pv, perc=perc, stats=stats, candidate=candidate.metadata())


def mix(x, generated, candidate, level_db):
    """EQ -> aligned dry + layer -> output gain -> product limiter -> PCM16.

    The limiter delay is compensated for file analysis, as in vb51.render().
    Nominal engine latency is still reported separately. No input normalization.
    """
    c = CANDIDATES[candidate] if isinstance(candidate, str) else candidate
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = np.repeat(x[:, None], 2, axis=1)
    if x.ndim != 2 or x.shape[1] != 2 or len(x) != len(generated):
        raise ValueError('expected stereo input and same-length mono layer')
    if not np.isfinite(x).all() or not np.isfinite(generated).all() or not np.isfinite(level_db):
        raise ValueError('nonfinite audio or gain')
    dry = sosfilt(C.eq_sos(FS, 'eq'), x, axis=0)
    delay = min(c.latency, len(x))
    dry = np.pad(dry, ((c.latency, 0), (0, 0)))[:len(x)] if delay else dry
    pre = (dry + np.asarray(generated)[:, None]*10**(level_db/20))*10**(C.OUT_DB/20)
    post, gain = C.tp_limit(pre, return_gain=True)
    pcm = np.clip(np.rint(post*32768), -32768, 32767).astype(np.int16)
    return dict(dry=dry*10**(C.OUT_DB/20), pre_limiter=pre,
                post_limiter=post, limiter_gain=gain, pcm16=pcm)
