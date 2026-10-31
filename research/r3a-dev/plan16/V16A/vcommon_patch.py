from pathlib import Path
p = Path.home() / 'r3a-dev/plan16/V16A/vcommon.py'
t = p.read_text()
old1 = "LIB16A = HOME / 'r3-work/tools/pvb-harness/build_core16a/libpvbcapi.so'    # 18 params\n"
new1 = old1 + "LIB16B = HOME / 'r3-work/tools/pvb-harness/build_core16b/libpvbcapi.so'    # 19 params (A1': creepMode)\n"
old2 = '''def make_params(rho=None, creep=None):
    """None, None -> 16 values (v1.5 call); rho -> 17 values; creep (needs rho, may be 0) -> 18 values"""
    v = list(BASE16)
    if rho is not None:
        v.append(float(rho))
    if creep is not None:
        v.append(float(creep))
    return np.array(v, np.float64)
'''
new2 = '''def make_params(rho=None, creep=None, mode=None):
    """None, None -> 16 values (v1.5 call); rho -> 17 values; creep (needs rho, may be 0) -> 18 values; mode (needs creep) -> 19 values (A1')"""
    v = list(BASE16)
    if rho is not None:
        v.append(float(rho))
    if creep is not None:
        v.append(float(creep))
    if mode is not None:
        v.append(float(mode))
    return np.array(v, np.float64)
'''
assert t.count(old1) == 1 and t.count(old2) == 1
t = t.replace(old1, new1).replace(old2, new2)
p.write_text(t)
