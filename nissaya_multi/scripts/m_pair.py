# -*- coding: utf-8 -*-
"""Step 3: pair one OCR nissaya sheet with its Pali text, paragraph by paragraph.

    python nissaya_multi/scripts/m_pair.py <sheet-number>        e.g.  m_pair.py 14      (see catalog.md)
    python nissaya_multi/scripts/m_pair.py 14 --pali mula_di_01  (override the Pali book(s), comma separated)

Output: nissaya_multi/paired/<NNN>.json  -> one entry per Pali block (paragraph / heading / verse) with the nissaya text
that belongs to it (nissaya pages are kept WHOLE and unchanged; for every page we list the Pali blocks it deals with).

How: the OCR text of all pages is one stream. Every stream word that exists in the Pali vocabulary is a candidate headword.
The database page map (pali page -> nissaya page) tells roughly where in the Pali we are, so a candidate is matched only to
Pali words inside a band around that place (this removes the repetition problem of Pali formulas). Unique n-gram anchors
(n=4,3,2,1) + longest increasing subsequence give a monotone skeleton; the gaps are filled by a small DP.
Nothing is edited: the OCR text is only cut."""
import json, os, re, sys, bisect, sqlite3, difflib
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); TIP = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(TIP, 'scripts'))
import nissaya_common as nc
import m_clean
import m_fix
import m_sandhi

ZW = "​‌‍﻿"
TOK = re.compile("[က-အဣ-ဿ" + ZW + "]+")
DB_FILE = {'pali': 'pali_nsy.db', 'attha': 'attha_nsy.db', 'tika': 'tika_nsy.db', 'annya': 'annya_nsy.db'}

def canon(s): return nc.norm_text(s)

def load_catalog(n):
    cat = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))
    return next(r for r in cat if r['n'] == n)

def page_map(db, nsy_id):
    c = sqlite3.connect(os.path.join(TIP, DB_FILE[db]))
    rows = c.execute("select pali_book_id,pali_book_page_number,nsy_book_page_number from pali_nsy_page_map where nsy_book_id=? order by nsy_book_page_number,pali_book_page_number", (nsy_id,)).fetchall()
    return [r for r in rows if isinstance(r[1], int) and isinstance(r[2], int)]       # (a few database rows hold text such as '#VALUE!' instead of a page number)

def pali_for(books, page_ranges):
    """concatenated blocks of the Pali books, each restricted to its page range; returns blocks (with 'book') """
    blocks = []
    for b in books:
        cfg = {'pali_path': os.path.join(TIP, 'data', b + '.json'), 'pali': 'data/%s.json' % b}
        lo, hi = page_ranges.get(b, (None, None))
        if lo is not None: cfg['pali_pages'] = [lo, hi]
        for blk in nc.pali_blocks(cfg):
            blk = dict(blk); blk['book'] = b; blk['i'] = len(blocks); blocks.append(blk)
    return blocks

def lis(pairs):
    """longest strictly increasing (in both i and j) chain; pairs sorted by i; weights = len"""
    # patience on j with weight 1 (n-gram anchors already carry multiple tokens through expansion)
    tails, idxs, prev = [], [], [-1] * len(pairs)
    for k, (i, j, w) in enumerate(pairs):
        p = bisect.bisect_left(tails, j)
        if p == len(tails): tails.append(j); idxs.append(k)
        else: tails[p] = j; idxs[p] = k
        prev[k] = idxs[p - 1] if p else -1
    out, k = [], idxs[-1] if idxs else -1
    while k >= 0: out.append(pairs[k]); k = prev[k]
    return out[::-1]

def fill_gap(A, B, a0, a1, b0, b1, match):
    """monotone LCS between A[a0:a1] and B[b0:b1]; returns [(i,j)]"""
    na, nb = a1 - a0, b1 - b0
    if na <= 0 or nb <= 0 or na * nb > 400000: return []
    dp = [[0] * (nb + 1) for _ in range(na + 1)]
    for x in range(1, na + 1):
        ax = A[a0 + x - 1]; row = dp[x]; prow = dp[x - 1]
        for y in range(1, nb + 1):
            if match(ax, B[b0 + y - 1]): row[y] = prow[y - 1] + 1
            else: row[y] = row[y - 1] if row[y - 1] >= prow[y] else prow[y]
    out, x, y = [], na, nb
    while x > 0 and y > 0:
        if match(A[a0 + x - 1], B[b0 + y - 1]) and dp[x][y] == dp[x - 1][y - 1] + 1:
            out.append((a0 + x - 1, b0 + y - 1)); x -= 1; y -= 1
        elif dp[x - 1][y] >= dp[x][y - 1]: x -= 1
        else: y -= 1
    return out[::-1]

def probe_offset(pages, pmap_full, books):
    """The page numbers in the databases are PDF page numbers (e.g. Pali page 1 -> 19), the Excel sheet starts at its own page 1:
    sheet_page = db_page - offset.  The offset is found from the TEXT: words that occur once in the Pali and once in the nissaya
    give true (Pali page, sheet page) pairs; for anchors sitting at the very start of a Pali page the difference
    db_page - sheet_page is counted, and the most frequent value is the offset. Returns (offset, share, top3)."""
    blocks = pali_for(books, {})
    B = []; Bblk = []
    for blk in blocks:
        for t in blk['tokens']: B.append(t); Bblk.append(blk['i'])
    vocab = set(B)
    for blk in blocks: vocab.update(m_sandhi.block_words(blk['text'], blk['tokens']))        # + the sandhi-cut forms (ဝဒေသိ ဣတိ ...)
    first_b = {}
    for k, b in enumerate(Bblk):
        key = (blocks[b]['book'], blocks[b]['page'])
        if key not in first_b: first_b[key] = k
    A, Apos, Apg = [], [], []
    for r in pages:
        if r['num'] is None: continue
        for m in TOK.finditer(r['text']):
            t = canon(re.sub('[' + ZW + ']', '', m.group()))
            if t in vocab and len(t) >= 2: A.append(t); Apg.append(r['num'])
    dbpage = {(b, pp): np_ for b, pp, np_ in pmap_full}
    ca = defaultdict(int); cb = {}
    for N in (4, 3):
        for i in range(len(A) - N + 1): ca[tuple(A[i:i + N])] += 1
        d = defaultdict(list)
        for j in range(len(B) - N + 1): d[tuple(B[j:j + N])].append(j)
        cb[N] = d
    cnt = defaultdict(int); tot = 0
    for N in (4, 3):
        for i in range(len(A) - N + 1):
            g = tuple(A[i:i + N]); c = cb[N].get(g)
            if not (c and len(c) == 1 and ca[g] == 1): continue
            j = c[0]; blk = blocks[Bblk[j]]; key = (blk['book'], blk['page'])
            if key in dbpage and j - first_b[key] <= 80:
                cnt[dbpage[key] - Apg[i]] += 1; tot += 1
    if not cnt: return None, 0, [], 0
    # an anchor at the very start of a Pali page sits on the start page or (if the page begins late on it) the next one: d or d-1
    best = max(cnt, key=lambda d: (cnt[d] + cnt.get(d - 1, 0), cnt[d]))
    top = sorted(cnt.items(), key=lambda x: -x[1])[:3]
    return best, round((cnt[best] + cnt.get(best - 1, 0)) / tot, 2), top, tot

