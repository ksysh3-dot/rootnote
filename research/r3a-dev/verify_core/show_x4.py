import json, sys
V = '/home/ksysh/r3a-dev/verify_core/'
x = json.load(open(V + 'xcheck_sanity.json'))['sanity']
hdr = f'{"cfg":3s} {"finite":6s} {"nanEv":5s} {"pkDry":>7s} {"pkWet":>7s} {"pk@-5":>7s} {"layer":>8s} {"vsP1":>7s} {"HF/lay":>7s} {"hfPk":>8s} {"click":>8s} {"zero%":>6s} {"act":>4s} {"<-40":>4s} {">+10":>4s}'
for sn, d in x.items():
    print('==', sn); print('   ' + hdr)
    for k in ('P1', 'A', 'B', 'C', 'D'):
        r = d.get(k)
        if not r:
            continue
        print(f'   {k:3s} {str(r["finite"]):6s} {r["nan_events_meter"]:5.0f} {r["peak_dry_dbfs"]:7.2f} {r["peak_wet_dbfs"]:7.2f} {r["peak_wet_at_outdb_minus5_dbfs"]:7.2f} {r["layer_150_600_db"]:8.1f} '
              f'{r.get("layer_re_P1_db_total", float("nan")):7.1f} {r["hf_over_layer_db"]:7.1f} {r["hf_peak"]:8.2e} {r["click_index"]:8.1f} {100*r["layer_exact_zero_frac"]:6.1f} '
              f'{r.get("bins_P1_active", -1):4d} {r.get("bins_core_below_P1_minus_40dB", -1):4d} {r.get("bins_core_above_P1_plus_10dB", -1):4d}')
