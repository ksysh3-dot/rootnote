import json
R = json.load(open('/home/ksysh/r3a-dev/plan16/G/stage0_raw.json'))
for kh in ['1_100', '2_100', '4_100', '1_150', '2_150', '4_150']:
    i = sum(R[k]['real'][kh]['e_p0'][0] for k in ['Track00024', 'Track00026']); o = sum(R[k]['real'][kh]['e_p1'][0] for k in ['Track00024', 'Track00026'])
    print(kh, round(100 * i / (i + o), 1))
