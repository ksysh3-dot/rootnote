// Accuracy of fastmath::sincos (pvb_fastmath.h) against long double sinl / cosl, and the same for the C library, on
// random arguments in the ranges the engine uses (|x| < 1000) and next to multiples of pi / 2.
//
//   g++ -std=c++17 -O2 -Iapp/src/main/cpp/libpvb tools/pvb-harness/fastmath_check.cpp -o /tmp/fm && /tmp/fm
#include <cmath>
#include <cstdio>
#include <random>

#include "pvb_fastmath.h"

namespace {
double ulpError(double got, long double ref) {
    const double r = static_cast<double>(ref);
    double ulp = std::nextafter(std::fabs(r), INFINITY) - std::fabs(r);
    if (r == 0) ulp = 4.9e-324;
    return static_cast<double>(fabsl(static_cast<long double>(got) - ref)) / ulp;
}
int failures = 0;
void check(bool ok, const char* what) {
    std::printf("[%s] %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) ++failures;
}
}  // namespace

int main() {
    std::mt19937_64 g(7);
    double worst = 0;
    const double ranges[3] = {0.785, 100, 1000};
    for (double hi : ranges) {
        std::uniform_real_distribution<double> d(-hi, hi);
        double es = 0, ec = 0, ls = 0, lc = 0;
        for (int i = 0; i < 2000000; ++i) {
            const double x = d(g);
            double s, c;
            pvb::fastmath::sincos(x, s, c);
            const long double rs = sinl(static_cast<long double>(x)), rc = cosl(static_cast<long double>(x));
            es = std::max(es, ulpError(s, rs));
            ec = std::max(ec, ulpError(c, rc));
            ls = std::max(ls, ulpError(std::sin(x), rs));
            lc = std::max(lc, ulpError(std::cos(x), rc));
        }
        std::printf("|x| < %-6g  fastmath: sin %.3f ulp, cos %.3f ulp   C library: sin %.3f, cos %.3f\n", hi, es, ec, ls, lc);
        worst = std::max(worst, std::max(es, ec));
    }
    double nearAxis = 0;
    for (int k = -600; k <= 600; ++k)
        for (int j = -50; j <= 50; ++j) {
            const double x = std::nextafter(k * 1.5707963267948966, 0.0) + j * 1e-15 * (std::fabs(k) + 1);
            double s, c;
            pvb::fastmath::sincos(x, s, c);
            nearAxis = std::max(nearAxis, static_cast<double>(fabsl(static_cast<long double>(s) - sinl(static_cast<long double>(x)))));
            nearAxis = std::max(nearAxis, static_cast<double>(fabsl(static_cast<long double>(c) - cosl(static_cast<long double>(x)))));
        }
    std::printf("next to multiples of pi/2 (|x| < 950): largest absolute error %.2e\n", nearAxis);
    double s0, c0;
    pvb::fastmath::sincos(0.0, s0, c0);
    check(worst < 1.0, "within 1 ulp for |x| < 1000");
    check(nearAxis < 1e-20, "accurate next to the zeros (absolute error < 1e-20)");
    check(s0 == 0.0 && c0 == 1.0, "sin 0 = 0, cos 0 = 1");
    std::printf(failures ? "fastmath_check: %d FAILED\n" : "fastmath_check: all passed\n", failures);
    return failures ? 1 : 0;
}
