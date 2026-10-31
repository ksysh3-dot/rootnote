import json, research_core_metrics as M
r = M.v0(M.REF_LIB, M.REF_LIB, quick=True)
print(json.dumps(M.jsonable(r['switch']), indent=0))
