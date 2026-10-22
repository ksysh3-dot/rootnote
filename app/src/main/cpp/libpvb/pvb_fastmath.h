// PVB speaker engine - sine and cosine for array loops.
//
// std::sin / std::cos are library calls, so a loop that uses them cannot be vectorised, and each call costs far more
// than the arithmetic around it. The virtual bass fit evaluates about 3000 of them per vocoder frame. sincos() below
// has no calls and no branches (the quadrant is chosen with selects), so such loops vectorise.
//
// Method: the medium-range reduction of fdlibm / FreeBSD msun (e_rem_pio2.c: x - n pi/2 with pi/2 split in two parts,
// the reduced argument kept as a head and a tail) and their kernels on [-pi/4, pi/4] (k_sin.c, k_cos.c, minimax
// polynomials, error < 1 ulp). Within |x| <= 1000 (every caller stays far below) the result is within 0.8 ulp of the
// correctly rounded value, against 0.52 ulp for glibc (tools/pvb-harness/fastmath_check.cpp); larger arguments lose
// accuracy gradually (one-step reduction).
//
// fdlibm: Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved. Developed at SunSoft, a Sun Microsystems,
// Inc. business. Permission to use, copy, modify, and distribute this software is freely granted, provided that this
// notice is preserved.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

namespace pvb {
namespace fastmath {

inline void sincos(double x, double& sinOut, double& cosOut) {
    constexpr double kRound = 6755399441055744.0;            // 1.5 * 2^52: (v + kRound) - kRound = nearest integer
    constexpr double kInvPio2 = 6.36619772367581382433e-01;  // 2 / pi
    constexpr double kPio2Hi = 1.57079632673412561417e+00;   // first 33 bits of pi / 2
    constexpr double kPio2Lo = 6.07710050650619224932e-11;   // pi / 2 - kPio2Hi
    constexpr double S1 = -1.66666666666666324348e-01, S2 = 8.33333333332248946124e-03,
                     S3 = -1.98412698298579493134e-04, S4 = 2.75573137070700676789e-06,
                     S5 = -2.50507602534068634195e-08, S6 = 1.58969099521155010221e-10;
    constexpr double C1 = 4.16666666666666019037e-02, C2 = -1.38888888888741095749e-03,
                     C3 = 2.48015872894767294178e-05, C4 = -2.75573143513906633035e-07,
                     C5 = 2.08757232129817482790e-09, C6 = -1.13596475577881948265e-11;
    // x = n pi/2 + (y0 + y1), |y0| <= pi/4
    const double fn = (x * kInvPio2 + kRound) - kRound;
    const double r = x - fn * kPio2Hi;  // exact: fn has few bits, kPio2Hi has 33
    const double w = fn * kPio2Lo;
    const double y0 = r - w;
    const double y1 = (r - y0) - w;
    // kernels (k_sin.c, k_cos.c)
    const double z = y0 * y0, zz = z * z;
    const double rs = S2 + z * (S3 + z * S4) + z * zz * (S5 + z * S6);
    const double v = z * y0;
    const double ks = y0 - ((z * (0.5 * y1 - v * rs) - y1) - v * S1);
    const double rc = z * (C1 + z * (C2 + z * C3)) + zz * zz * (C4 + z * (C5 + z * C6));
    const double hz = 0.5 * z, wc = 1.0 - hz;
    const double kc = wc + (((1.0 - wc) - hz) + (z * rc - y0 * y1));
    // quadrant q = n mod 4 (exact: fn is an integer, floor(fn / 4) = round(fn / 4 - 3/8))
    const double q = fn - 4.0 * ((fn * 0.25 - 0.375 + kRound) - kRound);
    const bool odd = q == 1.0 || q == 3.0;
    const double a = odd ? kc : ks, b = odd ? ks : kc;
    sinOut = q >= 2.0 ? -a : a;
    cosOut = (q == 1.0 || q == 2.0) ? -b : b;
}

}  // namespace fastmath
}  // namespace pvb
