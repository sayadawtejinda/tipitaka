"""Side-by-side (Pali | Myanmar) for the commentary books that have no paragraph numbers
(Dhammapada-atthakatha, Jataka-atthakatha): python -X utf8 scripts/sbs_attha.py [mm_book_id ...]

Anchors, in order of strength:
  1. the numbered story / jataka headings, paired one to one in reading order (Pali subhead <-> Myanmar <h2>);
  2. verses: the Pali verse quoted in a Myanmar <blockquote> is searched, letter for letter, in the Pali story;
  between anchors the Myanmar text is spread over the Pali pages in proportion to the text length.
Output has the same shape as sbs_build.py (sidebyside/<mm>.js and data/mm_split/<pali>.json)."""
import json, os, re, sys, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sbs_build as B

ROOT, DATA, OUT = B.ROOT, B.DATA, B.OUT
TAG = B.TAG
LET = re.compile(r'[^က-ဪေ-္ျ-ှ]')        # letters of the script only (no digits, marks, punctuation)
MMBLOCK = re.compile(r'<(h[1-6]|p|blockquote)\b[^>]*>.*?</\1>', re.S)
PBLOCK = re.compile(r'<p class="([^"]+)"[^>]*>(.*?)</p>', re.S)
HEAD = re.compile(r'\s*([၀-၉]+)\s*[။-]')

def mm_blocks(path):
    h = open(path, encoding='utf-8').read()
    return [{'tag': m.group(1), 'html': m.group(0)} for m in MMBLOCK.finditer(h[h.find('<body>') + 6 if '<body>' in h else 0:])]

def plain(h): return re.sub(r'\s+', ' ', TAG.sub('', h)).strip()
def norm(h): return LET.sub('', TAG.sub('', h))

def mm_stories(blocks, kind):
    """-> (pre, stories); a story starts at an <h2>; headings of higher level right before it go with it."""
    starts = [i for i, b in enumerate(blocks) if b['tag'] == 'h2']
    st = []
    for n, i in enumerate(starts):
        a = i
        while a > 0 and blocks[a - 1]['tag'] == 'h1' and (n == 0 or a - 1 >= starts[n - 1] + 1): a -= 1
        st.append(a)
    pre = blocks[:st[0]] if st else blocks
    out = []
    for n, a in enumerate(st):
        z = st[n + 1] if n + 1 < len(st) else len(blocks)
        out.append(blocks[a:z])
    return pre, out

def pali_stories(recs, is_story):
    """Pali blocks in reading order; story k starts at the k-th subhead accepted by is_story."""
    flat = []                                         # {page, cls, html, len, story}
    cur = -1
    for r in recs:
        content = re.sub(r'<a name="[^"]*"></a>', '', r['content'])
        for m in PBLOCK.finditer(content):
            cls, inner = m.group(1), m.group(2)
            if cls in ('subhead', 'title', 'bodytext') and is_story(cls, plain(inner)): cur += 1
            flat.append({'page': r['page'], 'cls': cls, 'html': inner, 'len': B.tlen(inner) + 1, 'story': cur})
    return flat

def interp(anchors, x):
    """piecewise linear map of mm position x -> pali position, anchors = sorted [(mm, pali)]"""
    xs = [a[0] for a in anchors]
    i = bisect.bisect_right(xs, x) - 1
    if i < 0: return anchors[0][1]
    if i >= len(anchors) - 1: return anchors[-1][1]
    (x0, y0), (x1, y1) = anchors[i], anchors[i + 1]
    return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)

def place_story(mm_blocks_, pblocks, stats):
    """-> {page: [html,...]} for one story"""
    items = []                                         # (kind, html, len, anchor_text|None, block id)
    for bi, b in enumerate(mm_blocks_):
        if b['tag'].startswith('h'): items.append(('h', b['html'], 0, None, None))
        elif b['tag'] == 'blockquote': items.append(('t', b['html'], B.tlen(b['html']), norm(b['html']), bi))
        else:
            for h, l in B.chunks(b['html']): items.append(('t', h, l, None, bi))
    total = sum(i[2] for i in items) or 1
    cum, c = [], 0                                     # pali cumulative start of each block
    for p in pblocks: cum.append(c); c += p['len']
    ptotal = c or 1
    # flat letters of the pali story with block index lookup
    letters, starts = '', []
    for p in pblocks: starts.append(len(letters)); letters += norm(p['html'])
    anchors, pos, last_y, last_find = [(0, 0)], 0, 0, 0
    for k, (kind, h, l, key, bid) in enumerate(items):
        if kind == 't' and key and len(key) >= 25:
            j = letters.find(key[:40], last_find)
            if j >= 0:
                bi = bisect.bisect_right(starts, j) - 1
                y = cum[bi] + (j - starts[bi]) * pblocks[bi]['len'] / max(1, len(norm(pblocks[bi]['html'])))
                if y >= last_y and pos >= anchors[-1][0]:
                    anchors.append((pos, y)); last_y = y; last_find = j; stats['anchored'] += 1
            else: stats['verse_not_found'] += 1
        if kind == 't': pos += l
    anchors.append((total, ptotal))
    # monotone mm positions required: already (pos nondecreasing); duplicates ok
    pages = {}
    pend, pos = [], 0
    page_of = lambda y: pblocks[min(len(pblocks) - 1, max(0, bisect.bisect_right(cum, y) - 1))]['page']
    for kind, h, l, key, bid in items:
        if kind == 'h': pend.append(h); continue
        pg = page_of(interp(anchors, pos + l / 2)); pos += l
        pages.setdefault(pg, []).extend([(None, x) for x in pend] + [(bid, h)]); pend = []
    if pend: pages.setdefault(page_of(ptotal - 1), []).extend((None, x) for x in pend)
    pages = {pg: B.join_pieces(v) for pg, v in pages.items()}
    # accuracy of plain proportion at the anchors (for the report)
    for mmpos, y in anchors[1:-1]:
        stats['err'].append(abs(page_of(total and mmpos * ptotal / total) - page_of(y)))
    return pages

