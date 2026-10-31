# r3a-dev — Resultant research work files (scripts, briefs, numeric results)

Mirror of the WSL working folder `~/r3a-dev/` used for the Resultant core research (design doc: `docs/RESULTANT_CORE.md`;
hand-over: `docs/RESULTANT_HANDOFF.md`). Copied 2026-10-31 so that another session can follow the work from the repository.

**What is here**: scripts (`.py`, `.sh`), worker briefs, `CHOICES.md` (methods fixed before results), reviews, reports,
logs and numeric results (`.json`, `.txt`, `.log`), diffs of reverted C++ experiments (`*.diff`), and one blind-listening
export (`listen/`).

**What is NOT here (by rule)**: any audio (the user's music, synthetic `.wav`, Slakh/MUSDB stems), dataset copies, caches
(`.npz`, `.npy`, `.pkl`, `cache*/`), build outputs (`.so`), source snapshots (`verify_core/src_*`), files over 2 MB.
Scripts that read music read it in place from the paths they name; those files are not in the repository.

## Where each design-doc section's work lives

| Section | Folder |
|---|---|
| 12 acceptance of v1.5 | `verify_core/`, `core_results/` |
| 13 v1.6 diagnosis / gate | `diag16/`, `gate16/` |
| 14 look-ahead stage 0 | `la0/` |
| 16.x (attribution, ladders, silent voices, blinds) | `plan16/{A,A2,B,D,F,G,K,L,P,S,T,V}` |
| 18.3-18.7 v1.6-a | `plan16/V16A/` |
| 18.8-18.9 "쿠쿠쿵" diagnosis | `plan16/B1/` (incl. `b12/`), `plan16/F2/` |
| 18.10, 18.13 H-aux | `plan16/HAUX/` |
| 18.11 A5 amplitude slew | `plan16/A5/` (`a5.diff`) |
| 18.12-18.14 A5' phase pull | `plan16/A5P/` (the reference measurement code: `p_primary.py`, suite, `decide_p.py`) |
| 18.15-18.16 A5'' | `plan16/A5PP/` (`a5pp.diff`) |
| 17 app integration | `plan16/APP/` |
| 19.1 event attribution | `plan16/S19/` (top level) |
| 19.2 review | `plan16/S19/R/` |
| 19.3 stage 0 oracle | `plan16/S19/O/` |
| 19.4 nFuture grid | `plan16/S19/NF/` |
| 19.5 metric leakage check | `plan16/S19/L/` |
| 19.6.1-19.8 layer high-pass (v1.6-c) | `plan16/S19/H/`, `plan16/S19/HP/` |
| 19.9 app chain / limiter at +6 dB | `plan16/S19/LIM/` |
| 19.11 Beyond / Last Carnival | `plan16/S19/BY/` |
| 19.12 level trim | `plan16/S19/TR/` |
| 19.13 slew re-test / a_2 oracle | `plan16/S19/SL/` |
| app models 16 (v1.6-b, v1.6-c), trim, slider | `plan16/APP16/` |
| 19.10 blind export | `listen/pvb_live_ab_20261031_220913.json` |

Paths inside the scripts are WSL paths (`/home/ksysh/...`, `/mnt/c/...`). Libraries are built from the repository with the
harness CMake into `tools/pvb-harness/build_*` (untracked); each report names the commit and build directory it used.
