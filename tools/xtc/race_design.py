#!/usr/bin/env python3
"""RACE-style crosstalk cancellation (XTC) for phone speakers: design numbers and a model check.

The canceller is the one in tools/xtc/race_xtc.eel. As in RACE, the feedback path is band-limited (B = 2nd-order
high-pass at f_lo times 2nd-order low-pass at f_hi), so nothing outside the band is touched and no crossover is summed:
    full RACE:   yL = xL - g * B[yR(t - tau)],   yR = xR - g * B[yL(t - tau)]
                 -> M = 1 / (1 + g B e^-jw tau),  S = 1 / (1 - g B e^-jw tau)
    centre safe: M passes unchanged, only S = 1 / (1 - g B e^-jw tau)  (less separation, no centre coloration)

No head measurement is needed: tau comes from a standard spherical head (Woodworth's formula) and the phone geometry
(speaker spacing, listening distance). Head presets follow hat size (head circumference ~54 / 57 / 60 cm, radius scaled
from the usual 8.75 cm standard head at 57 cm); they move tau by only about +-5 %, much less than the distance does. The "ear model" used to estimate separation adds a
one-pole head-shadow filter (Brown & Duda 1998 form; the alpha(theta) constants are the widely reproduced ones and were
not checked against the paper). All separation numbers here are model estimates, not measurements.

    python3 tools/xtc/race_design.py              # table of presets
    python3 tools/xtc/race_design.py --plot out.png
"""
import argparse
import math

import numpy as np

C = 343.0
HEADS = {"S": 0.0875 * 54 / 57, "M": 0.0875, "L": 0.0875 * 60 / 57}   # radius (m) by hat size 54 / 57 / 60 cm
STRENGTHS = {"약": -6.0, "중": -4.5, "강": -3.0}   # g in dB


def woodworth_itd(a, theta):
    """Interaural time difference (s) of a far source at azimuth theta (rad) for a sphere of radius a."""
    return a / C * (theta + math.sin(theta))


def geometry(spacing, distance, a):
    theta = math.atan2(spacing / 2, distance)        # each speaker's angle from the front
    return theta, woodworth_itd(a, theta)


def biquad_resp(kind, f0, fs, w):
    """RBJ 2nd-order Butterworth (Q = 1/sqrt 2) response at angular frequencies w (rad/sample)."""
    w0 = 2 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2 / math.sqrt(2))
    cw = math.cos(w0)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
    else:
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    a = [1 + alpha, -2 * cw, 1 - alpha]
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def head_shadow(f, a, theta_ear):
    """Brown-Duda one-pole/one-zero head shadow for incidence angle theta_ear (rad, 0 = straight at the ear)."""
    w = 2 * np.pi * f
    w0 = C / a
    alpha_min, theta_min = 0.1, math.radians(150)
    alpha = (1 + alpha_min / 2) + (1 - alpha_min / 2) * math.cos(theta_ear / theta_min * math.pi)
    return (1 + 1j * alpha * w / (2 * w0)) / (1 + 1j * w / (2 * w0))


MODE = "full"   # "full" (RACE) or "centre" (side only); set from the command line


def canceller(f, fs, g, tau, f_lo, f_hi):
    """Mid and side responses of the RACE canceller with a band-limited feedback path."""
    w = 2 * np.pi * f / fs
    loop = g * biquad_resp("hp", f_lo, fs, w) * biquad_resp("lp", f_hi, fs, w) * np.exp(-1j * 2 * np.pi * f * tau)
    m = np.ones_like(loop) if MODE == "centre" else 1 / (1 + loop)
    s = 1 / (1 - loop)
    return m, s


def separation(f, fs, g, tau_design, f_lo, f_hi, tau_true, a_true, theta_true):
    """Ear separation |ipsilateral| / |contralateral| (dB) for a left-only input, canceller on and off."""
    m, s = canceller(f, fs, g, tau_design, f_lo, f_hi)
    x_l, x_r = (m + s) / 2, (m - s) / 2                      # speaker outputs for input (1, 0)
    near = head_shadow(f, a_true, math.pi / 2 - theta_true)  # ear on the speaker's side
    far = head_shadow(f, a_true, math.pi / 2 + theta_true)
    cross = far / near * np.exp(-1j * 2 * np.pi * f * tau_true)
    ear_l = x_l + cross * x_r
    ear_r = cross * x_l + x_r
    on = 20 * np.log10(np.abs(ear_l) / np.abs(ear_r))
    off = 20 * np.log10(1 / np.abs(cross))
    return on, off


