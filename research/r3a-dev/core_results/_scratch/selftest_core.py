import numpy as np
import research_core_metrics as M, research_core_signals as S
ctx = M.Ctx(M.REF_LIB, 6, None)
sg = S.stepwise_line(25.0); r = ctx.render('step25', S.stereo(sg['noisy']), 0.0, harmonic=True)
p1 = M.vs_from_harm(r['harm']); core = p1.core
rows=[]
for h in range(len(core)):
    for j in np.flatnonzero(p1.valid[h]):
        row = np.zeros(22); row[0]=core[h]+16 ; row[1]=p1.vid[h][j]; row[2]=p1.vid[h][j]; row[3]=2 if p1.on[h][j] else 1
        row[5]=p1.f[h][j]; row[6]=p1.f[h][j]; row[8]=p1.A[h][j]; row[9]=p1.c[h][j]; row[10]=1.0; row[16]=0
        row[20]=0.3*p1.A[h][j]; row[21]=0.2*p1.A[h][j]
        rows.append(row)
tr = np.array(rows)
vc = M.vs_from_core(tr, r['harm'])
print('hop_offset detected', vc.hop_offset)
print('same on count', int(p1.on.sum()), int(vc.on.sum()))
for i in range(2,8):
    t0=sg['t0'][i]; f=sg['notes'][i]
    print(i, M.entering_time(p1,t0,f,dominant=True), M.entering_time(vc,t0,f,dominant=True))
print('A sum', np.nansum(p1.A), np.nansum(vc.A), 'w', p1.w.sum(), vc.w.sum())
