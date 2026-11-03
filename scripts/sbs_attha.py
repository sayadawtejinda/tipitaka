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
import sbs_gc as gc

ROOT, DATA, OUT = B.ROOT, B.DATA, B.OUT
TAG = B.TAG
LET = re.compile(r'[^က-ဪေ-္ျ-ှ]')        # letters of the script only (no digits, marks, punctuation)
MMBLOCK = re.compile(r'<(h[1-6]|p|blockquote)\b[^>]*>.*?</\1>', re.S)
PBLOCK = re.compile(r'<p class="([^"]+)"[^>]*>(.*?)</p>', re.S)
CONS = re.compile(r'[^က-အ]')
import math
LEX_C = float(os.environ.get('SBS_LEX_C', '40'))     # penalty per whole story of distance from the proportional / verse-anchored position
def grams(h, k=int(os.environ.get("SBS_K","3"))):
    s = CONS.sub('', TAG.sub('', h))
    return {s[i:i + k] for i in range(len(s) - k + 1)}

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
    cur, last_txt, last_at = -1, None, -99
    for r in recs:
        content = re.sub(r'<a name="[^"]*"></a>', '', r['content'])
        for m in PBLOCK.finditer(content):
            cls, inner = m.group(1), m.group(2)
            if is_story(cls, plain(inner)):
                txt = norm(inner)
                if not (txt == last_txt and len(flat) - last_at <= 4): cur += 1       # the same heading twice in a row is one story
                last_txt, last_at = txt, len(flat)
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

PWORD = re.compile(r"[\s၊။,;:?()\[\]\-.\u2018\u2019\u201c\u201d'\"]+")
SENT_HEAD = re.compile(r'(^|။\s*)([^၊။<>]{1,60})၊')
END_MM = re.compile(r'^\s*(?:(?:ဂါထာ|ဒေသနာ)\S*၏\s*အဆုံး|ဇာတ်ပေါင်း)')

BURMESE_HEAD = {'ဝါ'}                          # 'or' in the translation: Burmese although it stands before a ၊

def nw(w): return w.replace('၀', 'ဝ')           # the digit zero is often typed for the letter wa

def pali_wordset(pblocks):
    ws = set()
    for p in pblocks:
        for w in PWORD.split(TAG.sub(' ', p['html'])):
            if len(w) > 1: ws.add(nw(w))
    return ws

def is_pali_word(w, wordset):
    w = nw(w)
    return w in wordset or '္' in w                # a stacked consonant (က္ခ ဒ္ဓ ...) hardly occurs in Burmese words

def is_pali_head(head, wordset):
    ws = [w for w in PWORD.split(head.strip()) if w]
    ok = [w for w in ws if is_pali_word(w, wordset)]
    return bool(ok) and len(ok) >= len(ws) * 0.5

def group_gatha(blocks, wordset):
    """The jataka translation prints a verse as several short <p> lines in Pali (then 'ဟူသော ဤဂါထာကို ဟောတော်မူ၏။').
    Returns the blocks with every such run replaced by one blockquote."""
    def verse_line(b):
        if b['tag'] != 'p' or 'class="ending"' in b['html'][:40]: return False
        t_ = plain(b['html'])
        if not 4 <= len(t_) <= 90: return False
        ws = [w for w in PWORD.split(t_) if w and not re.fullmatch(r'[၀-၉]+', w)]
        return bool(ws) and sum(1 for w in ws if is_pali_word(w, wordset)) >= 0.7 * len(ws)
    out, i = [], 0
    while i < len(blocks):
        j = i
        while j < len(blocks) and verse_line(blocks[j]): j += 1
        if j - i >= 2:
            if j < len(blocks) and blocks[j]['tag'] == 'p' and plain(blocks[j]['html']).startswith('ဟူသော') and len(plain(blocks[j]['html'])) < 80: j += 1
            inner = [re.sub(r'^<p[^>]*>|</p>$', '', b['html'], flags=re.S) for b in blocks[i:j]]
            out.append({'tag': 'blockquote', 'html': '<blockquote>' + '<br>'.join(inner) + '</blockquote>'})
            i = j
        else:
            out.append(blocks[i]); i += 1
    return out

