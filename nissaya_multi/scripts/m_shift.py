# -*- coding: utf-8 -*-
"""Is the Pali <-> nissaya pairing of a sheet shifted by some pages?  Check it from the TEXT and fix it with one number.
    python m_shift.py check <sheet> [<sheet> ...]     for every Pali page: the nissaya pages it was paired with are compared with the pages a few pages before / after.
                                                      'shift +4' = the Pali page's text is found 4 nissaya pages LATER than it was paired (the pairing is 4 pages too early)
    python m_shift.py set <sheet> <shift>             writes the corrected offset into catalog_overrides.json (offset = used offset - shift) and pairs the sheet again (~5 min)
    python m_shift.py set <sheet> auto                same, with the shift that 'check' found (only when it is clear: >= 60 % of the pages agree)
    python m_shift.py reset <sheet>                   removes the sheet's offset from catalog_overrides.json (the database rule is used again) and pairs again
The sign: a positive shift means the pairing is too early (nissaya pages must move to the next ones), so the offset becomes smaller."""
import sys, os, re, json, collections, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OV = os.path.join(ROOT, 'catalog_overrides.json')


def _toks(s): return set(re.findall(r'[က-ဿ၀-၉]+', s))


def check(n, step=1, span=12):
    P = json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8'))
    pg = {p['num']: p['body'] for p in P['pages'] if p.get('num') is not None}
    pali = collections.defaultdict(list)
    for b in P['blocks']: pali[(b['book'], b['page'])].append(b['pali'])
    h = collections.Counter()
    for k in sorted(P['ppmap'], key=lambda k: (k.split('|')[0], int(k.split('|')[1])))[::step]:
        a, b = P['ppmap'][k]; bk, p = k.split('|'); pt = _toks(' '.join(pali[(bk, int(p))]))
        if len(pt) < 12: continue
        best = max(((len(pt & _toks(' '.join(pg.get(x, '') for x in range(a + d, b + d + 1)))) / len(pt), d) for d in range(-span, span + 1)))
        if best[0] > 0.25: h[best[1]] += 1
    tot = sum(h.values()); used = (P.get('stats', {}).get('offset') or {}).get('used')
    top = h.most_common(1)[0] if h else (None, 0)
    return {'sheet': n, 'pages_tested': tot, 'shift': top[0], 'share': round(top[1] / tot, 2) if tot else 0, 'used_offset': used, 'hist': h.most_common(4)}


def _pair(n):
    r = subprocess.run([sys.executable, os.path.join(HERE, 'm_pair.py'), str(n)], capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if r.returncode: raise RuntimeError('m_pair failed: ' + (r.stderr or r.stdout)[-400:])


def set_shift(n, shift):
    c = check(n, step=2); used = c['used_offset']
    if used is None: raise SystemExit('the sheet has no database offset')
    if shift == 'auto':
        if c['share'] < 0.6 or c['shift'] is None: raise SystemExit('no clear shift (%s) - give the number yourself' % c['hist'])
        shift = c['shift']
    shift = int(shift)
    d = json.load(open(OV, encoding='utf-8')) if os.path.exists(OV) else {}
    d.setdefault(str(n), {})['offset'] = used - shift
    json.dump(d, open(OV, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    _pair(n)
    return check(n, step=2)


def reset(n):
    d = json.load(open(OV, encoding='utf-8')) if os.path.exists(OV) else {}
    d.get(str(n), {}).pop('offset', None)
    if not d.get(str(n)): d.pop(str(n), None)
    json.dump(d, open(OV, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    _pair(n)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'check':
        for n in sys.argv[2:]: print(check(int(n)))
    elif cmd == 'set': print(set_shift(int(sys.argv[2]), sys.argv[3]))
    elif cmd == 'reset': reset(int(sys.argv[2])); print('ok')
