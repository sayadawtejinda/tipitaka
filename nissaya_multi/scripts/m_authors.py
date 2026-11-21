# -*- coding: utf-8 -*-
"""Author (short name of the sayadaw) of a nissaya sheet + 'hold' flag (Gemini has finished but the author is not known yet, so the book is not put on the web).
File: nissaya_multi/authors.json   {"302": {"author": "ဂူကြီး", "hold": false}}.  The web label of a published sheet becomes '<author> (<volume>)'."""
import os, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'authors.json')
def load():
    try: return json.load(open(P, encoding='utf-8'))
    except Exception: return {}
def get(n): return load().get(str(n), {})
_CAT = {'t': 0, 'd': {}}
def _cat(n):
    import time
    if time.time() - _CAT['t'] > 30:
        try: _CAT['d'] = {r['n']: r for r in json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))}
        except Exception: _CAT['d'] = {}
        _CAT['t'] = time.time()
    return _CAT['d'].get(int(n), {})
def author_known(n):
    """the author / edition name is known: given in run_tool, or the sheet's edition name is not just the book title ('...အဋ္ဌကထာနိသျ (ဒု)' = title only; 'ဂူကြီး'၊ 'မြင်းခြံမူ'၊ 'ဘာဋီ (ပ)'၊ 'ဘာသာဋီကာ' are names)"""
    if author(n): return True
    ed = (_cat(n).get('edition') or '').strip()
    if not ed: return True                       # no edition on the sheet: the name of the database book (nsy_books.name) is used - that is a name
    if len(ed) > 60 or chr(10) in ed: return False  # the edition cell holds page text, not a name
    return not (re.search('နိသျ|နိဿယ', ed) and 'ကူကြီး' not in ed)
def map_known(n):
    """the sheet has a reliable map to its Pali book(s): database name and page content agree (or the id was found by content)"""
    r = _cat(n); f = r.get('final') or {}; ck = r.get('check') or ''
    return bool(f.get('books')) and f.get('mode') == 'db' and not ck.startswith(('NO RELIABLE', 'UNKNOWN', 'content guess'))
def hold_reason(n):
    """None = may be published automatically; else why the book waits"""
    if get(n).get('hold'): return 'ကိုယ်တိုင် ဆိုင်းထားသည်'
    w = []
    if not author_known(n): w.append('ဆရာတော်/မူအမည် မသိသေး')
    if not map_known(n): w.append('database map မရှိ/မသေချာ')
    return ' + '.join(w) or None
def on_hold(n): return hold_reason(n) is not None
def author(n): return (get(n).get('author') or '').strip()
def save(n, author=None, hold=None):
    d = load(); e = d.get(str(n), {})
    if author is not None: e['author'] = ' '.join(author.split())
    if hold is not None: e['hold'] = bool(hold)
    if not e.get('author') and not e.get('hold'): d.pop(str(n), None)
    else: d[str(n)] = e
    json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
def label(n, edition):
    """'<author> (<volume>)'  - the volume letter(s) come from the sheet's edition text '... (ပ)'; no author -> None"""
    a = author(n)
    if not a: return None
    m = re.search(r'\(([^)]*)\)\s*(?:[^()]*)$', edition or '')
    return a + (' (' + m.group(1).split()[0] + ')' if m and m.group(1).strip() else '')
