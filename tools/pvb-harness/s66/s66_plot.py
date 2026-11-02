from pathlib import Path
import os,json,shutil
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path.home()/'r3a-dev/plan16/s66';G=Path('/mnt/c/Users/ksysh/rootnote-duo/gpt-cli')
def main():
 s=json.loads((O/'SUMMARY.json').read_text());v=json.loads((O/'WAVEFORM_CLOSURE_v2.json').read_text());fig,ax=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
 colors=['#315B82','#DB8B40','#649678'];bands=['150–300','300–600','600–3000','3000–20000'];xx=np.arange(4)
 ax[0].bar(xx-.16,[r['median_abs_db'] for r in v['errors20cm'][1:]],.32,label='Median absolute',color=colors[0]);ax[0].bar(xx+.16,[r['p90_abs_db'] for r in v['errors20cm'][1:]],.32,label='90th percentile',color=colors[1]);ax[0].axhline(2,color=colors[0],linestyle='--',linewidth=1);ax[0].axhline(5,color=colors[1],linestyle='--',linewidth=1);ax[0].set_xticks(xx,bands,rotation=25);ax[0].set_ylabel('Prediction error (dB)');ax[0].set_title('Held-out waveform error,20cm');ax[0].legend(frameon=False,fontsize=9)
 xx=np.arange(4);ax[1].bar(xx-.16,[r['observed_db'] for r in v['controls']],.32,label='Observed',color=colors[0]);ax[1].bar(xx+.16,[r['predicted_db'] for r in v['controls']],.32,label='Predicted',color=colors[1]);ax[1].set_xticks(xx,['+4 H','+4 L','Music H−L','Probe H−L'],rotation=25);ax[1].axhline(0,color='#888',linewidth=.6);ax[1].set_ylabel('Paired change (dB)');ax[1].set_title('Control responses');ax[1].legend(frameon=False,fontsize=9)
 for j,ctx in enumerate(['digital','phone20H','phone20L']):
  yy=[];err=[]
  for name in ['C1','C2','C3']:
   r=next(r for r in s['summary'] if r['variant']==name and r['reference']=='B' and r['context']==ctx);med=r['weak_db']['median'];ci=r['weak_median_bootstrap95'];yy.append(med);err.append([med-ci[0],ci[1]-med])
  ax[2].errorbar(np.arange(3)+(j-1)*.18,yy,yerr=np.array(err).T,fmt='o',capsize=3,color=colors[j],label=ctx)
 ax[2].set_xticks(np.arange(3),['C1 ratio','C2 history','C3 band']);ax[2].axhline(0,color='#888',linewidth=.8);ax[2].set_ylabel('Weak25 gain vs B (dB)');ax[2].set_title('DEV74 paired medians +95% bootstrap');ax[2].legend(frameon=False,fontsize=9)
 fig.suptitle('s66 — model fails screening; transferred scores are exploratory',fontsize=13)
 for a in ax:a.spines[['top','right']].set_visible(False);a.grid(axis='y',alpha=.16);a.set_axisbelow(True)
 path=O/'s66_diagnostics.png';fig.savefig(path,dpi=180);shutil.copy2(path,G/path.name);print(path)
if __name__=='__main__':main()
