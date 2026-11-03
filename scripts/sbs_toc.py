"""Myanmar table of contents for the Split View: data/mm_split_toc/<pali_id>.json = [[level, title, pali_page], ...]
built from the headings (h1-h3) of the published translation pages. Run after sbs_build.py / sbs_attha.py."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
SPLIT = os.path.join(DATA, 'mm_split')
OUT = os.path.join(DATA, 'mm_split_toc')
HEAD = re.compile(r'<h([1-4])\b[^>]*>(.*?)</h\1>', re.S)

def toc_of(pages, deep=False):
    out = []
    for pg in sorted(pages, key=int):
        for m in HEAD.finditer(pages[pg]):
            t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', m.group(2))).strip()
            lvl = int(m.group(1))
            if t and (lvl <= 3 or deep): out.append([min(lvl, 3), t, int(pg)])
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    idx = json.load(open(os.path.join(SPLIT, 'index.json'), encoding='utf-8'))
    for pali in idx:
        pages = json.load(open(os.path.join(SPLIT, pali + '.json'), encoding='utf-8'))
        toc = toc_of(pages, deep=pali.startswith('annya'))      # the Visuddhimagga keeps its chapter sections in <h4>
        with open(os.path.join(OUT, pali + '.json'), 'w', encoding='utf-8') as f:
            json.dump(toc, f, ensure_ascii=False, separators=(',', ':'))
        print(pali, len(toc))

if __name__ == '__main__':
    main()
