# -*- coding: utf-8 -*-
"""Files for the Gemini 'Pali Translate AI' Canvas app: PER PALI PAGE  ### ပါဠိ (the Pali text)  +  ### နိဿယ (the nissaya pages of that Pali page, the CHECKED text that Gemini returned
and m_gcheck collected into gold/gemini/NNN_collected.json).  Many sets in one file, one set = Pali pages until `maxchars` characters.
    build(n, lo, hi, ...)    -> output/tr_NNN_<book>_pali<a>-<b>.txt        (run from the button tool t_gui.pyw)
    ingest_downloads()       -> takes  tr_*_translated.txt  from Downloads into gold/tr_NNN.json  {Pali page: Burmese text}, moves the file to received/, deletes the finished input file
    export_book(n)           -> gold/tr_NNN.txt  every translated Pali page in order
A nissaya page that Gemini has not checked yet is NOT used (the Pali page is left out and listed) unless raw_ok=True (then the cleaned OCR text is used and the page is marked)."""
import glob, json, os, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); NSY = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(NSY, 'scripts'))
OUT = os.path.join(HERE, 'output'); GOLD = os.path.join(HERE, 'gold'); RECV = os.path.join(GOLD, 'received')
DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')
NL = chr(10)
HEAD_CLS = {'nikaya', 'book', 'chapter', 'subhead', 'subsubhead', 'title', 'centered', 'center_bold', 'center', 'ending'}      # Pali block classes that are headings


def _paired(n): return json.load(open(os.path.join(NSY, 'paired', '%03d.json' % n), encoding='utf-8'))


def _collected(n):
    p = os.path.join(NSY, 'gold', 'gemini', '%03d_collected.json' % n)
    return {int(k): v for k, v in json.load(open(p, encoding='utf-8')).items()} if os.path.exists(p) else {}


