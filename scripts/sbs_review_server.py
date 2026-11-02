"""Local review server for sidebyside/index.html (port 8796).

Lists every Myanmar paragraph number that could not be found in the Pali book (books with 1-6 such
numbers), shows the context, and lets the user correct the number in data/<mm>.html with one click.
Every edit keeps a backup in sidebyside/backups/ and the book is rebuilt straight away.
Run: python -X utf8 scripts/sbs_review_server.py   (or double-click sbs_review.bat)
"""
import json, os, re, sys, shutil, time, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sbs_build as B

ROOT, DATA, OUT = B.ROOT, B.DATA, B.OUT
BACKUP = os.path.join(OUT, 'backups')
PORT = 8796
MAX_ISSUES_PER_BOOK = 30         # books with more are "other kinds of problems" (restarts, jumps ...)
LOCK = threading.Lock()
_cache = {}                      # mm_id -> issues list
_pali = {}                       # pali_id -> pages
NAMES = {x['id']: x['name'] for x in json.load(open(os.path.join(ROOT, 'myanmar_books.json'), encoding='utf-8'))}
BOOKS = [b for b in json.load(open(os.path.join(ROOT, 'burmese_translated_books.json'), encoding='utf-8'))
         if b['link_type'] == 'paragraph' and os.path.exists(os.path.join(DATA, b['mm_book_id'] + '.html'))]
TAG = re.compile(r'<[^>]+>')

def plain(blocks):
    return '\n'.join(re.sub(r'\s+', ' ', TAG.sub('', b['html'])).strip() for b in blocks)

def pali_book(pali_id):
    if pali_id not in _pali:
        _pali[pali_id] = B.pali_segments(pali_id)
    return _pali[pali_id]

def analyze(mm_id, pali_id):
    pages, segs = pali_book(pali_id)
    groups, _ = B.group_blocks(B.parse_mm(os.path.join(DATA, mm_id + '.html')))
    num_idx, matched = B.match_groups(groups, segs)
    B.settle(groups, matched)
    used = {j for j in matched if j is not None}
    issues = []
    for gi, g in enumerate(groups):
        if matched[gi] is not None: continue
        prev = next((matched[x] for x in range(gi - 1, -1, -1) if matched[x] is not None), -1)
        nxt = next((matched[x] for x in range(gi + 1, len(groups)) if matched[x] is not None), len(num_idx))
        cands = []
        for j in range(prev + 1, nxt):
            if j in used: continue
            sg = segs[num_idx[j]]
            cands.append({'num': sg['num'], 'txt': sg['txt'], 'page': pages[sg['pi']]['page']})
        p_from = pages[segs[num_idx[prev]]['pi']]['page'] if prev >= 0 else pages[0]['page']
        p_to = pages[segs[num_idx[min(nxt, len(num_idx) - 1)]]['pi']]['page']
        if cands: p_to = max(p_to, cands[-1]['page']); p_from = min(p_from, cands[0]['page'])
        p_to = min(p_to, p_from + 4)
        sug = cands[0]['num'] if len(cands) == 1 else None
        issues.append({
            'id': '%s:%d:%d' % (mm_id, gi, g['num']), 'mm': mm_id, 'pali': pali_id, 'k': gi, 'num': g['num'],
            'book': NAMES.get(mm_id, mm_id), 'cands': cands, 'suggest': sug,
            'from': p_from, 'to': p_to,
            'prev': {'num': groups[gi - 1]['num'], 'text': plain(groups[gi - 1]['blocks'])[-350:]} if gi else None,
            'cur': plain(g['blocks'])[:1500],
            'next': {'num': groups[gi + 1]['num'], 'text': plain(groups[gi + 1]['blocks'])[:350]} if gi + 1 < len(groups) else None,
            'total': len(groups)})
    return issues

def all_issues():
    out = []
    for b in BOOKS:
        mm = b['mm_book_id']
        if mm not in _cache:
            try: _cache[mm] = analyze(mm, b['pali_book_id'])
            except Exception as e: print('analyze failed', mm, e); _cache[mm] = []
        if 0 < len(_cache[mm]) <= MAX_ISSUES_PER_BOOK: out.extend(_cache[mm])
    return out

WORD = re.compile(r'<[^>]*>|[^<\s]+')
def wrap_words(content):
    """Wrap every word of the raw page html in <i class=w data-o=raw-offset> so the viewer can say where a paragraph starts."""
    out, in_num, last = [], False, 0
    for m in WORD.finditer(content):
        t = m.group(0)
        out.append(content[last:m.start()]); last = m.end()
        if t.startswith('<'):
            if t.startswith('<span class="paranum"'): in_num = True
            elif in_num and t.startswith('</span'): in_num = False
            out.append(t)
        elif in_num: out.append(t)
        else: out.append('<i class="w" data-o="%d">%s</i>' % (m.start(), t))
    out.append(content[last:])
    return ''.join(out)

def pali_json_path(pali_id): return os.path.join(DATA, pali_id + '.json')