def build(mm_id, pali_id, is_story):
    recs = json.load(open(os.path.join(DATA, pali_id + '.json'), encoding='utf-8')); recs.sort(key=lambda r: r['page'])
    flat = pali_stories(recs, is_story)
    nst = max(x['story'] for x in flat) + 1
    pre, mst = mm_stories(mm_blocks(os.path.join(DATA, mm_id + '.html')), 'h2')
    stats = {'anchored': 0, 'verse_not_found': 0, 'err': [], 'pali_stories': nst, 'mm_stories': len(mst)}
    per_page = {}
    if nst != len(mst): return None, dict(stats, error='story counts differ')
    # order check by story numbers
    mism = 0
    for k in range(nst):
        pn = HEAD.match(plain(next(x['html'] for x in flat if x['story'] == k and x['cls'] in ('subhead', 'title', 'bodytext'))))
        mn = HEAD.match(plain(mst[k][[b['tag'] for b in mst[k]].index('h2')]['html']))
        if pn and mn and B.mm2int(pn.group(1)) != B.mm2int(mn.group(1)): mism += 1
    stats['number_mismatch'] = mism
    first_story_page = None
    for k in range(nst):
        pb = [x for x in flat if x['story'] == k]
        for pg, hs in place_story(mst[k], pb, stats).items(): per_page.setdefault(pg, []).extend(hs)
    if pre: per_page.setdefault(next(x['page'] for x in flat if x['story'] == 0), [])[:0] = [b['html'] for b in pre]
    pages, _ = B.pali_segments(pali_id)
    data = [{'p': p['page'], 'n': p['nums'], 'pali': p['html'], 'mm': chr(10).join(per_page.get(p['page'], []))} for p in pages]
    src = ''.join(re.sub(r'\s+', '', TAG.sub('', b['html'])) for b in mm_blocks(os.path.join(DATA, mm_id + '.html')))
    out = ''.join(re.sub(r'\s+', '', TAG.sub('', d['mm'])) for d in data)
    stats['text_kept'] = (len(out) / len(src)) if src else 0
    stats['max_page_chars'] = max(B.tlen(d['mm']) for d in data)
    stats['pages_with_mm'] = sum(1 for d in data if d['mm'].strip()); stats['pages'] = len(data)
    return data, stats

SETS = {
    '08_dhammapada_01': ('attha_ku_02_01', lambda cls, t: cls == 'subhead' and re.match(r'\s*[၀-၉]+။.*ဝတ္ထု', t) is not None),
    '08_dhammapada_02': ('attha_ku_02_02', lambda cls, t: cls == 'subhead' and re.match(r'\s*[၀-၉]+။.*ဝတ္ထု', t) is not None),
}

def main():
    want = set(sys.argv[1:]) or set(SETS)
    names = {x['id']: x['name'] for x in json.load(open(os.path.join(ROOT, 'myanmar_books.json'), encoding='utf-8'))}
    lst = []
    for mm, (pali, is_story) in SETS.items():
        if mm not in want: continue
        data, st = build(mm, pali, is_story)
        err = st.pop('err'); st['mean_page_error_of_plain_proportion'] = round(sum(err) / len(err), 2) if err else None
        print(mm, json.dumps(st, ensure_ascii=False))
        if data is None: continue
        with open(os.path.join(OUT, mm + '.js'), 'w', encoding='utf-8') as f:
            f.write('window.SBS_DATA=window.SBS_DATA||{};window.SBS_DATA[%s]=%s;' % (json.dumps(mm), json.dumps(data, ensure_ascii=False)))
        lst.append({'id': mm, 'name': names.get(mm, mm), 'pages': len(data), 'bad': 0})
        if st['text_kept'] == 1 and st.get('number_mismatch', 1) == 0:
            B.export_split(pali, mm, data)
    ab = os.path.join(OUT, 'attha_books.json')
    old = json.load(open(ab, encoding='utf-8')) if os.path.exists(ab) else []
    json.dump([x for x in old if x['id'] not in {y['id'] for y in lst}] + lst, open(ab, 'w', encoding='utf-8'), ensure_ascii=False)

if __name__ == '__main__':
    main()
