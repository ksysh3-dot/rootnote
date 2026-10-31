"""research_core_metrics.main() with the 17th / 18th Resultant parameters (capRho, windowCreep, creepMode) known (monkeypatch only; the harness file is untouched
except research_core_api.PARAMS which already lists them). usage: fmetrics16.py <research_core_metrics args>"""
import sys
import research_core_metrics as M
M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0)]
sys.argv = ['research_core_metrics.py'] + sys.argv[1:]
M.main()
