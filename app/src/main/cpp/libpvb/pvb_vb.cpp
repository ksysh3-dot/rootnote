// PVB speaker engine - virtual bass modules. See pvb_vb.h.
//
// VbHpv follows tools/pvb-harness/vb_port/hpv_ref.py operation by operation (same filter forms as scipy's sosfilt
// and lfilter, numpy's interp, window and summation formulas), so the host test can require agreement to rounding.
// The only intended difference: the core output comes kRtShift (15) samples at 3 kHz later than in the reference,
// because the reference places each vocoder grain up to 15 samples before the end of the frame it is computed from.
//
// Copyright (C) 2026 PVB project. Licensed under the GNU GPL v3 (same as RootlessJamesDSP).
#include "pvb_vb.h"

#include <algorithm>
#include <cassert>
#include <cmath>
#include <complex>
#include <initializer_list>
#include <iterator>

#include "pvb_dsp.h"
#include "pvb_simd.h"
#include "pvb_vb_tables.h"

namespace pvb {
bool VbHpv::setAlpha2Profile(int algorithm) {
    if (!supportedVbAlgo(algorithm)) return false;
    const unsigned flags=0; const int mode=3;
    s32Profile_=algorithm==VB_ALPHA2_P1;
    s32Flags_=s32Profile_?s32HostFlags_:0;
    s41Mode_=s32Profile_?s41HostMode_:0;
    s38Flags_=s32Profile_?s38HostFlags_:0; s38Mode_=s32Profile_?s38HostMode_:0;
#if defined(PVB_HOST_RESULTANT_REFERENCE)
    const bool resultant=algorithm==VB_RESULTANT_V16;
#else
    constexpr bool resultant=false;
#endif
    p1PlusProfile_=true;
    p1PlusFixed_=resultant;
    p1PlusFlags_=resultant ? 0u : p1PlusHostFlags_;
    p1ppImpactMode_=resultant ? 0 : p1ppHostImpact_;
    p1ppV04_=resultant ? 0u : p1ppV04Host_;
    modulationMode_=mode;tonalOnly_=false;continuity_=ContinuityParams{};continuity_.enabled=true;
    applyDevContinuity();
    // Resultant core: gen_ (host research, survives profile switches) is not used by algorithms 15 and 16; it comes back,
    // as the host or the engine last asked for it (genReq_), with the next other profile. Only a switch into or out of
    // the pair touches it, so the other profiles stay exactly as they were.
    if(resultant!=resultantOn_) {
        resultantOn_=resultant;
        gen_=resultantOn_?GenResearch52{}:genReq_;
    }
#if defined(PVB_HOST_RESULTANT_REFERENCE)
    // Fixed "modified c": s50/F1 length contract and fixes 27-29 ON (1-based slots).
    if (resultant) {
        double v[]={0,0,0,15,22,6,8,30,.05,.1,1.0,30,24,.03,0,200,1.5,16,2,150,8,1,0,10,0,0,1,1,1,0};
        static_assert(std::size(v)==ResultantCore::kV16PresetParams,"c preset length changed");
        static_assert(std::size(v)<=ResultantCore::kParams,"c preset exceeds API");
        const bool applied=resultant_.setParams(v,static_cast<int>(std::size(v)));
        assert(applied);(void)applied;
        resultantSet_=true;
    } else leaveResultantSet();
#endif
    // P1 is the host research profile: an explicitly attached stage probe may
    // precede the first vbApply() call. Preserve its assignment flags there.
    stageFlags_=flags|(algorithm==VB_ALPHA2_P1 ? stageHostFlags_ : 0u);reset();return true;
}

// ------------------------------------------------------------------------------------------------ developer mode
namespace {
// RBJ cookbook biquad at the 3 kHz core rate, normalised (a0 = 1): b0 b1 b2 a1 a2. The tables kBandSos/kOutSos are
// exactly these designs (band: LR4 high-pass 32 Hz + LR4 low-pass 190 Hz; out: Butterworth HP4 150 Hz + LP2 600 Hz),
// so a developer value equal to the model's uses the table itself and anything else follows the same shape.
void rbjCore(double f, double q, bool lowpass, double* c) {
    const double w = 2.0 * kPi * clampv(f, 1.0, 0.45 * VbHpv::kFsd) / VbHpv::kFsd;
    const double cw = std::cos(w), al = std::sin(w) / (2.0 * q), a0 = 1.0 + al;
    if (lowpass) { c[0] = (1.0 - cw) / 2.0 / a0; c[1] = (1.0 - cw) / a0; c[2] = c[0]; }
    else { c[0] = (1.0 + cw) / 2.0 / a0; c[1] = -(1.0 + cw) / a0; c[2] = c[0]; }
    c[3] = -2.0 * cw / a0;
    c[4] = (1.0 - al) / a0;
}
constexpr double kQ2 = 0.70710678118654752;     // Butterworth 2nd order
constexpr double kQ4a = 0.54119610014619698;    // Butterworth 4th order, section 1
constexpr double kQ4b = 1.30656296487637652;    // Butterworth 4th order, section 2
}  // namespace

void VbHpv::applyDevContinuity() {
    // Only the P1-family profiles use the continuity envelope; the defaults leave it exactly as the profile set it.
    if (!continuity_.enabled) return;
    if (dev_.attackHops != DevVoicing::kAttackHops) continuity_.attack = dev_.attackHops;
    if (dev_.releaseHops != DevVoicing::kReleaseHops) {
        // The onset/silence release (model 2 of 6 hops) follows: a third below the model, 4 hops less above it,
        // so a longer release also lengthens the tail after the music stops (continuous at the model's 6 -> 2).
        const int r = dev_.releaseHops;
        continuity_.release = r;
        continuity_.fastRelease = r < DevVoicing::kReleaseHops ? std::max(1, static_cast<int>(std::lround(r / 3.0)))
                                                                : r - 4;
    }
}

void VbHpv::setDev(const DevVoicing& d) {
    if (!masked_ || d == dev_) return;
    const DevVoicing old = dev_;
    dev_ = d;
    auto load = [](Biquad& b, const double* c, bool table) {
        // table rows are b0 b1 b2 a0(=1) a1 a2; designed rows b0 b1 b2 a1 a2
        b.b0 = c[0]; b.b1 = c[1]; b.b2 = c[2];
        b.a1 = table ? c[4] : c[3];
        b.a2 = table ? c[5] : c[4];
    };
    if (d.boundaryHz != old.boundaryHz) {
        if (d.boundaryHz == DevVoicing::kBoundaryHz) {
            for (int s = 2; s < 4; ++s) load(band_[s], vbt::kBandSos + 6 * s, true);
        } else {
            double c[5];
            rbjCore(d.boundaryHz, kQ2, true, c);
            for (int s = 2; s < 4; ++s) load(band_[s], c, false);
        }
        // Peak search range of the vocoder: up to 200 Hz in the model, 10 Hz above a higher boundary.
        const double top = std::max(200.0, d.boundaryHz + 10.0);
        hiBin_ = loBin_;
        while (hiBin_ * binHz_ < top) ++hiBin_;
    }
    if (d.outLoHz != old.outLoHz || d.outHiHz != old.outHiHz) {
        if (d.outLoHz == DevVoicing::kOutLoHz && d.outHiHz == DevVoicing::kOutHiHz) {
            for (int s = 0; s < 3; ++s) load(out_[s], vbt::kOutSos + 6 * s, true);
        } else {
            double c[5];
            rbjCore(d.outLoHz, kQ4a, false, c); load(out_[0], c, false);
            rbjCore(d.outLoHz, kQ4b, false, c); load(out_[1], c, false);
            rbjCore(d.outHiHz, kQ2, true, c); load(out_[2], c, false);
        }
    }
    devHarm_ = false;
    for (int k = 0; k < 4; ++k) {
        devHarmLin_[k] = std::pow(10.0, d.harmDb[k] / 20.0);
        if (d.harmDb[k] != 0.0) devHarm_ = true;
    }
    devRolloff_ = d.rolloffOffset != 0.0;
    devMix_ = d.sustDb != 0.0 || d.percDb != 0.0;
    devSustLin_ = std::pow(10.0, d.sustDb / 20.0);
    devPercLin_ = std::pow(10.0, d.percDb / 20.0);
    if (continuity_.enabled) {
        // back to the profile's values first, then the developer values that differ from them
        if (old.attackHops != DevVoicing::kAttackHops) continuity_.attack = ContinuityParams{}.attack;
        if (old.releaseHops != DevVoicing::kReleaseHops) {
            continuity_.release = ContinuityParams{}.release;
            continuity_.fastRelease = ContinuityParams{}.fastRelease;
        }
        applyDevContinuity();
    }
}

double VbHpv::devOutResponse(double f) const {
    const double w = 2.0 * kPi * f / kFsd;
    const std::complex<double> z1 = std::polar(1.0, -w), z2 = z1 * z1;
    std::complex<double> h = 1.0;
    for (const auto& b : out_) h *= (b.b0 + b.b1 * z1 + b.b2 * z2) / (1.0 + b.a1 * z1 + b.a2 * z2);
    return std::abs(h);
}

namespace {

// numpy's pairwise summation (used by ndarray.sum), so the vocoder's window sum matches the reference bit for bit.
double pairwiseSum(const double* a, int n) {
    if (n < 8) {
        double s = 0.0;
        for (int i = 0; i < n; ++i) s += a[i];
        return s;
    }
    if (n <= 128) {
        double r[8];
        for (int k = 0; k < 8; ++k) r[k] = a[k];
        int i = 8;
        for (; i < n - (n % 8); i += 8)
            for (int k = 0; k < 8; ++k) r[k] += a[i + k];
        double s = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; ++i) s += a[i];
        return s;
    }
    int n2 = n / 2;
    n2 -= n2 % 8;
    return pairwiseSum(a, n2) + pairwiseSum(a + n2, n - n2);
}

// numpy.hanning(n + 1)[:-1] (the reference's periodic Hann).
void hanning(double* w, int n) {
    const double m = n + 1;
    for (int i = 0; i < n; ++i) {
        const double x = 1.0 - m + 2.0 * i;
        w[i] = 0.5 + 0.5 * std::cos(kPi * x / (m - 1.0));
    }
}

// k-th smallest of n values (n <= 16), like the rank filter of scipy.ndimage.median_filter.
double kth(double* v, int n, int k) {
    for (int i = 1; i < n; ++i) {
        const double x = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > x) {
            v[j + 1] = v[j];
            --j;
        }
        v[j + 1] = x;
    }
    return v[k];
}

}  // namespace

