# -*- coding: utf-8 -*-
"""Which Bhasatika PDF books are on the web as nissaya editions, and how do their page numbers line up?
   python scripts/bt_web_map.py          -> writes data/bhasatika_web.json  (read by index.html; run again after every new edition is published)
For every edition file that has own-book page markers  '(နိဿယစာအုပ် စာမျက်နှာ N)'  and every PDF book of bhasatika_index.txt it takes
sample headwords, looks for them in the web pages and keeps the pair only when one page shift (delta = web page - index page) fits at least 40% of the sample (60% when the sample is small)."""
import re, json, os, collections, random, bisect
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')
idx = open(os.path.join(ROOT, 'bhasatika_index.txt'), encoding='utf-8').read().split('\n')
L = [l.split('\t') for l in idx if '\t' in l]
src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
B = json.loads(re.search(r'const TP_BT_BOOKS = (\[.*?\]);\n', src, re.S).group(1))
refs = {}
for b in B:
    key = b['index_key']; lst = []
    pat = re.compile(re.escape(key) + r'\s*([၀-၉၊,\s]+)$')
    for a, bb in L:
        w = re.sub(r'[=\s(].*', '', a)
        if len(w) < 5: continue
        for ref in bb.split('။'):
            m = pat.match(ref.strip().lstrip('*').strip())
            if m: lst.append((w, int(re.findall(r'[၀-၉]+', m.group(1))[0].translate(D))))
    refs[b['key']] = lst
E = json.load(open(os.path.join(ROOT, 'data', 'nissaya_editions.json'), encoding='utf-8'))
files = sorted({x['file'] for v in E.values() for x in v})
out = {}
for f in files:
    p = os.path.join(ROOT, 'data', f + '.html')
    if not os.path.exists(p): continue
    s = open(p, encoding='utf-8').read()
    parts = re.split(r'<p[^>]*>\(နိဿယစာအုပ် စာမျက်နှာ ([၀-၉]+)\)</p>', s)
    if len(parts) < 5: continue
    tokmap = collections.defaultdict(set); pagesset = set()
    for i in range(1, len(parts), 2):
        n = int(parts[i].translate(D)); pagesset.add(n)
        for t in re.findall(r'[က-႟]+', re.sub(r'<[^>]+>', ' ', parts[i + 1])):
            tokmap[t].add(n)
    pages = sorted(pagesset)
    best = None
    for b in B:
        lst = refs[b['key']]
        if len(lst) < 10: continue
        c = collections.Counter(); tot = 0
        for w, n in lst:
            hits = tokmap.get(w, ())
            if 1 <= len(hits) <= 3:
                tot += 1
                for h in hits:
                    if abs(h - n) < 80: c[h - n] += 1
        if tot >= 8 and c:
            d, k = c.most_common(1)[0]
            if k >= (0.4 if tot >= 20 else 0.6) * tot and (not best or k / tot > best[3]): best = (b, d, k, k / tot, tot)
    if best:
        b, d, k, r, tot = best
        if b['file'] in out and int(out[b['file']]['fit'].split('/')[0]) >= k: continue      # same PDF on several sheets -> keep the best fit
        out[b['file']] = {'file': f, 'delta': d, 'name': b['name'], 'fit': '%d/%d' % (k, tot), 'pages': '%d-%d' % (pages[0], pages[-1])}
        print(b['file'], '<-', f, 'delta', d, '%d/%d' % (k, tot), flush=True)
json.dump(out, open(os.path.join(ROOT, 'data', 'bhasatika_web.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out), 'books on the web')
