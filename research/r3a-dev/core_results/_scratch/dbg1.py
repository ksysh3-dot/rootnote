import numpy as np, json
import research_core_metrics as M, research_core_signals as S
FS=48000
ctx = M.Ctx(M.REF_LIB, 6, None)
# tail note envelope
xt = S.stereo(S.tail_note()); r0=ctx.render('tail', xt, 0.0); rd=ctx.render('tail', xt, -120.0)
lt = M.layer_of(r0, rd); et = M.amp_env(lt,5.0)
for t in (0.45,0.5,0.52,0.54,0.6,0.7,1.0,1.3,1.4,1.45,1.5,1.52,1.55,1.6,1.7):
    print(t, round(float(et[int(t*FS)]),5))
# step enter times
sg = S.stepwise_line(25.0); X=S.stereo(sg['noisy']); r=ctx.render('step25', X, 0.0, harmonic=True)
vs = M.voices(ctx, r)
for i in range(2,12):
    t0=sg['t0'][i]; f=sg['notes'][i]
    h0=int(np.searchsorted(vs.tc,t0)); 
    rowsx=[]
    for h in range(h0-2,h0+25,4):
        on=np.flatnonzero(vs.on[h]); 
        rowsx.append((round((vs.tc[h]-t0)*1000), [(round(float(vs.f[h][j]),1), round(float(vs.w[h][j]),5)) for j in on]))
    print(i, f, M.entering_time(vs,t0,f,dominant=True), M.entering_time(vs,t0,f))
    if i in (2,3): print(rowsx)