def insert_pali_number(pali_id, page, offset, num):
    """Insert <span class="paranum">N</span>။ at a raw offset of a Pali page and refresh that page's paranum field."""
    path = pali_json_path(pali_id)
    recs = json.load(open(path, encoding='utf-8'))
    rec = next((r for r in recs if r['page'] == page), None)
    if rec is None: raise ValueError('page not found')
    c = rec['content']
    if not (0 <= offset < len(c)) or c[offset] in ('<', '>', ' ', chr(10)): raise ValueError('bad position')
    if re.search(r'<span class="paranum">%s</span>' % my(num), c): raise ValueError('this page already has paragraph %d' % num)
    os.makedirs(BACKUP, exist_ok=True)
    shutil.copy2(path, os.path.join(BACKUP, '%s.%s.json' % (pali_id, time.strftime('%Y%m%d-%H%M%S'))))
    rec['content'] = c[:offset] + '<span class="paranum">%s</span>။ ' % my(num) + c[offset:]
    nums = [B.mm2int(x) for x in B.SPAN.findall(rec['content'])]
    rec['paranum'] = '-' + '-'.join(str(n) for n in nums) + '-'
    with open(path, 'w', encoding='utf-8', newline=chr(10)) as f:
        f.write(json.dumps(recs, indent=4, ensure_ascii=False, sort_keys=True))
    _pali.pop(pali_id, None)
    res = {'books': []}
    for b in BOOKS:
        if b['pali_book_id'] != pali_id: continue
        mm = b['mm_book_id']
        data, rep = B.build(mm, pali_id)
        with open(os.path.join(OUT, mm + '.js'), 'w', encoding='utf-8') as f:
            f.write('window.SBS_DATA=window.SBS_DATA||{};window.SBS_DATA[%s]=%s;' % (json.dumps(mm), json.dumps(data, ensure_ascii=False)))
        exported = False
        if B.exportable(rep): B.export_split(pali_id, mm, data); exported = True
        _cache.pop(mm, None)
        res.update({'left_in_book': rep['unmatched_count'], 'exported': exported})
    return res

def my(n):
    return ''.join(B.MM_DIGITS[int(c)] for c in str(n))

def apply_fix(mm, k, old, new):
    b = next((x for x in BOOKS if x['mm_book_id'] == mm), None)
    if not b: raise ValueError('unknown book')
    path = os.path.join(DATA, mm + '.html')
    raw = open(path, encoding='utf-8', newline='').read()
    base = raw.find('<body>') + 6
    cnt = -1
    for m in B.BLOCK.finditer(raw, base):
        pm = B.PARA.search(m.group(0))
        if not pm: continue
        cnt += 1
        if cnt != k: continue
        if B.mm2int(pm.group(1)) != old: raise ValueError('number changed meanwhile (%s != %s)' % (pm.group(1), old))
        a, z = m.start() + pm.start(1), m.start() + pm.end(1)
        os.makedirs(BACKUP, exist_ok=True)
        shutil.copy2(path, os.path.join(BACKUP, '%s.%s.html' % (mm, time.strftime('%Y%m%d-%H%M%S'))))
        open(path, 'w', encoding='utf-8', newline='').write(raw[:a] + my(new) + raw[z:])
        break
    else:
        raise ValueError('paragraph block not found')
    data, rep = B.build(mm, b['pali_book_id'])
    with open(os.path.join(OUT, mm + '.js'), 'w', encoding='utf-8') as f:
        f.write('window.SBS_DATA=window.SBS_DATA||{};window.SBS_DATA[%s]=%s;' % (json.dumps(mm), json.dumps(data, ensure_ascii=False)))
    exported = False
    if B.exportable(rep):
        B.export_split(b['pali_book_id'], mm, data); exported = True
    _cache.pop(mm, None)
    return {'left_in_book': rep['unmatched_count'], 'exported': exported}

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=OUT, **kw)
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def j(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/api/issues':
            with LOCK: return self.j({'issues': all_issues()})
        if u.path == '/api/pali':
            q = parse_qs(u.query); pid = q['book'][0]; a, z = int(q['from'][0]), int(q['to'][0])
            recs = json.load(open(pali_json_path(pid), encoding='utf-8'))
            return self.j([{'page': r['page'], 'html': wrap_words(r['content'])} for r in recs if a <= r['page'] <= z])
        return super().do_GET()
    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ('/api/fix', '/api/paliinsert'): return self.j({'error': 'not found'}, 404)
        try:
            d = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            with LOCK:
                if path == '/api/fix': res = apply_fix(d['mm'], int(d['k']), int(d['old']), int(d['new']))
                else: res = insert_pali_number(d['pali'], int(d['page']), int(d['offset']), int(d['num']))
                res['issues'] = all_issues()
            self.j(res)
        except Exception as e:
            self.j({'error': str(e)}, 400)
    def log_message(self, *a): pass

if __name__ == '__main__':
    print('Loading issues ...'); n = len(all_issues()); print('%d issues. Open http://127.0.0.1:%d/' % (n, PORT))
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
