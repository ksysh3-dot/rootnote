"""research_core_metrics.main() with the Resultant parameters 17..21 (capRho, windowCreep, creepMode, ampSlewDb, slewOnsetMode) known (monkeypatch only)."""
import sys
import research_core_metrics as M
M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0), ('windowCreep', 0), ('creepMode', 0), ('ampSlewDb', 0), ('slewOnsetMode', 0)]
sys.argv = ['research_core_metrics.py'] + sys.argv[1:]
M.main()
