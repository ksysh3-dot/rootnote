// Dumps impulse responses of pvb::Xtc (pvb_xtc.h) for tools/xtc/xtc_native_check.py.
// args: mode strength_db distance_cm hat_cm spacing_cm lo_hz hi_hz sr n
// stdout: n float64 values each of out L, out R for input (1, 1), then for input (1, -1)
#include <cstdio>
#include <cstdlib>
#include <vector>

#include "pvb_xtc.h"

int main(int argc, char** argv) {
    if (argc < 10) return 2;
    pvb::Xtc::Config c;
    c.mode = std::atoi(argv[1]);
    c.strengthDb = std::atof(argv[2]);
    c.distanceCm = std::atof(argv[3]);
    c.hatCm = std::atof(argv[4]);
    c.spacingCm = std::atof(argv[5]);
    c.loHz = std::atof(argv[6]);
    c.hiHz = std::atof(argv[7]);
    const int sr = std::atoi(argv[8]), n = std::atoi(argv[9]);
    for (int sign : {1, -1}) {
        pvb::Xtc x;
        x.setSampleRate(sr);
        x.setWanted(c);
        x.hardReset();
        std::vector<double> l(n), r(n);
        for (int i = 0; i < n; ++i) {
            const double in = i == 0 ? 1.0 : 0.0;
            x.tick(in, sign * in, l[i], r[i]);
        }
        std::fwrite(l.data(), sizeof(double), n, stdout);
        std::fwrite(r.data(), sizeof(double), n, stdout);
    }
    return 0;
}
