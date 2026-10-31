import json, sys
r = json.load(open(sys.argv[1]))
print('determinism', r['determinism_bitwise_identical'], 'T', r['T'], 'dur', r['dur'])
r_ = lambda v: None if v is None else round(v, 1)
for s, c in r['checks'].items():
    print('==', s)
    for k, v in c.items():
        if isinstance(v, dict):
            print('  %-22s %s maxdiff %.2e  first div re T: %s ms  (re T-L: %s)  peak %.3g' % (k, 'pass' if v['pass_'] else 'FAIL', v['max_abs_diff_t_le_T_minus_L'], r_(v['first_div_ms_re_T']), r_(v['first_div_ms_re_T_minus_L']), v['layer_peak']))
        else:
            print('  ', k, r_(v))