// ================================================================================================ hpv

VbHpv::VbHpv(bool, bool, int) {
    hanning(winHp_, kHpN);
    hanning(winPv_, kPvN);
    for (int n = 0; n < kHpN; ++n) {
        cosHp_[n] = std::cos(2.0 * kPi * n / kHpN);
        sinHp_[n] = std::sin(2.0 * kPi * n / kHpN);
    }
    for (int n = 0; n < kPvNfft; ++n) {
        cosPv_[n] = std::cos(2.0 * kPi * n / kPvNfft);
        sinPv_[n] = std::sin(2.0 * kPi * n / kPvNfft);
    }
    for (int i = 0; i < 64; ++i) {
        int r = 0;
        for (int b = 0; b < 6; ++b) r |= ((i >> b) & 1) << (5 - b);
        bitrev64_[i] = r;
    }
    for (int len = 2; len <= 64; len <<= 1) {
        const int hl = len >> 1, step = 64 / len;
        for (int k = 0; k < hl; ++k) {
            tw64r_[hl - 1 + k] = cosHp_[3 * k * step];
            tw64i_[hl - 1 + k] = -sinHp_[3 * k * step];
        }
    }
    for (int i = 0, bits = 0; i < kHalfFft; ++i) {
        while ((1 << bits) < kHalfFft) ++bits;
        int r = 0;
        for (int b = 0; b < bits; ++b) r |= ((i >> b) & 1) << (bits - 1 - b);
        bitrev_[i] = r;
    }
    for (int len = 2; len <= kHalfFft; len <<= 1) {
        const int hl = len >> 1, step = kPvNfft / len;
        for (int k = 0; k < hl; ++k) {
            twr_[hl - 1 + k] = cosPv_[k * step];
            twi_[hl - 1 + k] = -sinPv_[k * step];
        }
    }
    // Overlap-add normaliser at each of the 16 positions in the hop: sum of win^2 over the 12 frames that cover a
    // sample, in the reference's order (oldest frame first).
    for (int r = 0; r < kHpHop; ++r) {
        double s = 0.0;
        for (int q = (kHpN - kHpHop) / kHpHop; q >= 0; --q) {
            const double w = winHp_[r + kHpHop * q];
            s += w * w;
        }
        wsumHp_[r] = std::max(s, 1e-3);
    }
    pvWsum_ = pairwiseSum(winPv_, kPvN);
    // numpy.bartlett(2 H + 1)[:-1]
    for (int g = 0; g < 2 * kPvH; ++g) {
        const double nn = 1.0 - (2 * kPvH + 1) + 2.0 * g;
        const double d = 2.0 * kPvH;
        gw_[g] = nn <= 0.0 ? 1.0 + nn / d : 1.0 - nn / d;
    }
    // numpy.fft.rfftfreq(2048, 1/3000): k * (1 / (n * d))
    binHz_ = 1.0 / (kPvNfft * (1.0 / kFsd));
    loBin_ = 0;
    while (loBin_ * binHz_ < 25.0) ++loBin_;   // searchsorted(f, 25): first bin >= 25 Hz
    hiBin_ = loBin_;
    while (hiBin_ * binHz_ < 200.0) ++hiBin_;  // first bin >= 200 Hz (exclusive end)
    for (int s = 0; s < 4; ++s) {
        band_[s].b0 = vbt::kBandSos[6 * s + 0];
        band_[s].b1 = vbt::kBandSos[6 * s + 1];
        band_[s].b2 = vbt::kBandSos[6 * s + 2];
        band_[s].a1 = vbt::kBandSos[6 * s + 4];
        band_[s].a2 = vbt::kBandSos[6 * s + 5];
    }
    for (int s = 0; s < 3; ++s) {
        out_[s].b0 = vbt::kOutSos[6 * s + 0];
        out_[s].b1 = vbt::kOutSos[6 * s + 1];
        out_[s].b2 = vbt::kOutSos[6 * s + 2];
        out_[s].a1 = vbt::kOutSos[6 * s + 4];
        out_[s].a2 = vbt::kOutSos[6 * s + 5];
    }
    for (Hilbert* h : {&hilH_, &hilP_}) {
        for (int s = 0; s < 4; ++s) {
            h->i[s].c = vbt::kHilbertI[s] * vbt::kHilbertI[s];
            h->q[s].c = vbt::kHilbertQ[s] * vbt::kHilbertQ[s];
        }
    }
    for (int k = 0; k < kKMax - 1; ++k) {
        cPsi_[k] = std::cos(vbt::kPsi[k]);
        sPsi_[k] = std::sin(vbt::kPsi[k]);
    }
    configure(48000);
}

