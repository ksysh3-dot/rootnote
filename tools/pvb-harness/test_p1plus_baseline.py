#!/usr/bin/env python3
"""CI regression for the frozen P1+ behavior, not a perceptual approval test."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import research_p1hq as H
import research_p1plus as P
from p1plus_paths import default_library, P1PLUS_BASELINE_ID

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lib',type=Path,default=default_library())
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    oracle=H.oracle_check(P.api(a.lib.resolve()))
    expected=json.loads((HERE.parents[1]/'research/p1plus/2026-10-26/primary-envelopes.json').read_text(encoding='utf-8'))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    observed=a.report.with_name(a.report.stem+'-envelopes.json')
    subprocess.run([sys.executable,str(HERE/'check_p1hq_primary_envelopes.py'),
                    '--library',str(a.lib.resolve()),'--report',str(observed)],check=True)
    actual=json.loads(observed.read_text(encoding='utf-8'))
    assert len(actual['cases'])==len(expected['cases'])==6
    errors=[]
    for new,old in zip(actual['cases'],expected['cases']):
        assert (new['name'],new['primary_harmonic'])==(old['name'],old['primary_harmonic'])
        for flag in ('0','2','6','14'):
            delta=abs(new['variants'][flag]['shape_error_db']-old['variants'][flag]['shape_error_db'])
            # Numerical/compiler tolerance for a frozen regression, not a quality
            # adoption threshold or the superseded carrier-level constraint.
            assert delta<.05,(new['name'],flag,delta)
            errors.append(delta)
    report=dict(schema='pvb.p1plus.baseline_ci.v1',baseline_id=P1PLUS_BASELINE_ID,
                library_sha256=hashlib.sha256(a.lib.read_bytes()).hexdigest(),oracle=oracle,
                envelope_cases=6,variant_comparisons=24,max_metric_difference_db=max(errors),
                metric_tolerance_db=.05,passed=True,perceptual_validation=False)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('P1+ frozen-baseline regression PASS',flush=True)


if __name__=='__main__':main()
