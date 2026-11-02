"""Audit fixed result set, preserve sources, commit local code only."""
from pathlib import Path
import json,hashlib,shutil,subprocess,datetime
O=Path.home()/'r3a-dev/plan16/s66';W=Path.home()/'r3-s66';G=Path('/mnt/c/Users/ksysh/rootnote-duo/gpt-cli')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 summary=json.loads((O/'SUMMARY.json').read_text());assert summary['complete'] and summary['n']==87
 rows=[]
 for p in sorted((O/'v1_preserved/results').glob('*.json')):
  old=json.loads(p.read_text());new=json.loads((O/'results'/p.name).read_text())
  for name in old['variants']:
   a=old['variants'][name];b=new['variants'][name];assert a['engine']['pcm_sha256']==b['engine']['pcm_sha256']
   for key in ['Qweak','Qwhole','family_power','family_layer_power','N1_mixed_db','F']:
    assert a['contexts']['digital']['metrics'][key]==b['contexts']['digital']['metrics'][key],(p,name,key)
   rows.append(dict(id=old['id'],variant=name,raw_pcm_sha_equal=True,primary_digital_metrics_equal=True))
 (O/'DIGITAL_PRESERVATION.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
 fixture=json.loads((O/'kit_fixture/analysis.json').read_text());assert fixture['sync']['matched']==fixture['sync']['expected']==12 and fixture['clipped_samples']==0
 for c in fixture['controls']:assert c['delta_db'] is not None and abs(c['delta_db']-c['expected_digital_db'])<.001
 (O/'KIT_ANALYZER_QA.json').write_text(json.dumps(dict(sync=fixture['sync'],controls=fixture['controls'],clipping=0,flat_probe_correctly_unidentifiable=all(r.get('reason')=='no_identifiable_recovery_below_0_25dB' for r in fixture['recovery_fits']),scope='digital fixture only, no15cm measurement'),indent=2)+'\n',encoding='utf-8')
 # Record source revisions in work directory; only code+reproduction README enter git.
 dest=W/'tools/pvb-harness/s66';dest.mkdir(parents=True,exist_ok=True)
 for p in sorted(G.glob('s66_*.py')):
  shutil.copy2(p,O/p.name);shutil.copy2(p,dest/p.name)
 shutil.copy2(O/'common66.py',dest/'common66_frozen.py')
 readme='''# s66 phone-aware allocation research (local only)

Base9d408fb. This directory contains startup-only/default-off host controls and
reproduction scripts. No room recording, original music, rendered song audio,
private report, dataset, model result, app build or release is committed here.
The three controls are C1 ratio allocation,C2 burst-history allocation and C3
band allocation. The pre-existing20ms-release T is a diagnostic comparator.
Native latency stays7140 samples. Live mode transitions are not a supported API.

Authoritative frozen protocol, correction chronology, fits and results live in
`~/r3a-dev/plan16/s66/`. Read REGISTRATION.md/json,MODEL_CORRECTION_v2*,
MODEL_DOMAIN_v21*,CORRECTIONS,NA_CORRECTION and PREFETCH_* before interpreting
anything. Original V1 and intermediate uncensored V2 results remain preserved.
The final model fails screening; no transferred efficacy/adoption is established.

Environment: Ubuntu-24.04 WSL,`~/venv-rootnote/bin/python`,CPU<=6 threads,
BLAS1. Scripts deliberately bind to the existing exposed DEV/frozen-helper
workspace and in-place listen paths. They never enumerate dataset validation/test.
No network install or playback is needed. Reproduction is an existing-workspace
workflow,not a standalone dataset distribution.

Fresh setup (before the local commit; do not overwrite an active experiment):
`python s66_setup.py` then `python s66_engine.py`.
Original fit: `python s66_phone.py`; preserve V1 before the exploratory correction
with `python s66_phone_v2.py`. The current v2 module applies the separately
registered v2.1 restriction: exclude the unidentifiable input component<150Hz.
It does not predict fundamental preservation or low-frequency phone response.
Run `python s66_validate_v2.py` to test the actual reconstructed waveform.

Verify native controls with `python s66_eval.py --proof` and
`python s66_eval.py --thread-proof`. Run at most these two worker commands:
`python s66_eval.py --rest --shards 2 --shard 0`
`python s66_eval.py --rest --shards 2 --shard 1`
Each worker has a main scoring thread and two native prefetch threads; each uses
three CPU affinity slots. The original serial implementation is preserved in the
work directory. All weak-mask absence is N/A,not zero or silent exclusion.
Then `python s66_summary.py`, `python s66_detail.py`, `python s66_qa.py`.
The QA rebuilds to build_final without overwriting the evaluated shared library,
and checks final host PCM identity and native syntax without the research macro.
This native syntax check is not an Android app build.

Prepare only: `python s66_kit.py`. This writes the synthetic247s WAV,map,Korean
measurement instructions and analyzer to Windows`rootnote-duo/listen/s66/`.
There is no playback call. Analyzer usage:
`python analyze_s66.py /path/to/recording.wav --out /path/to/s66_analysis`
The waveform contains independent silence,12 sync chirps,tone steps/bursts,
identical/+4 controls and5s identical recovery probes after loud/quiet conditions.
Run the analyzer on the synthetic WAV only as a digital fixture; actual15cm
acquisition is a future user mic session. Noise floor,SNR,clipping and affine
clock checks precede tone-level and phenomenological recovery interpretation.

`python s66_plot.py` creates diagnostics; `s66_report_write.py` writes the Korean
report/section outside git after LOCAL_COMMIT.json is recorded. No push,merge,
CORE edit,private-repository commit or app integration is part of these scripts.
'''
 (dest/'README.md').write_text(readme,encoding='utf-8')
 subprocess.run(['git','-C',str(W),'diff','--check'],check=True)
 names=subprocess.check_output(['git','-C',str(W),'status','--porcelain','--untracked-files=all']).decode().splitlines()
 assert not any(Path(line[3:]).suffix.lower() in {'.wav','.flac','.mp3','.pcm','.npz','.so','.png'} for line in names),names
 paths=['app/src/main/cpp/libpvb/pvb_allocation66.h','app/src/main/cpp/libpvb/pvb_engine.h','app/src/main/cpp/libpvb/pvb_engine.cpp','app/src/main/cpp/libpvb/pvb_layer_peak42.h','tools/pvb-harness/pvb_capi.cpp','tools/pvb-harness/s66']
 subprocess.run(['git','-C',str(W),'add','--']+paths,check=True)
 (O/'final_source.diff').write_bytes(subprocess.check_output(['git','-C',str(W),'diff','--cached']))
 subprocess.run(['git','-C',str(W),'diff','--cached','--check'],check=True)
 subprocess.run(['git','-C',str(W),'commit','-m','research(s66): add default-off phone-aware allocation experiments','-m','Add three startup-only host allocation controls within the existing native schedule, a coarse phone-transfer evaluator and reproducible DEV and synthetic-characterisation tooling. Model corrections remain exploratory and do not establish phone benefit. No app integration or playback.'],check=True)
 head=subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD']).decode().strip();status=subprocess.check_output(['git','-C',str(W),'status','--porcelain']).decode();assert not status,status
 result=dict(commit=head,branch='research/s66-20261102',base='9d408fb38b16f4dc8078ec809d7ccbbefae6a2b9',local_only=True,worktree_clean=True,no_push=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 (O/'LOCAL_COMMIT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(result)
if __name__=='__main__':main()