bool VbHpv::configure(int sampleRate) {
    if (sampleRate == 48000) {
        L_ = 1; M_ = 16; taps_ = vbt::kAa48Taps; fir_ = vbt::kAa48;
    } else if (sampleRate == 44100) {
        L_ = 10; M_ = 147; taps_ = vbt::kAa441Taps; fir_ = vbt::kAa441;
    } else {
        supported_ = false;
        latency_ = 0;
        return false;
    }
    for (int j = 0; j < taps_; ++j) {
        firDec_[j] = fir_[j] * static_cast<double>(L_);
        firInt_[j] = fir_[j] * static_cast<double>(M_);
    }
    supported_ = true;
    // vbcore's measured hpv latency (6812 samples at 48 kHz) plus the 15 core samples (240 at 48 kHz) of the causal
    // grain placement; the same time at 44.1 kHz.
    latency_ = static_cast<int>(std::lround((vbt::kLat48Py + kRtShift * 16) / 48000.0 * sampleRate));
    reset();
    return true;
}

void VbHpv::Hilbert::clear() {
    for (int s = 0; s < 4; ++s) {
        i[s].clear();
        q[s].clear();
    }
    qPrev = 0;
}

void VbHpv::Hilbert::tick(double x, double& re, double& im) {
    double a = x, b = x;
    for (int s = 0; s < 4; ++s) a = i[s].tick(a);
    for (int s = 0; s < 4; ++s) b = q[s].tick(b);
    re = a;
    im = qPrev;  // the Q branch is one sample later
    qPrev = b;
}

