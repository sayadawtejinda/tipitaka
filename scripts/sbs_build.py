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

NUMRE = re.compile(r'\s*([၀-၉]+)(?:\s*[-–]\s*([၀-၉]+))?')
def parse_num(t):
    """'၁၇၇' -> (177, 177);  '၁၇၇-၁၇၉' -> (177, 179);  '၁။' -> (1, 1);  anything else -> None"""
    m = NUMRE.match(t or '')
    if not m: return None
    lo = mm2int(m.group(1)); hi = mm2int(m.group(2)) if m.group(2) else lo
    return (lo, hi) if hi >= lo else (lo, lo)

BLOCK = re.compile(r'<(p|h[1-6])\b[^>]*>.*?</\1>', re.S)
PARA = re.compile(r'<span class="paragraph">([^<]*)')   # closing </span> may be missing/garbled in the source (e.g. '၂၇၈</b></a></a>။')

def parse_mm(path):
    h = open(path, encoding='utf-8').read()
    body = h[h.find('<body>') + 6:]
    blocks = []
    for m in BLOCK.finditer(body):
        html = m.group(0)
        pm = PARA.search(html)
        pn = parse_num(pm.group(1)) if pm else None
        blocks.append({'tag': m.group(1), 'html': html,
                       'num': pn[0] if pn else None, 'hi': pn[1] if pn else None})
    return blocks

def group_blocks(blocks):
    """-> list of {num, blocks[]}; num None only for a leading group."""
    groups, pending = [], []
    for b in blocks:
        if b['num'] is not None:
            groups.append({'num': b['num'], 'hi': b['hi'], 'blocks': pending + [b]})
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
            pn = parse_num(parts[k]) or (None, None)
            segs.append({'pi': i, 'num': pn[0], 'hi': pn[1], 'txt': parts[k].strip(), 'len': (len(PMARK.findall(TAG.sub('', parts[k + 1]))) if MODE == 'clause' else tlen(parts[k + 1]) + 1)})
    return pages, segs

def is_foot(b): return b['tag'] == 'p' and 'text-indent:3em' in b['html'][:60]

import os as _os
MODE = _os.environ.get('SBS_MODE', 'chars')
SENT = re.compile(r'(?<=[။၊])(?![^<]*>)')
PMARK = re.compile(r'[,?–။]')
MMARK = re.compile(r'[၊။]')
def split_inner(inner):
    """Cut after every '။' or '၊' that is outside a tag. The pieces always add up to exactly `inner`."""
    out, cur = [], ''
    for tok in re.split('(<[^>]*>)', inner):
        if len(tok) > 1 and tok[0] == '<' and tok[-1] == '>':
            cur += tok; continue
        for piece in re.split('(?<=[။၊])', tok):
            cur += piece
            if piece.endswith('။') or piece.endswith('၊'):
                out.append(cur); cur = ''
    if cur: out.append(cur)
    return out

def chunks(html):
    m = re.match(r'(<(?:p|h\d)\b[^>]*>)(.*)(</(?:p|h\d)>)$', html, re.S)
    op, inner, cl = m.groups()
    return [(op + x + cl, (max(1, len(MMARK.findall(TAG.sub('', x)))) if MODE == 'clause' else tlen(x))) for x in split_inner(inner) if x]

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

def _ov(a, b): return a[0] <= b[1] and b[0] <= a[1]

def match_groups(groups, segs):
    """Align Myanmar paragraphs with the numbered Pali segments.
    Numbers may be ranges (177-179) on either side. Returns (num_idx, matched) where matched[gi] is an index
    into num_idx or None.  Greedy first; if anything is left over, longest-common-subsequence (so a duplicated or
    mistyped number blames the right paragraph, and the later duplicate keeps the match)."""
    num_idx = [i for i, s in enumerate(segs) if s['num'] is not None]
    sn = [(segs[i]['num'], segs[i]['hi']) for i in num_idx]
    gn = [(g['num'], g['hi']) for g in groups]
    n, m = len(gn), len(sn)
    matched, pos = [], 0
    for g in gn:
        j = pos
        while j < m and not _ov(g, sn[j]): j += 1
        if j >= m: matched.append(None)
        else: matched.append(j); pos = j + 1 if sn[j][1] <= g[1] else j
    if any(x is None for x in matched):
        dp = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            gi, row, prow = gn[i - 1], dp[i], dp[i - 1]
            for j in range(1, m + 1):
                if _ov(gi, sn[j - 1]):
                    v = prow[j - 1] + 1 - 1e-4 * abs(i / n - j / m)   # on equal counts prefer the match at the same relative place
                    if prow[j] > v: v = prow[j]
                    if row[j - 1] > v: v = row[j - 1]
                    row[j] = v
                else:
                    row[j] = prow[j] if prow[j] >= row[j - 1] else row[j - 1]
        matched = [None] * n
        i, j = n, m
        while i > 0 and j > 0:
            if _ov(gn[i - 1], sn[j - 1]) and dp[i][j] == dp[i - 1][j - 1] + 1 - 1e-4 * abs(i / n - j / m):
                matched[i - 1] = j - 1; i -= 1; j -= 1
            elif dp[i - 1][j] >= dp[i][j - 1]: i -= 1
            else: j -= 1
        # a leftover paragraph that sits inside the same range as its matched neighbour (177, 178 inside 177-179)
        for gi in range(n):
            if matched[gi] is not None: continue
            for nb in (gi - 1, gi + 1):
                if 0 <= nb < n and matched[nb] is not None and sn[matched[nb]][1] > sn[matched[nb]][0] and _ov(gn[gi], sn[matched[nb]]):
                    matched[gi] = matched[nb]; break
    return num_idx, matched

