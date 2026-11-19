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
    """sheets that are on the web.  A sheet with a web file is on the web when that file is committed; a sheet without any web file (published before .meta.json existed) counts when ALL its Pali books have a nissaya on the web."""
    tracked = _tracked(fresh); out = set(); has_meta = set()
    for mp in glob.glob(os.path.join(ROOT, 'web', '*.meta.json')):
        try:
            m = json.load(open(mp, encoding='utf-8')); n = int(m['sheet']); has_meta.add(n); f_ = 'data/' + m['file'] + '.html'
            if (f_ in tracked) if tracked else os.path.exists(os.path.join(TIPI, f_)): out.add(n)
        except Exception: pass
    wb = set(_jl(os.path.join(TIPI, 'data', 'nissaya_books.json'), [])) | set(_jl(os.path.join(TIPI, 'data', 'nissaya_editions.json'), []))
    for r in _jl(os.path.join(ROOT, 'catalog.json'), []):
        b = (r.get('final') or {}).get('books') or []
        if r['n'] not in has_meta and b and all(x in wb for x in b): out.add(r['n'])
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