void VbHpv::reset() {
    ++harmonicEpoch_; nextTrackId_=0; harmonicReady_=false;
    research_ = {};
    research_.upperBlend = research_.upperTarget = upperMode_==0 ? 0 : 1;
    std::fill(std::begin(inRing_), std::end(inRing_), 0.0);
    std::fill(std::begin(hcRing_), std::end(hcRing_), 0.0);
    n_ = m_ = mDue_ = 0;
    i_ = 0;
    for (auto& b : band_) b.clear();
    for (auto& b : out_) b.clear();
    std::fill(std::begin(bRing_), std::end(bRing_), 0.0);
    for (auto& row : sHist_) std::fill(std::begin(row), std::end(row), 0.0);
    sPos_ = 0;
    std::fill(std::begin(olaH_), std::end(olaH_), 0.0);
    std::fill(std::begin(olaP_), std::end(olaP_), 0.0);
    std::fill(std::begin(olaHA_), std::end(olaHA_), 0.0);
    std::fill(std::begin(bhCausal52_), std::end(bhCausal52_), 0.0);
    hilH_.clear();
    hilP_.clear();
    prevUr_ = prevUi_ = 0.0;
    first_ = true;
    eps_ = std::pow(10.0, params.epsDb / 20.0);
    ifFloor_ = std::pow(10.0, params.ifFloorDb / 20.0);
    pvAbs_ = std::pow(10.0, params.pvAbsDb / 20.0);
    pvRel_ = std::pow(10.0, params.pvRelDb / 20.0);
    const double a = std::exp(-1.0 / (params.ifSmoothS * kFsd));
    fInst_.a = a;
    fInst_.b0 = 1.0 - a;
    fInst_.z = params.ifDefaultHz * a;
    const double ag = std::exp(-1.0 / (params.gainSmoothS * kFsd));
    fGain_.a = ag;
    fGain_.b0 = 1.0 - ag;
    fGain_.z = 0.0;  // set from the first frequency, like the reference
    std::fill(std::begin(hpRing_), std::end(hpRing_), 0.0);
    std::fill(std::begin(bhRing_), std::end(bhRing_), 0.0);
    std::fill(std::begin(aRing_), std::end(aRing_), 0.0);
    std::fill(std::begin(pvOut_), std::end(pvOut_), 0.0);
    std::fill(std::begin(pvApv_), std::end(pvApv_), 0.0);
    nTracks_ = 0;
    const double al = std::exp(-1.0 / (params.envSmoothS * kFsd));
    envA_.a = envP_.a = al;
    envA_.b0 = envP_.b0 = 1.0 - al;
    envA_.z = envP_.z = 0.0;
    nt52_=apkCount_=histCount_=holdCount_=holdPos_=onsetLeft_=0;
    s32MaxA_=s32FocusHz_=0; s32FocusLeft_=0;
    s41LogCount_=0; s43OnsetPrev_=false;
    s38LogGain_=s38Fast_=s38Slow_=s38PrevApv_=0; s38OnsetLeft_=0; s38GainValid_=false;
    std::fill(std::begin(s32RawSlow_),std::end(s32RawSlow_),0.);
    impactCtx52_=preImpactN52_=lowGridHold52_=0; percSlow52_=0; graveN52_=0; hop52_=0; onsetBlend52_=1;
    for (auto& row : hold52_) std::fill(std::begin(row),std::end(row),-200.0);
    for (double* r : {md52_,md2_52_,max52_}) std::fill(r,r+kRing,0.0);
    std::fill(std::begin(polyT52_),std::end(polyT52_),1.0);
    poly52_=1; percEnv52_=harmEnv52_=0;
    std::fill(std::begin(detailRing52_),std::end(detailRing52_),0.);detailApplied52_=familyApplied52_=false;
    family52_={};familyCentre52_=0;familyCountdown52_=0;conditionalGain52_=0;
    std::fill(std::begin(oscillatorNominal52_),std::end(oscillatorNominal52_),0.);
    devGain_=devAttM_=devAttS_=0;
    genGain_=genFastE_=genSlowE_=0; lastFc_=60; lastGk_=0; genLastOnset_=-1000000;
    std::fill(std::begin(genAmpRing_),std::end(genAmpRing_),0.); std::fill(std::begin(genPhaseRing_),std::end(genPhaseRing_),0.);
    std::fill(std::begin(genOnsetRing_),std::end(genOnsetRing_),false);
    for(auto& b:bursts_) b=Burst{};
#if defined(PVB_HOST_RESULTANT_REFERENCE)
    resultant_.reset();
#endif
}

