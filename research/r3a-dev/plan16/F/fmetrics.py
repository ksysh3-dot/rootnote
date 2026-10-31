"""research_core_metrics.main() with the 17th Resultant parameter capRho known (monkeypatch only; the harness file is untouched).
usage: fmetrics.py [--p17] <research_core_metrics args>     --p17: send 17 parameters (new lib); without it 16 (v1.5 lib)."""
import sys
args = sys.argv[1:]
p17 = '--p17' in args
args = [a for a in args if a != '--p17']
import research_core_metrics as M
import research_core_api as CA
if p17:
    M.PARAM_ORDER = M.PARAM_ORDER + [('capRho', 0)]
    CA.PARAMS = CA.PARAMS + ('capRho',)
    CA.DEFAULTS = dict(CA.DEFAULTS, capRho=0)
sys.argv = ['research_core_metrics.py'] + args
M.main()
