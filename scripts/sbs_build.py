"""Side-by-side builder: re-paginate Myanmar translation onto Pali pages by paragraph number.

For every 'paragraph' book pair in burmese_translated_books.json:
  - Pali page -> list of paragraph numbers (paranum field, "-1-2-")
  - Myanmar HTML -> blocks; numbered paragraph = <span class="paragraph">N</span>
  - Headings go with the NEXT numbered paragraph, other unnumbered blocks with the PREVIOUS one
  - Sequential (monotonic) matching, so numbering restarts are handled
  - A Myanmar paragraph lands on the Pali page where that number starts
Output: sidebyside/<pali_book>.js (window.SBS_DATA[id]=...) + sbs_report.json
Run: python -X utf8 scripts/sbs_build.py [book_id ...]
"""
import json, re, sys, os
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'sidebyside')
os.makedirs(OUT, exist_ok=True)

MM_DIGITS = '၀၁၂၃၄၅၆၇၈၉'
def mm2int(s):
    s = s.strip()
    if not s: return None
    t = ''.join(str(MM_DIGITS.index(c)) if c in MM_DIGITS else c for c in s)
    return int(t) if t.isdigit() else None

BLOCK = re.compile(r'<(p|h[1-6])\b[^>]*>.*?</\1>', re.S)
PARA = re.compile(r'<span class="paragraph">([^<]*)</span>')

def parse_mm(path):
    h = open(path, encoding='utf-8').read()
    body = h[h.find('<body>') + 6:]
    blocks = []
    for m in BLOCK.finditer(body):
        html = m.group(0)
        pm = PARA.search(html)
        blocks.append({'tag': m.group(1), 'html': html,
                       'num': mm2int(pm.group(1)) if pm else None})
    return blocks

def group_blocks(blocks):
    """-> list of {num, blocks[]}; num None only for a leading group."""
    groups, pending = [], []
    for b in blocks:
        if b['num'] is not None:
            groups.append({'num': b['num'], 'blocks': pending + [b]})
            pending = []
        elif b['tag'].startswith('h'):
            pending.append(b)          # heading waits for next numbered paragraph
        elif groups:
            groups[-1]['blocks'].extend(pending + [b]); pending = []
        else:
            pending.append(b)
    tail = pending
    return groups, tail

SPAN = re.compile(r'<span class="paranum">([^<]*)</span>')
TAG = re.compile(r'<[^>]+>')
def tlen(h): return len(re.sub(r'\s+', '', TAG.sub('', h)))

def pali_segments(book):
    """-> pages[{page,html}], segs[{pi, num|None, len}] in reading order.
    A seg with num=None is text at the top of a page that continues the previous paragraph."""
    recs = json.load(open(os.path.join(DATA, book + '.json'), encoding='utf-8'))
    recs.sort(key=lambda r: r['page'])
    pages, segs = [], []
    for i, r in enumerate(recs):
        html = re.sub(r'<a name="[^"]*"></a>', '', r['content'])
        pages.append({'page': r['page'], 'html': html,
                      'nums': [int(x) for x in re.findall(r'\d+', r.get('paranum') or '')]})
        parts = SPAN.split(html)          # [pre, num, text, num, text ...]
        if tlen(parts[0]) > 0:
            segs.append({'pi': i, 'num': None, 'len': (len(PMARK.findall(TAG.sub('', parts[0]))) if MODE == 'clause' else tlen(parts[0]))})
        for k in range(1, len(parts), 2):
            segs.append({'pi': i, 'num': mm2int(parts[k]), 'len': (len(PMARK.findall(TAG.sub('', parts[k + 1]))) if MODE == 'clause' else tlen(parts[k + 1]) + 1)})
    return pages, segs

def is_foot(b): return b['tag'] == 'p' and 'text-indent:3em' in b['html'][:60]

import os as _os
MODE = _os.environ.get('SBS_MODE', 'chars')
SENT = re.compile(r'(?<=[။၊])(?![^<]*>)')
PMARK = re.compile(r'[,?–။]')
MMARK = re.compile(r'[၊။]')
def chunks(html):
    m = re.match(r'(<(?:p|h\d)\b[^>]*>)(.*)(</(?:p|h\d)>)$', html, re.S)
    op, inner, cl = m.groups()
    return [(op + x + cl, (max(1, len(MMARK.findall(TAG.sub('', x)))) if MODE == 'clause' else tlen(x))) for x in SENT.split(inner) if x]

def split_group(g, seglens):
    """Distribute group blocks over len(seglens) pieces proportionally -> list of html lists."""
    n = len(seglens)
    out = [[] for _ in range(n)]
    if n == 1:
        for b in g['blocks']: out[0].append(b['html'])
        return out
    items = []   # (kind, html, len)
    for b in g['blocks']:
        if b['tag'].startswith('h'): items.append(('h', b['html'], 0))
        elif is_foot(b): items.append(('f', b['html'], 0))
        else:
            for h, l in chunks(b['html']): items.append(('t', h, l))
    total = sum(l for k, h, l in items) or 1
    ptot = sum(seglens) or 1
    cuts, acc = [], 0
    for L in seglens[:-1]:
        acc += L; cuts.append(total * acc / ptot)
    pos, cur = 0, 0
    pending = []
    def which(mid):
        for i, c in enumerate(cuts):
            if mid < c: return i
        return n - 1
    for k, h, l in items:
        if k == 'h':
            pending.append(h); continue
        if k == 't':
            cur = which(pos + l / 2); pos += l
        for ph in pending: out[cur].append(ph)
        pending = []
        out[cur].append(h)
    for ph in pending: out[cur].append(ph)
    # merge adjacent split pieces of one paragraph back into valid <p> runs (cosmetic)
    return out

