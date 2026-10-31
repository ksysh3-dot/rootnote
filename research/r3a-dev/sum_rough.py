import json, sys
for line in open(sys.argv[1]):
    if line.startswith('=='): print(line.strip()); continue
    if '{' not in line: print(line.strip()[:200]); continue
    nm, js = line.split(' ', 1); d = json.loads(js); c = d.get('change_pct', {})
    print(f"  {nm:10s} rough mid {c.get('mid', 0):+6.1f}%  mid@hits {c.get('mid_hits', 0):+6.1f}%  "
          f"bass band {d.get('bass_band_change_db', 0):+5.2f} dB  total {d.get('total_change_db', 0):+5.2f} dB")
