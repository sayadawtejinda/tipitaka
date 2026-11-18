# -*- coding: utf-8 -*-
"""Files for the Gemini 'Pali Translate AI' Canvas app: PER PALI PAGE  ### ပါဠိ (the Pali text)  +  ### နိဿယ (the nissaya pages of that Pali page, the CHECKED text that Gemini returned
and m_gcheck collected into gold/gemini/NNN_collected.json).  Many sets in one file, one set = Pali pages until `maxchars` characters.
    build(n, lo, hi, ...)    -> output/tr_NNN_<book>_pali<a>-<b>.txt        (run from the button tool t_gui.pyw)
    ingest_downloads()       -> takes  tr_*_translated.txt  from Downloads into gold/tr_NNN.json  {Pali page: Burmese text}, moves the file to received/, deletes the finished input file
    export_book(n)           -> gold/tr_NNN.txt  every translated Pali page in order
A nissaya page that Gemini has not checked yet is NOT used (the Pali page is left out and listed) unless raw_ok=True (then the cleaned OCR text is used and the page is marked)."""
import glob, json, os, re, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); NSY = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(NSY, 'scripts'))
OUT = os.path.join(HERE, 'output'); GOLD = os.path.join(HERE, 'gold'); RECV = os.path.join(GOLD, 'received')
DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')
NL = chr(10)


def _paired(n): return json.load(open(os.path.join(NSY, 'paired', '%03d.json' % n), encoding='utf-8'))


def _collected(n):
    p = os.path.join(NSY, 'gold', 'gemini', '%03d_collected.json' % n)
    return {int(k): v for k, v in json.load(open(p, encoding='utf-8')).items()} if os.path.exists(p) else {}


def build(n, lo, hi, maxchars=10000, sets=10, raw_ok=False, log=print):
    P = _paired(n); col = _collected(n)
    pages = {p['num']: p for p in P['pages'] if p.get('num') is not None}
    blocks = {}
    for b in P['blocks']: blocks.setdefault((b['book'], b['page']), []).append(b)
    keys = sorted(((k.split('|')[0], int(k.split('|')[1])) for k in P['ppmap']), key=lambda x: (x[0], x[1]))
    keys = [g for g in keys if lo <= g[1] <= hi]
    if len({g[0] for g in keys}) > 1: log('⚠ ဤအကွာအဝေးတွင် ပါဠိစာအုပ် တစ်အုပ်ထက်ပို ပါသည် — ပထမစာအုပ်သာ ယူပါ (အကွာအဝေး ကျဉ်းပါ)')
    built = []; left_out = []; raw_used = set()
    for g in keys:
        r0, r1 = P['ppmap']['%s|%s' % g]
        nums = [k for k in range(r0, r1 + 1) if k in pages]
        texts = []; missing = []
        for k in nums:
            if k in col: texts.append('[နိဿယ မျက်နှာ %d]' % k + NL + col[k].strip())
            elif raw_ok: texts.append('[နိဿယ မျက်နှာ %d (Gemini မစစ်ရသေး)]' % k + NL + (pages[k]['body'] + (NL + pages[k]['foot'] if pages[k].get('foot') else '')).strip()); raw_used.add(k)
            else: missing.append(k)
        if missing: left_out.append((g[1], missing)); continue
        pali = NL.join(b['pali'] for b in sorted(blocks.get(g, []), key=lambda b: b['i']))
        if not pali.strip(): left_out.append((g[1], ['ပါဠိစာ မရှိ'])); continue
        built.append((g, '--- စာမျက်နှာ %d ---' % g[1] + NL + '### ပါဠိ' + NL + pali + NL + '### နိဿယ' + NL + (NL * 2).join(texts) + NL))
    for pg, miss in left_out: log('  ပါဠိ %d: ထုတ်မရ — နိဿယ %s' % (pg, ' '.join(map(str, miss)) if isinstance(miss[0], int) else miss[0]) + (' မစစ်ရသေး' if isinstance(miss[0], int) else ''))
    if raw_used: log('  ⚠ Gemini မစစ်ရသေးသော နိဿယစာမျက်နှာ %d ခု OCR စာဖြင့် ထည့်ထားသည်' % len(raw_used))
    groups = []; cur = []; size = 0
    for g, t in built:
        if cur and size + len(t) > maxchars: groups.append(cur); cur = []; size = 0
        cur.append((g, t)); size += len(t)
    if cur: groups.append(cur)
    os.makedirs(OUT, exist_ok=True); files = []
    for j in range(0, len(groups), sets):
        chunk = groups[j:j + sets]
        first, last = chunk[0][0][0], chunk[-1][-1][0]
        name = 'tr_%03d_%s_pali%d-%d.txt' % (n, first[0], first[1], last[1])
        body = NL.join('===== အစု %d / %d =====' % (k + 1, len(chunk)) + NL + NL.join(t for g, t in s) for k, s in enumerate(chunk))
        open(os.path.join(OUT, name), 'w', encoding='utf-8').write(body)
        files.append(name); log('  %s : %d sets (ပါဠိ %d-%d), %d characters' % (name, len(chunk), first[1], last[1], len(body)))
    log('%d ဖိုင်၊ ပါဠိ %d မျက်နှာ -> %s' % (len(files), len(built), OUT))
    return OUT, files