def build(n, lo, hi, maxchars=10000, sets=10, raw_ok=False, log=print, redo=False, only=None, rest=False, extra_pali=None):
    """redo=False: Pali pages that Gemini has already translated (gold/tr_NNN.json) are left out;  only={Pali pages}: just these;  rest=True: the 'rest' file of a half-finished input (old files of the book are NOT deleted)"""
    P = _paired(n); col = _collected(n)
    pages = {p['num']: p for p in P['pages'] if p.get('num') is not None}
    blocks = {}
    for b in P['blocks']: blocks.setdefault((b['book'], b['page']), []).append(b)
    keys = sorted(((k.split('|')[0], int(k.split('|')[1])) for k in P['ppmap']), key=lambda x: (x[0], x[1]))
    keys = [g for g in keys if lo <= g[1] <= hi]
    if only is not None: keys = [g for g in keys if g[1] in only]
    elif not redo:
        done = load_translations(n); skip = [g[1] for g in keys if g[1] in done]
        keys = [g for g in keys if g[1] not in done]
        if skip: log('  မြန်မာပြန်ပြီးသား ပါဠိ %d မျက်နှာ ချန်ထားသည်' % len(skip))
    mapped = {int(k.split('|')[1]) for k in P['ppmap']}
    if extra_pali:                # Pali pages WITHOUT a nissaya page (not in the page map, e.g. the last Pali page of a book): only when asked for - translated from the Pali alone
        bk0 = sorted({k.split('|')[0] for k in P['ppmap']})[0]
        for p in sorted(extra_pali):
            if p in mapped: log('  ပါဠိ %d က နိဿယနှင့် တွဲထားပြီးသား (ပုံမှန်နည်းဖြင့် ထုတ်ပါ)' % p)
            elif (bk0, p) not in blocks: log('  ပါဠိ %d ဤစာအုပ်ထဲ မတွေ့ပါ' % p)
            elif (bk0, p) not in keys: keys.append((bk0, p))
        keys.sort(key=lambda x: (x[0], x[1]))
    if len({g[0] for g in keys}) > 1: log('⚠ ဤအကွာအဝေးတွင် ပါဠိစာအုပ် တစ်အုပ်ထက်ပို ပါသည် — ပထမစာအုပ်သာ ယူပါ (အကွာအဝေး ကျဉ်းပါ)')
    built = []; left_out = []; raw_used = set()
    for g in keys:
        r0, r1 = P['ppmap'].get('%s|%s' % g) or (None, None)
        nums = [] if r0 is None else [k for k in range(r0, r1 + 1) if k in pages]
        texts = []; missing = []
        for k in nums:
            if k in col: texts.append('[နိဿယ မျက်နှာ %d]' % k + NL + col[k].strip())
            elif raw_ok: texts.append('[နိဿယ မျက်နှာ %d (Gemini မစစ်ရသေး)]' % k + NL + (pages[k]['body'] + (NL + pages[k]['foot'] if pages[k].get('foot') else '')).strip()); raw_used.add(k)
            else: missing.append(k)
        if missing: left_out.append((g[1], missing)); continue
        pali = NL.join(('## ' if (b.get('cls') or '').strip() in HEAD_CLS else '') + b['pali'] for b in sorted(blocks.get(g, []), key=lambda b: b['i']))      # headings (title, chapter ...) are marked '## ' so Gemini keeps them as separate heading lines
        if not pali.strip(): left_out.append((g[1], ['ပါဠိစာ မရှိ'])); continue
        built.append((g, '--- စာမျက်နှာ %d ---' % g[1] + NL + '### ပါဠိ' + NL + pali + NL + '### နိဿယ' + NL + ((NL * 2).join(texts) if texts else '(နိဿယ မရှိ — ပါဠိမှ တိုက်ရိုက်ပြန်ပါ)') + NL))
    for pg, miss in left_out: log('  ပါဠိ %d: ထုတ်မရ — နိဿယ %s' % (pg, ' '.join(map(str, miss)) if isinstance(miss[0], int) else miss[0]) + (' မစစ်ရသေး' if isinstance(miss[0], int) else ''))
    if raw_used: log('  ⚠ Gemini မစစ်ရသေးသော နိဿယစာမျက်နှာ %d ခု OCR စာဖြင့် ထည့်ထားသည်' % len(raw_used))
    groups = []; cur = []; size = 0
    for g, t in built:
        if cur and size + len(t) > maxchars: groups.append(cur); cur = []; size = 0
        cur.append((g, t)); size += len(t)
    if cur: groups.append(cur)
    os.makedirs(OUT, exist_ok=True); files = []
    for old in ([] if rest else glob.glob(os.path.join(OUT, 'tr_%03d_*.txt' % n))):               # the earlier input files of THIS book are deleted first (so old and new are never mixed up)
        os.remove(old); log('  🗑 ဖိုင်အဟောင်း ဖျက်ပြီး: ' + os.path.basename(old))
    for j in range(0, len(groups), sets):
        chunk = groups[j:j + sets]
        first, last = chunk[0][0][0], chunk[-1][-1][0]
        name = 'tr_%03d_%s_pali%d-%d%s.txt' % (n, first[0], first[1], last[1], '_rest' if rest else '')
        body = NL.join('===== အစု %d / %d =====' % (k + 1, len(chunk)) + NL + NL.join(t for g, t in s) for k, s in enumerate(chunk))
        open(os.path.join(OUT, name), 'w', encoding='utf-8').write(body)
        files.append(name); log('  %s : %d sets (ပါဠိ %d-%d), %d characters' % (name, len(chunk), first[1], last[1], len(body)))
    log('%d ဖိုင်၊ ပါဠိ %d မျက်နှာ -> %s' % (len(files), len(built), OUT))
    return OUT, files


LANGS = {'vi': 'ဗီယက်နမ်', 'en': 'အင်္ဂလိပ်'}