def mark_nissaya(blocks, wordset):
    """After a verse (<blockquote>) the translation gives a Pali-Myanmar word list: 'Pali၊ meaning။ Pali၊ meaning။'.
    Returns blocks with those paragraphs flagged ('nis') and the Pali word at the start of every pair in <b>."""
    out, after_verse = [], False
    wordset = set(wordset)
    for b in blocks:                                # the verses of the translation are Pali too
        if b['tag'] == 'blockquote':
            for w in PWORD.split(TAG.sub(' ', b['html'])):
                if len(w) > 1: wordset.add(nw(w))
    for b in blocks:
        nb = dict(b)
        if b['tag'] == 'blockquote': after_verse = True
        elif b['tag'].startswith('h') or (b['tag'] == 'p' and 'class="ending"' in b['html'][:40]): after_verse = False
        elif b['tag'] == 'p' and after_verse and END_MM.match(plain(b['html'])): after_verse = False
        elif b['tag'] == 'p' and after_verse and '<' not in re.sub(r'^<p[^>]*>|</p>$', '', b['html']):
            m = re.match(r'(<p[^>]*>)(.*)(</p>)$', b['html'], re.S)
            inner = m.group(2)
            heads = [(x.start(2), x.end(2)) for x in SENT_HEAD.finditer(inner)]
            good = [h for h in heads if is_pali_head(inner[h[0]:h[1]], wordset)]
            if heads and len(good) >= max(2, len(heads) * 0.5):
                s, last = [], 0
                for a_, z_ in [h for h in heads if inner[h[0]:h[1]].strip() not in BURMESE_HEAD]:
                    st_ = a_ + (len(inner[a_:z_]) - len(inner[a_:z_].lstrip()))
                    en_ = a_ + len(inner[a_:z_].rstrip())
                    s.append(inner[last:st_]); s.append('<b>' + inner[st_:en_] + '</b>'); last = en_
                s.append(inner[last:])
                nb['html'] = m.group(1) + ''.join(s) + m.group(3); nb['nis'] = True
            else:
                after_verse = False
        out.append(nb)
    return out

NIS_K = float(os.environ.get('SBS_NIS_K', '1'))     # the Pali explains a verse word by word at length; the translation only lists the words

KIND = ['dhp']

def pali_items(pblocks):
    """merge verse lines into one item and tiny labels into the next block"""
    items, cur = [], None
    for bi, p in enumerate(pblocks):
        isverse = p['cls'].startswith('gatha')
        if cur is not None and cur['verse'] and isverse:
            cur['len'] += p['len']; cur['html'] += ' ' + p['html']; continue
        if cur is not None and cur['len'] < 12 and not cur['verse']:
            cur['len'] += p['len']; cur['html'] += ' ' + p['html']; cur['verse'] = isverse; continue
        cur = {'len': p['len'], 'page': p['page'], 'html': p['html'], 'verse': isverse}
        items.append(cur)
    for it in items:
        it['grams'] = grams(it['html'])
        it['pend'] = 'ပရိယောသာနေ' in it['html'] or 'သမောဓာနေသိ' in it['html']
    return items

