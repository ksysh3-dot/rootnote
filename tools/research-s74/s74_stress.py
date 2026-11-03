from s74_verify import *
from scipy.signal import firwin
checks=[]
def ck(name,ok,**detail):
 checks.append(dict(name=name,passed=bool(ok),**detail));dump('STRESS_PARTIAL.json',dict(checks=checks));assert ok,checks[-1]
def tp(y):return float(20*np.log10(max(float(abs(resample_poly(y.astype(float),8,1,axis=0,window=firwin(321,1/8,window=('kaiser',8.6)))).max()),1e-30)))
def finite_cases():
 x=stimulus(sec=1.5);zero=np.zeros((24000,2),np.float32)
 signals={'silence':np.zeros_like(x),'mono':np.repeat(x[:,:1],2,axis=1),'antiphase':np.c_[x[:,0],-x[:,0]],'left_only':np.c_[x[:,0],np.zeros(len(x))],
 'silence_loud':np.r_[zero,np.clip(x*16,-1,1)],'clipped':np.clip(x*32,-1,1),'overrange12dB':x*4,'quiet70dB':x*10**(-70/20),'loud_to_quiet':np.r_[x*4,x*.01],'seek_unannounced':np.r_[x[:24000],-x[30000:]]}
 for mode in [1,2]:
  for name,z in signals.items():
   e=app(mode);y,l,tr,c=e.run(np.r_[z,zero],[1,37,64,257,1024]);lat=e.l.pvb_latency(e.h);e.close();p=tp(y)
   ck(f'{mode}_{name}',np.isfinite(y).all() and p<=-1+1e-5,tp8_dbfs=p,latency=lat,max_gr_db=float(tr[:,22].max()),max_sample_step=float(abs(np.diff(y,axis=0)).max()))
   if name=='silence':ck(f'{mode}_silence_exact_zero',not np.any(y))
   if name=='mono':ck(f'{mode}_mono_equal',np.array_equal(y[:,0],y[:,1]))
  a=app(mode);b=app(mode);bad=x.copy();bad[100,0]=np.nan;bad[101,1]=np.inf;bad[102,0]=-np.inf;clean=np.nan_to_num(bad,nan=0,posinf=0,neginf=0)
  ya=a.run(np.r_[bad,zero],64);yb=b.run(np.r_[clean,zero],64);a.close();b.close();ck(f'{mode}_naninf_zero_equivalent',np.array_equal(ya[0],yb[0]))
  a=app(mode);b=app(mode);a.run(x[:24000]);b.run(x[:24000]);ck(f'{mode}_pause_no_samples',np.array_equal(a.run(x[24000:])[0],b.run(x[24000:])[0]));a.close();b.close()
 # Causal prefix (second signal differs only after2s); allowed input/output index matches physical buffering.
 x=stimulus(sec=3);z=x.copy();z[96000:]*=-1;a=app(2);b=app(2);ya=a.run(x,64)[0];yb=b.run(z,64)[0];a.close();b.close();ck('causal_prefix_physical_time',np.array_equal(ya[:96000],yb[:96000]))
 # A stream reset must discard old separator/FIR/TCN/peak history and recover to fresh PCM after fades.
 a=app(2);a.run(x);a.l.pvb_reset(a.h);aa=a.run(x,64);b=app(2);bb=b.run(x,64);a.close();b.close();ck('reset_discards_separator_history',np.array_equal(aa[0][24000:],bb[0][24000:]))
def toggles():
 rng=np.random.default_rng(7403);e=app(0);events=[];p=e.p.copy();rate=48000
 for i in range(650):
  op=int(rng.integers(0,7));size=int(rng.choice([1,37,64,257,1024]))
  if op in [0,1]:
   p[57]=int(rng.integers(0,3)) if rate==48000 else 0;e.set(p);events.append([i,'mode',int(p[57])])
  elif op==2:e.l.pvb_reset(e.h);events.append([i,'reset_seek_pause'])
  elif op==3:
   rate=int(rng.choice([44100,48000,96000]));e.l.pvb_set_sample_rate(e.h,rate);p[57]=0;e.set(p);events.append([i,'rate_route',rate])
  elif op==4:
   p[0]=p[22]=int(rng.integers(0,2));p[57]=2 if p[0] and rate==48000 else 0;e.set(p);events.append([i,'speaker',int(p[0])])
  x=stimulus(rate,size/rate);y,l,tr,c=e.process(x)
  full=np.empty_like(y);ll=np.empty_like(y);tt=np.empty(90,np.float32);e.l.pvb_copy_diagnostic(e.h,ll.ctypes.data_as(FP),full.ctypes.data_as(FP),y.size,tt.ctypes.data_as(FP),90)
  ck('transaction_'+str(i),np.isfinite(y).all() and np.array_equal(y,full))
 e.close();dump('STRESS_EVENTS.json',events)
def perf():
 rows=[];x=stimulus(sec=8)
 for mode in [1,2]:
  for block in [64,256,1024]:
   e=app(mode,capture=False);_,_,_,c=e.run(x,block);e.close();budget=block/48;start=min(len(c),int(np.ceil(48000/block)));steady=c[start:]/1e6;warm=c[:start]/1e6
   def stats(a):return dict(cpu_p50_ms=float(np.percentile(a[:,0],50)),cpu_p999_ms=float(np.percentile(a[:,0],99.9)),cpu_max_ms=float(a[:,0].max()),wall_max_ms=float(a[:,1].max()),cpu_misses=int(np.sum(a[:,0]>budget)),wall_misses=int(np.sum(a[:,1]>budget)),blocks=len(a))
   rows.append(dict(mode=mode,block=block,budget_ms=budget,startup=stats(warm),steady=stats(steady)))
 dump('CPU_64_FRAME.json',dict(rows=rows,scope='x86 WSL process-only, dedicated single worker; JNI/capture/output/ARM excluded'))
 print('PERF',rows,flush=True)
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='perf':perf()
 else:finite_cases();toggles();dump('STRESS.json',dict(passed=True,n=len(checks),checks=checks));print('STRESS PASS',len(checks),flush=True)