def settle(groups, matched):
    """in place: attach numbered notes / repeated numbers to their paragraph; returns the attached numbers"""
    # a numbered note whose number restarts (1, 2 ... after paragraph 339) belongs to the paragraph before it
    attached, anchor, gi = [], None, 0
    while gi < len(groups):
        if matched[gi] is not None: anchor = gi; gi += 1; continue
        z = gi
        while z < len(groups) and matched[z] is None: z += 1
        if anchor is not None and z - gi <= 12:           # a long unmatched run is a real mismatch, not notes
            for x in range(gi, z):
                if groups[x]['num'] <= groups[anchor]['num']:
                    matched[x] = matched[anchor]; attached.append(groups[x]['num'])
        gi = z
    for gi in range(len(groups) - 2, -1, -1):          # same number twice in a row: both parts belong to one Pali paragraph
        if matched[gi] is None and matched[gi + 1] is not None and groups[gi]['num'] == groups[gi + 1]['num']:
            matched[gi] = matched[gi + 1]
    return attached

def build(mm_id, pali_id):
    pages, segs = pali_segments(pali_id)
    groups, tail = group_blocks(parse_mm(os.path.join(DATA, mm_id + '.html')))
    num_idx, matched = match_groups(groups, segs)
    attached = settle(groups, matched)
    per_page = [[] for _ in pages]
    unmatched = [g['num'] for g, j in zip(groups, matched) if j is None]
    last_pi, gi = 0, 0
    while gi < len(groups):
        j = matched[gi]
        if j is None:
            per_page[last_pi].extend(b['html'] for b in groups[gi]['blocks']); gi += 1; continue
        blocks = list(groups[gi]['blocks']); gi += 1
        while gi < len(groups) and matched[gi] == j:       # several paragraphs inside one Pali range -> one piece
            blocks.extend(groups[gi]['blocks']); gi += 1
        k = num_idx[j]
        chain = [segs[k]]; k += 1
        while k < len(segs) and segs[k]['num'] is None:
            chain.append(segs[k]); k += 1
        parts = split_group({'blocks': blocks}, [s['len'] for s in chain])
        for s, p in zip(chain, parts):
            per_page[s['pi']].extend(p)
        last_pi = chain[0]['pi']
    if tail: per_page[-1].extend(b['html'] for b in tail)
    out = [{'p': p['page'], 'n': p['nums'], 'pali': p['html'], 'mm': chr(10).join(mm)}
           for p, mm in zip(pages, per_page)]
    skipped = sum(1 for i, p in enumerate(pages) if p['nums'] and not per_page[i])
    big = max(tlen(chr(10).join(x)) for x in per_page)
    rep = {'mm': mm_id, 'pali': pali_id, 'pali_pages': len(pages), 'mm_paragraphs': len(groups),
           'pali_numbers': len(num_idx), 'unmatched_mm': unmatched[:50], 'unmatched_count': len(unmatched), 'attached_notes': len(attached), 'max_page_chars': big,
           'numbered_pali_pages_without_mm': skipped,
           'pali_pages_without_numbers': sum(1 for p in pages if not p['nums'])}
    return out, rep

SPLIT_DIR = os.path.join(DATA, 'mm_split')
def _published(pali_id):
    ip = os.path.join(SPLIT_DIR, 'index.json')
    return os.path.exists(ip) and pali_id in json.load(open(ip, encoding='utf-8'))
def exportable(rep):
    """fully matched and no page holds a lump of text (one huge Myanmar paragraph / a numbering gap)"""
    return rep['mm_paragraphs'] > 0 and rep['unmatched_count'] == 0 and rep['max_page_chars'] <= 30000
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
        if exportable(rep) or _published(b['pali_book_id']):
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
