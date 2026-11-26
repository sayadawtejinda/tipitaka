# -*- coding: utf-8 -*-
"""Pa-Auk Sayadaw books (library PDF books, OCR + spellcheck HTML) -> data/pa/<pa_id>.json {title,pages:[html],toc} + data/pa_ocr.json + data/pa_toc.json
  source: C:/Users/sayad/Documents/spellcheck/out/html/E*.html  (E01..E63 = the 63 PDF books of https://sayadawtejinda.github.io/dhamma/library/#books, same order as library/data/books.json)
  marker 'စာမျက်နှာ-N' = the scan number of the page (the chunk before the first marker = scan 1); PDF page = N + offset, the PDF having extra pages at the front:
    offset of a book = (PDF pages) - (last marker), refined where >= 4 of the 7 nearest contents entries of the library (library/data/toc.json, col 6 = PDF page, matched by title to the page text) say another offset
  every page of the reader starts with a head: number + 📕 (opens that PDF page on the right)
  usage: python scripts/build_pa_ocr.py [--push]
"""
import collections, glob, json, os, re, statistics, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
SRC = 'C:/Users/sayad/Documents/spellcheck/out/html'
LIB = 'C:/Users/sayad/Downloads/dhamma apps/public/library'
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(REPO, 'data', 'pa'); os.makedirs(OUT, exist_ok=True)
TR = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789'); MY = str.maketrans('0123456789', '၀၁၂၃၄၅၆၇၈၉')
MARK = re.compile(r'<p><font color="#999999" size="1">စာမျက်နှာ-([၀-၉]+)</font></p>\s*')
TOC = json.load(open(LIB + '/data/toc.json', encoding='utf-8'))
norm = lambda t: re.sub(r"[\s​\-–—.,၊။:;()\[\]\"“”‘’'*#]+", '', re.sub(r'<[^>]+>', '', t))
def offsets(n, labels, texts, npdf):
    base = npdf - max(labels); txt = [norm(t) for t in texts]; hits = []; cnt = [0] * len(txt)
    for e in TOC['toc']:
        if e[0] != n or len(norm(e[1])) < 8: continue
        nt = norm(e[1]); ps = [i for i, x in enumerate(txt) if nt in x]; hits.append((e[6] if e[6] is not None else e[2], ps))
        for i in ps: cnt[i] += 1
    tocp = {i for i, c in enumerate(cnt) if c >= 6}
    anc = sorted((labels[ps[0]], pg - labels[ps[0]]) for pg, ps in ((pg, [i for i in ps if i not in tocp]) for pg, ps in hits) if len(ps) == 1)
    out = []
    for lab in labels:
        o = base
        if len(anc) >= 3:
            near = sorted(anc, key=lambda a: abs(a[0] - lab))[:7]; med = int(statistics.median([a[1] for a in near]))
            if med != base and sum(1 for a in near if a[1] == med) >= 4: o = med
        out.append(o)
    return out
LB = json.load(open(LIB + '/data/books.json', encoding='utf-8'))
def body_of(s):
    a = s.index('<div id="bk">') + len('<div id="bk">'); b = s.find('<script', a); b = s.rfind('</div>', a, b if b > 0 else len(s)); return s[a:b].strip()
def strip_tags(t): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()
files = sorted(glob.glob(SRC + '/E*.html')); assert len(files) == len(LB), (len(files), len(LB))
books = {}; allbooks = []; tocs = []
for n, (f, lb) in enumerate(zip(files, LB)):
    s = open(f, encoding='utf-8').read(); tit = re.search(r'<title>(.*?)</title>', s, re.S).group(1)
    tit = re.sub(r'^E\d+\s+', '', tit).strip(); assert tit[:3] == lb['title'][:3], (tit, lb['title'])
    pid = 'pa_E%02d' % (n + 1); url = 'https://sayadawtejinda.github.io/dhamma/library/books/%s.pdf' % lb['id']
    parts = MARK.split(body_of(s)); pages = [(1, parts[0])] + [(int(parts[i].translate(TR)), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    if len(pages) > 1 and pages[0][0] == pages[1][0]: pages = [(pages[1][0], pages[0][1] + pages[1][1])] + pages[2:]      # front chunk + a first marker '1'
    elif len(pages) > 1 and not strip_tags(pages[0][1]): pages = pages[1:]
    offs = offsets(n, [pg for pg, _ in pages], [t for _, t in pages], lb['pages']); hp = []; toc = []
    for i, (pg0, t) in enumerate(pages):
        pg = min(max(pg0 + offs[i], 1), lb['pages'])
        hp.append('<div class="skp-ph"><span>စာမျက်နှာ-%s</span><button class="skp-pdf" data-pdf="%s" data-pg="%d" title="PDF စာမျက်နှာ %d ကို ဖွင့်မည်">📕</button></div>%s' % (str(pg0).translate(MY), url, pg, pg, t.strip()))
        for lv, hh in re.findall(r'<h([23])[^>]*>(.*?)</h\1>', t, re.S):
            tt = strip_tags(hh)
            if tt: toc.append({'level': int(lv) - 1, 'title': tt, 'page': i + 1})
    lib = [e for e in TOC['toc'] if e[0] == n]
    if lib:      # the contents of the library (checked by hand) is the truth: its PDF page -> the reader page whose PDF page is the same (or the nearest before)
        pgs = [min(max(pg0 + offs[i], 1), lb['pages']) for i, (pg0, _) in enumerate(pages)]; toc = []
        for e in lib:
            tp = e[6] if e[6] is not None else e[2]; ok = [i for i, q in enumerate(pgs) if q <= tp]
            toc.append({'level': 1, 'title': e[1].strip(), 'page': (max(ok, key=lambda i: (pgs[i], i)) if ok else 0) + 1})
    title = lb['title'] if len(lb['title']) >= len(tit) else tit
    json.dump({'title': title, 'pages': hp, 'toc': toc}, open(os.path.join(OUT, pid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    books[pid] = {'title': title, 'pages': len(hp), 'pdf': lb['id']}; allbooks.append(pid)
    for t in toc: tocs.append([n, t['page'], 0, t['title']])
    print(pid, len(hp), len(toc), title[:30])
json.dump({'books': books, 'order': allbooks}, open(os.path.join(REPO, 'data', 'pa_ocr.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump({'books': allbooks, 'toc': tocs}, open(os.path.join(REPO, 'data', 'pa_toc.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
if '--push' in sys.argv:
    g = lambda *a: subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True)
    g('add', '-A', '--', 'data/pa', 'data/pa_ocr.json', 'data/pa_toc.json')
    print(g('commit', '-m', 'Pa-Auk books: OCR pages with PDF buttons', '-m', 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>', '--', 'data/pa', 'data/pa_ocr.json', 'data/pa_toc.json').stdout)
    g('pull', '--rebase', '--autostash'); print('pushed' if g('push').returncode == 0 else 'PUSH FAILED')
