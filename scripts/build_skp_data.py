# ShweKyin+Sarpay/database/shwekyin.db ကနေ data/skp_index.json (ရွှေကျင်စာပေ - စာအုပ်စာရင်း၊ မာတိကာ၊ အညွှန်း) ထုတ်ပေးသည်
# page = PDF စာမျက်နှာအမှတ် (PDF viewer #page= နဲ့ တိုက်ရိုက်သုံးနိုင်သည်)
import sqlite3, json
c = sqlite3.connect('ShweKyin+Sarpay/database/shwekyin.db')
authors = [{'id': i, 'name': n, 'books': []} for i, n in c.execute("select distinct category_id, category_name from books order by 1")]
by_id = {a['id']: a for a in authors}
books = {}
for bid, title, cat in c.execute("select id, title, category_id from books order by id"):
    books[bid] = {'title': title.strip(), 'toc': []}
    by_id[cat]['books'].append(bid)
for h, lv, bid, pg in c.execute("select heading, level, book_id, page_number from tocs order by rowid"):
    if bid in books: books[bid]['toc'].append([h.strip(), lv, pg])
notes = [[n.strip(), bid, pg] for n, bid, pg in c.execute("select note, book_id, page_number from notes") if n and bid in books]
json.dump({'authors': authors, 'books': books, 'notes': notes}, open('data/skp_index.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(books), sum(len(b['toc']) for b in books.values()), len(notes))
