import numpy as np
d=np.load('/home/ksysh/r3a-dev/plan16/S19/cache/r_b0p0_s09.npz')
for k in d.files: print(k,d[k].shape,d[k].dtype)
st=d['state'];print('state counts',np.bincount(st.ravel()))
a=d['a_2'];print('a2 by state',[ (s, float(a[st==s].mean()), float((a[st==s]>0).mean())) for s in range(4)])
ih=d['hop'][:,0];print(ih[:3],ih[-3:])
H=np.where(st[:,0]>0)[0];print(H[:5])
for k in ('Np','A','c','sigma','f_osc','f_track'):
    x=d[k][st>=2];print(k,np.percentile(x,[0,5,50,95,100]))