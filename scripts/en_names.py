# -*- coding: utf-8 -*-
"""Alignment by sutta (or vagga) NAME for the English Anguttara books (build_en_ocr.py): the English headings 'N. NAME SUTTA' are paired with the Pali 'subhead' lines
'N။ ...သုတ္တံ' by a monotone dynamic-programming alignment on the Roman form of the names (Myanmar -> Roman, diacritics / aspirates blurred) + the sutta number."""
import difflib, json, os, re, unicodedata
TR = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')
C = {'က': 'k', 'ခ': 'kh', 'ဂ': 'g', 'ဃ': 'gh', 'င': 'n', 'စ': 'c', 'ဆ': 'ch', 'ဇ': 'j', 'ဈ': 'jh', 'ည': 'n', 'ဉ': 'n', 'ဋ': 't', 'ဌ': 'th', 'ဍ': 'd', 'ဎ': 'dh', 'ဏ': 'n', 'တ': 't', 'ထ': 'th', 'ဒ': 'd', 'ဓ': 'dh', 'န': 'n', 'ပ': 'p', 'ဖ': 'ph', 'ဗ': 'b', 'ဘ': 'bh', 'မ': 'm', 'ယ': 'y', 'ရ': 'r', 'လ': 'l', 'ဝ': 'v', 'သ': 's', 'ဟ': 'h', 'ဠ': 'l', 'အ': 'a'}
IV = {'ဣ': 'i', 'ဤ': 'i', 'ဥ': 'u', 'ဦ': 'u', 'ဧ': 'e', 'ဩ': 'o', 'ဪ': 'o'}
DV = {'ာ': 'a', 'ါ': 'a', 'ိ': 'i', 'ီ': 'i', 'ု': 'u', 'ူ': 'u', 'ေ': 'e', 'ံ': 'm'}


def my2lat(t):
    out = []; i = 0; n = len(t)
    while i < n:
        ch = t[i]
        if ch in C:
            out.append(C[ch]); j = i + 1; vow = False
            while j < n and t[j] in 'ေ်ာါိီုူံ့ျြွှ':
                if t[j] == 'ေ' and j + 1 < n and t[j + 1] in 'ာါ': out.append('o'); j += 2; vow = True; continue
                if t[j] in DV: out.append(DV[t[j]]); vow = True
                j += 1
            if not vow and '်' not in t[i + 1:j] and not (j < n and t[j] == '္'): out.append('a')
            if j < n and t[j] == '္': j += 1
            i = j; continue
        if ch in IV: out.append(IV[ch])
        i += 1
    return ''.join(out)


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower()); s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z]', '', s.replace('ṃ', 'm').replace('ṁ', 'm').replace('ñ', 'n'))
    for a, b in (('ph', 'p'), ('bh', 'b'), ('dh', 'd'), ('th', 't'), ('kh', 'k'), ('gh', 'g'), ('jh', 'j'), ('ch', 'c')): s = s.replace(a, b)
    return re.sub(r'(.)\1+', r'\1', s)


def en_items(bl, level):
    """[(block index, number, normalised name)]"""
    out = []
    for i, (t, x) in enumerate(bl):
        if t == 'p': continue
        if level == 'sutta':
            m = re.match(r'(\d+)\.\s+(.*?SUTTA[A-Z]*|.*?[Ss]utta)\b', x)
            if m and re.search(r'[A-Za-zā]{3}', m.group(2)): out.append((i, int(m.group(1)), re.sub(r'sutta[a-z]?$', '', norm(m.group(2)))))
        else:
            m = re.match(r'^(?:[IVXL]+\.\s+)?(?:THE\s+)?(.*?VAGGA|.*?[Vv]agga)$', x.split('\n')[0].strip())
            if m and len(x) < 60 and (re.match(r'^[IVXL]+\.', x) or x == x.upper()): out.append((i, 0, re.sub(r'vagga$', '', norm(m.group(1)))))
    return out


def pa_items(bid, DATA, level):
    P = json.load(open(os.path.join(DATA, bid + '.json'), encoding='utf-8')); out = []
    for r in P:
        for m in re.finditer(r'<p class="(\w+)"[^>]*>(.*?)</p>', r['content'], re.S):
            c = m.group(1); t = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if level == 'sutta' and c == 'subhead':
                mm = re.match(r'([၀-၉]+)။\s*(.*)', t)
                if mm: out.append((bid, int(r['page']), int(mm.group(1).translate(TR)), re.sub(r'suttam?$', '', norm(my2lat(mm.group(2))))))
            elif level == 'vagga' and c in ('chapter', 'title'):
                mm = re.match(r'([၀-၉]+)။\s*(.*ဝဂ္ဂေါ)', t)
                if mm: out.append((bid, int(r['page']), 0, re.sub(r'vago$', '', norm(my2lat(mm.group(2))))))
    return out


def dp(E, Pl):
    n, m = len(E), len(Pl); S = [[0.0] * (m + 1) for _ in range(n + 1)]; B = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): S[i][0] = -0.1 * i; B[i][0] = 1
    for j in range(1, m + 1): S[0][j] = -0.1 * j; B[0][j] = 2
    def sc(e, p): return difflib.SequenceMatcher(None, e[2], p[3]).ratio() + 0.15 * (e[1] == p[2] and e[1] > 0) - 0.5
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d = S[i - 1][j - 1] + sc(E[i - 1], Pl[j - 1]); u = S[i - 1][j] - 0.1; l = S[i][j - 1] - 0.1
            S[i][j] = max(d, u, l); B[i][j] = 0 if S[i][j] == d else (1 if S[i][j] == u else 2)
    i, j = n, m; pairs = []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and B[i][j] == 0:
            if sc(E[i - 1], Pl[j - 1]) > -0.05: pairs.append((i - 1, j - 1))
            i -= 1; j -= 1
        elif i > 0 and (j == 0 or B[i][j] == 1): i -= 1
        else: j -= 1
    return pairs[::-1]