// numpy.interp(f, grid, arange(400)), clipped, then linear interpolation of the weight and gain tables.
void VbHpv::lookup(double f, double* wk, double& gk) const {
    if (dev_.tableScale != 1.0) f /= dev_.tableScale;   // developer speaker-floor scale (1 = model, untouched)
    const double* x = vbt::kGridHz;
    const int n = vbt::kGrid;
    double idx;
    if (std::isnan(f)) {
        idx = f;
    } else if (f < x[0]) {
        idx = 0.0;
    } else if (f > x[n - 1]) {
        idx = n - 1;
    } else {
        int lo = 0, hi = n - 1;  // largest j with x[j] <= f
        while (hi - lo > 1) {
            const int mid = (lo + hi) / 2;
            if (x[mid] <= f) lo = mid; else hi = mid;
        }
        int j = (x[hi] <= f) ? hi : lo;
        if (j == n - 1 || x[j] == f) {
            idx = j;
        } else {
            const double slope = (static_cast<double>(j + 1) - static_cast<double>(j)) / (x[j + 1] - x[j]);
            idx = slope * (f - x[j]) + j;
        }
    }
    idx = clampv(idx, 0.0, static_cast<double>(n - 1));
    const int i0 = static_cast<int>(std::floor(idx));
    const int i1 = std::min(i0 + 1, n - 1);
    const double fr = idx - i0;
    for (int k = 0; k < kKMax - 1; ++k) {
        const double* w = vbt::kWeights + k * n;
        wk[k] = w[i0] * (1.0 - fr) + w[i1] * fr;
    }
    gk = vbt::kGain[i0] * (1.0 - fr) + vbt::kGain[i1] * fr;
}

// The 1-band analytic generator (reference band_layer), one sample of the percussive analytic stream.
double VbHpv::bandLayer(double re, double im) {
    const double A = std::hypot(re, im);
    const double den = A + eps_;
    const double ur = re / den, ui = im / den;
    double f;
    if (first_) {
        f = params.ifDefaultHz * kFsd / (2.0 * kPi);  // the reference scales the default as well...
    } else {
        const double dr = ur * prevUr_ - ui * (-prevUi_);
        const double di = ur * (-prevUi_) + ui * prevUr_;
        f = std::atan2(di, dr) * kFsd / (2.0 * kPi);
    }
    if (!(A >= ifFloor_)) f = params.ifDefaultHz;  // ...and then replaces it here (the stream starts silent)
    prevUr_ = ur;
    prevUi_ = ui;
    const double fi = fInst_.tick(f);
    const double fc = clampv(fi, params.fLoHz, dev_.tableScale != 1.0 ? params.fHiHz * dev_.tableScale : params.fHiHz);
    double wk[kKMax - 1], gUnused;
    lookup(fc, wk, gUnused);
    if (devHarm_) devWeights(wk);
    if (first_) {
        fGain_.z = fc * fGain_.a;
        first_ = false;
    }
    const double fg = fGain_.tick(fc);
    double wUnused[kKMax - 1], gk;
    lookup(fg, wUnused, gk);
    const double amp = A * gk;
    lastFc_ = fc; lastGk_ = gk;  // read only by the S2 research bursts
    double out = 0.0;
    double kr = ur, ki = ui;
    for (int k = 2; k <= kKMax; ++k) {
        const double nr = kr * ur - ki * ui;
        const double ni = kr * ui + ki * ur;
        kr = nr;
        ki = ni;
        out += wk[k - 2] * (kr * cPsi_[k - 2] - ki * sPsi_[k - 2]);
    }
    return out * amp;
}

