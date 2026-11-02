"""Prepare, never play, synthetic15cm phone characterization kit and analyzer."""
from pathlib import Path
import os,sys,json,hashlib,shutil
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import numpy as np
import soundfile as sf
from scipy.signal import chirp
H=Path.home();O=H/'r3a-dev/plan16/s66';L=Path('/mnt/c/Users/ksysh/rootnote-duo/listen/s66');L.mkdir(parents=True,exist_ok=True);FS=48000
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 parts=[];events=[];markers=[];n=0
 def add(z,kind,**kw):
  nonlocal n
  if np.ndim(z)==1:z=np.column_stack([z,z])
  events.append(dict(index=len(events)+1,kind=kind,start_sample=n,end_sample=n+len(z),start_s=n/FS,end_s=(n+len(z))/FS,**kw));parts.append(z);n+=len(z)
 def silence(s,kind='silence'):add(np.zeros(round(s*FS)),kind)
 def marker(label):
  start=n;silence(.25);t=np.arange(FS)/FS;add(chirp(t,1200,1,2400)*np.hanning(FS)*10**(-18/20),'sync',label=label)
  markers.append(dict(chirp_start_sample=start+FS//4,label=label));silence(.25)
 def tone(hz,s,level):
  t=np.arange(round(s*FS))/FS;z=np.sin(2*np.pi*hz*t)*10**(level/20);nf=min(240,len(z)//2);z[:nf]*=np.sin(np.linspace(0,np.pi/2,nf))**2;z[-nf:]*=np.sin(np.linspace(np.pi/2,0,nf))**2;return z
 def multi(s,level):
  t=np.arange(round(s*FS))/FS;z=sum(np.sin(2*np.pi*f*t+p) for f,p in [(80,0),(200,.2),(400,1.1),(1000,2.2),(4000,.8)]);z*=10**(level/20)/max(abs(z));nf=240;z[:nf]*=np.linspace(0,1,nf);z[-nf:]*=np.linspace(1,0,nf);return z
 silence(5,'head_noise')
 for hz in [80,200,400,1000,4000]:
  marker('band_'+str(hz))
  # Keep phase continuous across level steps; only start/end ramps.
  levels=[-42,-34,-26,-18,-10,-18,-26,-34];z=tone(hz,12,0)
  for j,db in enumerate(levels):add(z[j*72000:(j+1)*72000]*10**(db/20),'level_step',frequency_hz=hz,peak_dbfs=db,step_seconds=1.5)
  silence(1)
  for dur in [.1,.5,2.]:
   add(tone(hz,dur,-14),'tone_burst',frequency_hz=hz,peak_dbfs=-14,duration_s=dur);silence(2)
 control=multi(6,-16)
 for label,g in [('IDENTICAL_A',1.),('PLUS4',10**(4/20)),('IDENTICAL_B',1.)]:
  marker(label);add(control*g,'whole_pcm_control',condition=label,base_peak_dbfs=-16,gain_db=20*np.log10(g));silence(2)
 for repeat in [1,2]:
  for level,label in [(-24,'quiet'),(-6,'loud')]:
   marker('recovery_'+label+'_'+str(repeat));add(multi(8,level),'history_conditioner',condition=label,repeat=repeat,peak_dbfs=level)
   # Identical joint probe, immediate after conditioner, long enough for recovery.
   probe=(tone(250,5,-42)+tone(1000,5,-42));add(probe,'recovery_probe',condition=label,repeat=repeat,frequencies_hz=[250,1000],component_peak_dbfs=-42);silence(8)
 silence(8,'tail_noise');y=np.concatenate(parts).astype(np.float32);assert len(y)/FS<=300 and abs(y).max()<=10**(-3/20)
 wav=L/'s66_phone_characterisation_15cm.wav';sf.write(wav,y,FS,subtype='PCM_24')
 manifest=dict(schema='s66-phone-characterisation-v1',fs=FS,channels=2,duration_s=len(y)/FS,samples=len(y),peak_dbfs=float(20*np.log10(abs(y).max())),sha256=sha(wav),segments=markers,events=events,prepared_only=True,played=False)
 (L/'segment_map.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 with sf.SoundFile(wav) as f:assert f.samplerate==FS and f.channels==2 and f.frames==len(y) and f.subtype=='PCM_24'
 controls=[e for e in events if e['kind']=='whole_pcm_control'];a=y[controls[0]['start_sample']:controls[0]['end_sample']];b=y[controls[2]['start_sample']:controls[2]['end_sample']];assert np.array_equal(a,b)
 method='''s66 15 cm 폰 압축 특성 측정 방법

이 파일은 준비만 했으며 자동 재생하지 않았습니다. 길이는 약4분입니다.
S26 Ultra를 가로로 고정하고 UMIK-1을 폰 중앙에서15 cm에 고정합니다. 거리·각도·마이크 gain을 전체 측정 동안 유지합니다.
이전 측정과 같이 폰 세밀 볼륨100/150, Rootnote·Dolby Atmos·적응형 사운드·음량 균일화 OFF로 두고 실제 설정을 메모합니다.
폰 모델/SKU·OS build·케이스·마이크 방향·입력 gain·보정 파일 사용 여부도 적습니다. 이번15 cm 자료에20 cm 보정을 그대로 쓰지 않습니다.
REW에서48kHz mono 원본 PCM 녹음을 시작하고5초 이상 조용히 기다립니다. WAV를 한 번 끝까지 재생한 뒤8초 이상 더 녹음합니다.
중간 볼륨 조절·일시정지·곡 넘김은 피합니다. 말소리·물건 이동이 있으면 해당 시각을 적습니다. PCM peak가 포화되면 마이크 gain을 고정해 낮춘 새 전체 측정을 남깁니다.
80/200/400/1000/4000Hz 단계는 정적 압축과 step응답,0.1/0.5/2초 burst는 어택·회복을 봅니다.−42dBFS 단계는 방 소음 아래일 수 있어 SNR미달로 제외합니다.
IDENTICAL_A/B는 반복차, PLUS4는 완전히 같은 합성 PCM의+4dB 대조입니다. loud/quiet 뒤250/1000Hz probe는 동일하며5초 회복을 두 번 반복합니다.
원본 recording.wav를 listen/rew/log/새폴더에 유지하고 아래 명령으로 분석합니다. 원본을git에 넣지 않습니다.
WSL: ~/venv-rootnote/bin/python /mnt/c/Users/ksysh/rootnote-duo/listen/s66/analyze_s66.py /mnt/c/.../recording.wav --out /mnt/c/.../s66_analysis
분석기는 기존s59 chirp affine동기를 재사용하며 SNR≥10dB만 정량 fit합니다. 동기 실패·소음·clipping을 먼저 확인하고15cm 새자료로 PCM_PHONE의 기울기/회복/대역 순위를 다시 검증합니다.
'''
 (L/'측정 방법.md').write_text(method,encoding='utf-8');shutil.copy2(Path(__file__).with_name('s66_analyze_kit.py'),L/'analyze_s66.py')
 dump=dict(duration_s=len(y)/FS,peak_dbfs=manifest['peak_dbfs'],sha256=manifest['sha256'],identical_controls_bit_exact=True,played=False,encoding_reread=(L/'측정 방법.md').read_text().splitlines()[0]);(O/'KIT_QA.json').write_text(json.dumps(dump,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(dump)
if __name__=='__main__':main()
