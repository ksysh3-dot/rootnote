"""Aggregate paired DEV results without re-rendering or retuning candidates."""
from pathlib import Path
import os,json,csv
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import numpy as np
P=Path.home()/'r3a-dev/plan16/s66'
def stats(values):
 a=np.array([v for v in values if v is not None and np.isfinite(v)],float)
 if not len(a):return dict(n=0,median=None,p10=None,p90=None,min=None,max=None)
 return dict(n=len(a),median=float(np.median(a)),p10=float(np.percentile(a,10)),p90=float(np.percentile(a,90)),min=float(a.min()),max=float(a.max()))
def ci(a):
 a=np.array([v for v in a if v is not None],float)
 if not len(a):return None
 rng=np.random.default_rng(6602);v=np.median(a[rng.integers(0,len(a),(10000,len(a)))],axis=1);return list(np.percentile(v,[2.5,97.5]))
def summarize():
 ids=json.loads((P/'IDS.json').read_text());rows=[json.loads((P/'results'/(key+'.json')).read_text()) for key in ids if (P/'results'/(key+'.json')).exists()];summary=[];flat=[]
 for ctx in ['digital','phone20H','phone20L']:
  for ref in ['P1','B']:
   for name in ['B','T','C1','C2','C3']:
    if name==ref:continue
    values=[r['variants'][name]['contexts'][ctx]['versus_'+ref] for r in rows]
    weak=[v['Qweak_db'] for v in values];flags=[]
    for r,v in zip(rows,values):
     reasons=[]
     for k in ['family_power_db','N1_mixed_db_delta']:
      if v.get(k) is not None and v[k]>=1:reasons.append(k)
     if any(z is not None and z>=1 for z in v['N2_envelope_db']):reasons.append('N2_envelope')
     for k in ['gap_pp_delta','loss_pp_delta']:
      if v.get(k) is not None and v[k]>=1:reasons.append(k)
     at=v['attack_local10_ms']
     if (at['median_ms'] is not None and at['median_ms']>=10) or (at['p95_ms'] is not None and at['p95_ms']>=20):reasons.append('attack_local')
     if reasons:flags.append(dict(id=r['id'],reasons=reasons,deltas=v))
     flat.append(dict(id=r['id'],variant=name,context=ctx,reference=ref,weak_db=v['Qweak_db'],whole_db=v['Qwhole_db'],wrong_family_db=v['family_power_db'],N1_db=v['N1_mixed_db_delta'],N2_1_4_db=v['N2_envelope_db'][0],N2_4_10_db=v['N2_envelope_db'][1],N2_10_30_db=v['N2_envelope_db'][2],gap_pp=v['gap_pp_delta'],loss_pp=v['loss_pp_delta'],attack_median_ms=at['median_ms'],attack_p95_ms=at['p95_ms'],tp_P1_db=r['variants'][name]['engine']['tp_delta_P1_db'],body_db=v['body_power_db']))
    ratio_values=[]
    for r in rows:
     a=r['variants'][name]['contexts'][ctx]['metrics']['correct_ratio'];b=r['variants'][ref]['contexts'][ctx]['metrics']['correct_ratio'];ratio_values.append(10*np.log10(a/b) if a>1e-20 and b>1e-20 else None)
    aggregate=dict(context=ctx,reference=ref,variant=name,weak_db=stats(weak),weak_median_bootstrap95=ci(weak),weak_loss_gt05_count=sum(v is not None and v<-.5 for v in weak),ratio_db=stats(ratio_values),harm_flag_song_count=len(flags),harm_flags=flags)
    for k in ['Qwhole_db','family_power_db','N1_mixed_db_delta','gap_pp_delta','gap6_pp_delta','loss_pp_delta','rms_dbfs_delta','crest_db_delta','body_power_db']:aggregate[k]=stats([v[k] for v in values])
    aggregate['N2_bands_db']=[stats([v['N2_envelope_db'][j] for v in values]) for j in range(3)]
    aggregate['attack_local_median_ms']=stats([v['attack_local10_ms']['median_ms'] for v in values]);aggregate['attack_local_p95_ms']=stats([v['attack_local10_ms']['p95_ms'] for v in values]);summary.append(aggregate)
 peaks=[]
 for name in ['B','T','C1','C2','C3']:
  p=[r['variants'][name]['engine']['tp_delta_P1_db'] for r in rows];peaks.append(dict(variant=name,tp_delta_P1_db=stats(p),failures=[dict(id=r['id'],db=r['variants'][name]['engine']['tp_delta_P1_db']) for r in rows if not r['variants'][name]['engine']['tp_pass']],limiter_max_gr_db=stats([r['variants'][name]['engine']['max_limiter_gr_db'] for r in rows])))
 result=dict(n=len(rows),expected=len(ids),complete=len(rows)==len(ids),summary=summary,peaks=peaks,scope='DEV exploratory, final domain-restricted model fails screening, no confirmation claim')
 (P/'SUMMARY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if flat:
  with (P/'PAIRED_DEV.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 print('COMPLETE',result['complete'],'n',len(rows))
 for v in summary:
  if v['context'] in ['digital','phone20H'] and v['reference']=='B':print(v['variant'],v['context'],'weak',v['weak_db'],'CI',v['weak_median_bootstrap95'],'ratio',v['ratio_db']['median'],'harm flags',v['harm_flag_song_count'])
 print('peaks',peaks)
 return result
if __name__=='__main__':summarize()
