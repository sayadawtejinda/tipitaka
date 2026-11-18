# -*- coding: utf-8 -*-
"""Final web data of one nissaya book:  paragraphs (numbers / 'မှာထားချက်'), bold Pali, 🔖 Pali-page starts.
    python nissaya_multi/scripts/m_final.py <sheet n> [--out web]        ->  nissaya_multi/web/NNN_<book>.json  (+ web_report.txt)
Text of every nissaya page:  Gemini answer (gold/gemini/NNN_collected.json)  >  tool-corrected text (spacing, junk, rules, blue Pali; no ၊ ။ insertion)  >  cleaned OCR.
1. paragraph numbers: the numbers  '၅၇။'  that make an increasing run through the whole book are found (noise like '၄။' is skipped) and each one starts a paragraph;
   a paragraph also starts at 'မှာထားချက်။' (a note).  Other line breaks of the OCR are joined into spaces.
2. bold Pali: m_pair.pali_spans on the final paragraph text.
3. 🔖: the place where every Pali page starts inside the nissaya (marks of paired/NNN.json); in a Gemini text it is searched again by the words that followed the mark.
Output per Pali page:  {"pali_page": N, "npages": [first, last], "html": "..."}  - nissaya page breaks are dotted lines."""
import glob, sys, os, re, json, difflib, html as _html
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(ROOT))
import m_pair, m_sandhi
W = re.compile('[က-အဣ-ဿ၌၍၏]+')
BD = str.maketrans('၀၁၂၃၄၅၆၇၈၉ဝ', '01234567890')                 # the letter ဝ is how OCR often writes the zero
NUM = re.compile(r'(?<![၀-၉ဝ])((?:[၀-၉ဝ]{1,3}\s*[၊,]\s*){0,3}[၀-၉ဝ]{1,3})\s*။')
NUM_PAREN = re.compile(r'(?:(?<=\n)|(?<=။ )|(?<=။)|^)\(([၀-၉ဝ]{1,3})\)', re.M)


PBREAK = chr(0x2029)


def hash_breaks(t):
    """a '#' in the nissaya text marks the start of a new paragraph (# မှာထားချက်။ ။ / # ၁၉။ ...): it becomes a paragraph break (the '#' itself is not shown)"""
    return re.sub(r'[ \t]*#+[ \t]*', chr(10) + PBREAK + chr(10), t)


def page_texts(n, P):
    """{nissaya page: (text, source)}"""
    import m_tool
    gp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
    G = {int(k): v for k, v in json.load(open(gp, encoding='utf-8')).items()} if os.path.exists(gp) else {}
    out = {}
    for pg in P['pages']:
        k = pg['num']
        if k is None: continue
        if k in G:
            gt = G[k].strip()
            try:
                import m_gcheck
                gt, _n = m_gcheck.restore_punct(pg['body'] + (chr(10) + pg['foot'] if pg.get('foot') else ''), gt)      # the sheet's ၊ ။ win where Gemini changed a hyphen-style unit
            except Exception: pass
            out[k] = (hash_breaks(gt), 'gemini')
        else:
            t, _ = m_tool.apply_page(pg, True, False, False, True)          # no blue Pali proposals on the web (the user decides: Gemini's answer is published as it is)
            out[k] = (hash_breaks(t), 'tool')
    return out


