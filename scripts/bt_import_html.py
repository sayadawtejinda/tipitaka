# -*- coding: utf-8 -*-
"""Documents/spellcheck/out/html/c0N_*.html (Bhasatika books without nissaya, checked by Gemini) -> data/bt_*.html (the dictionary's right-hand web text).
Page marks  <p><font ... >စာမျက်နှာ-N</font></p>  become  (နိဿယစာအုပ် စာမျက်နှာ N). Usage: python scripts/bt_import_html.py   then  python scripts/bt_web_map.py"""
import os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.expanduser('~'), 'Documents', 'spellcheck', 'out', 'html')
BOOKS = [('c01_annya_366_ATAP.html', 'bt_annya_366_ATAP.html', 'အဋ္ဌကထာအခြေပြု'), ('c02_annya_407_VT_TCS_BT.html', 'bt_annya_407_VT_TCS_BT.html', 'ဝီထိနှင့် သုံးချက်စုဘာသာဋီကာ')]
MARK = '<p style="text-indent:0;text-align:right;color:#999;font-size:.8em;border-top:2px dotted #ccc;margin:.9em 0 .3em">(နိဿယစာအုပ် စာမျက်နှာ %s)</p>'
for sf, df, title in BOOKS:
    s = open(os.path.join(SRC, sf), encoding='utf-8').read()
    a = s.index('<div id="bk">') + len('<div id="bk">'); b = s.index('</div>\n<script', a) if '</div>\n<script' in s[a:] else s.rindex('</div>')
    body = s[a:b].strip(chr(10))
    body, n = re.subn(r'<p><font color="#999999" size="1">စာမျက်နှာ-([^<]*)</font></p>', lambda m: MARK % m.group(1).strip(), body)
    out = '<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n<title>%s</title>\n</head>\n<body>\n\n\n%s\n\n</body></html>\n' % (title, body)
    old = os.path.join(ROOT, 'data', df)
    open(old, 'w', encoding='utf-8').write(out); print(df, n, 'pages', len(out))
