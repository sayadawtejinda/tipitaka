# -*- coding: utf-8 -*-
"""ONE place that says where a nissaya book stands - run_tool (m_gui) and run_translate (t_gui) both ask here, so no book can fall between the two tools.
  on_web(n)       the book's web file is COMMITTED in the tipitaka repository (a file only copied into data/ is not on the web yet)
  gemini_done(n)  every nissaya page that is SHOWN on the web (belongs to a Pali page) is checked by Gemini, and no Gemini file is waiting
  state(n)        'todo'     Gemini has not finished  -> run_tool (files for Gemini; also when the book is already on the web)
                  'publish'  Gemini finished, not on the web yet -> run_tool (publish)
                  'done'     on the web and Gemini finished -> run_translate
"""
import os, json, glob, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); TIPI = os.path.dirname(ROOT)
import m_gcheck
_TRK = {'t': 0, 'set': None}
_CACHE = os.path.join(ROOT, 'gem_done_cache.json')
_VER = 2          # change when the rule of gemini_done changes (old cached answers are then computed again)
try: _GD = json.load(open(_CACHE, encoding='utf-8'))
except Exception: _GD = {}


def _tracked(fresh=False):
    if fresh or time.time() - _TRK['t'] > 60 or _TRK['set'] is None:
        try: _TRK['set'] = set(subprocess.run(['git', 'ls-files', 'data'], cwd=TIPI, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.split(chr(10)))
        except Exception: _TRK['set'] = None
        _TRK['t'] = time.time()
    return _TRK['set']


def _jl(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except Exception: return d


def on_web_set(fresh=False):
    """sheets that are on the web = a COMMITTED web file data/<book>_sheetNNN.html exists (the name carries the sheet number).  A Pali book having some other nissaya (the original 'မူလနိဿယ', another edition) says nothing about this sheet."""
    import re
    tracked = _tracked(fresh)
    if tracked is None: tracked = set('data/' + os.path.basename(f) for f in glob.glob(os.path.join(TIPI, 'data', '*_sheet*.html')))
    out = set()
    for f in tracked:
        m = re.search(r'_sheet(\d+)\.html$', f)
        if m: out.add(int(m.group(1)))
    # published before the file names carried a sheet number: the sheet counts when its edition (the label of the sheet) is listed for ALL its Pali books in data/nissaya_editions.json
    ed = _jl(os.path.join(TIPI, 'data', 'nissaya_editions.json'), {}); nb = set(_jl(os.path.join(TIPI, 'data', 'nissaya_books.json'), []))
    for r in _jl(os.path.join(ROOT, 'catalog.json'), []):
        n = r['n']; b = (r.get('final') or {}).get('books') or []
        if n in out or not b: continue
        lab = r.get('edition')
        if lab:
            if all(any(e.get('label') == lab or e.get('label', '').startswith(lab.split(' (')[0]) and lab in e.get('label', '') for e in ed.get(x, [])) for x in b): out.add(n)
        elif all(any(e.get('label') == 'ဘာသာဋီကာ' for e in ed.get(x, [])) for x in b): out.add(n)          # no edition name on the sheet (the Vinaya tika sheets): the book has the 'ဘာသာဋီကာ' edition on the web
    return out


def gemini_done(n):
    cp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
    try: key = [os.path.getmtime(cp), len(glob.glob(os.path.join(ROOT, 'output', 'gemini', '%03d_*.txt' % n))), os.path.getmtime(os.path.join(ROOT, 'paired', '%03d.json' % n)), _VER]
    except OSError: return False
    if _GD.get(str(n), [None, None])[0] == key: return _GD[str(n)][1]
    try:
        miss, waiting = m_gcheck.missing_pages(n)
        ok = key[1] == 0 and not miss and len(json.load(open(cp, encoding='utf-8'))) > 0
    except Exception: ok = False
    _GD[str(n)] = [key, ok]
    try: json.dump(_GD, open(_CACHE, 'w', encoding='utf-8'))
    except Exception: pass
    return ok


def state(n, web=None):
    web = on_web_set() if web is None else web
    if not gemini_done(n): return 'todo'
    return 'done' if n in web else 'publish'