SEP_GAP = re.compile(r'[၊,=–:-]')
KEEP_GAP = re.compile(r'''^[\s()\[\]"“”‘’'`]*$''')
def build_fuzzy_index(vocab):
    idx = defaultdict(list)
    for w in vocab:
        if len(w) >= 4:
            for g in set(w[k:k + 2] for k in range(len(w) - 1)): idx[g].append(w)
    return idx

def _lex_ok(t):
    try:
        import m_auto
        return m_auto.is_pali_token(t)
    except FileNotFoundError:
        return False


def _freq(t):
    try:
        import m_fix
        return m_fix.lexicon()[0].get(t, 0)
    except FileNotFoundError:
        return 0


def _breakable(t, maxpieces=4):
    """a fused token = lexicon words written together (ယေနပရိယာယေန, ဘောဂေါတမ, နအဘိဝါဒေတိဝါ): can t be cut into lexicon words?"""
    if len(t) < 5: return False
    best = {0: 0}
    for i in range(len(t)):
        if i not in best: continue
        for j in range(i + 2, min(len(t), i + 20) + 1):
            piece = t[i:j]
            f = _freq(piece)
            cc = len(re.findall('[က-အ]', piece))
            if (cc >= 3 and f >= 3) or (cc == 2 and f >= 150) or (cc == 1 and (piece in ('န', 'စ', 'ဝါ', 'တိ', 'တံ', 'ယံ') or (f >= 2000 and piece not in ('သော', 'ကို')))):
                if j not in best or best[i] + 1 < best[j]: best[j] = best[i] + 1
    return len(t) in best and 2 <= best[len(t)] <= maxpieces


def drop_map_outliers(pmap):
    """the database's rows (book, Pali page, nissaya page) must not go backwards: a row that breaks the order (e.g. Pali 95 -> nissaya 259 between 184 and 185) is a typing error of the
    database. Keeps the longest non-decreasing run of nissaya pages per book; a row outside it gets the nissaya page of the Pali page before it. returns (rows, the wrong rows)"""
    keep = []; dropped = []
    for b in sorted({r[0] for r in pmap}):
        rows = sorted([r for r in pmap if r[0] == b], key=lambda r: r[1])
        n = len(rows); best = [1] * n; prev = [-1] * n
        for i in range(n):
            for j in range(i):
                if rows[j][2] <= rows[i][2] and best[j] + 1 > best[i]: best[i] = best[j] + 1; prev[i] = j
        if not rows: continue
        i = max(range(n), key=lambda k: best[k]); chain = set()
        while i >= 0: chain.add(i); i = prev[i]
        last_ok = None
        for k, r in enumerate(rows):
            if k in chain: keep.append(r); last_ok = r[2]
            else:
                dropped.append(r)
                keep.append((r[0], r[1], last_ok if last_ok is not None else r[2]))       # repaired: the page of the Pali page before it (the Pali page still exists)
    keep.sort(key=lambda r: (r[0], r[1]))
    return keep, dropped


FIX_RANGE = {}          # {sheet number: (first page, last page)} - set by m_tool.py (overrides fix_on.json)


def zero_fix(s):
    """the user (and OCR) write the letter ဝ as the digit ၀ inside words (ဘဂ၀ါ): same length, so offsets stay valid"""
    return re.sub('(?<=[က-ဿ])၀|၀(?=[က-ဿ])', 'ဝ', s)


LOAN = set()


def _never_bold():
    """words the user lists in nissaya_multi/never_bold.json {"words": [...]}: Pali-looking words the nissaya uses as ordinary Burmese words (ဘိက္ခုနီ၏။). Only a unit WITHOUT ၊ after it is affected - a real head 'ဘိက္ခုနီ၊' stays bold."""
    try: return set(json.load(open(os.path.join(ROOT, 'never_bold.json'), encoding='utf-8')).get('words', []))
    except (OSError, ValueError): return set()


NEVER_BOLD = _never_bold()


def compute_loan(bodies, vocab, min_count=8):
    """Pali words that stand INSIDE the Burmese gloss (between a ၊ and the next ။) at least min_count times in the book: ဘိက္ခု ဘိက္ခုနီ ... (Burmese uses them as its own words).
    Used by pali_spans: such a word alone, without ၊ after it, is not a Pali head. Sets and returns the global LOAN."""
    global LOAN
    cnt = defaultdict(int)
    for body in bodies:
        for m in re.finditer('၊([^။၊]{1,160})။', zero_fix(body)):
            for t in TOK.findall(m.group(1)):
                c = canon(re.sub('[' + ZW + ']', '', t))
                if c in vocab and len(c) >= 4: cnt[c] += 1
    LOAN = {w for w, c in cnt.items() if c >= min_count}
    return LOAN


