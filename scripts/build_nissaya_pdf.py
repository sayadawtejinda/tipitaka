# -*- coding: utf-8 -*-
"""data/nissaya_pdf.json  {nissaya web file: {"id": archive.org item, "off": pdf page - marker}}  for the 📕 icon of the nissaya pages.

  - the nissaya PDF books are on archive.org as  nsy-pdf-<kind>-<number>  (scripts/nissaya_pdf in 'dhamma apps' uploads them;  --check asks archive.org which of them exist)
  - every web file data/<book>[_edition].html has page marks '(နိဿယစာအုပ် စာမျက်နှာ N)'.  The Pali-page <-> nissaya-PDF page map is in <kind>_nsy.db (pali_nsy_page_map).
    For each web file the nissaya book (nsy_book_id) whose map fits the marks best is taken: pdf page = mark + (the common difference);  a file is accepted only when >= 70 % of its pages agree on one difference.
  usage: python scripts/build_nissaya_pdf.py [--check] [--push]
"""
import json, os, re, sqlite3, statistics, sys, subprocess, time, urllib.request, collections
sys.stdout.reconfigure(encoding='utf-8')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DATA = os.path.join(REPO, 'data')
MAPFILE = r'C:/Users/sayad/Downloads/dhamma apps/scripts/nissaya_pdf/nissaya_pdf_map.json'
AVAIL = r'C:/Users/sayad/Downloads/dhamma apps/scripts/nissaya_pdf/available.json'
TR = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')
KIND = {'mula': 'pali', 'annya': 'annya', 'attha': 'attha', 'tika': 'tika'}

if '--check' in sys.argv:
    m = json.load(open(MAPFILE, encoding='utf-8')); ok = []
    for iid, v in m.items():
        for t in range(3):
            try:
                d = json.load(urllib.request.urlopen('https://archive.org/metadata/' + iid, timeout=30)); f = {x['name']: int(x.get('size', 0)) for x in d.get('files', [])}
                if iid + '.pdf' in f and (not v.get('size') or f[iid + '.pdf'] == v['size']): ok.append(iid)
                break
            except Exception: time.sleep(3)
        time.sleep(0.1)
    json.dump(ok, open(AVAIL, 'w'), ensure_ascii=False); print('archive.org has', len(ok), 'of', len(m))
avail = set(json.load(open(AVAIL, encoding='utf-8')))
DB = {k: sqlite3.connect(os.path.join(REPO, k + '_nsy.db')) for k in set(KIND.values())}
ED = json.load(open(os.path.join(DATA, 'nissaya_editions.json'), encoding='utf-8'))
BOOKS = json.load(open(os.path.join(DATA, 'nissaya_books.json'), encoding='utf-8')); BOOKS = BOOKS if isinstance(BOOKS, list) else BOOKS.get('books', [])
files = {}                                           # web file stem -> book id
for b in BOOKS: files.setdefault(b, b)
for b, eds in ED.items():
    for e in eds: files[e['file']] = b
out = {}; stats = collections.Counter()
for stem, book in sorted(files.items()):
    p = os.path.join(DATA, stem + '.html')
    if not os.path.exists(p): continue
    kind = KIND.get(book.split('_')[0]);
    if not kind: continue
    h = open(p, encoding='utf-8').read(); parts = re.split(r'\[စာမျက်နှာ-([၀-၉]+)\]', h); marks = {}
    for i in range(1, len(parts), 2):
        ns = re.findall(r'\(နိဿယစာအုပ် စာမျက်နှာ ([၀-၉]+)\)', parts[i + 1])
        if ns: marks[int(parts[i].translate(TR))] = int(ns[0].translate(TR))
    if len(marks) < 5: stats['few marks'] += 1; continue
    cands = collections.defaultdict(dict)
    for pp, nid, npg in DB[kind].execute('select pali_book_page_number, nsy_book_id, nsy_book_page_number from pali_nsy_page_map where pali_book_id=? and nsy_book_page_number is not null', (book,)):
        try: cands[nid].setdefault(int(pp), int(npg))
        except (TypeError, ValueError): pass
    best = None
    for nid, mp in cands.items():
        d = [mp[pp] - n for pp, n in marks.items() if pp in mp]
        if len(d) < 5: continue
        mode, cnt = collections.Counter(d).most_common(1)[0]; sc = cnt / len(marks)
        if best is None or sc > best[0]: best = (sc, nid, mode)
    if not best or best[0] < 0.7: stats['no fit'] += 1; continue
    iid = 'nsy-pdf-%s-%s' % (kind, best[1])
    if iid not in avail: stats['pdf not on archive.org yet'] += 1; continue
    out[stem] = {'id': iid, 'off': best[2]}; stats['ok'] += 1
# Bhasatika books whose PDFs are already on GitHub (bhasatika_web.json: web file <-> PDF; pdf page = mark - delta + page_offset, same rule as the Bhasatika dictionary)
idx = open(os.path.join(REPO, 'index.html'), encoding='utf-8').read()
BASE = re.search(r'const TP_BT_BASE = "([^"]+)"', idx).group(1); LOC = json.loads(re.search(r'const TP_BT_LOC = (\{.*?\});', idx).group(1))
BTB = {x['file']: x.get('page_offset', 0) for x in json.loads(re.search(r'const TP_BT_BOOKS = (\[.*?\]);', idx, re.S).group(1))}
for pdf, w in json.load(open(os.path.join(DATA, 'bhasatika_web.json'), encoding='utf-8')).items():
    if w['file'].startswith('bt_') or not os.path.exists(os.path.join(DATA, w['file'] + '.html')): continue
    out[w['file']] = {'url': (LOC.get(pdf) or BASE) + pdf, 'off': BTB.get(pdf, 0) - w['delta']}; stats['bhasatika (GitHub PDF)'] += 1
json.dump(out, open(os.path.join(DATA, 'nissaya_pdf.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'), sort_keys=True)
print(dict(stats), len(out), 'files')
if '--push' in sys.argv:
    g = lambda *a: subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True)
    g('add', '--', 'data/nissaya_pdf.json')
    if g('status', '--porcelain', '--', 'data/nissaya_pdf.json').stdout.strip():
        g('commit', '-m', 'Nissaya pages: PDF icon map (archive.org)', '-m', 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>', '--', 'data/nissaya_pdf.json'); g('pull', '--rebase', '--autostash'); print('pushed' if g('push').returncode == 0 else 'PUSH FAILED')
    else: print('nothing changed')
