# -*- coding: utf-8 -*-
"""Shwekyin books (OCR + spellcheck HTML)  ->  data/skp/<id>.json {title, pages:[html], toc:[{level,title,page}]}  +  data/skp_ocr.json (the book list for the reader).

  source  : C:/Users/sayad/Documents/spellcheck/out/html/*.html  (D = the 52-book Shwekyin app, numbered 01-66 and W = other books of the Shwekyin collection)
  the page of the reader = one "စာမျက်နှာ-N" marker of the HTML (the chunk before the first marker is page 1);  each page starts with a head: printed page number + 📕 (the PDF page)
  PDF page = printed page + offset (offset = page_number - actual_page_number of the book's tocs in ShweKyin+Sarpay/database/shwekyin.db);  books without a PDF get no 📕
  usage: python scripts/build_skp_ocr.py [--push] [--all]
     (default: only the D books = the books of the Shwekyin app, which are what the web shows;  --all also builds the numbered 01-66 and W books, NOT put on the web yet)
     --push : after building, commit data/skp + data/skp_ocr.json and push to GitHub (the web updates in 1-5 minutes)
"""
import glob, json, os, re, sqlite3, statistics, subprocess, sys
ALL = '--all' in sys.argv; PUSH = '--push' in sys.argv
sys.stdout.reconfigure(encoding='utf-8')
SRC = r'C:/Users/sayad/Documents/spellcheck/out/html'
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'data', 'skp'); os.makedirs(OUT, exist_ok=True)
for _f in glob.glob(os.path.join(OUT, '*.json')):
    if not ('--all' in sys.argv or os.path.basename(_f)[3:5].isdigit()): os.remove(_f)      # old files of books that are not published (numbered / W)
DB = sqlite3.connect(os.path.join(REPO, 'ShweKyin+Sarpay', 'database', 'shwekyin.db'))
TR = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789'); MY = str.maketrans('0123456789', '၀၁၂၃၄၅၆၇၈၉')
MARK = re.compile(r'<p><font color="#999999" size="1">စာမျက်နှာ-([၀-၉]+)</font></p>\s*|<span class="pg" id="p\d+">\[([၀-၉]+)\]</span>\s*')      # the second form: older exports (13 ဓမ္မဂီတိကာ) - the marker is inside a paragraph
SKP = json.load(open(os.path.join(REPO, 'data', 'skp_index.json'), encoding='utf-8'))
try:
    import pymupdf
except Exception:
    pymupdf = None
PDFDIR = r'C:/Users/sayad/Downloads/shwekyin-pdf'


def body_of(s):
    if '<div id="bk">' not in s:
        i = s.find('</h2>'); return s[i + 5:].strip() if i >= 0 else ''
    a = s.index('<div id="bk">') + len('<div id="bk">'); b = s.find('<script', a); b = s.rfind('</div>', a, b if b > 0 else len(s))
    return s[a:b].strip()


def strip_tags(t): return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()


def sheet_title(f, s):
    m = re.search(r'<title>(.*?)</title>', s, re.S); t = m.group(1).strip() if m else os.path.basename(f)
    return re.sub(r'^[A-Za-z]*\d+[A-Za-z]*\s+(?:\d+_\d+_\d+\s+)?', '', t).strip() or t


groups = {}
def addbook(gid, gname, sid, entry):
    g = groups.setdefault(gid, {'id': gid, 'name': gname, 'books': []}); g['books'].append(sid)