def number_starts(pages, anchor_pos=None):
    """pages = [(page num, text)];  anchor_pos = {paragraph number: (page, offset)} from the aligner (where the first matched Pali word of that Pali paragraph stands).
    returns ({(page, offset): (first number, last number)}, candidates)
    1. the numbers  '၅၇။'  '၆၃၊ ၆၄။'  '(၁၂)'  that make the longest increasing chain through the book (one numbering runs through the whole book; noise like '၄။' is skipped)
    2. a missing number between two found ones is searched as plain text between them
    3. a still missing number is placed at the aligner's anchor of its Pali paragraph (only between the neighbouring found numbers)"""
    cands = []
    for k, t in pages:
        for m in sorted(list(NUM.finditer(t)) + list(NUM_PAREN.finditer(t)), key=lambda m: m.start()):
            nums = [int(x.translate(BD)) for x in re.findall('[၀-၉ဝ]{1,3}', m.group(1))]
            cands.append((k, m.start(), nums[0], nums[-1]))
    best = {}; prev = {}
    for i, (k, off, v, v2) in enumerate(cands):
        best[i] = 1 if 1 <= v <= 8 else 0.5; prev[i] = None
        for j in range(i):
            vj = cands[j][3]
            if 0 < v - vj <= 80 and best[j] + 1 > best[i]:
                best[i] = best[j] + 1; prev[i] = j
    if not cands: return {}, []
    i = max(best, key=best.get); chain = []
    while i is not None: chain.append(i); i = prev[i]
    chain.reverse()
    sel = {(cands[i][0], cands[i][1]): (cands[i][2], cands[i][3]) for i in chain}
    order = {k: i for i, (k, _) in enumerate(pages)}
    key = lambda kp: (order[kp[0]], kp[1])
    BDI = str.maketrans('0123456789', '၀၁၂၃၄၅၆၇၈၉')

    def neighbours(m):
        """the found numbers just before / after the number m in the book order"""
        lo = hi = None
        for kp, (a, b) in sel.items():
            if b < m and (lo is None or b > lo[1]): lo = (kp, b)
            if a > m and (hi is None or a < hi[1]): hi = (kp, a)
        return lo, hi

    for m in range(1, max(v2 for _, _, _, v2 in cands) + 1):                                      # pass 2: the number written in the text, between its neighbours
        if any(a <= m <= b for a, b in sel.values()): continue
        lo, hi = neighbours(m)
        if not lo or not hi: continue
        (pa, oa), _ = lo; (pb, ob), _ = hi
        ds = str(m).translate(BDI).replace('၀', '[၀ဝ]'); best_ = None
        for k, t in pages[order[pa]:order[pb] + 1]:
            lo_c = oa + 1 if k == pa else 0; hi_c = ob if k == pb else len(t)
            for mm in re.finditer(r'(?:(?<=\n)|(?<=။ )|(?<=။))' + ds + r'(?![၀-၉ဝ])\s*[၊။.\-]?(?=\s*[က-အဣ-ဿ])', t[lo_c:hi_c]):
                best_ = (k, lo_c + mm.start()); break
            if best_: break
        if best_ and best_ not in sel: sel[best_] = (m, m)
    stats = {'text': len(sel), 'anchor': 0}
    if anchor_pos:                                                                                 # pass 3: from the aligner's anchors
        text_of = dict(pages)
        for m in sorted(anchor_pos):
            if any(a <= m <= b for a, b in sel.values()): continue
            k, off = anchor_pos[m]
            if k not in text_of: continue
            t = text_of[k]
            cut = max(t.rfind('။', 0, off), t.rfind(chr(10), 0, off))
            start = cut + 1 if (cut >= 0 and off - cut <= 60) else off
            while start < len(t) and t[start] in ' \n': start += 1
            lo, hi = neighbours(m)
            if lo and key(lo[0]) >= (order[k], start): continue
            if hi and key(hi[0]) <= (order[k], start): continue
            if (k, start) in sel: continue
            sel[(k, start)] = (m, m); stats['anchor'] += 1
    return sel, cands, stats


def paragraphs_of(text, starts_here):
    """split one page text at the numbers (offsets in starts_here) and at 'မှာထားချက်။'; returns [(start offset, kind, number)] (kind num / note / cont)"""
    cuts = {}
    for off, v in starts_here.items(): cuts[off] = ('num', v)
    for m in re.finditer('မှာထားချက်\\s*။', text):
        prev = text[max(0, m.start() - 3):m.start()].replace(' ', '')
        if m.start() == 0 or prev.endswith(('။', '\n', ')')) or text[m.start() - 1] == '\n': cuts.setdefault(m.start(), ('note', None))
    for m in re.finditer(PBREAK, text): cuts.setdefault(m.start(), ('cont', None))
    return cuts


