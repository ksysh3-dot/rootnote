#!/usr/bin/env python3
"""The engine's crosstalk canceller (pvb_xtc.h) against the Python port of the LiveProg prototype
(check_eel_port.py, the version judged by ear): impulse responses must agree to rounding, for both modes, three
strengths, three distances, three head sizes and 44.1 / 48 kHz."""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import check_eel_port as port  # noqa: E402


def main():
    exe = Path(tempfile.mkdtemp()) / "xtc_dump"
    subprocess.run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{ROOT}/app/src/main/cpp/libpvb",
                    str(HERE / "xtc_native_dump.cpp"), "-o", str(exe)], check=True)
    n = 4096
    failures = 0
    for sr in (48000, 44100):
        port.FS = float(sr)
        for mode in (1, 2):
            for gdb in (-6.0, -4.5, -3.0):
                for dist in (30.0, 40.0, 50.0):
                    for hat in (54.0, 57.0, 60.0):
                        out = subprocess.run([str(exe), str(mode), str(gdb), str(dist), str(hat), "15.5", "400", "8000",
                                              str(sr), str(n)], check=True, capture_output=True).stdout
                        v = np.frombuffer(out, dtype=np.float64).reshape(4, n)
                        radius = 0.0875 * hat / 57.0
                        theta = np.arctan((15.5 * 0.005) / (dist * 0.01))
                        tau = radius / 343.0 * (theta + np.sin(theta))
                        imp = np.zeros(n)
                        imp[0] = 1
                        g = 10 ** (gdb / 20)
                        pl1, pr1 = port.run(mode == 2, g, imp, imp, theta, tau, radius, 400, 8000)
                        pl2, pr2 = port.run(mode == 2, g, imp, -imp, theta, tau, radius, 400, 8000)
                        err = max(np.max(np.abs(v[0] - pl1)), np.max(np.abs(v[1] - pr1)),
                                  np.max(np.abs(v[2] - pl2)), np.max(np.abs(v[3] - pr2)))
                        if not err < 1e-9:
                            failures += 1
                            print(f"[FAIL] sr {sr} mode {mode} g {gdb} {dist} cm hat {hat}: max error {err:.2e}")
    total = 2 * 2 * 3 * 3 * 3
    print(f"xtc_native_check: {total - failures}/{total} match the prototype port (max error < 1e-9)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
