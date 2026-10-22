// PVB speaker engine - two-lane double vectors for the few hot loops that need them.
//
// GCC/Clang vector extensions: plain C++ arithmetic on pairs of doubles, compiled to NEON on arm64 and to SSE2 on the
// x86-64 host build. Each lane is computed exactly like the scalar expression would be (the same IEEE operations, and
// the same contraction rules of the compiler), so a loop written with them gives the same numbers as the scalar loop
// whose partial sums are split the same way; it is only guaranteed to be vectorised.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#pragma once

#include <cstring>

namespace pvb {
namespace simd {

typedef double d2 __attribute__((vector_size(16)));

inline d2 load(const double* p) {
    d2 v;
    std::memcpy(&v, p, sizeof v);
    return v;
}
inline void store(double* p, d2 v) { std::memcpy(p, &v, sizeof v); }
inline d2 splat(double x) { return d2{x, x}; }
inline double sum(d2 v) { return v[0] + v[1]; }

}  // namespace simd
}  // namespace pvb
