#!/usr/bin/env python3
"""Sample-by-sample Python port of tools/xtc/race_xtc.eel (same filters, same linear-interpolation delay line as
JamesDSP's fractionalDelayLine): checks that the script is stable and matches the model in race_design.py."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import race_design as r  # noqa: E402

FS = 48000.0


def fo(b0, b1, a0, a1):
    return [b0 / a0, b1 / a0, a1 / a0, 0.0]


def run1(s, x):
    y = s[0] * x + s[3]
    s[3] = s[1] * x - s[2] * y
    return y


def loop_set(theta, radius, f_lo, f_hi):
    k = math.tan(math.pi * f_lo / FS)
    hp = fo(1, -1, 1 + k, k - 1)
    k = math.tan(math.pi * f_hi / FS)
    lp = fo(k, k, 1 + k, k - 1)
    near, far = r.shelf_alphas(theta)
    w0, kk = 343 / radius, 2 * FS
    b, a = far / (2 * w0) * kk, near / (2 * w0) * kk
    return [hp, lp, fo(1 + b, 1 - b, 1 + a, 1 - a)]


def loop_run(sections, x):
    return run1(sections[2], run1(sections[1], run1(sections[0], x)))


class Delay:
    """JamesDSP fractionalDelayLine: write, then read `lag` samples back with linear interpolation."""

    def __init__(self, lag, n=64):
        self.buf, self.w, self.n, self.lag = [0.0] * n, 0, n, lag

    def proc(self, x):
        self.buf[self.w] = x
        rp = (self.w - self.lag) % self.n
        i = int(math.floor(rp))
        fr = rp - i
        y = self.buf[i] * (1 - fr) + self.buf[(i + 1) % self.n] * fr
        self.w = (self.w + 1) % self.n
        return y


def run(full, g, xl, xr, theta, tau, radius, f_lo, f_hi):
    a, b = loop_set(theta, radius, f_lo, f_hi), loop_set(theta, radius, f_lo, f_hi)
    da, db = Delay(tau * FS - 1), Delay(tau * FS - 1)
    ya = yb = 0.0
    out_l, out_r = [], []
    for xa, xb in zip(xl, xr):
        if full:
            fb_r = loop_run(b, db.proc(yb))
            fb_l = loop_run(a, da.proc(ya))
            ya, yb = xa - g * fb_r, xb - g * fb_l
            out_l.append(ya)
            out_r.append(yb)
        else:
            mid, side = (xa + xb) / 2, (xa - xb) / 2
            ya = side + g * loop_run(a, da.proc(ya))
            out_l.append(mid + ya)
            out_r.append(mid - ya)
    return np.array(out_l), np.array(out_r)


def main():
    n = 8192
    imp = np.zeros(n)
    imp[0] = 1
    f = np.fft.rfftfreq(n, 1 / FS)[1:]
    sel = (f > 150) & (f < 8000)
    failures = 0
    for d in (0.30, 0.40, 0.50):
        theta, tau = r.geometry(0.155, d, r.HEADS["M"])
        r.SHELF = (r.HEADS["M"], theta)
        for full in (True, False):
            r.MODE = "full" if full else "centre"
            for gdb in r.STRENGTHS.values():
                g = 10 ** (gdb / 20)
                l1, r1 = run(full, g, imp, imp, theta, tau, r.HEADS["M"], 400, 8000)
                l2, r2 = run(full, g, imp, -imp, theta, tau, r.HEADS["M"], 400, 8000)
                m = np.fft.rfft((l1 + r1) / 2)[1:]
                s = np.fft.rfft((l2 - r2) / 2)[1:]
                mm, sm = r.canceller(f, FS, g, tau, 400, 8000)
                dev = max(np.max(np.abs(20 * np.log10(np.abs(m[sel]) / np.abs(mm[sel])))),
                          np.max(np.abs(20 * np.log10(np.abs(s[sel]) / np.abs(sm[sel])))))
                tail = float(np.sum(l1[-500:] ** 2) + np.sum(l2[-500:] ** 2))
                ok = dev < 0.5 and tail < 1e-20
                failures += not ok
                print(f"[{'PASS' if ok else 'FAIL'}] {d * 100:.0f} cm {r.MODE:6s} g {gdb:+.1f} dB: "
                      f"max deviation from the model {dev:.2f} dB, tail energy {tail:.1e}")
    print("check_eel_port: all passed" if not failures else f"check_eel_port: {failures} FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
