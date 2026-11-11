// team2_family.h
#pragma once
#include <cmath>
#include <algorithm>
#include <numeric>

namespace fam2 {

struct Peak { double f, a; };

struct Hyp {
    double f, df, loga, dloga, uncertainty, phase, score;
    int missing;
};

struct Family {
    Hyp h[2];
    unsigned id;
    int selected, age;
    bool active;
};

struct Tracker {
    Family family[6];
    unsigned nextId;

    Tracker() { reset(); }

    static constexpr double dt = 16.0 / 3000.0;
    static constexpr double two_pi = 6.28318530717958647692;
    static constexpr int max_missing = 56; // floor(0.3 / dt) = 56 (0.29867s <= 0.3s)

    static double clamp_val(double v, double lo, double hi) {
        if (!(v >= lo && v <= hi)) return (v < lo) ? lo : ((v > hi) ? hi : lo);
        return v;
    }

    static double safe_log(double a) {
        double c = (a > 1e-12 && a < 1e12) ? a : ((a >= 1e12) ? 1e12 : 1e-12);
        return std::log(c);
    }

    static void init_hyp(Hyp& h, double f0, double loga0) {
        h.f = clamp_val(f0, 25.0, 200.0);
        h.df = 0.0;
        h.loga = clamp_val(loga0, -28.0, 28.0);
        h.dloga = 0.0;
        h.uncertainty = 2.0;
        h.phase = 0.0;
        h.score = 0.15;
        h.missing = 0;
    }

    static double score_hyp(double f, const Peak* pk, int valid_n) {
        double ev = 0.0;
        bool direct = false;
        int odd = 0, even = 0, order_gcd = 0;
        for (int k = 1; k <= 8 && k * f <= 615.0; ++k) {
            double tol = std::max(1.5, 0.015*k*f), best = tol;
            for (int q = 0; q < valid_n; ++q) best = std::min(best, std::fabs(pk[q].f - k * f));
            if (best >= tol) continue;
            order_gcd=std::gcd(order_gcd,k);
            double u = best / (0.45 * tol), fit = std::exp(-0.5 * u * u);
            if (k == 1) { direct = true; ev += 1.35 * fit; }
            else if (k & 1) { ++odd; ev += (0.55 / std::sqrt(double(k))) * fit; }
            else { ++even; ev += (0.50 / std::sqrt(double(k))) * fit; }
        }
        if (!direct) { if(order_gcd!=1)return 0.; if (odd && even) ev += 0.9; else ev *= 0.35; }
        return ev;
    }

    void reset() {
        nextId = 1;
        for (int i = 0; i < 6; ++i) {
            family[i].id = 0;
            family[i].selected = 0;
            family[i].age = 0;
            family[i].active = false;
            init_hyp(family[i].h[0], 50.0, -20.0);
            init_hyp(family[i].h[1], 25.0, -20.0);
        }
    }

