import sys
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/B1')
from b1_mod import *
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
FSx = 48000
BOX = 240
def envdb(sig):
    n = len(sig) // BOX
    r = np.sqrt(np.mean(sig[:n * BOX].reshape(n, BOX) ** 2, axis=1))
    return np.maximum(20 * np.log10(r + 1e-12), -90)
bands = {'20-150': (20, 150), '20-600': (20, 600), '150-600': (150, 600)}
L = {e: np.load(C / f'app_layer_{e}.npy').astype(np.float64) for e in ('P1', 'v15', 'v16a')}
for b, (lo, hi) in bands.items():
    sos = butter(4, [lo, hi], 'bandpass', fs=FSx, output='sos')
    S = {e: mod_series(envdb(sosfiltfilt(sos, L[e]))) for e in L}
    t = S['P1'][0]
    D = S['v15'][1] - S['P1'][1]
    el = S['v15'][3] > -70
    print(b, 'elig', el.sum(), 'D>0', (D[el] > 0).sum(), 'D>1', (D[el] > 1).sum(), 'D>2', (D[el] > 2).sum(), 'medM', {e: round(float(np.median(S[e][1][el])), 2) for e in L})
    o = np.argsort(-np.where(el, D, -1e9))[:6]
    print('  top', [(f'{int(t[k]//60)}:{t[k]%60:04.1f}', round(float(D[k]), 2)) for k in o])
