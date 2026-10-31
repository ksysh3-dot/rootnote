import sys, json, time
sys.path.insert(0, '/home/ksysh/r3a-dev/plan16/S19/O')
import numpy as np
from s19o_lib import *
R = json.load(open('/home/ksysh/r3a-dev/plan16/S19/s19_attr.json'))
for row, i, sk in (('f4', 9, 'app'), ('f4', 6, 'rem')):
    t = time.time()
    d, boxes = load(row, i)
    cl = classify(d, boxes)
    ms = masks(cl, len(boxes), sk)
    # render-box class sums vs s19_attr.json
    hn, ex = cl['hn'], cl['ex']
    for nm in ('song', 'win'):
        m = ms[nm]
        tot = boxes[m].sum()
        print(row, i, nm, 'noevent %.4f' % (boxes[m & (ex == NT)].sum() / tot), 'novoice %.4f' % (boxes[m & (ex == -1)].sum() / tot),
              {k: round(boxes[m & (ex == j)].sum() / tot, 4) for j, k in enumerate(TYPES)})
    if nm == 'win':
        pass
    js = [s for s in R[row]['songs'] if s['idx'] == i][0]['res']
    print('  json song noevent %.4f' % (js['noevent'] / js['total']), {k: round(v / js['total'], 4) for k, v in js['excl'].items()})
    runs = make_runs(d, cl)
    nseg = sum(len(r['segs']) for r in runs); hops_seg = sum(e - s + 1 for r in runs for (s, e) in r['segs'])
    nxf = sum(len(r['xf']) for r in runs)
    nhops_on = sum(int((r['state'][1:] == 2).sum()) for r in runs)
    print('  runs', len(runs), 'segs', nseg, 'seg hops', hops_seg, 'ON hops', nhops_on, 'xf events', nxf, 'dur s', len(d['hop']) * HOPS, 'segments/s', nseg / (len(d['hop']) * HOPS))
    # per-slot check
    for s in (0, 3, 6):
        Elo, Emid = recon_bands(d, cl, runs, ('base',), slots={s})
        E = d['_E'][:, s]
        print('  slot', s, 'max rel err %.2e' % (np.abs(Elo - E).max() / max(E.max(), 1e-30)), 'sum %.4e %.4e' % (Elo.sum(), E.sum()))
    Elo, Emid = recon_bands(d, cl, runs, ('base',))
    print('  total recon lo %.4e sum slot E %.4e' % (Elo.sum(), d['_E'].sum()), 'time', time.time() - t)
    t = time.time()
    for v in (('sus', 4, True, True, False), ('sus', 1, True, True, False), ('xf', 20)):
        el, em = recon_bands(d, cl, runs, v)
        c0 = class_sums(cl, Elo, Emid, ms); c1 = class_sums(cl, el, em, ms)
        print('  ', v, {nm: {k: round(10 * np.log10(c1[nm][k] / c0[nm][k]), 2) for k in ('noevent', 'event', 'all', 'nc20', 'mid')} for nm in ms}, round(time.time() - t, 1))