// HPSS frame j (complete at core sample i = 16 j - 1): b[i-191 .. i].
void VbHpv::hpssFrame() {
    int64_t i = static_cast<int64_t>(i_);
    double fr[kHpN];
    for (int n = 0; n < kHpN; ++n) fr[n] = bRing_[(i - (kHpN - 1) + n) & (kRing - 1)] * winHp_[n];
    double Fr[kHpBins], Fi[kHpBins], S[kHpBins];
    {
        const double zero[kHpN] = {};
        dft192(fr, zero, Fr, Fi, kHpBins);
    }
    for (int k = 0; k < kHpBins; ++k) S[k] = std::hypot(Fr[k], Fi[k]);
    const int future=hpssLookahead();
    const bool prominence=future && (p1PlusFlags_&8);
    const int history=prominence?kHpMedT+5:kHpMedT;
    std::copy(S, S + kHpBins, sHist_[sPos_]);
    sPos_ = (sPos_ + 1) % history;
    if(future) {
        // Current spectrum updates the eleven-frame history; classify the
        // frame five hops earlier, now with five past and five future frames.
        // Recompute its complex spectrum from the input ring, not magnitudes
        // with a guessed phase. Extra work is an explicit HQ-mode cost.
        if(i<future) return;
        i-=future;
        for(int n=0;n<kHpN;++n)
            fr[n]=bRing_[(i-(kHpN-1)+n)&(kRing-1)]*winHp_[n];
        const double zero[kHpN]={};
        dft192(fr,zero,Fr,Fi,kHpBins);
        for(int k=0;k<kHpBins;++k) S[k]=std::hypot(Fr[k],Fi[k]);
    }
    double Mh[kHpBins], MhA[kHpBins], Mc[kHpBins];
    // olaHA_ holds the harmonic part the output does not use: the C5 mask under C6, the causal mask under C5 (both
    // only for the analysis side: C6's vocoder spectrum, or the polyphony count)
    const bool analysisMask=!future && (stageFlags_&(StageAnalysisProminence|StageCausalProminence));
    for (int k = 0; k < kHpBins; ++k) {
        double v[kHpMedT];
        for (int t = 0; t < kHpMedT; ++t)
            v[t] = sHist_[prominence?(sPos_+5+t)%history:t][k];
        const double H = kth(v, kHpMedT, kHpMedT / 2);  // causal or centered eleven-frame median
        double u[kHpMedF];
        for (int d = 0; d < kHpMedF; ++d) u[d] = S[clampv(k - kHpMedF / 2 + d, 0, kHpBins - 1)];
        const double P = kth(u, kHpMedF, kHpMedF / 2);  // median over +-3 bins
        Mh[k] = (H * H) / (H * H + P * P + 1e-20);
        if(prominence) {
            double past[kHpMedT];
            for(int t=0;t<kHpMedT;++t) past[t]=sHist_[(sPos_+t)%history][k];
            const double causal=kth(past,kHpMedT,kHpMedT/2);
            const double causalMask=causal*causal/(causal*causal+P*P+1e-20);
            const double weight=clampv((S[k]/(P+1e-20)-1.)/(std::sqrt(10.)-1.),0.,1.);
            Mh[k]=causalMask+weight*(Mh[k]-causalMask);
        } else if(!future && (stageFlags_&(StageCausalProminence|StageAnalysisProminence))) {
            // Study 3 C5: no lookahead. A peak prominent in this frame AND at the same bin one hop earlier (10 dB
            // over its +-3 bin median at full weight; the smaller weight counts) is harmonic now, as if its
            // eleven-frame history were already the current spectrum. A flat (impact) spectrum and a peak that is
            // still moving (a kick's falling body) keep the causal median. Weight as in the HQ prominence blend.
            // C6 uses this mask only for the analysis harmonic part (olaHA_); the output paths keep the causal one.
            const double* prev=sHist_[(sPos_+history-2)%history];
            double up[kHpMedF];
            for(int d=0;d<kHpMedF;++d) up[d]=prev[clampv(k-kHpMedF/2+d,0,kHpBins-1)];
            const double Pp=kth(up,kHpMedF,kHpMedF/2);
            const auto prominent=[](double s,double p) {return clampv((s/(p+1e-20)-1.)/(std::sqrt(10.)-1.),0.,1.);};
            const double weight=std::min(prominent(S[k],P),prominent(prev[k],Pp));
            const double instant=S[k]*S[k]/(S[k]*S[k]+P*P+1e-20);
            MhA[k]=std::max(Mh[k],Mh[k]+weight*(instant-Mh[k]));
            Mc[k]=Mh[k];
            if(stageFlags_&StageCausalProminence) {Mh[k]=MhA[k];MhA[k]=Mc[k];}
        }
    }
    // inverse real DFT of F * Mh (numpy.fft.irfft, n = 192), windowed, overlap-added. The percussive part
    // irfft(F * (1 - Mh)) is the windowed frame minus that (the inverse of F itself is the windowed frame).
    // irfft through the forward transform: y[n] = Re(DFT(conj(H))[n]) / N, H Hermitian (imaginary parts of the DC
    // and Nyquist bins ignored, like numpy).
    double gr[kHpN], gi[kHpN], yr[kHpN], yi[kHpN];
    auto inverse = [&](const double* mask) {
        for (int k = 0; k < kHpBins; ++k) {
            gr[k] = Fr[k] * mask[k];
            gi[k] = -(Fi[k] * mask[k]);
        }
        gi[0] = 0.0;
        gi[kHpBins - 1] = 0.0;
        for (int k = 1; k < kHpBins - 1; ++k) {   // conj(H[N - k]) = H[k]
            gr[kHpN - k] = gr[k];
            gi[kHpN - k] = -gi[k];
        }
        dft192(gr, gi, yr, yi, kHpN);
    };
    if (analysisMask) {
        inverse(MhA);
        for (int n = 0; n < kHpN; ++n) {
            const int64_t t = i - (kHpN - 1) + n;
            if (t >= 0) olaHA_[t & (kRing - 1)] += yr[n] / kHpN * winHp_[n];
        }
    }
    inverse(Mh);
    for (int n = 0; n < kHpN; ++n) {
        const int64_t t = i - (kHpN - 1) + n;
        if (t < 0) continue;  // before the stream: the reference drops these too
        const double yh = yr[n] / kHpN;
        olaH_[t & (kRing - 1)] += yh * winHp_[n];
        olaP_[t & (kRing - 1)] += (fr[n] - yh) * winHp_[n];
    }
}

