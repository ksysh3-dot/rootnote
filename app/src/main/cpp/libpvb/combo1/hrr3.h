#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstddef>

namespace hrr3 {

constexpr double kTau = 0.200;
constexpr double kDt = 16.0 / 3000.0;
constexpr std::size_t kMaxSnapshots = 12;
constexpr std::size_t kNumHarmonics = 7;

struct State {
    unsigned id = 0;
    std::int64_t stamp = -1;
    double emitted[kNumHarmonics]{};
    double rawPower = 0.0;
    double previousRawPower = 0.0;

    constexpr void reset() noexcept {
        id = 0;
        stamp = -1;
        for (std::size_t j = 0; j < kNumHarmonics; ++j) {
            emitted[j] = 0.0;
        }
        rawPower = 0.0;
        previousRawPower = 0.0;
    }
};

struct Snapshot {
    unsigned id = 0;
    double f = 0.0;
    double life = 0.0;
    double rawPower = 0.0;
    double previousRawPower = 0.0;
    std::int64_t stamp = -1;
    bool active = false;
};

inline double sanitizeNonNegative(double v) noexcept {
    if (!std::isfinite(v) || v <= 0.0) {
        return 0.0;
    }
    return v;
}

inline bool isHarmonicRatio(double childF, double parentF) noexcept {
    if (!std::isfinite(childF) || !std::isfinite(parentF) || childF <= 0.0 || parentF <= 0.0) {
        return false;
    }
    // 50 cents = 2^(50/1200) = 2^(1/24)
    const double kTol = std::exp2(1.0 / 24.0);
    const double ratio = childF / parentF;
    for (int k = 2; k <= 8; ++k) {
        const double low = static_cast<double>(k) / kTol;
        const double high = static_cast<double>(k) * kTol;
        if (ratio >= low && ratio <= high) {
            return true;
        }
    }
    return false;
}

inline const Snapshot* findParent(
    unsigned childId,
    double childF,
    std::int64_t now,
    const Snapshot* snapshots,
    std::size_t count) noexcept
{
    if (!snapshots || !std::isfinite(childF) || childF <= 0.0) {
        return nullptr;
    }
    const std::size_t n = (count > kMaxSnapshots) ? kMaxSnapshots : count;
    const Snapshot* best = nullptr;
    for (std::size_t i = 0; i < n; ++i) {
        const Snapshot& s = snapshots[i];
        if (!s.active || s.id == childId) {
            continue;
        }
        if (s.stamp != now - 16) {
            continue;
        }
        if (!std::isfinite(s.life) || s.life <= 0.0 || !std::isfinite(s.f) || s.f <= 0.0) {
            continue;
        }
        if (!isHarmonicRatio(childF, s.f)) {
            continue;
        }
        if (!best || s.f < best->f || (s.f == best->f && s.id < best->id)) {
            best = &s;
        }
    }
    return best;
}

inline double computeParentRmsRatio(const Snapshot* parent) noexcept {
    if (!parent) {
        return 0.0;
    }
    const double prev = parent->previousRawPower;
    const double curr = parent->rawPower;
    if (!std::isfinite(prev) || prev <= 0.0 || !std::isfinite(curr) || curr <= 0.0) {
        return 0.0;
    }
    const double ratio = std::sqrt(curr / prev);
    if (!std::isfinite(ratio)) {
        return 0.0;
    }
    return std::min(1.0, ratio);
}

inline void beginTrackStep(State& state, unsigned trackId, std::int64_t now) noexcept {
    const bool discontinuous = (state.id != trackId) || (state.stamp != now - 16);
    if (discontinuous) {
        state.id = trackId;
        state.rawPower = 0.0;
        state.previousRawPower = 0.0;
    } else {
        state.previousRawPower = sanitizeNonNegative(state.rawPower);
        state.rawPower = 0.0;
    }
    if (discontinuous) {
        for (std::size_t j = 0; j < kNumHarmonics; ++j) {
            state.emitted[j] = 0.0;
        }
    }
    state.stamp = now;
}

inline double processOne(State& state,int j,double target,double decay) noexcept {
    target=sanitizeNonNegative(target);
    state.rawPower+=target*target;
    const double out=std::max(target,sanitizeNonNegative(state.emitted[j])*decay);
    state.emitted[j]=out;return out;
}
inline void processTrackHarmonics(
    bool enabled,
    State& state,
    unsigned trackId,
    double trackF,
    double trackLife,
    bool fastEnding,
    std::int64_t now,
    const Snapshot* snapshots,
    std::size_t snapshotCount,
    const double targets[kNumHarmonics],
    const double weights[kNumHarmonics],
    double out[kNumHarmonics],
    double tau = kTau) noexcept
{
    if (!enabled) {
        for (std::size_t j = 0; j < kNumHarmonics; ++j) {
            const double w = weights ? weights[j] : 1.0;
            if (!std::isfinite(w) || w <= 1e-4) {
                out[j] = 0.0;
            } else {
                out[j] = sanitizeNonNegative(targets[j]);
            }
        }
        return;
    }

    beginTrackStep(state, trackId, now);

    const bool bypassRelease = (!std::isfinite(trackLife) || trackLife <= 0.0 || fastEnding);
    const Snapshot* parent = bypassRelease
        ? nullptr
        : findParent(trackId, trackF, now, snapshots, snapshotCount);

    const double r = parent ? computeParentRmsRatio(parent) : 0.0;
    const double decay = (parent && std::isfinite(tau) && tau > 0.0)
        ? std::exp(-kDt / tau) * r
        : 0.0;

    for (std::size_t j = 0; j < kNumHarmonics; ++j) {
        const double w = weights ? weights[j] : 1.0;
        const bool weightZero = (!std::isfinite(w) || w <= 1e-4);
        const double t = weightZero ? 0.0 : sanitizeNonNegative(targets[j]);

        state.rawPower += t * t;

        if (weightZero) {
            out[j] = 0.0;
            state.emitted[j] = 0.0;
            continue;
        }

        double val = t;
        if (parent) {
            const double prevE = sanitizeNonNegative(state.emitted[j]);
            const double released = prevE * decay;
            if (released > val) {
                val = released;
            }
        }
        out[j] = val;
        state.emitted[j] = val;
    }
}

inline Snapshot makeSnapshot(
    const State& state,
    double f,
    double life,
    bool active) noexcept
{
    Snapshot s;
    s.id = state.id;
    s.f = sanitizeNonNegative(f);
    s.life = std::isfinite(life) ? life : 0.0;
    s.rawPower = sanitizeNonNegative(state.rawPower);
    s.previousRawPower = sanitizeNonNegative(state.previousRawPower);
    s.stamp = state.stamp;
    s.active = active && (s.life > 0.0);
    return s;
}

} // namespace hrr3
