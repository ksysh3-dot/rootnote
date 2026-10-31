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
#include <cmath>
#include <complex>
#include <initializer_list>

#include "pvb_dsp.h"
#include "pvb_simd.h"
#include "pvb_vb_tables.h"

namespace pvb {
bool VbHpv::setAlpha2Profile(int algorithm) {
    unsigned flags=0;int mode=3;
    switch(algorithm) {
        case VB_ALPHA2_P1: case VB_ALPHA2_P1_PLUS: case VB_ALPHA2_P1PP: case VB_ALPHA2_P1PP_V03: break;
        case VB_RESULTANT: case VB_RESULTANT_V16: break;   // P1 settings with every research flag fixed at 0 (below), the sustained path is the new core's
        case VB_ALPHA2_P1_C1: flags=StageNominalPower;break;
        case VB_ALPHA2_D2: flags=StageShortDetail|StageConditionalGain;break;
        case VB_ALPHA2_J2: flags=StageShortDetail|StageConditionalGain|StageAmFamily|StageFamilyFilterComp;break;
        case VB_ALPHA2_OSC: mode=0;flags=StageOscillator;break;
        case VB_ALPHA2_OSC_CORRECT: mode=0;flags=StageOscillator|StageOscillatorCorrect;break;
        default:return false;
    }
    const bool resultant=algorithm==VB_RESULTANT || algorithm==VB_RESULTANT_V16;
    p1PlusProfile_=algorithm==VB_ALPHA2_P1 || algorithm==VB_ALPHA2_P1_PLUS || algorithm==VB_ALPHA2_P1PP ||
                   algorithm==VB_ALPHA2_P1PP_V03 || algorithm==VB_ALPHA2_P1_C1 || resultant;
    // 6: the original P1 (or the host's research flags); 11: P1+ (flags 6); 12: P1++ v0.2 (flags 6, impact 4);
    // 13: P1++ v0.3 (flags 6, impact 8); 14: P1 + C1 (no P1+ flags, impact 0, power-sum nominal amplitude);
    // 15, 16: Resultant core (P1 with no research flags: fixed like 14, so later host setters cannot change them)
    p1PlusFixed_=algorithm==VB_ALPHA2_P1_PLUS || algorithm==VB_ALPHA2_P1PP || algorithm==VB_ALPHA2_P1PP_V03 ||
                 algorithm==VB_ALPHA2_P1_C1 || resultant;
    p1PlusFlags_=algorithm==VB_ALPHA2_P1_C1 || resultant ? 0u : p1PlusFixed_ ? 6u : p1PlusHostFlags_;
    p1ppImpactMode_=algorithm==VB_ALPHA2_P1PP_V03 ? 8 : algorithm==VB_ALPHA2_P1PP ? 4 :
                    algorithm==VB_ALPHA2_P1_PLUS || algorithm==VB_ALPHA2_P1_C1 || resultant ? 0 : p1ppHostImpact_;
    p1ppV04_=p1PlusFixed_ ? 0u : p1ppV04Host_;
    modulationMode_=mode;tonalOnly_=false;continuity_=ContinuityParams{};continuity_.enabled=true;
    applyDevContinuity();
    // Resultant core: gen_ (host research, survives profile switches) is not used by algorithms 15 and 16; it comes back,
    // as the host or the engine last asked for it (genReq_), with the next other profile. Only a switch into or out of
    // the pair touches it, so the other profiles stay exactly as they were.
    if(resultant!=resultantOn_) {
        resultantOn_=resultant;
        gen_=resultantOn_?GenResearch52{}:genReq_;
    }
    // Algorithm 16 is 15 with the v1.6-b parameters (5.8 order: voicing .. maxDfdtBirth at the defaults, then capRho 1.5,
    // windowCreep 16, creepMode 2); every other profile, 15 included, gets the pvb_resultant.h defaults back after a 16.
    if(algorithm==VB_RESULTANT_V16) {
        const double v16[ResultantCore::kParams]={0,0,0,15,22,6,8,30,.05,.1,1.0,30,24,.03,0,200,1.5,16,2};
        resultant_.setParams(v16,ResultantCore::kParams);
        resultantV16_=true;
    } else leaveResultantV16();
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

VbHpv::VbHpv(bool masked, bool gentle, int upperMode)
    : masked_(masked), gentle_(gentle), upperMode_(upperMode) {
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
    upperPolicy_.reset();
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
    resultant_.reset();
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
void VbHpv::pvFrame() {
    const int64_t i = static_cast<int64_t>(i_);
    const int64_t s0 = i - (kPvN - 1);
    const int half = kPvN / 2;
    double frame[kPvN];
    for (int n = 0; n < kPvN; ++n) frame[n] = bhRing_[(s0 + n) & (kRing - 1)] * winPv_[n];
    // zero-phase arrangement fr = [frame[half:], zeros, frame[:half]] (2048 points), real FFT: the even samples go into
    // the real and the odd ones into the imaginary part of a 1024-point complex FFT. Only the bins 25..200 Hz are used.
    const int nb = hiBin_ - loBin_;
    std::fill(std::begin(zr_), std::end(zr_), 0.0);
    std::fill(std::begin(zi_), std::end(zi_), 0.0);
    auto put = [&](int pos, double v) {
        const int j = bitrev_[pos >> 1];
        if (pos & 1) zi_[j] = v; else zr_[j] = v;
    };
    for (int n = 0; n < half; ++n) {
        put(n, frame[half + n]);
        put(kPvNfft - half + n, frame[n]);
    }
    fftHalf();
    double mag[256], Xr[256], Xi[256];
    double mx = 0.0;
    for (int b = 0; b < nb; ++b) {
        const int k = loBin_ + b;                 // 0 < k < 1024
        const double ar = zr_[k], ai = zi_[k];
        const double br = zr_[kHalfFft - k], bi = -zi_[kHalfFft - k];   // conj(Z[N - k])
        const double er = 0.5 * (ar + br), ei = 0.5 * (ai + bi);         // even part
        const double dr = 0.5 * (ar - br), di = 0.5 * (ai - bi);
        const double orr = di, oi = -dr;                                 // odd part = (Z - conj Z') / 2i
        const double wr = cosPv_[k], wi = -sinPv_[k];                    // exp(-2 pi i k / 2048)
        Xr[b] = er + (orr * wr - oi * wi);
        Xi[b] = ei + (orr * wi + oi * wr);
        mag[b] = std::hypot(Xr[b], Xi[b]);
        if (b == 0 || mag[b] > mx) mx = mag[b];
    }
    if (nb == 0 || mx * 2.0 / pvWsum_ < pvAbs_) {
        nTracks_ = 0;
        return;
    }
    int lm[256], nl = 0;
    for (int b = 1; b < nb - 1; ++b)
        if (mag[b] >= mag[b - 1] && mag[b] > mag[b + 1]) lm[nl++] = b;
    if (nl == 0) {
        nTracks_ = 0;
        return;
    }
    // descending by magnitude (stable ascending sort, then reversed, like argsort(...)[::-1] on small arrays)
    for (int a = 1; a < nl; ++a) {
        const int x = lm[a];
        int j = a - 1;
        while (j >= 0 && mag[lm[j]] > mag[x]) {
            lm[j + 1] = lm[j];
            --j;
        }
        lm[j + 1] = x;
    }
    std::reverse(lm, lm + nl);
    const double thr = mx * pvRel_;
    double pf[kMaxPeaks], pa[kMaxPeaks], pph[kMaxPeaks];
    int np = 0;
    const int maxPeaks = std::min(params.pvMaxPeaks, kMaxPeaks);
    for (int o = 0; o < nl; ++o) {
        const int b = lm[o];
        if (mag[b] < thr || np >= maxPeaks) break;
        const double a_ = std::log(mag[b - 1] + 1e-30), b_ = std::log(mag[b] + 1e-30), c_ = std::log(mag[b + 1] + 1e-30);
        const double den = a_ - 2.0 * b_ + c_;
        double off = std::fabs(den) > 1e-12 ? 0.5 * (a_ - c_) / den : 0.0;
        off = clampv(off, -1.0, 1.0);
        const double fp = (loBin_ + b) * binHz_ + off * (binHz_ - 0.0);
        const double ap = std::exp(b_ - 0.25 * (a_ - c_) * off) * 2.0 / pvWsum_;
        const double ph = std::atan2(Xi[b], Xr[b]);
        bool near = false;
        for (int q = 0; q < np; ++q)
            if (std::fabs(fp - pf[q]) < params.pvPeakMinSepHz) near = true;
        if (near) continue;
        pf[np] = fp;
        pa[np] = ap;
        pph[np] = ph;
        ++np;
    }
    double grain[2 * kPvH] = {};
    double agrain = 0.0;
    Track next[kMaxPeaks];
    int nNext = 0;
    bool used[kMaxPeaks] = {};
    for (int p = 0; p < np; ++p) {
        const double fp = pf[p], ap = pa[p], ph = pph[p];
        int best = -1;
        for (int t = 0; t < nTracks_; ++t) {
            if (used[t]) continue;
            if (std::fabs(tracks_[t].f - fp) < params.pvTrackTol * fp &&
                (best < 0 || std::fabs(tracks_[t].f - fp) < std::fabs(tracks_[best].f - fp)))
                best = t;
        }
        double Phi = ph;
        if (best >= 0) {
            used[best] = true;
            const double pred = tracks_[best].phi + kPi * (tracks_[best].f + fp) * kPvH / kFsd;
            Phi = ph + 2.0 * kPi * std::nearbyint((pred - ph) / (2.0 * kPi));
        }
        next[nNext++] = Track{fp, Phi};
        double wk[kKMax - 1], gk;
        lookup(fp, wk, gk);
        const double amp = ap * gk;
        for (int k = 2; k <= kKMax; ++k) {
            const double w = wk[k - 2];
            if (!(w > params.harmonicMinWeight)) continue;
            const double aw = amp * w;
            for (int g = 0; g < 2 * kPvH; ++g) {
                const double phase = Phi + 2.0 * kPi * fp * static_cast<double>(g - kPvH) / kFsd;
                grain[g] += aw * std::cos(k * phase + vbt::kPsi[k - 2]);
            }
        }
        agrain += ap;
    }
    for (int t = 0; t < nNext; ++t) tracks_[t] = next[t];
    nTracks_ = nNext;
    const int64_t c = s0 + kPvN;  // grain centre
    for (int g = 0; g < 2 * kPvH; ++g) {
        const int64_t t = c - kPvH + g;
        pvOut_[t & (kRing - 1)] += grain[g] * gw_[g];
        pvApv_[t & (kRing - 1)] += agrain * gw_[g];
    }
}

double VbHpv::core(double d) {
    if (masked_) return core52(d);
    const int64_t i = static_cast<int64_t>(i_);
    double b = d;
    for (auto& s : band_) b = s.tick(b);
    bRing_[i & (kRing - 1)] = b;
    if ((i + 1) % kHpHop == 0) hpssFrame();

    // HPSS outputs, delayed by N - 1 = 191 (final at this point)
    double bh = 0.0, bp = 0.0;
    if (i >= kHpN - 1) {
        const int64_t t = i - (kHpN - 1);
        const int slot = static_cast<int>(t & (kRing - 1));
        const double ws = wsumHp_[t % kHpHop];
        bh = olaH_[slot] / ws;
        bp = olaP_[slot] / ws;
        olaH_[slot] = olaP_[slot] = 0.0;
    }
    double hr, hi, pr, pim;
    hilH_.tick(bh, hr, hi);
    hilP_.tick(bp, pr, pim);
    bhRing_[i & (kRing - 1)] = bh;
    aRing_[i & (kRing - 1)] = std::hypot(hr, hi);
    hpRing_[i & (kRing - 1)] = bandLayer(pr, pim);
    if (i >= kPvN - 1 && (i - (kPvN - 1)) % kPvH == 0) pvFrame();

    // output stage at t = i - 15: every grain that touches t is in
    double y = 0.0;
    if (i >= kRtShift) {
        const int64_t t = i - kRtShift;
        const int slot = static_cast<int>(t & (kRing - 1));
        const double out = pvOut_[slot], apv = pvApv_[slot];
        pvOut_[slot] = pvApv_[slot] = 0.0;
        const int half = kPvN / 2;
        const double aDel = t >= half ? aRing_[(t - half) & (kRing - 1)] : 0.0;
        const double As = envA_.tick(aDel);
        const double Ps = envP_.tick(apv);
        const double g = clampv(As / (Ps + 1e-9), 0.0, params.envCap) * (apv > 0.0 ? 1.0 : 0.0);
        const double hpd = t >= half ? hpRing_[(t - half) & (kRing - 1)] : 0.0;
        y = out * g + hpd;
    }
    for (auto& s : out_) y = s.tick(y);
    ++i_;
    return y;
}

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

// ================================================================================================ Bankstown
// Port of Bankstown by James Calligeros, https://github.com/chadmed/bankstown. Copyright 2023 James Calligeros,
// MIT License (full notice: app/src/general/assets/licenses/THIRD_PARTY.txt).

VbBankstown::Biquad VbBankstown::rbj(double fs, double f, bool lowpass) {
    const double q = 1.0 / std::sqrt(2.0);
    const double w = 2.0 * kPi * f / fs;
    const double al = std::sin(w) / (2.0 * q);
    const double c = std::cos(w);
    const double a0 = 1.0 + al;
    Biquad b;
    if (lowpass) {
        b.b0 = (1.0 - c) / 2.0 / a0;
        b.b1 = (1.0 - c) / a0;
        b.b2 = (1.0 - c) / 2.0 / a0;
    } else {
        b.b0 = (1.0 + c) / 2.0 / a0;
        b.b1 = -(1.0 + c) / a0;
        b.b2 = (1.0 + c) / 2.0 / a0;
    }
    b.a1 = -2.0 * c / a0;
    b.a2 = (1.0 - al) / a0;
    return b;
}

bool VbBankstown::configure(int sampleRate) {
    sr_ = sampleRate;
    const double fs = sampleRate;
    const double top = 0.45 * fs;
    for (int c = 0; c < 2; ++c) {
        hp_[c] = rbj(fs, std::min(params.floorHz, top), false);
        lp_[c] = rbj(fs, std::min(params.ceilHz, top), true);
        hpOut_[c] = rbj(fs, std::min(params.finalHpHz, top), false);
        lpOut_[c] = rbj(fs, std::min(3.0 * params.ceilHz, top), true);
    }
    k_ = kPi / (0.5 + 2.718281828459045);
    reset();
    return sampleRate >= 8000;
}

void VbBankstown::reset() {
    for (int c = 0; c < 2; ++c)
        for (Biquad* b : {&hp_[c], &lp_[c], &hpOut_[c], &lpOut_[c]}) b->z0 = b->z1 = 0.0;
}

inline double VbBankstown::chan(int c, double x) {
    const double p = lp_[c].tick(hp_[c].tick(x));
    const double sat = k_ * (params.blend * std::tanh(params.s3 * p) +
                             (1.0 - params.blend) * std::tanh(params.s2 * p) * (p <= 0.0 ? 1.0 : 0.0));
    return lpOut_[c].tick(hpOut_[c].tick(params.amt * sat));
}

void VbBankstown::tick(double inL, double inR, double& outL, double& outR) {
    outL = chan(0, inL);
    outR = chan(1, inR);
    // keep the filter states out of the denormal range in long silences
    for (int c = 0; c < 2; ++c)
        for (Biquad* b : {&hp_[c], &lp_[c], &hpOut_[c], &lpOut_[c]}) {
            if (std::fabs(b->z0) < 1e-25) b->z0 = 0.0;
            if (std::fabs(b->z1) < 1e-25) b->z1 = 0.0;
        }
}

}  // namespace pvb


