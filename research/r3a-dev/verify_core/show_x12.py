import json
x = json.load(open('/home/ksysh/r3a-dev/verify_core/xcheck_v6both.json'))['v6both']
suite_A = json.load(open('/home/ksysh/r3a-dev/core_results/verify_A/results.json'))['metrics']['V6']
suite_P = json.load(open('/home/ksysh/r3a-dev/core_results/p1_baseline/results.json'))['metrics']['V6']
print('V6 independent (own MIDI/stem/harmonic parsers): coverage P1 %.4f core %.4f diff %+.2f %%p | wrong share P1 %.4f core %.4f diff %+.2f %%p' % (
    x['P1']['coverage'], x['A']['coverage'], 100 * (x['A']['coverage'] - x['P1']['coverage']), x['P1']['wrong_share'], x['A']['wrong_share'], 100 * (x['A']['wrong_share'] - x['P1']['wrong_share'])))
print('V6 suite:                                          coverage P1 %.4f core %.4f diff %+.2f %%p | wrong share P1 %.4f core %.4f diff %+.2f %%p' % (
    suite_P['coverage'], suite_A['coverage'], 100 * (suite_A['coverage'] - suite_P['coverage']), suite_P['wrong_share'], suite_A['wrong_share'], 100 * (suite_A['wrong_share'] - suite_P['wrong_share'])))
for t, sa, sp in zip(x['per_track'], suite_A['per_track'], suite_P['per_track']):
    print(f'  {t["name"]}: wrong share P1 {t["P1"]["bad"]/max(t["P1"]["w"],1e-30):.4f} (suite {sp["wrong"]/sp["total"]:.4f}) core {t["A"]["bad"]/max(t["A"]["w"],1e-30):.4f} (suite {sa["wrong"]/sa["total"]:.4f}) | loud P1 {t["P1"]["loud"]} (suite {sp["loud_hops"]}) cov P1 {t["P1"]["cov"]} (suite {sp["covered"]}) | core cov {t["A"]["cov"]} (suite {sa["covered"]})')