def place_story(mm_blocks_, pblocks, stats, c):
    """-> {page: [html, ...]} for one story, by Gale-Church alignment of paragraphs (length ratio + shared names)"""
    P = pali_items(pblocks)
    ws_ = pali_wordset(pblocks)
    if KIND[0] == 'jat': mm_blocks_ = group_gatha(mm_blocks_, ws_)
    mm_blocks_ = mark_nissaya(mm_blocks_, ws_)
    pnum = [norm(it['html']) for it in P]
    mm_items, head = [], []
    for bi, b in enumerate(mm_blocks_):
        if b['tag'].startswith('h'):
            head.append(b['html']); continue
        if b.get('nis') and mm_items and mm_items[-1]['tag'] == 'blockquote' and not head:
            mm_items[-1]['extra'].append((bi, b['html'])); continue
        mm_items.append({'bid': bi, 'html': b['html'], 'tag': b['tag'], 'head': head, 'len': B.tlen(b['html']) + 1, 'extra': [],
                         'grams': grams(b['html']), 'key': norm(b['html']) if b['tag'] == 'blockquote' else None,
                         'nis': b.get('nis', False), 'endm': bool(END_MM.match(plain(b['html'])))})
        mm_items[-1]['elen'] = mm_items[-1]['len'] * (c if mm_items[-1]['tag'] == 'blockquote' else 1)   # the verse is Pali: not 1.9 times longer
        head = []
    tail_head = head
    df = {}
    for it in P:
        for g in it['grams']: df[g] = df.get(g, 0) + 1
    # verses found letter for letter in the Pali = ground truth (used to measure how good the alignment is)
    truth, last = {}, -1
    for j, it in enumerate(mm_items):
        if it['key'] and len(it['key']) >= 25:
            for i in range(last + 1, len(P)):
                if P[i]['verse'] and it['key'][:40] in pnum[i]:
                    truth[j] = i; last = i; break
    stats['anchored'] += len(truth)
    stats['verse_not_found'] += sum(1 for it in mm_items if it['key'] and len(it['key']) >= 25) - len(truth)
    if not P or not mm_items:
        return {}
    no_lex = [it['key'] is None for it in mm_items]
    where = {}
    for i0, i1, j0, j1 in gc.align(P, mm_items, c, df, len(P), no_lex, False):
        for j in range(j0, j1): where[j] = (i0, i1)
    # the 'at the end of the verse / teaching' paragraph belongs to the Pali block that says 'pariyosane': second ground truth
    endt, last = {}, 0
    for j, it in enumerate(mm_items):
        if it['endm']:
            for i in range(last, len(P)):
                if P[i]['pend']: endt[j] = i; last = i + 1; break
    for j, i in endt.items():
        w = where.get(j)
        stats['err_end'].append(0 if w and w[0] <= i < max(w[1], w[0] + 1) else (abs(P[min(w[0], len(P) - 1)]['page'] - P[i]['page']) if w else 9))
    tot = sum(x['len'] for x in mm_items) or 1
    ptot = sum(x['len'] for x in P) or 1
    for j, i in truth.items():
        before = sum(x['len'] for x in mm_items[:j]) + mm_items[j]['len'] / 2
        acc, pi_ = 0, len(P) - 1
        for k, x in enumerate(P):
            if acc + x['len'] >= before * ptot / tot: pi_ = k; break
            acc += x['len']
        stats['err_plain'].append(abs(P[pi_]['page'] - P[i]['page']))
        w = where.get(j)
        stats['err_lex'].append(0 if w and w[0] <= i < max(w[1], w[0] + 1) else (abs(P[min(w[0], len(P) - 1)]['page'] - P[i]['page']) if w else 9))
    # A verse found letter for letter (with its nissaya) belongs on the page of that Pali verse, wherever the translator put it
    # (it may come after the story in the translation but before it in the Pali), so it is taken out of the ordered alignment.
    seq = [it for j, it in enumerate(mm_items) if j not in truth]
    tv = set(truth.values())
    Pf = [it for i, it in enumerate(P) if i not in tv]            # the Pali verse leaves the ordered alignment together with its translation
    beads = gc.align(Pf, seq, c, df, len(Pf)) if seq and Pf else []
    pages = {}

    def put(pg, head_, html, bid, extra=()):
        pages.setdefault(pg, []).extend([(None, h) for h in head_] + [(bid, html)] + list(extra))

    prev_page = (Pf or P)[0]['page']
    for i0, i1, j0, j1 in beads:
        if j1 == j0:
            prev_page = Pf[i1 - 1]['page']; continue
        if i1 == i0:                                    # no Pali counterpart: stays with the previous page
            for j in range(j0, j1): put(prev_page, seq[j]['head'], seq[j]['html'], seq[j]['bid'], seq[j]['extra'])
            continue
        lens = [Pf[i]['len'] for i in range(i0, i1)]
        if len(lens) == 1:
            for j in range(j0, j1): put(Pf[i0]['page'], seq[j]['head'], seq[j]['html'], seq[j]['bid'], seq[j]['extra'])
        else:                                           # several Pali paragraphs: spread the sentences by length
            parts = []                                  # (headings, html, bid, len, forced page or None)
            pend_i = next((i for i in range(i0, i1) if Pf[i]['pend']), None)
            for j in range(j0, j1):
                it = seq[j]
                forced = Pf[truth[j]]['page'] if False else (Pf[pend_i]['page'] if it['endm'] and pend_i is not None else None)
                if it['tag'] == 'blockquote':
                    parts.append((it['head'], it['html'], it['bid'], it['len'], forced, it['extra'])); continue
                ch = B.chunks(it['html'])
                for q, (h, l) in enumerate(ch): parts.append((it['head'] if q == 0 else [], h, it['bid'], l, forced, ()))
            total = sum(x[3] for x in parts) or 1
            cuts, acc = [], 0
            for L in lens[:-1]:
                acc += L; cuts.append(total * acc / (sum(lens) or 1))
            pos = 0
            for hd, h, bid, l, fp, ex in parts:
                mid = pos + l / 2; pos += l
                k = next((q for q, cu in enumerate(cuts) if mid < cu), len(lens) - 1)
                put(fp if fp is not None else Pf[i0 + k]['page'], hd, h, bid, ex)
        prev_page = Pf[i1 - 1]['page']
    for j, i in sorted(truth.items(), reverse=True):
        it = mm_items[j]
        pages.setdefault(P[i]['page'], [])[0:0] = [(None, h) for h in it['head']] + [(it['bid'], it['html'])] + list(it['extra'])
    if tail_head: pages.setdefault(prev_page, []).extend((None, h) for h in tail_head)
    return {pg: B.join_pieces(v) for pg, v in pages.items()}

