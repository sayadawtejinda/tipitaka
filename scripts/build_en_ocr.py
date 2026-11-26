# -*- coding: utf-8 -*-
"""English translations of the Pali Tipitaka (Myanmar Dept. of Sasana, OCR + spellcheck HTML F01-F09 in spellcheck/out/html)
 -> data/translations_en/<pali book>.json {Pali page: text}  (+ index.json entry), so the English side of the reader shows them page by page.
Alignment (paragraph-number books): English paragraphs that start with a number 'N.' are anchors (longest increasing run of numbers = restarts of sub-lists ignored);
the anchor goes to the Pali page where paragraph N starts; unnumbered paragraphs follow the anchor before them, headings go with the NEXT anchor.
usage: python scripts/build_en_ocr.py F06 [--write] [--push]      (without --write only the report is printed)"""
import json, os, re, sys, glob, bisect
from html import unescape
sys.stdout.reconfigure(encoding='utf-8')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DATA = os.path.join(REPO, 'data')
SRC = r'C:/Users/sayad/Documents/spellcheck/out/html'
TR = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')
# English file -> [(Pali book, English part)]  (Pali book ids of data/*.json)
JOBS = {'F06': ['mula_bi_01'], 'F07': ['mula_ku_02'], 'F09': ['mula_di_02']}      # Pali book(s) of each English file
VERSE = {'F07'}                    # files whose anchors are verse numbers ('Verse 12' / 'Verses 3 and 4' / '12. ...')


def blocks_of(f):
    s = open(f, encoding='utf-8').read(); s = s[s.index('<div id="bk">') + 13:]
    out = []
    for t, h in re.findall(r'<(p|h[1-6])\b[^>]*>(.*?)</\1>', s, re.S):
        h = re.sub(r'<br\s*/?>', '\n', h); txt = unescape(re.sub(r'<[^>]+>', '', h))
        if 'စာမျက်နှာ' in txt and len(txt) < 40: continue            # page marker
        txt = '\n'.join(l.strip() for l in txt.split('\n') if l.strip())
        if txt: out.append((t, txt))
    return out


WT = {}                                 # Pali page -> length of its text (weights for spreading the English text over the pages between two anchors)


def pali_paras(bid):
    P = json.load(open(os.path.join(DATA, bid + '.json'), encoding='utf-8')); start = {}; pages = []; WT.clear()
    for r in P:
        pg = int(r['page']); pages.append(pg); WT[pg] = max(1, len(re.sub(r'<[^>]+>', '', r['content'])))
        for m in re.finditer(r'class="paranum">([၀-၉]+)', r['content']):
            start.setdefault(int(m.group(1).translate(TR)), pg)
        for n in re.findall(r'\d+', r.get('paranum') or ''): start.setdefault(int(n), pg)
    return start, pages


def lis(nums):                       # indices of the longest strictly increasing subsequence
    tails = []; idx = []; prev = [-1] * len(nums)
    for i, v in enumerate(nums):
        j = bisect.bisect_left([nums[k] for k in tails], v)
        if j == len(tails): tails.append(i)
        else: tails[j] = i
        prev[i] = tails[j - 1] if j else -1
    out = []; k = tails[-1] if tails else -1
    while k >= 0: out.append(k); k = prev[k]
    return out[::-1]