def locate_mark(old_body, mark, new_text):
    """where the Pali page start is in a changed text: the words of the old snippet are searched near the same relative place"""
    snippet = old_body[mark['off']:max(mark['end'], mark['off'] + 1)]
    toks = W.findall(snippet)[:3]
    rel = mark['off'] / max(1, len(old_body))
    if not toks: return int(rel * len(new_text))
    target = rel * len(new_text); best = None
    for m in re.finditer(re.escape(toks[0]), new_text):
        score = 0
        tail = new_text[m.start():m.start() + 80]
        for t in toks[1:]:
            if t in tail: score += 1
        d = abs(m.start() - target)
        if best is None or (score, -d) > (best[0], -best[1]): best = (score, d, m.start())
    if best: return best[2]
    best = max(((difflib.SequenceMatcher(None, toks[0], w.group()).ratio(), -abs(w.start() - target), w.start()) for w in W.finditer(new_text)), default=None)
    return best[2] if best and best[0] >= 0.75 else int(rel * len(new_text))


FOOT_SKIPPED = []


def _fgrams(s, k=4):
    s = re.sub(r'[\s၊။\-#,.]+', '', s)
    return [s[i:i + k] for i in range(len(s) - k + 1)]


def foot_in_text(foot, text):
    """True when the (corrected) page text clearly holds the foot too: the share of the foot's 4-letter pieces found in the text is high (an unrelated text gives under 0.35)."""
    f = _fgrams(foot)
    if len(f) < 6: return False
    g = set(_fgrams(text))
    share = sum(1 for x in f if x in g) / len(f)
    return share >= (0.4 if len(f) >= 150 else 0.6)


