# -*- coding: utf-8 -*-
"""Pali pages that an edition file really has nissaya text for:  string '1-5,8,10-20'  (a page whose [စာမျက်နှာ-N] part has only the marker / the '(နိဿယစာအုပ် စာမျက်နှာ N)' line is not counted).
The reader shows an edition button only on these pages.   python m_edpages.py   (re)writes 'pg' of every edition in data/nissaya_editions.json from its data/<file>.html"""
import re, os, json, sys
MY = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')
MARK = re.compile(r'\[စာမျက်နှာ-([၀-၉]+)\]')

def page_ranges(html):
    ms = list(MARK.finditer(html)); have = set()
    for i, m in enumerate(ms):
        chunk = html[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(html)]
        chunk = re.sub(r'<p[^>]*>\(နိဿယစာအုပ် စာမျက်နှာ [၀-၉]+\)</p>', '', chunk)
        chunk = re.sub(r'<[^>]+>', '', chunk)
        chunk = re.sub(r'</?body>|</?html>|\s+', '', chunk)
        if chunk: have.add(int(m.group(1).translate(MY)))
    out = []
    for p in sorted(have):
        if out and p == out[-1][1] + 1: out[-1][1] = p
        else: out.append([p, p])
    return ','.join(('%d' % a) if a == b else ('%d-%d' % (a, b)) for a, b in out)

def span(pg):
    n = [int(x) for x in re.findall(r'\d+', pg)]
    return (n[0], n[-1]) if n else (None, None)

if __name__ == '__main__':
    REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    ep = os.path.join(REPO, 'data', 'nissaya_editions.json'); ed = json.load(open(ep, encoding='utf-8')); ch = 0
    for book, lst in ed.items():
        for e in lst:
            if e['file'] == book: continue
            f = os.path.join(REPO, 'data', e['file'] + '.html')
            if not os.path.exists(f): print('missing', f); continue
            r = page_ranges(open(f, encoding='utf-8').read())
            a, b = span(r); tot = sum((int(y) - int(x) + 1) if '-' in t else 1 for t in r.split(',') if t for x, y in [(t.split('-') + [t])[:2] if '-' in t else (t, t)])
            if r and e.get('pg') != r:
                e['pg'] = r; e['from'], e['to'] = a, b; ch += 1
                if '--v' in sys.argv or tot < (b - a + 1): print(book, e['label'], 'pages', tot, 'of', e['to'] - e['from'] + 1)
    json.dump(ed, open(ep, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); print('changed', ch)