def align(bl, start, pages, verse=False):
    cand = []
    for i, (t, x) in enumerate(bl):
        m = (re.match(r'Verses?\s+(\d+)', x) or re.match(r'(\d+)\s*[\.\-,]', x)) if (t == 'p' and verse) else (re.match(r'(\d+)\s*[\.\-,]', x) if t == 'p' else None)
        if m and int(m.group(1)) in start: cand.append((i, int(m.group(1))))
    keep = [cand[k] for k in lis([n for _, n in cand])]
    anchor = {i: start[n] for i, n in keep}; ai = sorted(anchor); first = pages[0]; res = {}
    L = [len(x) for _, x in bl]
    def put(i, pg): res.setdefault(pg, []).append(bl[i])
    # headings stay with the block after them
    def seg_end(j):                       # last block index (exclusive) of the segment that ends before the next anchor, without the headings that lead into it
        while j > 0 and bl[j - 1][0] != 'p': j -= 1
        return j
    for a_i in range(len(ai) + 1):
        lo = ai[a_i - 1] if a_i else 0; hi = ai[a_i] if a_i < len(ai) else len(bl)
        p0 = anchor[ai[a_i - 1]] if a_i else first; p1 = anchor[ai[a_i]] if a_i < len(ai) else (pages[-1] if a_i else first)
        if a_i == 0: p0 = p1 = anchor[ai[0]] if ai else first        # text before the first anchor: with the first anchor
        end = seg_end(hi) if a_i < len(ai) else hi
        end = max(end, lo + 1) if a_i else end
        if a_i and a_i < len(ai) or a_i == len(ai):
            pr = [q for q in pages if p0 <= q <= p1] or [p0]
        else: pr = [p0]
        tot = sum(WT.get(q, 1) for q in pr); cum = []; c = 0
        for q in pr: c += WT.get(q, 1); cum.append(c / tot)
        blen = sum(L[lo:end]) or 1; run = 0
        for b in range(lo, end):
            f = run / blen; run += L[b]
            k = next((n for n, v in enumerate(cum) if f < v), len(pr) - 1)
            put(b, pr[k] if b != lo or not a_i else p0)
        for b in range(end, hi): put(b, anchor[ai[a_i]] if a_i < len(ai) else p0)       # the headings in front of the next anchor
    return res, len(keep), len(cand)


def render(items): return '\n'.join(('## ' + x.replace('\n', ' ') if t != 'p' else x) for t, x in items)


if __name__ == '__main__':
    key = sys.argv[1]; f = glob.glob(os.path.join(SRC, key + '_*.html'))[0]; bl = blocks_of(f)
    if key == 'F09':                     # Mahavagga (Sitagu translation): from the first sutta heading to the index
        a = next(i for i, (t, x) in enumerate(bl) if t != 'p' and x.startswith('I. MAHĀPADĀNA SUTTA DISCOURSE')); z = next(i for i, (t, x) in enumerate(bl) if i > a and t != 'p' and x == 'Index'); bl = bl[a:z]
    if key in VERSE:                     # Dhammapada: from the first chapter heading to the glossary
        a = next(i for i, (t, x) in enumerate(bl) if t != 'p' and x.startswith('Chapter I ')); z = next(i for i, (t, x) in enumerate(bl) if t != 'p' and x == 'Glossary'); bl = bl[a:z]
    for bid in JOBS[key]:
        start, pages = pali_paras(bid); res, nk, nc = align(bl, start, pages, key in VERSE)
        cov = len(res); print(key, bid, 'blocks', len(bl), 'numbered', nc, 'anchors', nk, 'pali pages', len(pages), 'with English', cov, 'first/last page', min(res), max(res))
        gaps = [p for p in pages if p not in res]; print('pages without English:', len(gaps), gaps[:40])
        if '--write' in sys.argv:
            out = {str(p): render(res[p]) for p in sorted(res)}
            d = os.path.join(DATA, 'translations_en'); fp = os.path.join(d, bid + '.json')
            if os.path.exists(fp) and not any(a == '--force' for a in sys.argv):
                old = json.load(open(fp, encoding='utf-8'))
                if old != out and any(k in old for k in out): print('existing English file differs - use --force to replace'); continue
            json.dump(out, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            ip = os.path.join(d, 'index.json'); idx = json.load(open(ip, encoding='utf-8')); n = 3000 + int(key[1:])
            ents = idx.setdefault(bid, []); e = next((x for x in ents if x['file'] == bid + '.json'), None)
            if e is None: ents.append({'file': bid + '.json', 'sheet': n})
            json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False); print('written', fp)