def _evidence(t, vocab, fidx, cache):
    """is the word a Pali word (in the Pali text, a close misspelling of one, in the whole-Tipitaka lexicon, a fused Pali word, or Pali in form: >= 3 consonants with a stacked consonant)"""
    if t in vocab and len(t) >= 3: return True
    for sfx in ('သည်', 'ကို', 'တို့', 'ဖြင့်', 'နှင့်', 'အလို', 'သော', 'ကား', 'အား', 'တည်း', 'ပင်'):        # a Burmese word glued to the end (ဘိက္ခုသံဃာသည်, ဤအဋ္ဌကထာအလို): not a Pali word
        if t.endswith(sfx) and len(t) > len(sfx) + 2: return False
    if len(t) >= 4:
        r = cache.get(t)
        if r is None:
            cnt = defaultdict(int)
            for g in set(t[q:q + 2] for q in range(len(t) - 1)):
                for w in fidx.get(g, ()): cnt[w] += 1
            r = False
            need = max(2, int(0.6 * (len(t) - 1)))
            for w, c in cnt.items():
                if c >= need and abs(len(w) - len(t)) <= 2 and difflib.SequenceMatcher(None, t, w).ratio() >= 0.86: r = True; break
            cache[t] = r
        if r: return True
    if _lex_ok(t) or (_breakable(t) and (len(t) <= 14 or '္' in t)): return True
    return len(re.findall('[က-အ]', t)) >= 3 and '္' in t                  # ဥဒ္ဒိဿေထ: Pali in form even when the spelling is not known


def pali_spans(body, vocab, fidx, cache):
    """character spans [start, end) of the Pali words inside one cleaned nissaya page (shown in bold).
    nissaya form:   Pali words ၊ Burmese gloss ။     - ONLY the Pali part (before the ၊) is bold, never the Burmese gloss (ဘိက္ခုနိယာ၊ ဘိက္ခုနီ၏။ - the second word is Burmese).
    The text is cut at ၊ and ။ into chunks:
      * after a ။ (or at the start) a chunk that ends with ၊ is a HEAD: bold when it is Pali (at least half of its words are Pali words, at most 12 words);
      * after a head (inside the gloss) a chunk ending with ၊ is a new head only when ALL its words are Pali (a ။ lost by OCR) - otherwise it is part of the gloss;
      * a chunk that ends with ။ is a gloss (or an end of a unit): never bold."""
    bz = zero_fix(body)
    spans = []; state = 'head'; start = 0
    for m in list(re.finditer('[၊။]', bz)) + [None]:
        end = m.start() if m else len(bz); sep = m.group() if m else ''
        toks = [(mm.start() + start, mm.end() + start, canon(re.sub('[' + ZW + ']', '', mm.group()))) for mm in TOK.finditer(bz[start:end])]
        if sep == '၊' and toks:
            if state == 'head':                                         # ဝါ (vā) and the short Pali words of the Pali text (စ အထ ...) are Pali in a head: ။ ဝါ၊  ။ အထ၊  ။ ပရိယာပုဏေယျာထ စ၊
                use = [(s, e, t) for s, e, t in toks if t not in AMBIG_BURMESE and t not in ('သော', 'ဟု', 'ဟူ', 'ပေ', 'ကို')]
                ev = [t == 'ဝါ' or _evidence(t, vocab, fidx, cache) or (t in vocab and len(t) >= 1) for s, e, t in use]
            else:
                use = [(s, e, t) for s, e, t in toks if t not in AMBIG_BURMESE and t not in ('ဝါ', 'သော', 'ဟု', 'ဟူ', 'ပေ', 'ကို')]
                ev = [_evidence(t, vocab, fidx, cache) for s, e, t in use]
            if state == 'head':
                is_head = bool(use) and len(toks) <= 12 and sum(ev) >= 1 and sum(ev) * 2 >= len(use)
            else:
                is_head = bool(use) and len(toks) <= 6 and all(ev)
            if is_head:
                for s, e, t in use: spans.append([s, e])
                state = 'gloss'
            else:
                tail = []                                               # the chunk is gloss text + a Pali head whose ။ was lost: the Pali words standing right before this ၊ are the head
                for s, e, t in reversed(toks):
                    if t in AMBIG_BURMESE or t in ('ဝါ', 'သော', 'ဟု', 'ဟူ', 'ပေ', 'ကို') or not _evidence(t, vocab, fidx, cache): break
                    tail.append((s, e, t))
                if tail and len(tail) <= 6 and any((t in vocab and len(t) >= 4) for _, _, t in tail):
                    for s, e, t in tail: spans.append([s, e])
                    state = 'gloss'
                elif state == 'head': state = 'gloss'
        elif sep == '။' or m is None:
            if state == 'head' and toks:                                   # a unit whose ၊ was lost by OCR (အနာထပိဏ္ဍိကဿ ၏။): bold only when ALL its words are Pali
                use = [(s_, e_, t) for s_, e_, t in toks if t not in AMBIG_BURMESE and t not in ('ဝါ', 'သော', 'ဟု', 'ဟူ', 'ပေ', 'ကို')]
                if use and len(toks) <= 5 and any(len(t) >= 4 for _, _, t in use) and all(_evidence(t, vocab, fidx, cache) for _, _, t in use):
                    for s_, e_, t in use: spans.append([s_, e_])
            state = 'head'
        if m: start = m.end()
    spans.sort(); merged = []
    for s, e in spans:
        if merged and KEEP_GAP.match(bz[merged[-1][1]:s]) and '။' not in bz[merged[-1][1]:s] and '၊' not in bz[merged[-1][1]:s]: merged[-1][1] = e
        else: merged.append([s, e])
    try:
        import m_auto
        for k, (s, e, t) in enumerate([(mm.start(), mm.end(), mm.group()) for mm in TOK.finditer(bz)]):     # a gloss glued in front of a Pali word (ကိုဝစီဒုစ္စရိတေန): only the Pali tail is bold
            i = m_auto.glued_split(canon(t))
            if i and not any(a <= s < b for a, b in merged): merged.append([s + i, e])
        merged.sort()
    except FileNotFoundError:
        pass
    return merged


