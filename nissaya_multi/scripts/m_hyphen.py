# -*- coding: utf-8 -*-
"""Nissaya books that are written  'ပါဠိ-အနက်၊ ပါဠိ-အနက်၊'  (hyphen style, mostly the ဘာသာဋီကာ books) are turned into the common form
        ပါဠိ၊ အနက်။ ပါဠိ၊ အနက်။
which the rest of the system understands (bold Pali words, the one-word pop-up beside the Pali text, Gemini's own style).
    အန္ဓော-သူကန်းသည်၊ (သမာနော-ဖြစ်ပါလျက်၊) ပဗ္ဗတံ- တောင်ပေါ်သို့၊   ->   အန္ဓော၊ သူကန်းသည်။ (သမာနော၊ ဖြစ်ပါလျက်။) ပဗ္ဗတံ၊ တောင်ပေါ်သို့။
The text is cut at ၊ ။ and line ends; in a chunk the FIRST hyphen whose left side is mostly Pali words (checked with the Pali text of the book) separates Pali and meaning;
the ၊ that ends such a chunk becomes ။.  A hyphen inside a Pali compound (ပုဗ္ဗ-ကိစ္စ: Pali on both sides, no spaces) is left alone.  Nothing else of the text is touched.
    convert(text, is_pali, mark=False) -> (new text, number of units changed)        is_pali(token) -> bool
    transfer(marked, gemini_text)      -> (new text, number of marks set)           takes the ၊ ။ of the converted sheet text into Gemini's page (Gemini keeps the sheet's separators)"""
import re, difflib
ZW = '​‌‍﻿'
TOK = re.compile('[က-အဣ-ဿ' + ZW + ']+')
HY = re.compile(r'^(?P<lead>[\s(\[“"‘\']*)(?P<left>[^\-–\n]*?[^\s\-–][^\-–\n]*?)(?P<sp1>\s*)[-–](?P<sp2>\s*)(?P<right>\S[\s\S]*)$')
OKW = {'ဝါ', 'စ', 'ဣတိ', 'ပေ', 'တဿ', 'တေ'}
S, E = '\x00', '\x01'


def convert(text, is_pali, mark=False):
    out = []; n = 0
    for part in re.split('([၊။\n])', text):
        if part in ('၊', '။', '\n') or not part:
            out.append(part); continue
        m = HY.match(part)
        if m:
            lt = [re.sub('[' + ZW + ']', '', t) for t in TOK.findall(m.group('left'))]
            rt = [re.sub('[' + ZW + ']', '', t) for t in TOK.findall(m.group('right'))]
            ev = [t in OKW or is_pali(t) for t in lt]
            ok = 1 <= len(lt) <= 8 and sum(ev) >= 1 and sum(ev) * 2 >= len(lt)          # as for the heads of the common form: at least half of the words are Pali
            compound = ok and rt and is_pali(rt[0]) and not m.group('sp1') and not m.group('sp2')
            if ok and not compound:
                out.append(S + m.group('lead') + m.group('left').strip() + '၊ ' + m.group('right').lstrip() + E); n += 1; continue
        out.append(part)
    s = ''.join(out)
    s = re.sub(S + '([^' + E + ']*)' + E + '၊', (S + r'\1။' + E) if mark else r'\1။', s)          # the ၊ that ended the chunk becomes ။
    s = re.sub(S + '([^' + E + ']*)' + E, (S + r'\1' + E) if mark else r'\1', s)
    return s, n


_PW = re.compile('([က-အဣ-ဿ၌၍၏]+)([ \t]*)([၊။]?)')


def transfer(marked, gem):
    """marked = convert(sheet text, mark=True).  For every word that stands in a converted unit and is the same word in Gemini's page, the mark after it is the one of the
    converted sheet text (၊ after the Pali, ။ after the meaning).  returns (new text, number of marks set)"""
    A = []; inside = False
    for m in re.finditer('[' + S + E + ']|' + _PW.pattern, marked):
        if m.group() == S: inside = True; continue
        if m.group() == E: inside = False; continue
        A.append((m.group(1), m.group(3), inside))
    Bm = list(_PW.finditer(gem))
    sm = difflib.SequenceMatcher(None, [a for a, _, _ in A], [m.group(1) for m in Bm], autojunk=False)
    edits = []
    for a, b, n in sm.get_matching_blocks():
        for i in range(n):
            w, mk, ins = A[a + i]; m = Bm[b + i]
            if ins and mk and m.group(3) != mk: edits.append((m, mk))
    out = gem
    for m, mk in sorted(edits, key=lambda x: -x[0].start()):
        if m.group(3): out = out[:m.start(3)] + mk + out[m.end(3):]
        else: out = out[:m.end(1)] + mk + out[m.end(1):]
    return out, len(edits)


def finish(text, is_pali):
    """Gemini's page of a hyphen-style book where Gemini changed some words, so transfer() could not follow: a meaning that still ends with ၊ and is followed by a Pali head
    (a chunk whose words are mostly Pali) ends there - the ၊ becomes ။.  returns (new text, number of marks changed)"""
    chunks = [(m.group(1), m.group(2), m.start(2)) for m in re.finditer('([^၊။\n]*)([၊။\n]|$)', text) if m.group(1) or m.group(2)]
    def head(c):
        t = [re.sub('[' + ZW + ']', '', x) for x in TOK.findall(c)]
        if not t or len(t) > 8: return False
        ev = [x in OKW or is_pali(x) for x in t]
        return sum(ev) >= 1 and sum(ev) * 2 >= len(t)
    H = [head(c) for c, _, _ in chunks]; edits = []
    for i in range(1, len(chunks) - 1):
        c, mk, pos = chunks[i]
        if mk == '၊' and not H[i] and H[i + 1] and H[i - 1] is not None and chunks[i + 1][0].strip() and chunks[i - 1][1] in ('၊', '။') and chunks[i - 1][1] == '၊' and (H[i - 1] or not H[i - 1]):
            edits.append(pos)
    out = text
    for pos in sorted(edits, reverse=True): out = out[:pos] + '။' + out[pos + 1:]
    return out, len(edits)


def tidy(text):
    """'၊-' left behind by Gemini ('အင်္ဂုလျာ၊- အနက်') -> '၊ '"""
    return re.sub('၊\s*[-–]\s*', '၊ ', text)
