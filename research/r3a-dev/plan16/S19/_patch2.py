p='/home/ksysh/r3a-dev/plan16/S19/s19_attr.py'
s=open(p).read()
s=s.replace("    m = box_sel\n","    top = np.argmax(w, 1); ftop = fo[hn, top]\n    m = box_sel\n",1)
s=s.replace("noevent=float(E[m & (ex == len(TYPES))].sum()),","noevent=float(E[m & (ex == len(TYPES))].sum()), none_direct=float(E[m & (ex == len(TYPES)) & (ftop <= BAND_F)].sum()),",1)
open(p,'w').write(s)
t=open('/home/ksysh/r3a-dev/plan16/S19/s19_tab.py').read()
t+='''
print('\\n=== "none" class split: top voice with 2*f_osc<=150 (direct in-band k=2, not splatter) -> share of total 20-150 energy %')
for lab in ROWS:
    w = R[lab]['win']['res']; sg = [100*s['res']['none_direct']/s['res']['total'] for s in R[lab]['songs']]; sn = [100*s['res']['noevent']/s['res']['total'] for s in R[lab]['songs']]
    print(f"[{lab}] windows none {100*w['noevent']/w['total']:.1f} of which direct {100*w['none_direct']/w['total']:.1f} | songs median none {np.median(sn):.1f} direct {np.median(sg):.1f}")
'''
open('/home/ksysh/r3a-dev/plan16/S19/s19_tab.py','w').write(t)