def build_lang(n, lang, maxchars=10000, sets=10, log=print, redo=False, only=None, rest=False):
    """Vietnamese / English input files: every Pali page that HAS a Burmese translation (gold/tr_NNN.json) -> '### ပါဠိ' (the Pali text, to look at when the Burmese is unclear) + '### မြန်မာပြန်'
    (the text to translate).  Pages already translated into the language (gold/tr_NNN_<lang>.json) are left out unless redo.  -> output/tr_NNN_<book>_pali<a>-<b>_for<lang>.txt
    (the Canvas app's answer comes back as ..._for<lang>_<lang>.txt and is ingested by ingest_downloads)"""
    P = _paired(n); my = load_translations(n)
    if not my: raise RuntimeError('စာအုပ် %03d: မြန်မာပြန် မရှိသေးပါ' % n)
    done = {} if redo else load_translations(n, lang)
    keyset = {(k.split('|')[0], int(k.split('|')[1])) for k in P['ppmap']}
    books = sorted({b for b, p in keyset}); blocks = {}
    for b in P['blocks']: blocks.setdefault((b['book'], b['page']), []).append(b)
    have = [p for p in my if my[p].strip() and (only is None or p in only)]
    pages = sorted(p for p in have if p not in done)
    if len(pages) < len(have): log('  %sပြီးသား ပါဠိ %d မျက်နှာ ချန်ထားသည်' % (LANGS[lang], len(have) - len(pages)))
    built = []
    for pg in pages:
        owners = [b for b in books if (b, pg) in blocks] or books[:1]
        bk = owners[0]; bl = sorted(blocks.get((bk, pg), []), key=lambda b: b['i'])
        pali = NL.join(('## ' if (b.get('cls') or '').strip() in HEAD_CLS else '') + b['pali'] for b in bl)
        built.append(((bk, pg), '--- စာမျက်နှာ %d ---' % pg + NL + '### ပါဠိ' + NL + (pali.strip() or '(ပါဠိစာ မတွေ့)') + NL + '### မြန်မာပြန်' + NL + my[pg].strip() + NL))
    groups = []; cur = []; size = 0
    for g, t in built:
        if cur and size + len(t) > maxchars: groups.append(cur); cur = []; size = 0
        cur.append((g, t)); size += len(t)
    if cur: groups.append(cur)
    os.makedirs(OUT, exist_ok=True); files = []
    for old in ([] if rest else glob.glob(os.path.join(OUT, 'tr_%03d_*_for%s.txt' % (n, lang)))): os.remove(old); log('  🗑 ဖိုင်အဟောင်း ဖျက်ပြီး: ' + os.path.basename(old))          # the _rest file of a half-finished input does not delete the old files
    for j in range(0, len(groups), sets):
        chunk = groups[j:j + sets]; first, last = chunk[0][0][0], chunk[-1][-1][0]
        name = 'tr_%03d_%s_pali%d-%d%s_for%s.txt' % (n, first[0], first[1], last[1], '_rest' if rest else '', lang)
        body = NL.join('===== အစု %d / %d =====' % (k + 1, len(chunk)) + NL + NL.join(t for g, t in s_) for k, s_ in enumerate(chunk))
        open(os.path.join(OUT, name), 'w', encoding='utf-8').write(body)
        files.append(name); log('  %s : %d sets (ပါဠိ %d-%d), %d characters' % (name, len(chunk), first[1], last[1], len(body)))
    log('%d ဖိုင်၊ %sပြန်ရန် ပါဠိ/မြန်မာပြန် %d မျက်နှာ -> %s' % (len(files), LANGS[lang], len(built), OUT))
    return OUT, files


_PAGE = re.compile(r'^---\s*စာမျက်နှာ\s*([0-9၀-၉]+)\s*---\s*$', re.M)
_DIG = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')


def parse_pages(text):
    ms = list(_PAGE.finditer(text)); out = {}
    for i, m in enumerate(ms):
        out[int(m.group(1).translate(_DIG))] = text[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(text)].strip()
    return out


def load_translations(n, lang=''):
    p = os.path.join(GOLD, 'tr_%03d%s.json' % (n, ('_' + lang) if lang else ''))
    return {int(k): v for k, v in json.load(open(p, encoding='utf-8')).items()} if os.path.exists(p) else {}


