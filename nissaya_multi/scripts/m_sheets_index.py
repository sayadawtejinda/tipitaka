# -*- coding: utf-8 -*-
"""One list of every sheet of the three Excel files (နိဿယပေါင်းစုံ.xlsx, နိသျ.xlsx = နိဿယပေါင်းစုံ-၂, OCR Books (auto).xlsx) for sheets_browser.html.
Writes nissaya_multi/sheets_browser_index.json  (reads sheet_index.json + catalog.json only; the Excel files are not touched)."""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
si = json.load(open(os.path.join(ROOT, 'sheet_index.json'), encoding='utf-8'))
cat = {r['n']: r for r in json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))}
out = []
for e in si:
    c = cat.get(e['n'], {}); f = c.get('final') or {}
    out.append({'n': e['n'], 'sheet': e['sheet'], 'src': e.get('book_file') or '-', 'rows': e['rows'], 'meta': e.get('meta', {}).get('strs', []),
                'edition': (c.get('edition') or '')[:80], 'pali': f.get('books') or [], 'mode': f.get('mode') or '', 'check': c.get('check') or '', 'status': c.get('status') or ''})
json.dump(out, open(os.path.join(ROOT, 'sheets_browser_index.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print(len(out), 'sheets')
