"""Native final-source equivalence, input persistence, kit and scope QA."""
from pathlib import Path
import subprocess,json,hashlib,shutil,datetime,sys,os
H=Path.home();P=H/'r3a-dev/plan16';O=P/'s66';W=H/'r3-s66';SRC=Path('/mnt/c/Users/ksysh/rootnote-duo/gpt-cli')
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(name,v):(O/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 ids=json.loads((O/'IDS.json').read_text());assert all((O/'results'/(v+'.json')).exists() for v in ids)
 cmd=json.loads((O/'BUILD_COMMAND.json').read_text());final=O/'build_final/libpvbcapi.so';final.parent.mkdir(exist_ok=True);cmd[-1]=str(final)
 with (O/'build_final/build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 # Native-only syntax check without research macro. No APK/Gradle/app build.
 syntax=[a for a in cmd[:-2] if a not in ['-shared','-fPIC','-DPVB_HOST_RESEARCH=1']]+['-fsyntax-only']
 with (O/'build_final/nonresearch_syntax.log').open('w') as f:subprocess.run(syntax,stdout=f,stderr=subprocess.STDOUT,check=True)
 sys.path.insert(0,str(SRC));import s66_eval as E
 t=E.np.arange(E.FS*3)/E.FS;rng=E.np.random.default_rng(6612);x=E.np.column_stack([.3*E.np.sin(2*E.np.pi*63*t),.24*E.np.sin(2*E.np.pi*117*t)]).astype(E.np.float32);x+=rng.normal(0,.02,x.shape).astype(E.np.float32)
 eq=[]
 for name in ['P1','B','T','C1','C2','C3']:
  a,b,e=E.capture(x,name);c,d,f=E.capture(x,name,path=final)
  assert E.np.array_equal(a,c) and E.np.array_equal(b,d) and e['latency']==f['latency'];eq.append(dict(variant=name,pcm_equal=True,layer_equal=True,latency=e['latency']))
 # Default-off V0 at44.1kHz as well. Allocation setter correctly rejects non48kHz.
 rate=[]
 for sr in [44100,48000]:
  lib=E.C55.bind(final);lib.pvb_set_allocation66.argtypes=[E.C.c_void_p,E.C.c_int,E.C.c_int,E.C.c_int];lib.pvb_set_allocation66.restype=E.C.c_int
  eng=E.C55.T.Engine(lib,sr,vb_on=1,vb_algo=6,vb_level_db=0,out_db=-5,ramp_ms=0)
  assert lib.pvb_set_allocation66(eng.h,4,1,100)==0
  assert lib.pvb_set_allocation66(eng.h,1,1,100)==int(sr==48000)
  eng.close();rate.append(dict(sample_rate=sr,invalid_mode_rejected=True,allocation_rate_gate=True))
 saved_fs=E.C55.FS;E.C55.FS=44100
 try:
  a,b,e=E.C55.capture(x[:88200],on=False,path=final,raw=True);c,d,f=E.C55.capture(x[:88200],on=False,path=E.BASE,raw=True)
  assert E.np.array_equal(a,c) and E.np.array_equal(b,d);rate.append(dict(test='44100_default_off_V0',pcm_equal=True,layer_equal=True))
 finally:E.C55.FS=saved_fs
 inputs=json.loads((O/'INPUTS.json').read_text());persistence=[]
 for item in inputs['recordings']+[inputs['digital']]:
  h=sha(item['path']);assert h==item['sha256'];persistence.append(dict(path=item['path'],sha256=h,unchanged=True))
 rows=[json.loads((O/'results'/(v+'.json')).read_text()) for v in ids];split=json.loads((P/'s46/SPLIT_FROZEN.json').read_text());assert set(ids)<=set(split['dev']);assert not set(ids)&set(split['excluded_confirm_ids'])
 for r in rows:
  assert all(v['engine']['latency']==7140 for v in r['variants'].values())
  assert r['source']['mix_sha256']==sha(r['source']['item']['mix'])
 kit=Path('/mnt/c/Users/ksysh/rootnote-duo/listen/s66');mp=json.loads((kit/'segment_map.json').read_text());assert mp['duration_s']<=300 and not mp['played'];assert sha(kit/'s66_phone_characterisation_15cm.wav')==mp['sha256']
 dump('FINAL_QA.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),n=len(rows),nonresearch_native_syntax=True,host_guard_fix_equivalence=eq,rate_gate_checks=rate,input_persistence=persistence,all_native_latency_7140=True,dev_only=True,validation_test_enumeration=False,recordings_read_in_place=True,room_audio_in_git=False,app_build=False,push=False,kit_played=False,kit_duration_s=mp['duration_s'],threads='2 processes x main+2 prefetch threads=6 max; BLAS1; earlier fitting/QA <=6',evaluation_library_sha256=sha(E.LIB),final_library_sha256=sha(final),limitations=['V0 proof is finite synthetic/DEV evidence; not physical device execution','Allocation parameters are startup-only; seamless live mode switching not claimed']))
 print('FINAL QA passed',len(rows),flush=True)
if __name__=='__main__':main()
