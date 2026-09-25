# Tipitaka+Abidan/tipitaka_abidan.db ကနေ data/tabidan_index.json (တိပိဋကအဘိဓာန် - ဝေါဟာရ → အတွဲ:စာမျက်နှာ) ထုတ်ပေးသည်
# PDF စာမျက်နှာ = စာမျက်နှာအမှတ် + start_page (အတွဲ ၁ ၏ ၃၈ = PDF ၁၅၈ ဖြင့် အတည်ပြုပြီး)
import sqlite3, json, os
c = sqlite3.connect('Tipitaka+Abidan/tipitaka_abidan.db')
books = {i: {'name': n.strip(), 'info': (inf or '').strip(), 'start': s} for i, n, inf, s in c.execute("select id,name,name_info,start_page from books order by id")}
words = {}
for w, b, p in c.execute("select word, book_id, page_number from words order by id"):
    refs = words.setdefault(w.strip(), [])
    r = f"{b}:{p}"
    if r not in refs: refs.append(r)
out = {'books': books, 'words': [[w, ",".join(r)] for w, r in words.items()]}
json.dump(out, open('data/tabidan_index.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(books), len(words), os.path.getsize('data/tabidan_index.json'))
# repo နှစ်ခုခွဲရန် (GitHub Pages 1GB ကန့်သတ်ချက်) - အတွဲအလိုက် အရွယ်အစားညီအောင်
tot = 0; acc = 0; split = []
sizes = {i: os.path.getsize(f'Tipitaka+Abidan/books/{i}.pdf') for i in books}
half = sum(sizes.values()) / 2
for i in sorted(books):
    acc += sizes[i]; split.append((i, 1 if acc <= half else 2))
print(split, sum(s for i, s in sizes.items() if dict(split)[i] == 1) / 1e6, sum(s for i, s in sizes.items() if dict(split)[i] == 2) / 1e6)
