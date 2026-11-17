# -*- coding: utf-8 -*-
"""One-click corrector:  chosen pages (or the whole book) of one nissaya book  ->  corrected text, ready for Google Sheets.

    python nissaya_multi/scripts/m_tool.py <sheet number> <first page> <last page>        e.g.  m_tool.py 1 29 40
    python nissaya_multi/scripts/m_tool.py <sheet number> all                              the whole book
    options:  --no-auto   do not add ၊ ။ / spacing / remove stray marks           --no-pali   do not correct misspelt Pali heads
              --punct     ALSO insert / change ၊ ။ (off by default: the user adds those himself with Find&Replace)
              --col C     (Google Sheets upload only) the column the corrected text is written to (never B = your text)
              --gsheet <url> --creds <service-account.json>     write straight into the Google Sheet (needs `pip install gspread`, see README)

What it does (nothing of the sheet is changed, the ORIGINAL OCR text stays untouched):
  * runs the same program as the viewer for those pages (page map from the database, alignment with the Pali text, ၊ ။ layer, Pali-head corrections)
  * writes  nissaya_multi/output/<sheet>_<pages>.xlsx   with columns:  A page label | B the text now in your sheet | C corrected text | D what was changed
    -> copy column C into the Google Sheet (or use --gsheet to do it automatically)
Corrected text = the cleaned page (page numbers / running heads / OCR garbage lines removed, footnotes kept after the text) with the chosen corrections applied."""
import json, os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import m_pair

OUT = os.path.join(ROOT, 'output')


def list_sheets():
    cat = json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))
    idx_path = os.path.join(ROOT, 'paired_index.json')
    idx = json.load(open(idx_path, encoding='utf-8')) if os.path.exists(idx_path) else {}
    out = []
    hp = os.path.join(ROOT, 'hidden_sheets.json')                      # sheet numbers the user does not want in the book list
    hidden = set(json.load(open(hp, encoding='utf-8'))) if os.path.exists(hp) else set()
    for r in cat:
        if not r.get('final') or r['n'] in hidden: continue
        name = re.sub(r'^Z\d\d\s*\d{3}\s*', '', r['sheet'])
        out.append((r['n'], '%d · %s → %s' % (r['n'], name, ' + '.join(r['final']['books']))))
    return out


def sheet_pages(n):
    cat = m_pair.load_catalog(n)
    rows = json.load(open(os.path.join(ROOT, 'sheets', cat['file']), encoding='utf-8'))['rows']
    return cat, [r for r in rows if r.get('text') is not None and not r.get('orphan') and r.get('num') is not None]


def run_corrections(n, lo, hi, log=print):
    """returns the payload (pages with 'fixes') of the better of the two page-map variants"""
    m_pair.FIX_RANGE[n] = (lo, hi)
    cat = m_pair.load_catalog(n); fin = cat['final']
    log('sheet %d: aligning with the Pali text, pages %s-%s ...' % (n, lo, hi))
    a = m_pair.run_variant(n, fin, None)
    best = a
    if fin.get('alt'):
        b = m_pair.run_variant(n, fin['alt'], None)
        if b['stats']['match_ratio'] > a['stats']['match_ratio']: best = b
    m_pair.FIX_RANGE.pop(n, None)
    return best


_RULES = {}


def _rules():
    if not _RULES:
        p = os.path.join(ROOT, 'learned_rules.json')
        _RULES['r'] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    return _RULES['r']


def apply_page(page, use_auto=True, use_pali=True, use_punct=False, use_rules=True):
    """corrected text of one page + list of the applied edits"""
    edits = [q for q in page.get('fixes', []) if (q.get('auto') and use_auto and (use_punct or q['kind'] != 'punct')) or (q['kind'] == 'pali' and use_pali)]
    body = page['body']
    for q in sorted(edits, key=lambda q: (-q['off'], -q['len'])): body = body[:q['off']] + q['new'] + body[q['off'] + q['len']:]
    text = body + ('\n' + page['foot'] if page.get('foot') else '')
    if use_rules:
        for old, r in _rules().items():                                     # spelling rules learned from the user's own Find&Replace work (m_rules.py)
            text, k = re.subn('(?<![က-ဿ])' + re.escape(old) + '(?![ါ-ှ])', r['new'], text)
            if k: edits = edits + [{'kind': 'rule', 'off': 0, 'len': 0, 'new': r['new']}] * k
    return text, edits


