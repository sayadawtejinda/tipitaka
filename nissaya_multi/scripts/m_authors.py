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
def on_hold(n): return bool(get(n).get('hold'))
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