def pali_spans_old(body, vocab, fidx, cache):
    """character spans [start, end) of the Pali words inside one cleaned nissaya page (shown in bold).
    nissaya form:  Pali words ၊ Burmese gloss ။
    1. a word of the head (the text between the end of the previous unit ။ and the first ၊) is Pali when it is a word of the Pali text or a close misspelling of one;
       if MOST (>= half) of the head words are Pali, ALL words of that head are bold - also the short ones (စ တံ ဣတိ ဘော ...)
    2. elsewhere only exact Pali-text words of >= 4 letters"""
    bz = zero_fix(body)
    toks = [(m.start(), m.end(), canon(re.sub('[' + ZW + ']', '', m.group()))) for m in TOK.finditer(bz)]
    flags = []; heads = []; terminated = set()                  # heads: list of lists of token indices of one head
    head = True; prev_end = 0; cur = []
    for k, (s, e, t) in enumerate(toks):
        gap = bz[prev_end:s]
        if '။' in gap:
            if cur: heads.append(cur)
            cur = []; head = True
        elif head and SEP_GAP.search(gap):
            if cur: heads.append(cur); terminated.add(len(heads) - 1)          # this head really ends with ၊ (or - = :)
            cur = []; head = False
        prev_end = e
        pali = False
        if t in vocab and len(t) >= (3 if head else 4): pali = True
        elif head and len(t) >= 4:
            r = cache.get(t)
            if r is None:
                cnt = defaultdict(int)
                for g in set(t[q:q + 2] for q in range(len(t) - 1)):
                    for w in fidx.get(g, ()): cnt[w] += 1
                r = False
                need = max(2, int(0.6 * (len(t) - 1)))
                for w, c in cnt.items():
                    if c >= need and abs(len(w) - len(t)) <= 2 and difflib.SequenceMatcher(None, t, w).ratio() >= 0.86: r = True; break
                cache[t] = r
            pali = r
        if not pali and _lex_ok(t): pali = True                  # a word of the whole-Tipitaka lexicon (commentary Pali that is not in this sheet's Pali text)
        flags.append(pali)
        if head: cur.append(k)
    if cur: heads.append(cur)
    newheads = []; newterm = set()                              # a 'head' that does NOT end with ၊ and is made only of Pali words the nissaya uses INSIDE its Burmese gloss (ဘိက္ခုနီ၏။: LOAN words) is gloss: never bold
    for hi_, h in enumerate(heads):
        last = h[-1]; g = bz[toks[last][1]:toks[last + 1][0]] if last + 1 < len(toks) else bz[toks[last][1]:]
        if hi_ not in terminated and (LOAN or NEVER_BOLD) and all(toks[k][2] in LOAN or toks[k][2] in NEVER_BOLD for k in h):
            for k in h: flags[k] = False
            continue
        if hi_ in terminated: newterm.add(len(newheads))
        newheads.append(h)
    heads, terminated = newheads, newterm
    for h in heads:                                             # a head of 1-3 short words that all are frequent Pali words (ယံ တံ မံ အထ တဿ)
        if 1 <= len(h) <= 3 and not all(flags[k] for k in h) and all(_freq(toks[k][2]) >= 200 and toks[k][2] not in AMBIG_BURMESE and toks[k][2] not in ('ဝါ', 'သော', 'ဟု', 'ဟူ', 'ပေ', 'ကို') for k in h):
            for k in h: flags[k] = True
        for k in h:                                             # fused Pali words
            if not flags[k] and _breakable(toks[k][2]): flags[k] = True
    for hi_, h in enumerate(heads):                             # a head that is mostly Pali is Pali all through (short words included) - only when it really ends with ၊ (a missing ၊ must not swallow the Burmese gloss)
        if hi_ in terminated and 1 <= len(h) <= 10 and sum(flags[k] for k in h) * 2 >= len(h):
            for k in h:
                if toks[k][2] not in AMBIG_BURMESE: flags[k] = True
    spans = []
    for k, (s, e, t) in enumerate(toks):
        if flags[k]:
            if spans and KEEP_GAP.match(bz[spans[-1][1]:s]) and '။' not in bz[spans[-1][1]:s]: spans[-1][1] = e
            else: spans.append([s, e])
    try:
        import m_auto
        for k, (s, e, t) in enumerate(toks):                    # a gloss glued in front of a Pali word (ကိုဝစီဒုစ္စရိတေန): only the Pali tail is bold
            if not flags[k]:
                i = m_auto.glued_split(t)
                if i: spans.append([s + i, e])
        spans.sort()
    except FileNotFoundError:
        pass
    return spans


AMBIG_BURMESE = set('ကို သည် ၏ ၌ မှ နှင့် အား တို့ ကား ဟု ဟူ၍ ၍ ပြီ ကုန် ဖြင့် ရာ'.split())      # never bold: Burmese grammar words