def band_mean(f, v, lo, hi):
    sel = (f >= lo) & (f <= hi)
    return float(np.mean(v[sel]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--spacing", type=float, default=0.155, help="speaker port spacing in landscape (m)")
    p.add_argument("--fs", type=float, default=48000)
    p.add_argument("--f-lo", type=float, default=700)
    p.add_argument("--f-hi", type=float, default=5000)
    p.add_argument("--mode", choices=["full", "centre"], default="full")
    p.add_argument("--plot", help="write a PNG of the mid/side responses and separation")
    args = p.parse_args()
    global MODE
    MODE = args.mode
    fs = args.fs
    f = np.geomspace(50, 20000, 2000)

    print(f"mode {MODE}, speaker spacing {args.spacing * 100:.1f} cm, band {args.f_lo:.0f}-{args.f_hi:.0f} Hz, fs {fs:.0f}")
    print("\n1. Delay tau by distance and head size (samples at fs)")
    print("   distance  " + "  ".join(f"head {k}" for k in HEADS))
    for d in (0.30, 0.40, 0.50):
        row = []
        for a in HEADS.values():
            _, tau = geometry(args.spacing, d, a)
            row.append(f"{tau * 1e6:5.0f} us {tau * fs:4.2f}")
        print(f"   {d * 100:3.0f} cm    " + "   ".join(row))

    print("\n2. Presets at 40 cm, head M: coloration and model separation (dB)")
    print("   (M = centre, e.g. vocals, 150 Hz-8 kHz; S = side; separation averaged over 1-4 kHz)")
    print("   strength  g      M max  M min  S max   sep 1-4k off/on   worst sep 1-4k (30-50 cm, head S-L)")
    theta, tau = geometry(args.spacing, 0.40, HEADS["M"])
    for name, gdb in STRENGTHS.items():
        g = 10 ** (gdb / 20)
        m, s = canceller(f, fs, g, tau, args.f_lo, args.f_hi)
        on, off = separation(f, fs, g, tau, args.f_lo, args.f_hi, tau, HEADS["M"], theta)
        worst = 1e9
        for d in (0.30, 0.35, 0.45, 0.50):
            for a in HEADS.values():
                th, tt = geometry(args.spacing, d, a)
                on2, _ = separation(f, fs, g, tau, args.f_lo, args.f_hi, tt, a, th)
                worst = min(worst, band_mean(f, on2, 1000, 4000))
        voice = (f >= 150) & (f <= 8000)
        mdb, sdb = 20 * np.log10(np.abs(m[voice])), 20 * np.log10(np.abs(s))
        print(f"   {name}  {gdb:5.1f} dB  {mdb.max():+5.1f}  {mdb.min():+5.1f}  {sdb.max():+5.1f}   "
              f"{band_mean(f, off, 1000, 4000):4.1f} / {band_mean(f, on, 1000, 4000):4.1f}"
              f"            {worst:4.1f}")

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
        for name, gdb in STRENGTHS.items():
            g = 10 ** (gdb / 20)
            m, s = canceller(f, fs, g, tau, args.f_lo, args.f_hi)
            ax[0].semilogx(f, 20 * np.log10(np.abs(m)), label=f"M {gdb:g} dB")
            ax[0].semilogx(f, 20 * np.log10(np.abs(s)), "--", label=f"S {gdb:g} dB")
            on, off = separation(f, fs, g, tau, args.f_lo, args.f_hi, tau, HEADS["M"], theta)
            ax[1].semilogx(f, on, label=f"on {gdb:g} dB")
        ax[1].semilogx(f, off, "k:", label="off")
        ax[0].set_ylabel("dB"); ax[0].set_title("mid / side response (40 cm, head M)"); ax[0].legend(ncol=3)
        ax[1].set_ylabel("separation dB (model)"); ax[1].set_xlabel("Hz"); ax[1].legend(ncol=4)
        for a_ in ax:
            a_.grid(True, which="both", alpha=0.3)
        fig.tight_layout()
        fig.savefig(args.plot, dpi=120)
        print(f"\nplot: {args.plot}")


if __name__ == "__main__":
    main()