def build(mm_id, pali_id):
    pages, segs = pali_segments(pali_id)
    groups, tail = group_blocks(parse_mm(os.path.join(DATA, mm_id + '.html')))
    # numbered seg index -> [seg + following continuation segs]
    num_idx = [i for i, s in enumerate(segs) if s['num'] is not None]
    per_page = [[] for _ in pages]
    unmatched, pos = [], 0
    for g in groups:
        j = pos
        while j < len(num_idx) and segs[num_idx[j]]['num'] != g['num']:
            j += 1
        if j >= len(num_idx):
            unmatched.append(g['num'])
            pi = segs[num_idx[pos - 1]]['pi'] if pos else 0
            per_page[pi].extend(b['html'] for b in g['blocks']); continue
        pos = j + 1
        k = num_idx[j]
        chain = [segs[k]]
        k += 1
        while k < len(segs) and segs[k]['num'] is None:
            chain.append(segs[k]); k += 1
        parts = split_group(g, [s['len'] for s in chain])
        # several chain segs may sit on one page? no: cont seg is always on a later page
        for s, p in zip(chain, parts):
            per_page[s['pi']].extend(p)
    if tail: per_page[-1].extend(b['html'] for b in tail)
    out = [{'p': p['page'], 'n': p['nums'], 'pali': p['html'], 'mm': chr(10).join(mm)}
           for p, mm in zip(pages, per_page)]
    skipped = sum(1 for i, p in enumerate(pages) if p['nums'] and not per_page[i])
    rep = {'mm': mm_id, 'pali': pali_id, 'pali_pages': len(pages), 'mm_paragraphs': len(groups),
           'pali_numbers': len(num_idx), 'unmatched_mm': unmatched[:50], 'unmatched_count': len(unmatched),
           'numbered_pali_pages_without_mm': skipped,
           'pali_pages_without_numbers': sum(1 for p in pages if not p['nums'])}
    return out, rep

SPLIT_DIR = os.path.join(DATA, 'mm_split')
def export_split(pali_id, mm_id, data):
    """Publishable form: data/mm_split/<pali_id>.json = {"<pali page>": "<mm html>"} (empty pages left out)
    and data/mm_split/index.json = {pali_id: {"mm": mm_id}} (only books that matched fully)."""
    os.makedirs(SPLIT_DIR, exist_ok=True)
    pages = {str(d['p']): d['mm'] for d in data if d['mm'].strip()}
    with open(os.path.join(SPLIT_DIR, pali_id + '.json'), 'w', encoding='utf-8') as f:
        json.dump(pages, f, ensure_ascii=False, separators=(',', ':'))
    ip = os.path.join(SPLIT_DIR, 'index.json')
    idx = json.load(open(ip, encoding='utf-8')) if os.path.exists(ip) else {}
    idx[pali_id] = {'mm': mm_id, 'pages': len(data)}
    json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)

def main():
    books = json.load(open(os.path.join(ROOT, 'burmese_translated_books.json'), encoding='utf-8'))
    want = set(sys.argv[1:])
    reps = []
    for b in books:
        if b['link_type'] != 'paragraph' or (want and b['mm_book_id'] not in want):
            if b['link_type'] != 'paragraph': reps.append({'mm': b['mm_book_id'], 'skipped': 'link_type=' + b['link_type']})
            continue
        if not os.path.exists(os.path.join(DATA, b['mm_book_id'] + '.html')):
            continue          # old translation file removed after its split was published (data/mm_split/)
        try:
            data, rep = build(b['mm_book_id'], b['pali_book_id'])
        except Exception as e:
            reps.append({'mm': b['mm_book_id'], 'error': repr(e)}); continue
        rep['title'] = b['mm_book_id']
        rep['pali_book'] = b['pali_book_id']
        if rep['unmatched_count'] == 0 and rep['mm_paragraphs'] > 0:
            export_split(b['pali_book_id'], b['mm_book_id'], data)
        reps.append(rep)
        with open(os.path.join(OUT, b['mm_book_id'] + '.js'), 'w', encoding='utf-8') as f:
            f.write('window.SBS_DATA=window.SBS_DATA||{};window.SBS_DATA[%s]=%s;' % (
                json.dumps(b['mm_book_id']), json.dumps(data, ensure_ascii=False)))
        print(b['mm_book_id'], rep['pali_pages'], 'pages; mm paras', rep['mm_paragraphs'],
              'unmatched', rep['unmatched_count'])
    names = {x['id']: x['name'] for x in json.load(open(os.path.join(ROOT, 'myanmar_books.json'), encoding='utf-8'))}
    lst = [{'id': r['mm'], 'name': names.get(r['mm'], r['mm']), 'pages': r['pali_pages'],
            'bad': r['unmatched_count']} for r in reps if 'pali_pages' in r and r['mm_paragraphs'] > 0]
    with open(os.path.join(OUT, 'books.js'), 'w', encoding='utf-8') as f:
        f.write('window.SBS_BOOKS=' + json.dumps(lst, ensure_ascii=False) + ';')
    json.dump(reps, open(os.path.join(OUT, 'sbs_report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