books = {}
files = sorted(glob.glob(os.path.join(SRC, '*.html')))
for f in files:
    name = os.path.basename(f)
    if name.startswith('c0') or (not ALL and not name.startswith('D')): continue                      # c01 / c02 = the Bhasatika dictionary texts (already on the web elsewhere)
    s = open(f, encoding='utf-8').read(); body = body_of(s)
    if not strip_tags(body): print('empty, skipped:', name); continue
    m = re.match(r'D\d+_(\d+)_(\d+)_(\d+)_', name)
    pdf = None; auth = None
    if m:
        auth = int(m.group(2)); pdf = '%s_%s' % (m.group(2), m.group(3)); sid = 'sk_' + pdf
        r = DB.execute('select title from books where id=?', (pdf,)).fetchone(); title = r[0] if r else sheet_title(f, s)
        gid = auth
    elif name[0] == 'W': sid = 'sk_w' + name[1:3]; title = sheet_title(f, s); gid = 'x2'
    else: sid = 'sk_n' + name[:2]; title = sheet_title(f, s); gid = 'x1'
    parts = MARK.split(body)                                 # [front, label1(form 1), label1(form 2), text1, ...]
    pages = [(None, parts[0])] + [((parts[i] or parts[i + 1]).translate(TR), parts[i + 2]) for i in range(1, len(parts) - 2, 3)]
    first1 = next((i for i, (lb, _) in enumerate(pages) if lb == '1'), None)       # the in-order run of printed pages starts here (what comes before = front matter / stray numbers)
    off = None
    if pdf:
        pts = sorted({(b, a - b) for a, b in DB.execute('select page_number, actual_page_number from tocs where book_id=? and page_number is not null and actual_page_number is not null', (pdf,))})
        off = int(statistics.median([o for _, o in pts])) if pts else None      # offsets can change inside one book (several works bound together): the offset of the nearest earlier contents entry is used for each page
    npdf = 0
    if pdf and pymupdf:
        try: npdf = pymupdf.open(os.path.join(PDFDIR, pdf + '.pdf')).page_count
        except Exception: npdf = 0
    html_pages = []; label_to_page = {}
    for i, (lb, t) in enumerate(pages):
        head = ''
        if lb is not None:
            pp = (int(lb) + ([o for ap, o in pts if ap <= int(lb)] or [pts[0][1]])[-1]) if (pdf and off is not None and first1 is not None and i >= first1) else None
            if pp is not None and npdf and not (1 <= pp <= npdf): pp = None
            btn = ('<button class="skp-pdf" data-pdf="%s" data-pg="%d" title="PDF စာမျက်နှာ %d ကို ဖွင့်မည်">📕</button>' % (pdf, pp, pp)) if pp else ''
            head = '<div class="skp-ph"><span>စာမျက်နှာ-%s</span>%s</div>' % (lb.translate(MY), btn)
            if i >= (first1 or 0) and lb not in label_to_page: label_to_page[lb] = i + 1
            elif first1 is None and lb not in label_to_page: label_to_page[lb] = i + 1
        elif pdf:
            head = '<div class="skp-ph"><span>အစ</span><button class="skp-pdf" data-pdf="%s" data-pg="1" title="PDF ကို ဖွင့်မည်">📕</button></div>' % pdf
        html_pages.append(head + t.strip())
    toc = []
    if pdf:
        for h, lv, act in DB.execute('select heading, level, actual_page_number from tocs where book_id=? order by rowid', (pdf,)):
            pg = label_to_page.get(str(act)) if act is not None else None
            if pg is None and act is not None:                                 # the printed page has no marker of its own: the next one that has
                nx = [v for k, v in label_to_page.items() if int(k) >= act]; pg = min(nx) if nx else None
            if pg: toc.append({'level': min(int(lv or 1), 3), 'title': re.sub(r'\s+', ' ', h).strip(), 'page': pg})
    if not toc:
        for i, (lb, t) in enumerate(pages):
            for hh in re.findall(r'<h[23][^>]*>(.*?)</h[23]>', t, re.S):
                tt = strip_tags(hh)
                if tt: toc.append({'level': 1, 'title': tt, 'page': i + 1})
    json.dump({'title': title, 'pages': html_pages, 'toc': toc}, open(os.path.join(OUT, sid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    books[sid] = {'title': title, 'pages': len(html_pages), 'pdf': pdf, 'group': gid}
    print('%-10s %-8s pages %4d toc %4d pdf %s off %s  %s' % (sid, gid, len(html_pages), len(toc), npdf or '-', off, title[:40]))

names = {int(a['id']): a['name'] for a in SKP['authors']}
glist = []
for a in SKP['authors']:
    ids = [sid for sid, b in books.items() if b['group'] == a['id']]
    if ids: glist.append({'id': a['id'], 'name': a['name'], 'books': ids})
for gid, gname in (('x1', 'ဓမ္မစာပေများ'), ('x2', 'ဝိနည်းနှင့် သံဃာ့စာပေများ')):
    ids = [sid for sid, b in books.items() if b['group'] == gid]
    if ids: glist.append({'id': gid, 'name': gname, 'books': ids})
json.dump({'books': books, 'groups': glist}, open(os.path.join(REPO, 'data', 'skp_ocr.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(books), 'books;', sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, '*.json'))) // 1024 // 1024, 'MB')

if PUSH:
    g = lambda *a: subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True)
    g('add', '-A', '--', 'data/skp', 'data/skp_ocr.json')
    if not g('status', '--porcelain', '--', 'data/skp', 'data/skp_ocr.json').stdout.strip(): print('nothing changed - the web is already the same')
    else:
        print(g('commit', '-m', 'Shwekyin OCR books: corrections from the spellcheck HTML', '-m', 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>', '--', 'data/skp', 'data/skp_ocr.json').stdout)
        g('pull', '--rebase', '--autostash'); r = g('push'); print('pushed' if r.returncode == 0 else 'PUSH FAILED: ' + r.stderr)