def run(n, pali_override=None, verbose=True, _fin=None, _off=None):
    ce = load_catalog(n)
    sh = json.load(open(os.path.join(ROOT, 'sheets', ce['file']), encoding='utf-8'))
    pages = [r for r in sh['rows'] if r.get('text') is not None and not r.get('orphan')]
    _gem_nums = []
    if os.environ.get('M_USE_GEMINI') == '1':                                   # stage 2 (after Gemini, before the web): the pages Gemini checked are used instead of the sheet text
        gp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
        if os.path.exists(gp):
            G = {int(k): v for k, v in json.load(open(gp, encoding='utf-8')).items()}
            pages = [dict(r, text=G[r['num']]) if r.get('num') in G else r for r in pages]
            _gem_nums = sorted(r['num'] for r in pages if r.get('num') in G)
            if verbose: print('text of %d pages = the Gemini answer' % sum(1 for r in pages if r.get('num') in G))
    # ---- page map from the database (mode 'db') or none (mode 'content' -> bootstrapped below)
    fin = _fin or ce.get('final') or {}
    ov = (json.load(open(os.path.join(ROOT, 'catalog_overrides.json'), encoding='utf-8')) if os.path.exists(os.path.join(ROOT, 'catalog_overrides.json')) else {}).get(str(n), {})
    fin = dict(fin, **ov)
    db, nsy_id = fin.get('db'), fin.get('nsy_id')
    pmap = page_map(db, nsy_id) if (fin.get('mode') == 'db' and db) else []
    _po = os.path.join(ROOT, 'pagemap_override', '%d.json' % n)   # page map built from the page marks typed in the nissaya (used when the database map is wrong)
    MAP_AS_IS = 404 <= n <= 409 or bool(fin.get('as_is'))           # the annya_nsy page map of these books was checked by the user: used exactly as it is (no override, no outlier repair)
    if os.path.exists(_po) and not MAP_AS_IS: pmap = [tuple(r) for r in json.load(open(_po, encoding='utf-8'))]; print('page map override:', _po)
    if MAP_AS_IS: db_outliers = []; print('page map: database map used as it is')
    else: pmap, db_outliers = drop_map_outliers(pmap)
    if db_outliers: print('db page map: rows out of order dropped:', db_outliers)
    books = pali_override or fin.get('books') or []
    if not books: raise SystemExit('no Pali book known for sheet %d - give --pali <book>' % n)
    last_label = max([r['num'] for r in pages if r['num']] or [0])
    rng = {}
    offset = None; offset_info = None; pmap_all = []
    if pmap:
        det, share, top, _tot = probe_offset(pages, pmap, books)
        rule = 0 if n >= 400 else min(r[2] for r in pmap) - 1  # databases trusted. 'OCR Books (auto)' (sheet >= 400): 0001.jpg = PDF page 1, so sheet page = db page. Older workbooks: sheet page = db page - (first db page - 1)
        if _off is None and fin.get('offset') is not None: _off = fin['offset']      # catalog 'final' may carry the offset chosen by hand (sheet page = db page - offset)
        offset = rule if _off is None else _off
        offset_info = {'offset': offset, 'used': offset, 'rule': rule, 'detected_from_text': det, 'share': share, 'top': top, 'first_pali_page_db': pmap[0][2],
                       'differs': (det is not None and abs(det - rule) > 1 and share >= 0.6)}
        pmap_all = [(b, pp, np_ - offset) for (b, pp, np_) in pmap]
        pmap = [(b, pp, np_ - offset) for (b, pp, np_) in pmap]
        pmap = [r for r in pmap if 1 <= r[2] <= last_label + 1]       # only Pali pages whose nissaya lies inside the sheet
    for b in books:
        ps = [r[1] for r in pmap if r[0] == b]
        if ps: rng[b] = (max(1, min(ps) - 1), max(ps) + 1)
    blocks = pali_for(books, rng)
    # ---- Pali token stream B
    B, Bblk = [], []
    for blk in blocks:
        for t in blk['tokens']:
            B.append(t); Bblk.append(blk['i'])
    off = {}                                           # (book,page) -> first B index
    for blk in blocks:
        key = (blk['book'], blk['page'])
        if key not in off and blk['tokens']:
            off[key] = bisect.bisect_left(Bblk, blk['i'])
    vocab = set(B)
    # ---- nissaya stream: pages -> text, candidate tokens
    jp = os.path.join(ROOT, 'junk', '%03d.json' % n)
    junk_rules = json.load(open(jp, encoding='utf-8'))['rules'] if os.path.exists(jp) else []
    cleaned, stems = m_clean.clean_sheet(pages, junk_rules)                 # junk lines / page numbers / running heads / footnotes separated (original kept)
    stream, page_start = [], {}                        # page_start[label num] = char offset in stream
    pos = 0
    for r, cl in zip(pages, cleaned):
        t = cl['body'] if cl['body'].endswith(chr(10)) else cl['body'] + chr(10)
        page_start[len(stream)] = (r['num'], r['label'], pos)
        stream.append(t); pos += len(t)
    S = ''.join(stream)
    page_offsets = [v[2] for v in page_start.values()]
    page_nums = [v[0] for v in page_start.values()]
    A, Apos = [], []
    S_tok = zero_fix(S)
    for m in TOK.finditer(S_tok):
        t = canon(re.sub('[' + ZW + ']', '', m.group()))
        if t in vocab and (len(t) >= 2):
            A.append(t); Apos.append(m.start())
    # ---- expected Pali position e(i) from the page map (knots: A-index at page start -> B offset of the Pali page that starts there)
    def a_index_at_char(c): return bisect.bisect_left(Apos, c)
    nums = {num: pos_ for (num, _, pos_) in page_start.values() if num is not None}
    knots = []
    for (bk, pp, np_) in pmap:
        if bk in books and (bk, pp) in off and np_ in nums:
            knots.append((a_index_at_char(nums[np_]), off[(bk, pp)]))
    knots.sort()
    # monotone knots
    mk = []
    for x, y in knots:
        if mk and y < mk[-1][1]: continue
        if mk and x == mk[-1][0]: continue
        mk.append((x, y))
    if len(mk) < 3:                                    # 'content' mode: no page map -> bootstrap knots from globally unique anchors
        d4 = {}
        for N in (4, 3):
            d = defaultdict(list)
            for j in range(len(B) - N + 1): d[tuple(B[j:j + N])].append(j)
            d4[N] = d
        ca = defaultdict(int)
        for N in (4, 3):
            for i in range(len(A) - N + 1): ca[tuple(A[i:i + N])] += 1
        boot = []
        for N in (4, 3):
            for i in range(len(A) - N + 1):
                g = tuple(A[i:i + N]); c = d4[N].get(g)
                if c and len(c) == 1 and ca[g] == 1: boot.append((i, c[0], N))
        boot = lis(sorted(boot))
        mk = []
        for x, y, _ in boot:
            if mk and (y <= mk[-1][1] or x <= mk[-1][0]): continue
            mk.append((x, y))
        # smooth: keep knots whose neighbours do not jump (robust against a few false anchors)
        if len(mk) > 5:
            keep = [mk[0]]
            for k in range(1, len(mk) - 1):
                if (mk[k][1] - keep[-1][1]) < 6000: keep.append(mk[k])
            mk = keep + [mk[-1]]
        stats_boot = len(mk)
    if not mk: mk = [(0, 0), (len(A), len(B))]
    if mk[0][0] > 0: mk.insert(0, (0, 0))
    if mk[-1][0] < len(A): mk.append((len(A), len(B)))
    kx = [k[0] for k in mk]
    def expect(i):
        p = bisect.bisect_right(kx, i) - 1
        p = min(max(p, 0), len(mk) - 2)
        (x0, y0), (x1, y1) = mk[p], mk[p + 1]
        return y0 + (y1 - y0) * (i - x0) / max(1, x1 - x0)
    avg_page_tokens = max(200, len(B) // max(1, len(set((b['book'], b['page']) for b in blocks))))
    if not pmap: avg_page_tokens *= 2
    W = int(avg_page_tokens * 2.5)
    # ---- anchors
    index = {}
    for N in (4, 3, 2, 1):
        d = defaultdict(list)
        for j in range(len(B) - N + 1): d[tuple(B[j:j + N])].append(j)
        index[N] = d
    used_i, used_j, anchors = set(), set(), []
    for N in (4, 3, 2, 1):
        for i in range(len(A) - N + 1):
            if any((i + k) in used_i for k in range(N)): continue
            if N == 1 and len(A[i]) < 4: continue
            cand = index[N].get(tuple(A[i:i + N]))
            if not cand: continue
            e = expect(i)
            c2 = [j for j in cand if abs(j - e) <= W]
            if len(c2) != 1: continue
            j = c2[0]
            if any((j + k) in used_j for k in range(N)): continue
            for k in range(N): anchors.append((i + k, j + k, N)); used_i.add(i + k); used_j.add(j + k)
    anchors.sort()
    chain = lis([(i, j, w) for i, j, w in anchors])
    # ---- gap fill
    def match(a, b): return a == b
    pairs = list(chain)
    pts = [(-1, -1, 0)] + chain + [(len(A), len(B), 0)]
    for (i0, j0, _), (i1, j1, _) in zip(pts, pts[1:]):
        for (i, j) in fill_gap(A, B, i0 + 1, i1, j0 + 1, j1, match):
            pairs.append((i, j, 1))
    pairs.sort()
    # ---- monotone block assignment
    first_char = {}; last_char = {}; cnt = defaultdict(int)
    for i, j, _ in pairs:
        k = Bblk[j]
        cnt[k] += 1
        if k not in first_char: first_char[k] = Apos[i]
        last_char[k] = Apos[i]
    covered = sorted(first_char)
    # Nissaya pages are NEVER cut: every OCR page stays whole. We only say which Pali blocks each page deals with.
    def page_idx(c): return max(0, bisect.bisect_right(page_offsets, c) - 1)
    pg_of_block = {}                                     # block -> (first page index, last page index)
    for k in covered: pg_of_block[k] = (page_idx(first_char[k]), page_idx(last_char[k]))
    page_blocks = defaultdict(list)
    anchors_of = defaultdict(list)                      # per page: [offset in body, length, Pali block] of every matched word (for the later per-paragraph split / Pali-word replacement)
    for i, j, _ in pairs:
        pi_ = page_idx(Apos[i]); anchors_of[pi_].append([Apos[i] - page_offsets[pi_], TOK.match(S_tok, Apos[i]).end() - Apos[i], Bblk[j]])
    prev_last = None
    for blk in blocks:
        k = blk['i']
        if k in pg_of_block:
            pf, pl = pg_of_block[k]
            page_blocks[pf].append(k)                    # a Pali paragraph is listed ONCE: on the page where its nissaya starts
            prev_last = pl
        else:                                            # no nissaya words found: shown on the page where the previous paragraph ended
            nxt = next((pg_of_block[x][0] for x in covered if x > k), None)
            p = prev_last if prev_last is not None else (nxt if nxt is not None else 0)
            page_blocks[p].append(k)
    out_blocks = []
    for blk in blocks:
        k = blk['i']; pg = pg_of_block.get(k)
        out_blocks.append({'i': k, 'book': blk['book'], 'page': blk['page'], 'cls': blk['cls'], 'num': blk['num'], 'pali': blk['text'],
                           'nsy_pages': [page_nums[pg[0]], page_nums[pg[1]]] if pg else [], 'matched': cnt.get(k, 0), 'pali_tokens': len(blk['tokens'])})
    fidx = build_fuzzy_index(vocab); fcache = {}
    compute_loan([cleaned[pi]['body'] for pi in range(len(pages))], vocab)
    out_pages = []
    for pi, (num_, label, pos_) in enumerate(page_start.values()):
        out_pages.append({'num': num_, 'label': label, 'text': pages[pi]['text'], 'body': cleaned[pi]['body'], 'foot': cleaned[pi]['foot'],
                          'removed': cleaned[pi]['removed'], 'blocks': page_blocks.get(pi, []), 'anchors': anchors_of.get(pi, []), 'pali_spans': pali_spans(cleaned[pi]['body'], vocab, fidx, fcache)})
    # typed paragraph numbers at the start of a page vs the first Pali block's number (information only)
    agree = total = 0
    NL = chr(10)
    lossless = all(p['text'] == pages[i]['text'] for i, p in enumerate(out_pages))      # original OCR text of every page kept untouched next to the cleaned body
    stats = {'sheet': ce['sheet'], 'n': n, 'db': db, 'nsy_id': nsy_id, 'books': books, 'nsy_pages': len(pages), 'pali_blocks': len(blocks),
             'cand_tokens': len(A), 'matched_tokens': len(pairs), 'match_ratio': round(len(pairs) / max(1, len(A)), 3),
             'blocks_with_nissaya': len(covered), 'blocks_empty': len(blocks) - len(covered), 'lossless': lossless, 'band': W, 'knots': len(mk), 'mode': 'db' if pmap else 'content', 'typed_numbers': total, 'typed_numbers_agree': agree, 'offset': offset_info}
    ppmap = {}
    if pmap_all:
        order = {b: k for k, b in enumerate(books)}
        srt = sorted(pmap_all, key=lambda r: (order.get(r[0], 99), r[1]))
        for k, (b, pp, st) in enumerate(srt):
            en = srt[k + 1][2] if k + 1 < len(srt) else st + 2
            en = max(en, st)
            if en < 1 or st > last_label: continue
            ppmap['%s|%d' % (b, pp)] = [max(st, 1), min(en, last_label)]
    if not ppmap:                                        # no database page map (e.g. the sheet has no id): take the Pali page -> nissaya page ranges from the content alignment itself
        rng_c = {}
        for blk in blocks:
            pgs = pg_of_block.get(blk['i'])
            if not pgs: continue
            a_, z_ = out_pages[pgs[0]]['num'], out_pages[pgs[1]]['num']
            if a_ is None or z_ is None: continue
            k_ = '%s|%d' % (blk['book'], blk['page'])
            r_ = rng_c.setdefault(k_, [a_, z_]); r_[0] = min(r_[0], a_); r_[1] = max(r_[1], z_)
        ppmap = {k_: [max(r_[0], 1), min(r_[1], last_label)] for k_, r_ in rng_c.items()}
    # ---- where does every Pali page START inside the nissaya?  (the nissaya page that carries it is known from the db map; the exact spot is searched)
    import difflib
    order_b = {b: k for k, b in enumerate(books)}
    okey = lambda b, pg: (order_b.get(b, 99), pg)
    first_blk = {}
    for blk in blocks:
        if blk['tokens'] and (blk['book'], blk['page']) not in first_blk: first_blk[(blk['book'], blk['page'])] = blk
    num_to_pi = {}
    for pi_, pg_ in enumerate(out_pages): num_to_pi.setdefault(pg_['num'], pi_)
    def sim(a, b): return difflib.SequenceMatcher(None, a, b).ratio()
    def tok_list(body, lo, hi):
        return [(m.start(), m.end(), canon(re.sub('[' + ZW + ']', '', m.group()))) for m in TOK.finditer(body, lo, hi)]
    marks_n = 0
    for (bk, pg), blk in first_blk.items():
        rng_ = ppmap.get('%s|%d' % (bk, pg))
        if rng_: cand_pages = [x for x in range(rng_[0], min(rng_[1], rng_[0] + 1) + 1) if x in num_to_pi]       # the page where it starts (+ the next one when the start lies at the very end)
        else:
            k0 = blk['i']; pis = [pg_of_block[k0][0]] if k0 in pg_of_block else []
            cand_pages = [out_pages[x]['num'] for x in pis]
        W4 = blk['tokens'][:4]
        found = None
        for num_ in cand_pages:
            pi_ = num_to_pi[num_]; body = out_pages[pi_]['body']; an = out_pages[pi_]['anchors']
            prev_end = max([a[0] + a[1] for a in an if okey(blocks[a[2]]['book'], blocks[a[2]]['page']) < okey(bk, pg)] or [0])
            nxt = min([a[0] for a in an if okey(blocks[a[2]]['book'], blocks[a[2]]['page']) >= okey(bk, pg)] or [len(body)])
            lo, hi = prev_end, max(nxt + 40, prev_end)
            T = tok_list(body, lo, min(hi, len(body)))
            best = None
            for i0, (s0, e0, t0) in enumerate(T):
                s_ = sim(t0, W4[0]) if len(t0) > 1 else 0
                if s_ < 0.7: continue
                matched, last_e, pos = 1, e0, i0
                for w in W4[1:]:
                    hit = next((q for q in range(pos + 1, min(len(T), pos + 15)) if sim(T[q][2], w) >= 0.75), None)
                    if hit is not None: matched += 1; pos = hit; last_e = T[hit][1]
                sc = (matched, s_)
                if best is None or sc > best[0]: best = (sc, s0, last_e)
            if best and (best[0][0] >= min(2, len(W4))):
                found = {'num': num_, 'off': best[1], 'end': best[2], 'how': 'text', 'matched': best[0][0]}; break
            if found is None and an:
                a_ = next((a for a in sorted(an) if okey(blocks[a[2]]['book'], blocks[a[2]]['page']) >= okey(bk, pg)), None)
                if a_: found = found or {'num': num_, 'off': a_[0], 'end': a_[0] + a_[1], 'how': 'anchor', 'matched': 1}
        if found:
            found.update({'book': bk, 'page': pg}); out_pages[num_to_pi[found['num']]].setdefault('marks', []).append(found); marks_n += 1
    stats['page_start_marks'] = marks_n
    if os.environ.get('M_USE_GEMINI') == '1': stats['use_gemini'] = True; stats['gemini_pages'] = _gem_nums
    # ---- Pali words of the Pali text that the nissaya does not have (only for the sheets listed in missing_on.json)
    mp = os.path.join(ROOT, 'missing_on.json')
    if os.path.exists(mp) and n in json.load(open(mp, encoding='utf-8')):
        matched_j = {}
        for i_, j_, _w in pairs: matched_j[j_] = i_
        js = sorted(matched_j)
        covered_set = set(covered)
        n_missing = n_mis = n_omit = n_fused = 0
        for a_, b_ in zip(js, js[1:]):                                  # consecutive matched Pali words: what lies between them is not in the nissaya
            if b_ - a_ <= 1: continue
            gap = [j_ for j_ in range(a_ + 1, b_) if Bblk[j_] in covered_set and cnt.get(Bblk[j_], 0) >= 0.25 * max(1, len(blocks[Bblk[j_]]["tokens"]))]      # only paragraphs the nissaya really follows (>=25% of their words found)
            if not gap: continue
            i_prev, i_next = matched_j[a_], matched_j[b_]
            pe = Apos[i_prev] + TOK.match(S_tok, Apos[i_prev]).end() - Apos[i_prev]
            win = [(m_.start(), canon(re.sub('[' + ZW + ']', '', m_.group()))) for m_ in TOK.finditer(S, pe, Apos[i_next])]
            pi_n = page_idx(Apos[i_next]); off_n = Apos[i_next] - page_offsets[pi_n]
            if len(gap) > 12:                                           # a whole passage left out (peyyala / abbreviation): one note, not 12+ proposals
                out_pages[pi_n].setdefault('missing', []).append({'off': off_n, 'kind': 'omitted', 'words': [B[j_] for j_ in gap][:40], 'count': len(gap), 'blk': Bblk[gap[0]]})
                n_omit += 1; continue
            wtext = S[pe:Apos[i_next]]
            wcanon, widx = (canon(wtext), None)
            for j_ in gap:
                w = B[j_]
                if len(w) >= 2 and w in wtext:                          # it is there, only written together with its neighbours (sandhi / compound) -> not missing
                    n_fused += 1; continue
                best = None
                if len(w) >= 3:
                    for L in (len(w) - 1, len(w), len(w) + 1):         # a close spelling inside the text (also inside a fused word)
                        for s_ in range(0, len(wtext) - L + 1):
                            c0 = wtext[s_]
                            if not ('က' <= c0 <= 'အ' or c0 in 'ဣဤဥဦဧဩဪ'): continue
                            sub = wtext[s_:s_ + L]
                            sm = difflib.SequenceMatcher(None, w, sub)
                            if sm.real_quick_ratio() < 0.8 or sm.quick_ratio() < 0.8: continue
                            r_ = sm.ratio()
                            if r_ >= 0.8 and (best is None or r_ > best[0]): best = (r_, s_, sub)
                if best:                                                # the word is there but spelt differently (OCR / typist): not a missing word
                    pos_ = pe + best[1]; pi_c = page_idx(pos_)
                    out_pages[pi_c].setdefault('misspelt', []).append({'off': pos_ - page_offsets[pi_c], 'len': len(best[2]), 'w': w, 'cand': best[2], 'blk': Bblk[j_]}); n_mis += 1
                else:
                    out_pages[pi_n].setdefault('missing', []).append({'off': off_n, 'kind': 'missing', 'w': w, 'blk': Bblk[j_]}); n_missing += 1
        stats['missing_words'] = n_missing; stats['misspelt_words'] = n_mis; stats['omitted_passages'] = n_omit; stats['fused_words'] = n_fused
    # ---- correction proposals (Pali heads, punctuation, ...) for the nissaya pages in FIX_RANGE (set by the tool) or fix_on.json {"sheet": [first page, last page]}
    fp_ = os.path.join(ROOT, 'fix_on.json')
    fcfg = json.load(open(fp_, encoding='utf-8')) if os.path.exists(fp_) else {}
    fix_range = FIX_RANGE.get(n) or fcfg.get(str(n))
    if fix_range:
        import m_fix2
        lo_p, hi_p = fix_range
        ids_all = [pi_ for pi_, pg_ in enumerate(out_pages) if pg_['num'] is not None and lo_p <= pg_['num'] <= hi_p]
        pali_words_of = {}                                                   # Pali page -> its words (also the sandhi-cut forms); tells Pali from Burmese on the nissaya pages that belong to it
        for blk_ in blocks: pali_words_of.setdefault('%s|%d' % (blk_['book'], blk_['page']), set()).update(blk_['tokens'], m_sandhi.block_words(blk_['text'], blk_['tokens']))
        pvocab = []
        for pg_ in out_pages:
            v_ = set()
            for key_, (a_, z_) in ppmap.items():
                if pg_['num'] is not None and a_ <= pg_['num'] <= z_: v_ |= pali_words_of.get(key_, set())
            pvocab.append(v_)
        bodies_all = [pg_['body'] for pg_ in out_pages]
        order_k = sorted(ppmap.items(), key=lambda kv: (books.index(kv[0].split('|')[0]) if kv[0].split('|')[0] in books else 99, int(kv[0].split('|')[1])))
        by_page = defaultdict(list)
        for blk_ in blocks: by_page[(blk_['book'], blk_['page'])].append(blk_)
        kinds = defaultdict(int)
        for c0 in range(0, len(ids_all), 12):                                # 12 pages at a time (the alignment is quadratic in the window)
            ids = ids_all[c0:c0 + 12]
            w0 = max(0, ids[0] - 1); w1 = min(len(out_pages) - 1, ids[-1] + 1)          # one page of margin on each side
            W_parts = []; page_starts = []; pos_ = 0
            for pi_ in range(w0, w1 + 1):
                page_starts.append((pi_, pos_)); W_parts.append(out_pages[pi_]['body']); pos_ += len(out_pages[pi_]['body']) + 1
            W = '\n'.join(W_parts)
            lo_c = page_starts[ids[0] - w0][1]; hi_c = page_starts[ids[-1] - w0][1] + len(out_pages[ids[-1]]['body']) + 1
            nums_w = {out_pages[pi_]['num'] for pi_ in range(w0, w1 + 1) if out_pages[pi_]['num'] is not None}
            lo_n, hi_n = min(nums_w), max(nums_w)
            pali_words, pali_blk, blocks_tokens, pali_alts = [], [], {}, []
            for key_, (a_, z_) in order_k:
                if z_ < lo_n or a_ > hi_n: continue
                bk_, pg_s = key_.split('|')
                for blk_ in by_page.get((bk_, int(pg_s)), []):
                    blocks_tokens[blk_['i']] = len(blk_['tokens'])
                    ws_, al_ = m_sandhi.block_words2(blk_['text'], blk_['tokens'])        # the words as the NISSAYA writes them (ဝဒေသီ’’တိ = ဝဒေသိ + ဣတိ)
                    for t_, a_t in zip(ws_, al_): pali_words.append(t_); pali_blk.append(blk_['i']); pali_alts.append(a_t)
            props = m_fix2.compute(W, page_starts, pali_words, pali_blk, blocks_tokens, (lo_c, hi_c), bodies_all, pvocab, pali_alts)
            for pi_, lst in props.items():
                if pi_ in ids:
                    out_pages[pi_]['fixes'] = lst
                    for q in lst: kinds[q['kind']] += 1
        stats['fix_proposals'] = dict(kinds); stats['fix_pages'] = [lo_p, hi_p]
    payload = {'stats': stats, 'blocks': out_blocks, 'pages': out_pages, 'ppmap': ppmap}
    if _fin is not None: return payload
    return save(n, payload, verbose)

def save(n, payload, verbose=True):
    os.makedirs(os.path.join(ROOT, 'paired'), exist_ok=True)
    json.dump(payload, open(os.path.join(ROOT, 'paired', '%03d.json' % n), 'w', encoding='utf-8'), ensure_ascii=False)
    if verbose: print(json.dumps(payload['stats'], ensure_ascii=False))
    return payload['stats']

def run_variant(n, fin, po):
    """one (database or content) variant; when the text-detected page offset is doubtful, also try the plain rule 'Pali page 1 = db page - 1'
    and 0, keep the one that matches the Pali words best"""
    a = run(n, po, False, _fin=fin)
    return a

def run_best(n, pali_override=None, verbose=True):
    ce = load_catalog(n); fin = ce.get('final') or {}
    a = run_variant(n, fin, pali_override)
    best = a
    if fin.get('alt'):
        b = run_variant(n, fin['alt'], None)
        a['stats']['alt'] = 'content:' + ','.join(a['stats']['books']); b['stats']['alt'] = 'db:' + ','.join(b['stats']['books'])
        if b['stats']['match_ratio'] > a['stats']['match_ratio']: best = b
        best['stats']['compared'] = {'content': [a['stats']['books'], a['stats']['match_ratio']], 'db': [b['stats']['books'], b['stats']['match_ratio']]}
    return save(n, best, verbose)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:]]
    po = None
    if '--pali' in args:
        k = args.index('--pali'); po = args[k + 1].split(','); del args[k:k + 2]
    run_best(int(args[0]), po)
