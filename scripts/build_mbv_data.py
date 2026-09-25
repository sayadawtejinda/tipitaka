# မဟာဗုဒ္ဓဝင် ၈ တွဲကို data/mbv_N.json အဖြစ် ထုတ်ပေးသည် (pages = body HTML, toc = မာတိကာ)
import sqlite3, json, re, os
SRC = 'မဟာဗုဒ္ဓဝင်'
FILES = "one two three four five six seven eight".split()
c = sqlite3.connect(f'{SRC}/MaharBuddha.sqlite')
for n, f in enumerate(FILES, 1):
    rows = c.execute("select cast(page as int), name from MyTable where file=? order by 1", (f + '.json',)).fetchall()
    pages = []
    for _, v in rows:
        m = re.search(r'<body[^>]*>(.*)</body>', v, re.S)
        pages.append((m.group(1) if m else v).strip())
    toc = []
    for t in json.loads(open(f'{SRC}/{f}.json', encoding='utf-8-sig').read()):
        pg = int(str(t['page']).strip() or 0) + 1
        lv = int(str(t['level']).strip() or 1)
        toc.append({'title': t['name'].strip(), 'level': lv, 'page': min(max(pg, 1), len(pages))})
    json.dump({'pages': pages, 'toc': toc}, open(f'data/mbv_{n}.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(n, len(pages), len(toc), os.path.getsize(f'data/mbv_{n}.json'))