_PAGE = re.compile(r'^---\s*စာမျက်နှာ\s*([0-9၀-၉]+)\s*---\s*$', re.M)
_DIG = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')


def parse_pages(text):
    ms = list(_PAGE.finditer(text)); out = {}
    for i, m in enumerate(ms):
        out[int(m.group(1).translate(_DIG))] = text[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(text)].strip()
    return out


def load_translations(n):
    p = os.path.join(GOLD, 'tr_%03d.json' % n)
    return {int(k): v for k, v in json.load(open(p, encoding='utf-8')).items()} if os.path.exists(p) else {}


def save_translations(n, d):
    os.makedirs(GOLD, exist_ok=True)
    json.dump({str(k): d[k] for k in sorted(d)}, open(os.path.join(GOLD, 'tr_%03d.json' % n), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def ingest_downloads(log=print):
    got = 0
    for f in sorted(glob.glob(os.path.join(DOWNLOADS, 'tr_*_translated*.txt'))):
        name = os.path.basename(f); m = re.match(r'tr_(\d+)_(.+?)_pali(\d+)-(\d+)_translated', name)
        if not m or time.time() - os.path.getmtime(f) < 3: continue
        n = int(m.group(1))
        pg = parse_pages(open(f, encoding='utf-8-sig').read())
        if not pg: log('⚠ Downloads/%s — "--- စာမျက်နှာ N ---" မတွေ့ပါ' % name); continue
        d = load_translations(n); repl = [k for k in pg if k in d]
        d.update({k: v for k, v in pg.items() if v.strip()}); save_translations(n, d)
        os.makedirs(RECV, exist_ok=True); shutil.move(f, os.path.join(RECV, time.strftime('%Y%m%d_%H%M%S_') + name))
        log('⬇ %s — စာအုပ် %03d ထဲ ပါဠိ %d မျက်နှာ ထည့်ပြီး%s' % (name, n, len(pg), (' (အစားထိုး %d)' % len(repl)) if repl else ''))
        inp =os.path.join(OUT, re.sub(r'_translated.*$', '.txt', name))
        if os.path.exists(inp):
            want = set(parse_pages(open(inp, encoding='utf-8').read()))
            if want <= set(d): os.remove(inp); log('  ✔ ထည့်ဖိုင်ပြီးစီးသဖြင့် ဖျက်ပြီး')
            else: log('  ပြန်မလာသေးသော ပါဠိစာမျက်နှာ: %s — ထည့်ဖိုင်ကို မဖျက်' % ' '.join(map(str, sorted(want - set(d)))))
        got += 1
    return got


def export_book(n):
    d = load_translations(n)
    p = os.path.join(GOLD, 'tr_%03d.txt' % n)
    open(p, 'w', encoding='utf-8').write((NL * 2).join('--- ပါဠိစာမျက်နှာ %d ---' % k + NL + d[k] for k in sorted(d)))
    return p, len(d)