def build(n, log=print):
    P = json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8'))
    s1_ = os.path.join(ROOT, 'paired', '%03d_stage1.json' % n)
    if P['stats'].get('use_gemini') and os.path.exists(s1_): P = json.load(open(s1_, encoding='utf-8'))        # the viewer data holds the Gemini-text check; the web is built from the sheet-text data (+ Gemini pages as they are)
    HEAD_WORDS.clear(); HEAD_WORDS.update(w for b in P['blocks'] if b.get('cls') in ('title', 'subhead', 'chapter', 'centered') and len(b['pali']) < 120 for w in _hwords(b['pali']))
    texts = page_texts(n, P)
    order = sorted(texts)
    bodies0 = {pg['num']: pg for pg in P['pages'] if pg['num'] is not None}
    blk_num = {b['i']: int(str(b['num']).translate(BD)) for b in P['blocks'] if b.get('num') and re.fullmatch('[၀-၉]+', str(b['num']))}
    anchor_pos = {}
    for k in order:                                                  # the earliest anchor of every numbered Pali paragraph, moved to the text that is used
        for off, ln, bi in bodies0[k].get('anchors', []):
            if bi not in blk_num: continue
            nn = blk_num[bi]
            pos = off if texts[k][1] == 'tool' and texts[k][0] == bodies0[k]['body'] else locate_mark(bodies0[k]['body'], {'off': off, 'end': off + 14}, texts[k][0])
            if nn not in anchor_pos or (order.index(k), pos) < (order.index(anchor_pos[nn][0]), anchor_pos[nn][1]): anchor_pos[nn] = (k, pos)
    nums_sel, cands, nstat = number_starts([(k, texts[k][0]) for k in order], anchor_pos)
    # vocabulary for the bold Pali
    vocab = set()
    for b in P['blocks']:
        toks = [m_pair.canon(re.sub('[' + m_pair.ZW + ']', '', t)) for t in m_pair.TOK.findall(b['pali'])]
        vocab.update(toks); vocab.update(m_sandhi.block_words(b['pali'], toks))
    fidx = m_pair.build_fuzzy_index(vocab); cache = {}
    m_pair.compute_loan([pg['body'] for pg in P['pages']], vocab)
    bodies = {pg['num']: pg for pg in P['pages'] if pg['num'] is not None}
    marks = {}
    for k in order:
        for mk in bodies[k].get('marks', []):
            marks.setdefault(k, []).append(dict(mk, pos=mk['off'] if texts[k][1] == 'tool' and texts[k][0] == bodies[k]['body'] else locate_mark(bodies[k]['body'], mk, texts[k][0])))
    pages_html = {}
    for k in order:
        t = texts[k][0]
        here = {off: (v[0] if v[0] == v[1] else '%d-%d' % v) for (p, off), v in nums_sel.items() if p == k}
        cuts = paragraphs_of(t, here)
        for mk in marks.get(k, []): cuts.setdefault(-1 - mk['pos'], None)        # (marks do not cut paragraphs)
        cut_offs = sorted(o for o in cuts if o >= 0)
        pieces = []; prev = 0; kind = ('cont', None)
        for o in cut_offs:
            if o > prev: pieces.append((prev, o, kind))
            prev = o; kind = cuts[o]
        pieces.append((prev, len(t), kind))
        out = []
        for a, b, (kd, v) in pieces:
            seg = t[a:b]
            if not seg.strip(): continue
            # bold Pali on the line-joined text; marks inside the piece
            joined = re.sub('\\s*\\n\\s*', ' ', seg.replace(PBREAK, '')).strip()
            spans = m_pair.pali_spans(joined, vocab, fidx, cache)
            mk_here = [m for m in marks.get(k, []) if a <= m['pos'] < b or (b == len(t) and m['pos'] >= len(t))]
            # marks: map the offset inside seg to the offset inside joined (by the number of non-space characters before)
            def to_joined(off):
                cnt = len(re.sub('\\s+', '', seg[:off - a]))
                c = 0
                for i, ch in enumerate(joined):
                    if c >= cnt: return i
                    if not ch.isspace(): c += 1
                return len(joined)
            ins = sorted({to_joined(m['pos']): m for m in mk_here}.items())
            cuts_at = sorted(set([0, len(joined)] + [x for sp in spans for x in sp] + [i for i, _ in ins]))
            parts = []
            for x, y in zip(cuts_at, cuts_at[1:]):
                for i, m in ins:
                    if i == x: parts.append('<span class="nsy-mark" data-page="%d" title="ပါဠိ စာမျက်နှာ %d စတင်သည်">🔖</span>' % (m['page'], m['page']))
                s_ = _html.escape(joined[x:y])
                parts.append('<b class="pl">%s</b>' % s_ if any(a_ <= x < b_ for a_, b_ in spans) else s_)
            for i, m in ins:
                if i == len(joined): parts.append('<span class="nsy-mark" data-page="%d" title="ပါဠိ စာမျက်နှာ %d စတင်သည်">🔖</span>' % (m['page'], m['page']))
            cls = {'num': 'nsy-p nsy-num', 'note': 'nsy-p nsy-note', 'cont': 'nsy-p nsy-cont'}[kd]
            out.append('<p class="%s"%s>%s</p>' % (cls, ' data-n="%s"' % v if v else '', ''.join(parts)))
        foot = bodies[k].get('foot')
        if foot and texts[k][1] == 'gemini' and foot_in_text(foot, texts[k][0]):        # Gemini was given the foot with the body and wrote its corrected version inside the page text: the raw OCR foot is not added a second time (a foot Gemini left out stays, nothing is lost)
            FOOT_SKIPPED.append(k); foot = None
        pages_html[k] = ''.join(out) + (('<p class="nsy-foot">%s</p>' % _html.escape(' '.join(foot.split()))) if foot else '')
    per = {}
    for key, rng in P['ppmap'].items():
        book, pg = key.split('|'); lo, hi = rng
        ks = [k for k in range(lo, hi + 1) if k in pages_html]
        if not ks: continue
        body = ''.join('<div class="nsy-pb" data-p="%d"><span>%d</span></div>%s' % (k, k, pages_html[k]) for k in ks)
        per[(book, int(pg))] = {'pali_page': int(pg), 'npages': [ks[0], ks[-1]], 'html': body}
    srcs = {}
    for k in order: srcs[texts[k][1]] = srcs.get(texts[k][1], 0) + 1
    chain_vals = sorted({x for a_, b_ in nums_sel.values() for x in range(a_, b_ + 1)})
    rep = ['sheet %d | pages %d | text source %s | paragraph starts %d (%d from the text, %d placed by the aligner anchors) of %d numbered Pali paragraphs | first/last %s/%s' % (n, len(order), srcs, len(nums_sel), nstat['text'], nstat['anchor'], len(blk_num), chain_vals[:1], chain_vals[-1:]),
           'missing numbers inside the run: %s' % sorted(set(range(chain_vals[0], chain_vals[-1] + 1)) - set(chain_vals))[:60] if chain_vals else 'no numbers']
    log('\n'.join(rep))
    return per, rep, P


EDITION_SLUG = {'ဘုရားကြီးမူ': 'bhurakyi', 'ပခုက္ကူမူ': 'pakhokku', 'ဘာသာဋီကာ': 'bhasatika'}
BURMESE = str.maketrans('0123456789', '၀၁၂၃၄၅၆၇၈၉')
P_STYLE = 'style="text-indent:2em"'


