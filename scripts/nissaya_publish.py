# -*- coding: utf-8 -*-
"""One command to put a reviewed book on the web (what the AI did by hand after every 'Export').

    python scripts/nissaya_publish.py ku2

1. takes the NEWEST  <book>_edits*.json  from your Downloads folder (what the Export button saved)
2. warns if you saved more work in the review page AFTER that Export (then press Export again first)
3. copies it to nissaya_data/<book>_edits.json and runs nissaya_export.py <book> --html (lossless check included)
4. shows what will be uploaded and asks y/n before git commit + push (only data/<pali id>.html and data/nissaya_books.json)
"""
import glob, json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding="utf-8")
book = sys.argv[1] if len(sys.argv) > 1 else input("Book id (e.g. ku2): ").strip()
dl = os.path.join(os.path.expanduser("~"), "Downloads")
cands = [f for f in glob.glob(os.path.join(dl, book + "_edits*.json")) if re.search(r"^" + re.escape(book) + r"_edits( \(\d+\))?\.json$", os.path.basename(f))]
if not cands:
    raise SystemExit(f"No {book}_edits*.json in {dl}. Open the review page of {book} and press Export first.")
src = max(cands, key=os.path.getmtime)
st = os.path.join(ROOT, "nissaya_data", "state", book + ".json")
print("newest Export :", os.path.basename(src), time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(src))))
if os.path.exists(st):
    print("review state  :", time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(st))))
    if os.path.getmtime(st) > os.path.getmtime(src) + 120:
        print("WARNING: you worked in the review page AFTER this Export. Press Export again, then run this again.")
        if input("Continue anyway? (y/n) ").strip().lower() != "y":
            raise SystemExit(1)
shutil.copy2(src, os.path.join(ROOT, "nissaya_data", book + "_edits.json"))
env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, os.path.join(HERE, "nissaya_export.py"), book, "--html"], cwd=ROOT, env=env)
if r.returncode:
    raise SystemExit("export failed - nothing uploaded")
cfg = json.load(open(os.path.join(ROOT, "nissaya_data", "books", book + ".json"), encoding="utf-8"))
pid = os.path.splitext(os.path.basename(cfg["pali"]))[0]
files = [f"data/{pid}.html", "data/nissaya_books.json"]
print("\nWill upload:", files)
if input("Commit and push to the web now? (y/n) ").strip().lower() != "y":
    raise SystemExit("not uploaded (the html is built locally)")
subprocess.run(["git", "add"] + files, cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", f"Nissaya: {book} ({pid}) published"], cwd=ROOT, check=True)
subprocess.run(["git", "push"], cwd=ROOT, check=True)
print(f"\nDONE - {book} is on the web. In the browser press Ctrl+Shift+R.")
