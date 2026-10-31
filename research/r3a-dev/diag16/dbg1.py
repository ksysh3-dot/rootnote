import numpy as np, common16 as C
from q1 import since
rf = C.ref('Track00060')
print(rf['drum_on'][:30], len(rf['drum_on']), len(rf['kick_on']))
t = np.arange(0.5, 29, 0.00533)
dk = since(rf['kick_on'], t); dd = since(rf['drum_on'], t)
print((dk < .2).mean(), (dd < .2).mean(), np.mean(dk == dd))
print(rf['kick_on'][:20])
