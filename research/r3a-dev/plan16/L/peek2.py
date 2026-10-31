import numpy as np, re, pathlib
z = np.load("sil_series.npz", allow_pickle=True)
for k in z.files:
    print(k, z[k].shape, z[k].dtype)
src = pathlib.Path("score.py").read_text()
for i, l in enumerate(src.splitlines(), 1):
    if re.search(r"def |savez|stem|onset|import", l):
        print(i, l)