def mm(x):
    """digits as Burmese digits (the web page does not show English numbers)"""
    return str(x).translate(BURMESE)


HEAD_TAIL = re.compile(r'(?<=[။၊\)])\s+((?:<[^>]+>)*[၀-၉ဝ]{1,3}\s*-(?:[^။၊<]|<[^>]+>){2,90}?(?:။)?)\s*$')


HEAD_WORDS = set()                                                     # words of the Pali headings of the book (title / subhead / chapter / centered lines), set by build()
HEAD_SUFFIX = re.compile(r'(?:သိက္ခာပဒံ?|ဝဂ္ဂေါ?|ကဏ္ဍံ?|ဝိနီတဝတ္ထု|ဘာဏဝါရော?|နိဒ္ဒေသော?|ဝိဘင်္ဂေါ?)\W*$')
TAIL2 = re.compile(r'(?<=။)\s*((?:<[^>]+>|[^။၊<])+?)\s*[၊]?\s*$')


def _hwords(text):
    import m_clean
    return [m_clean.norm(w) for w in text.split() if len(m_clean.norm(w)) >= 4]


def _head_match(w):
    w = w.rstrip('ံ')
    return any(h.rstrip('ံ') == w or (len(w) >= 6 and (h.startswith(w) or w.startswith(h.rstrip('ံ')))) and len(h) >= 6 for h in HEAD_WORDS)


def split_heading(inner):
    inner, head = _split_heading_num(inner)
    if head: return inner, head
    m = TAIL2.search(inner)                                             # the unnumbered heading of the next rule at the end of the paragraph (Pakhokku: 'ဒုတိယသံဃာဒိသေသ ကာယသံသဂ္ဂသိက္ခာပဒံ')
    if not m or not inner[:m.start()].strip(): return inner, ''
    plain = re.sub(r'<[^>]+>', '', m.group(1)).replace('🔖', '').strip()
    if not plain or len(plain) > 90 or not HEAD_SUFFIX.search(plain): return inner, ''
    words = _hwords(plain)
    if not words or (HEAD_WORDS and not any(_head_match(w) for w in words)): return inner, ''      # the Pali side must have a heading with one of these words
    return inner[:m.start()], m.group(1).strip()


def _split_heading_num(inner):
    """a heading of the NEXT rule ('၁၀-ခုမြောက် ပထဝီခဏနသိက္ခာပဒ', '၂-ကာယသံသဂ္ဂသိက္ခာပဒံ။') that stands glued to the end of the paragraph -> (paragraph, heading)"""
    m = HEAD_TAIL.search(inner)
    if not m or not m.group(1).strip(): return inner, ''
    plain = re.sub(r'<[^>]+>', '', m.group(1))
    if not re.search('သိက္ခာပဒ|ကဏ္ဍ|ဝဂ္ဂ', plain) or not inner[:m.start()].strip(): return inner, ''
    return inner[:m.start()], m.group(1)


def webify(html, own_page):
    """the chunk html of one Pali page -> the form the web page already uses for the other nissaya books:  <p style="text-indent:2em"> paragraphs, Pali words in <b>"""
    html = re.sub(r'<div class="nsy-pb" data-p="(\d+)"><span>[^<]*</span></div>',
                  lambda m: '<p style="text-indent:0;text-align:right;color:#999;font-size:.8em;border-top:2px dotted #ccc;margin:.9em 0 .3em">(နိဿယစာအုပ် စာမျက်နှာ %s)</p>' % mm(m.group(1)), html)
    # only the start of THIS Pali page is marked (the marks of the other Pali pages are dropped)
    html = re.sub(r'<span class="nsy-mark" data-page="(\d+)"[^>]*>🔖</span>',
                  lambda m: '<span style="background:#ffe9a8;border-radius:3px;padding:0 2px" title="ပါဠိစာမျက်နှာ စတင်သည့်နေရာ">🔖</span>' if int(m.group(1)) == own_page else '', html)

    def para(m):
        kind, n_, inner = m.group(1), m.group(2), m.group(3)
        if kind == 'note': return '<p class="tp-nsy-note" %s>%s</p>' % (P_STYLE, inner)
        lead = ''
        if kind == 'num' and n_ and not re.match(r'^(?:<[^>]+>|\s)*[၀-၉ဝ]{1,3}\s*[၊။]', inner):        # the number is not written in the text: put the Pali paragraph number in front
            lead = (mm(n_.replace('-', '၊ ')) if '-' in n_ else mm(n_)) + '။ '
        inner, head = split_heading(inner)
        return '<p %s>%s%s</p>' % (P_STYLE, lead, inner) + ('<p %s>%s</p>' % (P_STYLE, head) if head else '')
    html = re.sub(r'<p class="nsy-p nsy-(num|note|cont)"(?: data-n="([^"]*)")?>(.*?)</p>', para, html, flags=re.S)
    html = html.replace('<b class="pl">', '<b>')
    html = re.sub(r'<p class="nsy-foot">(.*?)</p>', r'<p style="text-indent:2em;color:#666;font-size:.9em">\1</p>', html, flags=re.S)
    return html