// Radix-2 complex FFT of 64 points (twiddles from the 192-point table: exp(-2 pi i j / 64) = index 3 j, kept per stage
// in tw64r_ / tw64i_). As in fftHalf(), the stages from half length 2 on compute two butterflies per vector.
void VbHpv::fft64(double* re, double* im) const {
    alignas(16) double ar[64], ai[64];
    for (int n = 0; n < 64; ++n) {
        ar[bitrev64_[n]] = re[n];
        ai[bitrev64_[n]] = im[n];
    }
    for (int i0 = 0; i0 < 64; i0 += 2) {   // half length 1: twiddle exp(0)
        const double wr = tw64r_[0], wi = tw64i_[0];
        const int a = i0, b = a + 1;
        const double tr = ar[b] * wr - ai[b] * wi;
        const double ti = ar[b] * wi + ai[b] * wr;
        ar[b] = ar[a] - tr;
        ai[b] = ai[a] - ti;
        ar[a] += tr;
        ai[a] += ti;
    }
    using simd::d2;
    for (int len = 4; len <= 64; len <<= 1) {
        const int hl = len >> 1;
        const double* wrs = tw64r_ + hl - 1;
        const double* wis = tw64i_ + hl - 1;
        for (int i0 = 0; i0 < 64; i0 += len) {
            for (int k = 0; k < hl; k += 2) {
                const int a = i0 + k, b = a + hl;
                const d2 wr = simd::load(wrs + k), wi = simd::load(wis + k);
                const d2 xr = simd::load(ar + b), xi = simd::load(ai + b);
                const d2 tr = xr * wr - xi * wi;
                const d2 ti = xr * wi + xi * wr;
                const d2 yr = simd::load(ar + a), yi = simd::load(ai + a);
                simd::store(ar + b, yr - tr);
                simd::store(ai + b, yi - ti);
                simd::store(ar + a, yr + tr);
                simd::store(ai + a, yi + ti);
            }
        }
    }
    std::copy(ar, ar + 64, re);
    std::copy(ai, ai + 64, im);
}

