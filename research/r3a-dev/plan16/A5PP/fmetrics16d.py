"""research_core_metrics.main() with the 17th-22nd Resultant parameters known (monkeypatch only). usage: fmetrics16d.py <research_core_metrics args>"""
import sys
import research_core_metrics as M
M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0), ('betaSusMin', 0), ('betaSusMax', 0), ('betaOnsetMs', 0)]
sys.argv = ['research_core_metrics.py'] + sys.argv[1:]
M.main()