def write_web_html(n, per, book, edition, outdir, log=print):
    """data file for the web page: [စာမျက်နှာ-၁] + paragraphs, one block per Pali page (the web page cuts the file at these markers)"""
    slug = EDITION_SLUG.get(edition, 'sheet%03d' % n)
    path = os.path.join(outdir, '%s_%s.html' % (book, slug))
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"', '  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">',
           '<html xmlns="http://www.w3.org/1999/xhtml">', '<head>', '<title>%s - %s</title>' % (book, edition), '</head>', '<body>']
    for (b, pg), v in sorted(per.items(), key=lambda x: x[0][1]):
        if b != book: continue
        out.append('[စာမျက်နှာ-%s]' % mm(pg))
        out.append(webify(v['html'], pg))
    out += ['</body>', '</html>']
    text = '\n'.join(out)
    open(path, 'w', encoding='utf-8').write(text)
    log('web file: %s  (%d KB, %d Pali pages)  edition %s' % (os.path.relpath(path, os.path.dirname(ROOT)), len(text.encode('utf-8')) // 1000, sum(1 for b, _ in per if b == book), edition))
    return path, slug


if __name__ == '__main__':
    n = int(sys.argv[1]); outdir = os.path.join(ROOT, sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'web')
    per, rep, P = build(n)
    os.makedirs(outdir, exist_ok=True)
    cat = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))
    _r = [r for r in cat if r['n'] == n][0]; edition = _r.get('edition')
    if edition and not re.match(r'^Z\d+\s', edition.strip()) and (chr(10) in edition or len(edition) > 30): edition = None     # cover-page text / a whole title, not an edition name
    if not edition:                                             # no edition on the sheet -> the nissaya book name stored in the db (nsy_books.name), e.g. 011 -> 'အခြေပြု'
        try:
            import sqlite3; _f = _r.get('final') or {}
            _c = sqlite3.connect(os.path.join(os.path.dirname(ROOT), '%s_nsy.db' % _f['db']))
            _q = _c.execute('select name from nsy_books where id=?', (_f['nsy_id'],)).fetchone(); edition = _q[0] if _q else None
        except Exception: edition = None
    edition = edition or ('နိဿယ-%s' % n)
    for _mp in glob.glob(os.path.join(outdir, '*.meta.json')):     # the web files an EARLIER build of this sheet made (another edition name -> another file name) are removed, so the sheet never gets published twice
        try:
            _m = json.load(open(_mp, encoding='utf-8'))
            if _m.get('sheet') == n:
                for _x in (os.path.join(outdir, _m['file'] + '.html'), _mp):
                    if os.path.exists(_x): os.remove(_x)
        except Exception: pass
    for book in sorted({b for b, _ in per}):                    # a sheet that covers two books (e.g. 113: attha_ma_01_01 + attha_ma_01_02) gives one web file per book
        path, slug = write_web_html(n, per, book, edition, outdir)
        json.dump({'book': book, 'edition': edition, 'file': os.path.splitext(os.path.basename(path))[0], 'sheet': n}, open(os.path.join(outdir, '%s_%s.meta.json' % (book, slug)), 'w', encoding='utf-8'), ensure_ascii=False)
    open(os.path.join(outdir, 'web_report_%03d.txt' % n), 'w', encoding='utf-8').write(chr(10).join(rep))