def write_xlsx(n, title, results, path):
    import openpyxl
    from openpyxl.styles import Alignment
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = re.sub(r'[\\/*?:\[\]]', '_', title)[:31]
    ws.append(['စာမျက်နှာ', 'ယခု sheet ထဲက စာသား (မပြင်)', 'ပြင်ပြီးစာသား (ဒီကော်လံကို ကူးသုံးပါ)', 'ပြင်ချက်'])
    for label, orig, corr, summary in results:
        ws.append([label, orig, corr, summary])
    ws.column_dimensions['A'].width = 16; ws.column_dimensions['B'].width = 70; ws.column_dimensions['C'].width = 70; ws.column_dimensions['D'].width = 30
    for row in ws.iter_rows(min_row=2):
        for c in row: c.alignment = Alignment(wrap_text=True, vertical='top')
    wb.save(path)


def upload_gsheet(url, worksheet, labels_to_text, creds, col='C', log=print):
    """writes the corrected text next to the original (column `col`, default C) of the Google Sheet. needs: pip install gspread + a service-account json shared with the sheet"""
    try:
        import gspread
    except ImportError:
        raise SystemExit('gspread is not installed:  pip install gspread   (see README: Google Sheets upload)')
    gc = gspread.service_account(filename=creds)
    sh = gc.open_by_url(url)
    ws = sh.worksheet(worksheet)
    labels = ws.col_values(1)
    cells = []
    for i, lab in enumerate(labels, start=1):
        if lab in labels_to_text: cells.append({'range': '%s%d' % (col, i), 'values': [[labels_to_text[lab]]]})
    for k in range(0, len(cells), 50): ws.batch_update(cells[k:k + 50], value_input_option='RAW')
    log('Google Sheet: %d cells written to column %s of "%s"' % (len(cells), col, worksheet))


def process(n, lo, hi, use_auto=True, use_pali=True, gsheet=None, creds=None, col='C', log=print, use_punct=False):
    t0 = time.time()
    cat, pages = sheet_pages(n)
    nums = [r['num'] for r in pages]
    if lo is None: lo, hi = min(nums), max(nums)
    payload = run_corrections(n, lo, hi, log)
    byn = {}
    for pg in payload['pages']:
        if pg['num'] is not None: byn.setdefault(pg['num'], pg)
    results = []; kinds = {}
    for r in pages:
        if not (lo <= r['num'] <= hi): continue
        pg = byn.get(r['num'])
        if pg is None: continue
        text, edits = apply_page(pg, use_auto, use_pali, use_punct)
        for q in edits: kinds[q['kind']] = kinds.get(q['kind'], 0) + 1
        sm = {}
        for q in edits: sm[q['kind']] = sm.get(q['kind'], 0) + 1
        results.append((r['label'], r['text'], text, ', '.join('%s %d' % kv for kv in sm.items())))
    os.makedirs(OUT, exist_ok=True)
    name = re.sub(r'[^\w\-]+', '_', re.sub(r'^Z\d\d\s*\d{3}\s*', '', cat['sheet']))[:30] or 'sheet%d' % n
    path = os.path.join(OUT, '%03d_%s_p%s-%s.xlsx' % (n, name, lo, hi))
    write_xlsx(n, cat['sheet'], results, path)
    log('pages: %d | applied: %s | %s | %.0f s' % (len(results), kinds or 'nothing', os.path.relpath(path, os.path.dirname(ROOT)), time.time() - t0))
    if gsheet:
        upload_gsheet(gsheet, cat['sheet'], {lab: corr for lab, orig, corr, s in results}, creds, col, log)
    return path


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: print(__doc__); raise SystemExit
    opts = {k: (a[a.index(k) + 1] if k in a else None) for k in ('--gsheet', '--creds', '--col')}
    flags = {'--no-auto': '--no-auto' in a, '--no-pali': '--no-pali' in a, '--punct': '--punct' in a}
    pos = [x for i, x in enumerate(a) if not x.startswith('--') and not (i > 0 and a[i - 1] in ('--gsheet', '--creds', '--col'))]
    n = int(pos[0])
    lo, hi = (None, None) if (len(pos) < 2 or pos[1] == 'all') else (int(pos[1]), int(pos[2]) if len(pos) > 2 else int(pos[1]))
    process(n, lo, hi, not flags['--no-auto'], not flags['--no-pali'], opts['--gsheet'], opts['--creds'], opts['--col'] or 'C', use_punct=flags['--punct'])
