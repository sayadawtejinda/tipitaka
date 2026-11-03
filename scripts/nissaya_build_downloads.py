# -*- coding: utf-8 -*-
"""Rebuilds data/nissaya_downloads.json = the list the download page (nissaya_downloads.html) shows:
every book that is on the web as a nissaya (data/nissaya_books.json) with its title, group, size and the DATE the file last changed (git commit date).

    python scripts/nissaya_build_downloads.py

nissaya_publish.py runs this after every publish, so the page always lists new books and shows the new date of re-published ones.
"""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding="utf-8")
def J(p): return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
ids = J("data/nissaya_books.json"); ids = ids if isinstance(ids, list) else ids.get("books", [])
bk = J("books.json"); meta = {b["id"]: b for b in bk["books"]}
BASKET = {"mula": "ပါဠိတော်", "attha": "အဋ္ဌကထာ", "tika": "ဋီကာ", "annya": "အညဂန္ထဝင်"}
BASKET.update(bk.get("basket_labels", {}))
CAT = bk.get("category_labels", {})
ORDER = {"vi": 1, "di": 2, "ma": 3, "sa": 4, "an": 5, "ku": 6, "abh": 7}
out = []
for i in ids:
    p = os.path.join(ROOT, "data", i + ".html")
    if not os.path.exists(p): continue
    m = meta.get(i, {})
    parts = i.split("_")
    basket, cat = parts[0], parts[1] if len(parts) > 1 else ""
    r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "data/" + i + ".html"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    date = r.stdout.strip() or time.strftime("%Y-%m-%d")
    st = subprocess.run(["git", "status", "--porcelain", "--", "data/" + i + ".html"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if st: date = time.strftime("%Y-%m-%d")
    name = m.get("name") or i
    out.append({"id": i, "title": name, "basket": BASKET.get(basket, basket), "basket_key": basket,
                "category": CAT.get(m.get("category", cat), CAT.get(cat, cat)), "cat_key": cat,
                "size": os.path.getsize(p), "date": date, "order": [list(BASKET).index(basket) if basket in BASKET else 9, ORDER.get(cat, 9), i]})
# other editions of the same Pali book (nissaya_multi/scripts/m_publish.py writes data/nissaya_editions.json + data/<book>_<edition>.html, e.g. mula_vi_01_bhurakyi): each one is its own download line
ed = J("data/nissaya_editions.json") if os.path.exists(os.path.join(ROOT, "data", "nissaya_editions.json")) else {}
by_id = {x["id"]: x for x in out}
for book, eds in ed.items():
    base = by_id.get(book)
    if not base: continue
    for e in eds:
        f = e["file"]
        if f == book or f in by_id: continue
        p = os.path.join(ROOT, "data", f + ".html")
        if not os.path.exists(p): continue
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "data/" + f + ".html"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        st = subprocess.run(["git", "status", "--porcelain", "--", "data/" + f + ".html"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        x = dict(base); x.update({"id": f, "title": base["title"] + " (" + e.get("label", "") + ")", "size": os.path.getsize(p),
                                  "date": time.strftime("%Y-%m-%d") if st else (r.stdout.strip() or time.strftime("%Y-%m-%d")), "edition_of": book})
        out.append(x)
out.sort(key=lambda x: x["order"])
for x in out: del x["order"]
json.dump({"generated": time.strftime("%Y-%m-%d"), "books": out, "n_books": sum(1 for x in out if not x.get("edition_of")), "n_editions": sum(1 for x in out if x.get("edition_of"))}, open(os.path.join(ROOT, "data", "nissaya_downloads.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"data/nissaya_downloads.json: {len(out)} books, {sum(x['size'] for x in out)/1e6:.0f} MB")