// 192-point DFT (exp(-2 pi i k n / 192)) by decimation in time into three 64-point FFTs; bins 0 .. nOut-1.
void VbHpv::dft192(const double* xr, const double* xi, double* yr, double* yi, int nOut) {
    for (int r = 0; r < 3; ++r) {
        for (int m = 0; m < 64; ++m) {
            fr3_[r][m] = xr[3 * m + r];
            fi3_[r][m] = xi[3 * m + r];
        }
        fft64(fr3_[r], fi3_[r]);
    }
    for (int k = 0; k < nOut; ++k) {
        const int q = k & 63;
        const int t1 = k % kHpN, t2 = (2 * k) % kHpN;
        const double w1r = cosHp_[t1], w1i = -sinHp_[t1], w2r = cosHp_[t2], w2i = -sinHp_[t2];
        yr[k] = fr3_[0][q] + (fr3_[1][q] * w1r - fi3_[1][q] * w1i) + (fr3_[2][q] * w2r - fi3_[2][q] * w2i);
        yi[k] = fi3_[0][q] + (fr3_[1][q] * w1i + fi3_[1][q] * w1r) + (fr3_[2][q] * w2i + fi3_[2][q] * w2r);
    }
}

// Radix-2 decimation in time on zr_ / zi_ (bit-reversed input). Every butterfly is the same arithmetic as before
// (twiddle exp(-2 pi i k / len) from the per-stage table); from the third stage on, two neighbouring butterflies of a
// block are computed as one pair of vector lanes (they are independent), which gives the same numbers.
void VbHpv::fftHalf() {
    // stages of half length 1 and 2: scalar
    for (int len = 2; len <= 4; len <<= 1) {
        const int hl = len >> 1;
        for (int i0 = 0; i0 < kHalfFft; i0 += len) {
            for (int k = 0; k < hl; ++k) {
                const double wr = twr_[hl - 1 + k], wi = twi_[hl - 1 + k];
                const int a = i0 + k, b = a + hl;
                const double tr = zr_[b] * wr - zi_[b] * wi;
                const double ti = zr_[b] * wi + zi_[b] * wr;
                zr_[b] = zr_[a] - tr;
                zi_[b] = zi_[a] - ti;
                zr_[a] += tr;
                zi_[a] += ti;
            }
        }
    }
    using simd::d2;
    for (int len = 8; len <= kHalfFft; len <<= 1) {
        const int hl = len >> 1;
        const double* wrs = twr_ + hl - 1;
        const double* wis = twi_ + hl - 1;
        for (int i0 = 0; i0 < kHalfFft; i0 += len) {
            double* ar = zr_ + i0;
            double* ai = zi_ + i0;
            double* br = ar + hl;
            double* bi = ai + hl;
            for (int k = 0; k < hl; k += 2) {
                const d2 wr = simd::load(wrs + k), wi = simd::load(wis + k);
                const d2 xr = simd::load(br + k), xi = simd::load(bi + k);
                const d2 tr = xr * wr - xi * wi;
                const d2 ti = xr * wi + xi * wr;
                const d2 yr = simd::load(ar + k), yi = simd::load(ai + k);
                simd::store(br + k, yr - tr);
                simd::store(bi + k, yi - ti);
                simd::store(ar + k, yr + tr);
                simd::store(ai + k, yi + ti);
            }
        }
    }
}

// Vocoder frame (complete at core sample i): harmonic stream bh[i-383 .. i]; grain centred at i + 1.
double VbHpv::core(double d) { return core52(d); }

void VbHpv::tick(double inL, double inR, double& outL, double& outR) {
    harmonicReady_=false;
    if (!supported_) {
        outL = outR = 0.0;
        return;
    }
    const double x = (inL + inR) / 2.0;
    inRing_[n_ & (kInRing - 1)] = x;
    const uint64_t taps = static_cast<uint64_t>(taps_), L = static_cast<uint64_t>(L_), M = static_cast<uint64_t>(M_);
    while (mDue_ == n_) {
        // decimated sample m_: sum_k x[k] * L h[M m - L k]
        const uint64_t r = M * m_ - L * mDue_;
        double d = 0.0;
        if (mDue_ >= taps) {
            // Once the stream is longer than the filter the input index never reaches 0 first: the same sum
            // without that test.
            for (uint64_t j = r, k = mDue_; j < taps; j += L, --k) d += firDec_[j] * inRing_[k & (kInRing - 1)];
        } else {
            for (uint64_t j = r, k = mDue_;; j += L) {
                if (j >= taps) break;
                d += firDec_[j] * inRing_[k & (kInRing - 1)];
                if (k == 0) break;
                --k;
            }
        }
        hcRing_[m_ & (kHcRing - 1)] = core(d);
        ++m_;
        mDue_ = (M * m_) / L;
    }
    // y[n] = sum_m hc[m] * M h[L n - M m]
    const uint64_t mMax = (L * n_) / M;
    double y = 0.0;
    const uint64_t j0 = L * n_ - M * mMax;
    if (mMax >= taps) {
        for (uint64_t j = j0, m = mMax; j < taps; j += M, --m) y += firInt_[j] * hcRing_[m & (kHcRing - 1)];
    } else {
        for (uint64_t j = j0, m = mMax;; j += M) {
            if (j >= taps) break;
            y += firInt_[j] * hcRing_[m & (kHcRing - 1)];
            if (m == 0) break;
            --m;
        }
    }
    ++n_;
    outL = outR = y;
}

}  // namespace pvb