def skel(s, cut):
    s = re.sub(r'\[[၀-၉]+\]', '', s)
    s = re.sub(r'^\s*[၀-၉]+\s*[။.\-]?\s*', '', s)
    s = re.sub(cut, '', s)
    return CONS.sub('', s)

def pair_titles(pk, mk):
    """order preserving pairing of Pali headings and translation headings by similarity of their consonants (DP/LCS)"""
    import difflib
    n, m = len(pk), len(mk)
    sim = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio()
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            s_ = sim(pk[i], mk[j])
            v = dp[i + 1][j + 1] + (s_ if s_ >= 0.7 else -1)
            dp[i][j] = max(v, dp[i + 1][j], dp[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        s_ = sim(pk[i], mk[j])
        if s_ >= 0.7 and abs(dp[i][j] - (dp[i + 1][j + 1] + s_)) < 1e-9: pairs.append((i, j)); i += 1; j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]: i += 1
        else: j += 1
    return pairs

def build_jat(mm_id, pali_id, is_story):
    recs = json.load(open(os.path.join(DATA, pali_id + '.json'), encoding='utf-8')); recs.sort(key=lambda r: r['page'])
    flat = pali_stories(recs, is_story)
    nst = max(x['story'] for x in flat) + 1
    blocks = mm_blocks(os.path.join(DATA, mm_id + '.html'))
    h2 = [i for i, b in enumerate(blocks) if b['tag'] == 'h2']
    pk = [skel(plain(next(x['html'] for x in flat if x['story'] == k)), 'ဇာတကဝဏ္ဏနာ|ဇာတက|ဝဏ္ဏနာ|\\s') for k in range(nst)]
    mk = [skel(plain(blocks[i]['html']), 'ဇာတ်တော်ကြီး|ဇာတ်|ဝတ္ထု|\\s') for i in h2]
    pairs = pair_titles(pk, mk)
    if len(pairs) < 0.8 * min(nst, len(h2)):
        # the great jatakas: a story has several <h2> (title, title again, 'ပဏာမ', ...): join them, then pair by order
        import difflib
        groups, glue = [], False
        for n_, i in enumerate(h2):
            title = plain(blocks[i]['html'])
            same = groups and difflib.SequenceMatcher(None, mk[groups[-1][-1]], mk[n_]).ratio() >= 0.6
            if glue or same: groups[-1].append(n_)
            else: groups.append([n_])
            glue = title.startswith('ပဏာမ')
        if len(groups) == nst:
            pairs = [(k, g[0]) for k, g in enumerate(groups)]
    stats = {'anchored': 0, 'verse_not_found': 0, 'err_plain': [], 'err_lex': [], 'err_end': [], 'pali_stories': nst, 'mm_stories': len(h2), 'paired': len(pairs)}
    if len(pairs) < 0.8 * min(nst, len(h2)): return None, dict(stats, error='too few headings paired')
    starts = [h2[j] for _, j in pairs]
    # headings of a higher level right before an <h2> belong to it
    st = []
    for n_, a in enumerate(starts):
        while a > 0 and blocks[a - 1]['tag'] in ('h1',) and (n_ == 0 or a - 1 > starts[n_ - 1]): a -= 1
        st.append(a)
    pre = blocks[:st[0]]
    mst = [blocks[a:(st[n_ + 1] if n_ + 1 < len(st) else len(blocks))] for n_, a in enumerate(st)]
    pk_idx = [i for i, _ in pairs]
    ratio = sum(B.tlen(b['html']) for s_ in mst for b in s_) / max(1, sum(x['len'] for x in flat if x['story'] in set(pk_idx)))
    per_page = {}
    for n_, k in enumerate(pk_idx):
        pb = [x for x in flat if x['story'] == k]
        for pg, hs in place_story(mst[n_], pb, stats, ratio).items(): per_page.setdefault(pg, []).extend(hs)
    if pre: per_page.setdefault(next(x['page'] for x in flat if x['story'] == pk_idx[0]), [])[:0] = [b['html'] for b in pre]
    pages, _ = B.pali_segments(pali_id)
    data = [{'p': p['page'], 'n': p['nums'], 'pali': p['html'], 'mm': chr(10).join(per_page.pop(p['page'], []))} for p in pages]   # two Pali records with one page number: the text goes to the first
    src = ''.join(re.sub(r'\s+', '', TAG.sub('', b['html'])) for b in blocks)
    out = ''.join(re.sub(r'\s+', '', TAG.sub('', d['mm'])) for d in data)
    stats['text_kept'] = (len(out) / len(src)) if src else 0
    stats['number_mismatch'] = 0
    stats['max_page_chars'] = max(B.tlen(d['mm']) for d in data)
    stats['pages_with_mm'] = sum(1 for d in data if d['mm'].strip()); stats['pages'] = len(data)
    return data, stats

def build(mm_id, pali_id, is_story):
    if KIND[0] == 'jat': return build_jat(mm_id, pali_id, is_story)
    return build_dhp(mm_id, pali_id, is_story)

def build_dhp(mm_id, pali_id, is_story):
    recs = json.load(open(os.path.join(DATA, pali_id + '.json'), encoding='utf-8')); recs.sort(key=lambda r: r['page'])
    flat = pali_stories(recs, is_story)
    nst = max(x['story'] for x in flat) + 1
    pre, mst = mm_stories(mm_blocks(os.path.join(DATA, mm_id + '.html')), 'h2')
    stats = {'anchored': 0, 'verse_not_found': 0, 'err_plain': [], 'err_lex': [], 'err_end': [], 'pali_stories': nst, 'mm_stories': len(mst)}
    per_page = {}
    if nst != len(mst): return None, dict(stats, error='story counts differ')
    # order check by story numbers
    mism = 0
    for k in range(nst):
        pn = HEAD.match(plain(next(x['html'] for x in flat if x['story'] == k and x['cls'] in ('subhead', 'title', 'bodytext'))))
        mn = HEAD.match(plain(mst[k][[b['tag'] for b in mst[k]].index('h2')]['html']))
        if pn and mn and B.mm2int(pn.group(1)) != B.mm2int(mn.group(1)): mism += 1
    stats['number_mismatch'] = mism
    ratio = sum(B.tlen(b['html']) for st_ in mst for b in st_) / max(1, sum(x['len'] for x in flat if x['story'] >= 0))
    for k in range(nst):
        pb = [x for x in flat if x['story'] == k]
        for pg, hs in place_story(mst[k], pb, stats, ratio).items(): per_page.setdefault(pg, []).extend(hs)
    if pre: per_page.setdefault(next(x['page'] for x in flat if x['story'] == 0), [])[:0] = [b['html'] for b in pre]
    pages, _ = B.pali_segments(pali_id)
    data = [{'p': p['page'], 'n': p['nums'], 'pali': p['html'], 'mm': chr(10).join(per_page.pop(p['page'], []))} for p in pages]   # two Pali records with one page number: the text goes to the first
    src = ''.join(re.sub(r'\s+', '', TAG.sub('', b['html'])) for b in mm_blocks(os.path.join(DATA, mm_id + '.html')))
    out = ''.join(re.sub(r'\s+', '', TAG.sub('', d['mm'])) for d in data)
    stats['text_kept'] = (len(out) / len(src)) if src else 0
    stats['max_page_chars'] = max(B.tlen(d['mm']) for d in data)
    stats['pages_with_mm'] = sum(1 for d in data if d['mm'].strip()); stats['pages'] = len(data)
    return data, stats

JAT = lambda cls, t: len(t) < 90 and re.match(r'^\s*(\[[၀-၉]+\]\s*)?[၀-၉]+\s*[။.]\s*.{0,50}?ဇာတကဝဏ္ဏနာ\s*$', t) is not None
SETS = {
    '08_dhammapada_01': ('attha_ku_02_01', lambda cls, t: cls == 'subhead' and re.match(r'\s*[၀-၉]+။.*ဝတ္ထု', t) is not None),
    '08_jataka_01': ('attha_ku_zat_01', JAT), '08_jataka_02': ('attha_ku_zat_02', JAT), '08_jataka_03': ('attha_ku_zat_03', JAT),
    '08_jataka_04': ('attha_ku_zat_04', JAT), '08_jataka_05': ('attha_ku_zat_05', JAT), '08_jataka_06': ('attha_ku_zat_06', JAT),
    '08_jataka_07': ('attha_ku_zat_07', JAT),
    '08_dhammapada_02': ('attha_ku_02_02', lambda cls, t: cls == 'subhead' and re.match(r'\s*[၀-၉]+။.*ဝတ္ထု', t) is not None),
}

def main():
    want = set(sys.argv[1:]) or {k for k in SETS if 'dhammapada' in k}
    names = {x['id']: x['name'] for x in json.load(open(os.path.join(ROOT, 'myanmar_books.json'), encoding='utf-8'))}
    lst = []
    for mm, (pali, is_story) in SETS.items():
        if mm not in want: continue
        KIND[0] = 'jat' if 'jataka' in mm else 'dhp'
        data, st = build(mm, pali, is_story)
        for k_ in ('err_plain', 'err_lex', 'err_end'):
            e_ = st.pop(k_); st['mean_page_error_' + k_[4:]] = round(sum(e_) / len(e_), 3) if e_ else None; st['pct_off_by_over1_' + k_[4:]] = round(100 * sum(1 for x in e_ if x > 1) / len(e_), 1) if e_ else None
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