    void step(const Peak* peaks, int n) {
        int np = (peaks && n > 0) ? ((n > 8) ? 8 : n) : 0;
        Peak pk[8];
        int valid_n = 0;
        for (int i = 0; i < np; ++i) {
            if (std::isfinite(peaks[i].f) && std::isfinite(peaks[i].a) &&
                peaks[i].f >= 20.0 && peaks[i].f <= 600.0 && peaks[i].a > 0.0) {
                pk[valid_n++] = peaks[i];
            }
        }
        // Sort descending by amplitude for deterministic seeding
        for (int i = 0; i < valid_n; ++i) {
            for (int j = i + 1; j < valid_n; ++j) {
                if (pk[j].a > pk[i].a) {
                    Peak tmp = pk[i];
                    pk[i] = pk[j];
                    pk[j] = tmp;
                }
            }
        }

        // 1. Predict all active families
        for (int i = 0; i < 6; ++i) {
            if (!family[i].active) continue;
            for (int m = 0; m < 2; ++m) {
                Hyp& h = family[i].h[m];
                h.f = clamp_val(h.f + h.df * dt, 25.0, 200.0);
                h.df = clamp_val(h.df * 0.92, -150.0, 150.0);
                h.loga = clamp_val(h.loga + h.dloga * dt, -28.0, 28.0);
                h.dloga = clamp_val(h.dloga * 0.90, -80.0, 80.0);
                h.uncertainty = clamp_val(h.uncertainty + 2.5 * dt, 0.25, 10.0);
            }
        }

        // 2. Soft competition per peak across existing active hypotheses (prevents global takeover)
        double peak_tot_w[8] = {0};
        for (int p = 0; p < valid_n; ++p) {
            for (int i = 0; i < 6; ++i) {
                if (!family[i].active) continue;
                for (int m = 0; m < 2; ++m) {
                    const Hyp& h = family[i].h[m];
                    for (int k = 1; k <= 8; ++k) {
                        double kf = k * h.f;
                        if (kf > 615.0) break;
                        double tol = std::min(k * std::max(1.2, std::min(3.5, h.uncertainty)) + 0.8, std::max(1.5,0.015*k*h.f));
                        double err = std::fabs(pk[p].f - kf);
                        if (err <= tol) {
                            double w = std::exp(-0.5 * (err / (0.45 * tol)) * (err / (0.45 * tol))) / k;
                            peak_tot_w[p] += w;
                        }
                    }
                }
            }
        }

        bool peak_claimed[8] = {false};
        bool hyp_direct[6][2] = {{false}};
        int prev_sel_arr[6] = {0};
        double prev_sel_f_arr[6] = {0.0};

        // 3. Correct each active family & select best hypothesis
        for (int i = 0; i < 6; ++i) {
            if (!family[i].active) continue;
            prev_sel_arr[i] = (family[i].selected == 1) ? 1 : 0;
            prev_sel_f_arr[i] = family[i].h[prev_sel_arr[i]].f;

            for (int m = 0; m < 2; ++m) {
                Hyp& h = family[i].h[m];
                double f_num = 0.0, f_den = 0.0;
                double best_loga = -28.0;
                bool has_f0 = false;
                int odd_cnt = 0, even_cnt = 0, harm_cnt = 0, order_gcd = 0;
                double raw_ev = 0.0;

                for (int k = 1; k <= 8; ++k) {
                    double kf = k * h.f;
                    if (kf > 615.0) break;
                    double tol = std::min(k * std::max(1.2, std::min(3.5, h.uncertainty)) + 0.8, std::max(1.5,0.015*k*h.f));
                    int best_p = -1;
                    double best_err = tol;
                    for (int p = 0; p < valid_n; ++p) {
                        double err = std::fabs(pk[p].f - kf);
                        if (err <= best_err) {
                            best_err = err;
                            best_p = p;
                        }
                    }
                    if (best_p >= 0) {
                        int p = best_p;
                        double u = best_err / (0.45 * tol);
                        double fit = std::exp(-0.5 * u * u);
                        double own_w = fit / k;
                        double share = own_w / (peak_tot_w[p] + 1e-9);
                        // Ownership is recomputed from the selected hypothesis after correction.

                        // Bounded amplitude evidence so a huge unrelated peak cannot pull a track
                        double la = safe_log(pk[p].a);
                        double amp_gate = 1.0; // Pitch fit independent of injected oracle amplitude.
                        double w_f = fit * (0.3 + 0.7 * share) * amp_gate / (double)(k * k);
                        f_num += w_f * (pk[p].f / k - h.f);
                        f_den += w_f;

                        double est_loga = la + 0.5 * std::log((double)k);
                        if (harm_cnt == 0 || est_loga > best_loga) best_loga = est_loga;

                        harm_cnt++;order_gcd=std::gcd(order_gcd,k);
                        if (k == 1) {
                            has_f0 = true;
                            raw_ev += 1.35 * fit * 1.0;
                        } else if (k & 1) {
                            odd_cnt++;
                            raw_ev += (0.55 / std::sqrt((double)k)) * fit * 1.0;
                        } else {
                            even_cnt++;
                            raw_ev += (0.50 / std::sqrt((double)k)) * fit * 1.0;
                        }
                    }
                }

                // Missing fundamental support requires coprime observed orders; odd/even adds prior evidence.
                bool mf_supported = (!has_f0 && order_gcd==1 && odd_cnt >= 1 && even_cnt >= 1 && (odd_cnt + even_cnt) >= 2);
                if (mf_supported) {
                    raw_ev += 0.90;
                } else if (!has_f0) {
                    raw_ev *= 0.35; // Penalize sub-octave f/2 when only even harmonics exist
                }

                if (harm_cnt > 0 && (has_f0 || mf_supported || (order_gcd==1 && raw_ev > 0.0))) {
                    double df_corr = clamp_val(f_num / (f_den + 1e-9), -8.0, 8.0);
                    double alpha_f = clamp_val(h.uncertainty / (h.uncertainty + 1.2), 0.15, 0.65);
                    double new_f = clamp_val(h.f + alpha_f * df_corr, 25.0, 200.0);
                    double inst_df = (new_f - h.f) / dt;
                    h.df = clamp_val(0.75 * h.df + 0.25 * inst_df, -150.0, 150.0);
                    h.f = new_f;

                    double l_err = clamp_val(best_loga - h.loga, -6.0, 6.0);
                    double new_loga = clamp_val(h.loga + 0.35 * l_err, -28.0, 28.0);
                    double inst_dloga = (new_loga - h.loga) / dt;
                    h.dloga = clamp_val(0.75 * h.dloga + 0.25 * inst_dloga, -80.0, 80.0);
                    h.loga = new_loga;

                    h.uncertainty = clamp_val(h.uncertainty * 0.72, 0.25, 10.0);
                    h.score = clamp_val(0.78 * h.score + 0.22 * raw_ev, 0.0, 5.0);
                    h.missing = 0;
                    hyp_direct[i][m] = has_f0;
                } else {
                    h.missing += 1;
                    h.score = clamp_val(h.score * 0.88, 0.0, 5.0);
                }

                // Pure phase integration (never FFT-phase pulled)
                h.phase = std::fmod(h.phase + two_pi * h.f * dt, two_pi);
                if (h.phase < 0.0) h.phase += two_pi;
            }
        }

        for (int i = 0; i < 6; ++i) {
            if (!family[i].active) continue;
            int prev_sel = prev_sel_arr[i];
            double prev_sel_f = prev_sel_f_arr[i];
            if(family[i].h[prev_sel].missing > max_missing){family[i].active=false;continue;}
            // Select between h[0] and h[1] with hysteresis; never use oracle amplitude
            int new_sel = prev_sel;
            int other = 1 - prev_sel;
            if (family[i].h[other].score > family[i].h[prev_sel].score + 0.18 &&
                family[i].h[other].missing <= family[i].h[prev_sel].missing) {
                bool blocked = false;
                if (family[i].h[prev_sel].missing <= max_missing) {
                    double fo = family[i].h[other].f;
                    for (int j = 0; j < 6; ++j) {
                        if (j == i || !family[j].active) continue;
                        int jsel = prev_sel_arr[j];
                        double fj = family[j].h[jsel].f;
                        if (family[j].h[jsel].missing <= max_missing &&
                            std::fabs(fo - fj) <= std::max(1.2, 0.012 * std::min(fo, fj))) {
                            blocked = true;
                            break;
                        }
                    }
                }
                if (!blocked) new_sel = other;
            }
            family[i].selected = new_sel;
            family[i].age += 1;

            // Substantial octave/frequency change on selected hypothesis -> new monotone ID
            double cur_sel_f = family[i].h[new_sel].f;
            double ratio = (prev_sel_f > 1e-6) ? (cur_sel_f / prev_sel_f) : 1.0;
            if (ratio > 1.35 || ratio < 0.74) {
                family[i].id = nextId++;
                family[i].age = 1;
            }

            // Expire after > 0.3s (missing > 56 steps)
            if (family[i].h[family[i].selected].missing > max_missing) {
                family[i].active = false;
            }
        }

        // Merge only converged duplicate fundamentals; unrelated births never terminate a voice.
        for(int i=0;i<6;++i)if(family[i].active)
          for(int j=i+1;j<6;++j)if(family[j].active){
            const double fi=family[i].h[family[i].selected].f,fj=family[j].h[family[j].selected].f;
            if(std::abs(fi-fj)<=std::max(1.2,.012*std::min(fi,fj))){
              int mi=family[i].h[family[i].selected].missing,mj=family[j].h[family[j].selected].missing;
              int lose=mi!=mj?(mi>mj?i:j):(family[i].age>=family[j].age?j:i);
              family[lose].active=false;
              if(lose==i)break;
            }
          }
        // 4. Re-check claimed peaks against updated active families to block harmonic duplicate births
        for (int p = 0; p < valid_n; ++p) {
            if (peak_claimed[p]) continue;
            for (int i = 0; i < 6; ++i) {
                if (!family[i].active) continue;
                if (family[i].h[family[i].selected].missing > 0) continue;
                double sf = family[i].h[family[i].selected].f;
                for (int k = 1; k <= 8; ++k) {
                    if (std::fabs(pk[p].f - k * sf) <= std::max(1.5,.015*k*sf)) {
                        peak_claimed[p] = true;
                        break;
                    }
                }
                if (peak_claimed[p]) break;
            }
        }

        // 5. Birth new families from unclaimed peaks (no global born termination of active slots)
        for (int step_b = 0; step_b < 6; ++step_b) {
            int slot = -1;
            for (int i = 0; i < 6; ++i) {
                if (!family[i].active) { slot = i; break; }
            }
            if (slot < 0) break; // All 6 slots active: never terminate existing active family

            int best_p = -1;
            double best_seed_f = 0.0, best_score = -1.0, best_amp = -1.0, best_sel_f = 0.0;

            auto consider_seed = [&](int p, double cand_f) {
                if (cand_f < 25.0 || cand_f > 200.0) return;
                double half_f = (cand_f * 0.5 >= 25.0) ? (cand_f * 0.5) : cand_f;
                double s0 = score_hyp(cand_f, pk, valid_n);
                double s1 = score_hyp(half_f, pk, valid_n);
                double sc = (s1 > s0) ? s1 : s0;
                double sf = (s1 > s0) ? half_f : cand_f;
                if (!(sc > 0.0)) return;
                // A chosen root must actually explain the unclaimed seeding peak.
                double order=std::round(pk[p].f/sf);
                if(order<1 || order>8 || std::fabs(pk[p].f-order*sf)>std::max(1.5,.015*order*sf))return;
                for(int j=0;j<6;++j)if(family[j].active){
                    double fj=family[j].h[family[j].selected].f;
                    if(std::fabs(sf-fj)<=std::max(1.2,.012*std::min(sf,fj)))return;
                }
                double amp = pk[p].a;
                if (best_p < 0 ||
                    sc > best_score + 1e-12 ||
                    (std::fabs(sc - best_score) <= 1e-12 &&
                     (amp > best_amp + 1e-12 ||
                      (std::fabs(amp - best_amp) <= 1e-12 && sf > best_sel_f + 1e-12)))) {
                    best_p = p;
                    best_seed_f = cand_f;
                    best_score = sc;
                    best_amp = amp;
                    best_sel_f = sf;
                }
            };

            for (int p = 0; p < valid_n; ++p) {
                if (peak_claimed[p]) continue;
                if (pk[p].f <= 200.0) consider_seed(p, pk[p].f);
                {
                    for (int k = 2; k <= 8; ++k) {
                        double cand_f = pk[p].f / k;
                        if (cand_f < 25.0 || cand_f > 200.0) continue;
                        consider_seed(p, cand_f);
                    }
                }
            }

            if (best_p < 0) break;

            double seed_f = best_seed_f;
            double la = safe_log(pk[best_p].a);
            Family& fam = family[slot];
            fam.active = true;
            fam.id = nextId++;
            fam.age = 1;
            fam.selected = 0;
            init_hyp(fam.h[0], seed_f, la);
            double half_f = (seed_f * 0.5 >= 25.0) ? (seed_f * 0.5) : seed_f;
            init_hyp(fam.h[1], half_f, la);

            fam.h[0].score = score_hyp(fam.h[0].f, pk, valid_n);
            fam.h[1].score = score_hyp(fam.h[1].f, pk, valid_n);
            fam.selected=fam.h[1].score>fam.h[0].score?1:0;
            const double selected_f=fam.h[fam.selected].f;
            // Mark support using the chosen fundamental, never discard the input observations.

            peak_claimed[best_p] = true;
            for (int q = 0; q < valid_n; ++q) {
                for (int k = 1; k <= 8; ++k) {
                    if (std::fabs(pk[q].f - k * selected_f) <= std::max(1.5,.015*k*selected_f)) {
                        peak_claimed[q] = true;
                        break;
                    }
                }
            }
        }
    }
};

} // namespace fam2
