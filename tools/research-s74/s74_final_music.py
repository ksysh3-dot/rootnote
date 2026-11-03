from s74_music import *
def final_one(task):
 phase,src=task;dest=O/(phase+'_rows')/(src['key']+'.json')
 if dest.exists():return json.loads(dest.read_text())
 x,rate=load(src);result=dict(source=src,source_rate=rate,frames=len(x),input_pcm_sha256=hashlib.sha256(x.tobytes()).hexdigest())
 if phase=='parity':result['parity']=parity(src,x);result['passed']=result['parity']['passed']
 else:
  # Final STABLE is rerun in full; pre-refinement STRONG full renders are preserved evidence.
  result['music']=music(src,x);result['passed']=all(r['passed'] for r in result['music'])
 dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');return result
def main():
 for name in ['parity_rows','final_music_rows','music_features']:(O/name).mkdir(exist_ok=True)
 sources=[]
 for i,s in enumerate(json.loads((O.parent/'s67/MUSIC_INPUTS.json').read_text())['sources']):sources.append(dict(**s,key=f'A{i:03d}'))
 inv=json.loads((O.parent/'s73/corrected_v2/SOURCE_INVENTORY_FROZEN.json').read_text())
 musdb=[{**inv['tracks'][key],'key':key,'group':'MUSDB','seconds':30} for key in inv['ids']]
 files={str(p):sha(p) for p in (W/'app/src/main/cpp/libpvb').glob('*') if p.is_file()};files[str(LIB)]=sha(LIB)
 dump('FINAL_MUSIC_EXECUTION_LOCK.json',dict(files=files,sources=sources+musdb,tolerance=dict(max_error=2e-6,rms_db=-80,tp_db=.01),audio_persistence=False,workers=16))
 allowed={s['path'] for s in sources}
 def guard(event,args):
  if event in ['open','os.listdir','os.scandir'] and isinstance(args[0],(str,bytes,os.PathLike)):
   p=os.fsdecode(args[0]);assert not p.startswith('/mnt/d/rootnote-data')
   if '/datasets/slakh2100' in p:assert event=='open' and p in allowed,p
 sys.addaudithook(guard)
 for phase,items in [('parity',[s for s in sources if s['group']=='DEV']+musdb),('final_music',sources)]:
  results=[];progress('FINAL '+phase+' START '+str(len(items)))
  with ProcessPoolExecutor(max_workers=16) as pool:
   futures={pool.submit(final_one,(phase,s)):s['key'] for s in items}
   for f in as_completed(futures):
    r=f.result();results.append(r);progress(f'FINAL {phase} {len(results)}/{len(items)} {futures[f]} pass={r["passed"]}')
  dump('FINAL_'+phase.upper()+'.json',dict(rows=results,n=len(results),passed=all(r['passed'] for r in results)))
  progress('FINAL '+phase+' COMPLETE pass='+str(all(r['passed'] for r in results)))
  if phase=='parity' and not all(r['passed'] for r in results):raise RuntimeError('Strict2e-6 parity failed; preserve evidence and diagnose')
if __name__=='__main__':main()