def save_translations(n, d, lang=''):
    os.makedirs(GOLD, exist_ok=True)
    json.dump({str(k): d[k] for k in sorted(d)}, open(os.path.join(GOLD, 'tr_%03d%s.json' % (n, ('_' + lang) if lang else '')), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def _heads(text):
    """number of '## ' heading lines of each page of a Gemini file: {page: count}"""
    return {k: sum(1 for l in v.split(NL) if l.strip().startswith('## ')) for k, v in parse_pages(text).items()}


_NAME = re.compile(r'tr_(DD+)_(.+?)_pali(DD+)-(DD+)(?:_rest)?(?:_translated(?:_(vi|en))?|_for(?:vi|en)_(vi|en))(?: [(]DD+[)])?[.]txt$'.replace('DD', chr(92) + 'd'))


def mostly_burmese(v):
    """a Vietnamese / English answer that is still (mostly) Burmese script = Gemini gave the Burmese back, nothing was translated"""
    t = ''.join(v.split()); return bool(t) and sum(1 for c in t if 'က' <= c <= '႟') > 0.3 * len(t)


def burmese_share(v):
    t = ''.join(v.split()); return (sum(1 for c in t if 'က' <= c <= '႟') / len(t)) if t else 0.0


def check_lang_page(out_txt, src_burmese=None):
    """why a Vietnamese / English answer of ONE page cannot be taken (None = fine).  src_burmese = the Burmese translation that was sent (when the input file is still there)."""
    t = out_txt.strip()
    if not t: return 'ဗလာ'
    bs = burmese_share(t)
    if bs > 0.30: return 'မြန်မာစာကိုပဲ ပြန်ပေးသည် (%d%%)' % (bs * 100)
    if bs > 0.04: return 'ဘာသာမပြန်ရသေးသော မြန်မာစာ ကျန်နေသည် (%d%%)' % (bs * 100)
    if src_burmese:
        a, b = len(''.join(t.split())), len(''.join(src_burmese.split()))
        if b > 400 and a < 0.25 * b: return 'အတိုချုံ့ / ဖြတ်ထားသည် (ပို့ %d လုံး၊ ပြန် %d လုံး)' % (b, a)
        if b > 100 and a > 5 * b: return 'ပြန်လာတာ အလွန်ရှည်နေသည် (ပို့ %d လုံး၊ ပြန် %d လုံး)' % (b, a)
        hs, ho = sum(1 for l in src_burmese.split(NL) if l.strip().startswith('## ')), sum(1 for l in t.split(NL) if l.strip().startswith('## '))
        if hs != ho: return 'ခေါင်းစဉ် ("## ") အရေအတွက် မကိုက် (ပို့ %d / ပြန် %d)' % (hs, ho)
    return None


def check_my_page(out_txt, pali=None):
    """why a Burmese translation (from the Pali) of ONE page cannot be taken (None = fine)"""
    t = out_txt.strip()
    if not t: return 'ဗလာ'
    bs = burmese_share(t)
    if bs < 0.5: return 'မြန်မာစာ မဟုတ်သလောက် (မြန်မာအက္ခရာ %d%%)' % (bs * 100)
    if pali:
        a, b = len(''.join(t.split())), len(''.join(pali.split()))
        if b > 400 and a < 0.3 * b: return 'အတိုချုံ့ / ဖြတ်ထားသည် (ပါဠိ %d လုံး၊ ပြန် %d လုံး)' % (b, a)
    return None


def _rejects(n, lang):
    p = os.path.join(GOLD, 'tr_%03d_%s_rejects.json' % (n, lang))
    return p, (json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {})


def ingest_downloads(log=print, after=None, after_lang=None):
    got = 0
    for f in sorted(glob.glob(os.path.join(DOWNLOADS, 'tr_*_translated*.txt')) + glob.glob(os.path.join(DOWNLOADS, 'tr_*_for??_??*.txt'))):
        name = os.path.basename(f); m = _NAME.match(name)
        if not m or time.time() - os.path.getmtime(f) < 3: continue
        n = int(m.group(1)); lang = m.group(5) or m.group(6) or ''
        pg = parse_pages(open(f, encoding='utf-8-sig').read())
        if not pg: log('⚠ Downloads/%s — "--- စာမျက်နှာ N ---" မတွေ့ပါ' % name); continue
        if lang:             # every page is checked: nothing Burmese, not cut short, headings kept.  A page that fails is NOT stored - it is sent again (the _rest file); after 3 failures of a page that is not Burmese-only it is stored and marked
            inp0 = os.path.join(OUT, re.sub('_' + lang + r'(?: [(]\d+[)])?[.]txt$', '.txt', name)); srcs = {}
            if '_for' + lang in name and os.path.exists(inp0):
                srcs = {k: v.split('### မြန်မာပြန်', 1)[1].strip() for k, v in parse_pages(open(inp0, encoding='utf-8').read()).items() if '### မြန်မာပြန်' in v}
            rp, rj = _rejects(n, lang); bad = {}
            for k, v in list(pg.items()):
                why = check_lang_page(v.replace(chr(92) + 'n', NL), srcs.get(k))
                if not why: rj.pop(str(k), None); continue
                cnt = rj.get(str(k), 0) + 1
                if cnt >= 3 and burmese_share(v) <= 0.30 and v.strip(): log('  ⚠ ပါဠိမျက်နှာ %d: %s — ၃ ကြိမ်ပြန်ထုတ်ပြီးသော်လည်း ထိုအတိုင်း၊ သိမ်းထားသည် (ကိုယ်တိုင် စစ်ကြည့်ပါ)' % (k, why)); rj.pop(str(k), None); continue
                bad[k] = why; rj[str(k)] = cnt
            if rj or os.path.exists(rp):
                os.makedirs(GOLD, exist_ok=True); json.dump(rj, open(rp, 'w', encoding='utf-8'))
            if bad:
                for k, why in sorted(bad.items()): log('  ⚠ ပါဠိမျက်နှာ %d — %s: မသိမ်းပါ၊ ထပ်ထုတ်မည်' % (k, why))
                pg = {k: v for k, v in pg.items() if k not in bad}
        if not lang:         # Burmese from the Pali: the same care - empty / not Burmese / cut short pages are not stored but sent again (after 3 failures stored and marked)
            inp0 = os.path.join(OUT, re.sub(r'_translated.*$', '.txt', name)); srcs = {}
            if os.path.exists(inp0): srcs = {k: v.split('### နိဿယ')[0].replace('### ပါဠိ', '').strip() for k, v in parse_pages(open(inp0, encoding='utf-8').read()).items()}
            rp, rj = _rejects(n, 'my'); bad = {}
            for k, v in list(pg.items()):
                why = check_my_page(v.replace(chr(92) + 'n', NL), srcs.get(k))
                if not why: rj.pop(str(k), None); continue
                cnt = rj.get(str(k), 0) + 1
                if cnt >= 3 and v.strip() and burmese_share(v) >= 0.5: log('  ⚠ ပါဠိမျက်နှာ %d: %s — ၃ ကြိမ်ပြန်ထုတ်ပြီးသော်လည်း ထိုအတိုင်း၊ သိမ်းထားသည် (ကိုယ်တိုင် စစ်ကြည့်ပါ)' % (k, why)); rj.pop(str(k), None); continue
                bad[k] = why; rj[str(k)] = cnt
            if rj or os.path.exists(rp):
                os.makedirs(GOLD, exist_ok=True); json.dump(rj, open(rp, 'w', encoding='utf-8'))
            if bad:
                for k, why in sorted(bad.items()): log('  ⚠ ပါဠိမျက်နှာ %d — %s: မသိမ်းပါ၊ ထပ်ထုတ်မည်' % (k, why))
                pg = {k: v for k, v in pg.items() if k not in bad}
        d = load_translations(n, lang); repl = [k for k in pg if k in d]
        d.update({k: v.replace(chr(92) + 'n', NL) for k, v in pg.items() if v.strip()}); save_translations(n, d, lang)          # a literal \n that Gemini wrote inside the text is a line break
        os.makedirs(RECV, exist_ok=True); shutil.move(f, os.path.join(RECV, time.strftime('%Y%m%d_%H%M%S_') + name))
        log('⬇ %s — စာအုပ် %03d ထဲ %s %d မျက်နှာ ထည့်ပြီး%s' % (name, n, {'vi': 'ဗီယက်နမ်ပြန်', 'en': 'အင်္ဂလိပ်ပြန်'}.get(lang, 'ပါဠိ'), len(pg), (' (အစားထိုး %d)' % len(repl)) if repl else ''))
        if lang:                                           # Vietnamese / English of the Burmese translation: kept in gold/tr_NNN_vi.json / _en.json
            inp = os.path.join(OUT, re.sub('_' + lang + r'(?: [(]\d+[)])?[.]txt$', '.txt', name))          # ..._forvi_vi.txt -> the input file ..._forvi.txt
            if '_for' + lang in name and os.path.exists(inp):
                want = set(parse_pages(open(inp, encoding='utf-8').read()))
                if want <= set(d): os.remove(inp); log('  ✔ ထည့်ဖိုင်ပြီးစီးသဖြင့် ဖျက်ပြီး')
                else:
                    miss = want - set(d)
                    log('  ပြန်မလာသေးသော ပါဠိစာမျက်နှာ: %s — ကျန်တာကို ဖိုင်အသစ် (_rest) အလိုအလျောက် ထုတ်မည်' % ' '.join(map(str, sorted(miss))))
                    try:
                        build_lang(n, lang, only=miss, rest=True, log=log)
                        os.remove(inp); log('  🗑 မပြည့်စုံသော ထည့်ဖိုင်အဟောင်း ဖျက်ပြီး')
                    except BaseException as e: log('  ⚠ _rest ဖိုင် မထုတ်နိုင်: %r (ထည့်ဖိုင်ကို မဖျက်)' % e)
            got += 1
            if after_lang:
                try: after_lang(n, lang)
                except BaseException as e: log('⚠ after-step (web တင်) အမှား: %r' % e)
            continue

        inp = os.path.join(OUT, re.sub(r'_translated.*$', '.txt', name))
        if os.path.exists(inp):
            src = open(inp, encoding='utf-8').read(); want = set(parse_pages(src))
            sent = {}                                      # headings ('## ' lines of the Pali part) of every page that was sent
            for k, v in parse_pages(src).items(): sent[k] = sum(1 for l in v.split('### နိဿယ')[0].split(NL) if l.strip().startswith('## '))
            back = _heads(open(os.path.join(RECV, [x for x in sorted(os.listdir(RECV)) if x.endswith(name)][-1]), encoding='utf-8-sig').read())
            bad = sorted(k for k in sent if k in back and sent[k] != back[k])
            if bad: log('  ⚠ ခေါင်းစဉ် ("## " စာကြောင်း) အရေအတွက် မကိုက်သော ပါဠိမျက်နှာ: ' + ', '.join('%d (ပို့ %d / ပြန် %d)' % (k, sent[k], back[k]) for k in bad[:12]) + ' — ခေါင်းစဉ်ကို စာပိုဒ်ထဲ ပေါင်းမိနိုင်သည်၊ ကြည့်ပါ')
            if want <= set(d): os.remove(inp); log('  ✔ ထည့်ဖိုင်ပြီးစီးသဖြင့် ဖျက်ပြီး')
            else:
                miss = want - set(d)
                log('  ပြန်မလာသေးသော ပါဠိစာမျက်နှာ: %s — ကျန်တာကို ဖိုင်အသစ် (_rest) အလိုအလျောက် ထုတ်မည်' % ' '.join(map(str, sorted(miss))))
                try:
                    build(n, 1, 10 ** 6, only=miss, rest=True, log=log, raw_ok=False)
                    os.remove(inp); log('  🗑 မပြည့်စုံသော ထည့်ဖိုင်အဟောင်း ဖျက်ပြီး')
                except BaseException as e: log('  ⚠ _rest ဖိုင် မထုတ်နိုင်: %r (ထည့်ဖိုင်ကို မဖျက်)' % e)
        got += 1
        if after:
            try: after(n)
            except BaseException as e: log('⚠ after-step (web တင်) အမှား: %r' % e)
    return got


def resume_partial(log=print):
    """input files that are HALF translated (some of their pages came back, the answer was taken before this rule existed or the tool was closed): the missing pages get a _rest file by themselves, the old input file goes.
    An input file nothing came back for yet is left alone (it waits for the Canvas app).  Done when the tool starts."""
    n_made = 0
    for f in sorted(glob.glob(os.path.join(OUT, 'tr_*_pali*-*.txt'))):
        name = os.path.basename(f)
        m = re.match(r'tr_(\d+)_(.+?)_pali(\d+)-(\d+)(_rest)?(?:_for(vi|en))?[.]txt$', name)
        if not m: continue
        n = int(m.group(1)); lang = m.group(6) or ''
        try:
            want = set(parse_pages(open(f, encoding='utf-8').read())); d = load_translations(n, lang)
            got = want & set(d)
            if not got: continue                                   # nothing back yet
            if want <= set(d): os.remove(f); log('✔ %s — ပြီးစီးပြီးသား၊ ထည့်ဖိုင် ဖျက်ပြီး' % name); continue
            miss = want - set(d)
            log('↻ %s — ပြန်လာပြီး %d / %d မျက်နှာ၊ ကျန် %d မျက်နှာကို ဖိုင်အသစ် (_rest) ထုတ်မည်' % (name, len(got), len(want), len(miss)))
            if lang: build_lang(n, lang, only=miss, rest=True, log=log)
            else: build(n, 1, 10 ** 6, only=miss, rest=True, log=log, raw_ok=False)
            os.remove(f); n_made += 1; log('  🗑 မပြည့်စုံသော ထည့်ဖိုင်အဟောင်း ဖျက်ပြီး')
        except BaseException as e: log('⚠ %s: %r' % (name, e))
    return n_made


def export_book(n):
    d = load_translations(n)
    p = os.path.join(GOLD, 'tr_%03d.txt' % n)
    open(p, 'w', encoding='utf-8').write((NL * 2).join('--- ပါဠိစာမျက်နှာ %d ---' % k + NL + d[k] for k in sorted(d)))
    return p, len(d)


REPO = os.path.dirname(NSY)
WEBDIR = os.path.join(REPO, 'data', 'nissaya_translations')


def _git(*args):
    r = subprocess.run(['git'] + list(args), cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode: raise RuntimeError('git %s: %s' % (' '.join(args), (r.stderr or r.stdout).strip()[:500]))
    return r


def lang_progress(n, lang):
    """(Pali pages with a Burmese translation, of them already translated into the language)"""
    my = {k for k, v in load_translations(n).items() if v.strip()}; return len(my), len(my & set(load_translations(n, lang)))


def is_complete(n):
    """no input file of this book is waiting for Gemini any more (every Pali page that could be sent has been translated)"""
    return not glob.glob(os.path.join(OUT, 'tr_%03d_*.txt' % n))


def publish(n, log=print, lang=''):
    """data/nissaya_translations/<book>.json {Pali page: Burmese} (merged with what is already there) + index.json (the books that have a translation) -> git commit ONLY these files + push.
    The reader (index.html) shows the 'မြန်မာ' button of a nissaya book when its id is in index.json."""
    d = load_translations(n, lang)
    if not d: raise RuntimeError('စာအုပ် %03d: %sပြန် မရှိသေးပါ' % (n, LANGS.get(lang, 'မြန်မာ')))
    WEBDIR = os.path.join(REPO, 'data', 'nissaya_translations' if not lang else 'translations_' + lang)          # vi / en: data/translations_vi/<book>.json + index.json (the reader's Tiếng Việt / English buttons)
    P = _paired(n)
    keys = {(k.split('|')[0], int(k.split('|')[1])) for k in P['ppmap']}
    books = sorted({b for b, p in keys})
    per = {b: {} for b in books}
    for pg, txt in d.items():
        owners = [b for b in books if (b, pg) in keys]
        if not owners and len(books) == 1: owners = books                # a Pali page without nissaya (translated from the Pali alone) belongs to the only Pali book of the sheet
        if len(owners) == 1: per[owners[0]][pg] = txt
        elif len(owners) > 1: log('  ⚠ ပါဠိမျက်နှာ %d က စာအုပ် %s တွင် အားလုံးပါ — ကျော်သည်' % (pg, '/'.join(owners)))
    os.makedirs(WEBDIR, exist_ok=True); paths = []
    ip = os.path.join(WEBDIR, 'index.json')
    raw_idx = json.load(open(ip, encoding='utf-8')) if os.path.exists(ip) else {}
    idx = {b: [{'file': b + '.json', 'sheet': None}] for b in raw_idx} if isinstance(raw_idx, list) else raw_idx      # index.json: {Pali book: [{file, sheet}, ...]} - one entry for each nissaya sheet that was translated ("မြန်မာ ၁", "မြန်မာ ၂" on the web); the old list form is read too
    for b, pages in per.items():
        if not pages: continue
        vs = idx.setdefault(b, [])
        v = next((x for x in vs if n in (x.get('sheets') or [x.get('sheet')])), None)
        if v is None:                                                 # an old entry (written before the sheet number was kept) whose text is the same as this sheet's translation: it IS this sheet
            for x in vs:
                if x.get('sheet') is None:
                    fo = os.path.join(WEBDIR, x['file'])
                    od = json.load(open(fo, encoding='utf-8')) if os.path.exists(fo) else {}
                    same = sum(1 for k, t in pages.items() if od.get(str(k)) == t)
                    if same >= max(1, len(pages) // 2): x['sheet'] = n; v = x; break
        if v is None:                                                 # another VOLUME of the same Pali book (its Pali pages do not overlap with this sheet's): the same file, not a second variant ("မြန်မာ ၂" is for another EDITION of the same pages)
            for x in vs:
                fo = os.path.join(WEBDIR, x['file']); od = json.load(open(fo, encoding='utf-8')) if os.path.exists(fo) else {}
                if od and not (set(int(k) for k in od) & set(pages)):
                    x['sheets'] = sorted(set((x.get('sheets') or [x.get('sheet')]) + [n]), key=lambda q: (q is None, q)); v = x; log('  %s : အတွဲအသစ် (ပါဠိစာမျက်နှာ မထပ်) - ရှိပြီးသားဖိုင်ထဲ ပေါင်းထည့်သည်' % b); break
        if v is None:
            v = {'file': (b + '.json') if not vs else '%s__%d.json' % (b, n), 'sheet': n}; vs.append(v)
            log('  %s : မြန်မာပြန် အသစ် (မူကွဲ %d) — web တွင် "မြန်မာ %d" ဟု ပေါ်မည်' % (b, len(vs), len(vs)))
        fp = os.path.join(WEBDIR, v['file'])
        old = {int(k): t for k, t in json.load(open(fp, encoding='utf-8')).items()} if os.path.exists(fp) else {}
        old.update(pages)
        json.dump({str(k): old[k] for k in sorted(old)}, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        paths.append(os.path.relpath(fp, REPO).replace(os.sep, '/')); log('  %s : မြန်မာပြန် ပါဠိ %d မျက်နှာ' % (v['file'], len(old)))
    json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False)
    paths.append(os.path.relpath(ip, REPO).replace(os.sep, '/'))
    if not _git('status', '--porcelain', '--', *paths).stdout.strip(): log('  (web ပေါ်ရှိနှင့် တူနေသည် — ပြောင်းစရာ မရှိ)'); return paths
    _git('fetch', 'origin')
    if int(_git('rev-list', '--count', 'HEAD..origin/main').stdout.strip() or 0):
        r = subprocess.run(['git', 'pull', '--rebase', '--autostash'], cwd=REPO, capture_output=True, text=True)
        if r.returncode: subprocess.run(['git', 'rebase', '--abort'], cwd=REPO); raise RuntimeError('git pull --rebase မအောင်မြင်ပါ')
    _git('add', '--', *paths)
    msg = 'Nissaya translation (%s, per Pali page): ' % {'': 'Burmese', 'vi': 'Vietnamese', 'en': 'English'}[lang] + ', '.join(sorted(b for b, p in per.items() if p)) + chr(10) * 2 + 'Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>'
    _git('commit', '-m', msg, '--', *paths)
    _git('push')
    log('✔ web သို့ တင်ပြီး (GitHub Pages ပေါ် ၁–၂ မိနစ်အတွင်း ပေါ်လာမည်)')
    return paths
