# -*- coding: utf-8 -*-
"""Check what Gemini returned (pages marked '--- နိဿယ စာမျက်နှာ N ---') against the page text we have.
    python nissaya_multi/scripts/m_gcheck.py <sheet n> <file with Gemini's answer | clipboard>
Per page the words are compared (၊ ။ are counted only):
    pali OK   one word replaced by a similar Pali lexicon word (the old one is not a lexicon word)        -> goes into the SAFE column
    check     one word replaced by something else (spelling of Burmese, other word)                       -> look at it
    extra     words Gemini ADDED  (the 'a little extra' you remove by hand)                               -> look at it
    missing   words Gemini LEFT OUT                                                                       -> look at it
The pasted pages are collected in gold/gemini/NNN_collected.json (no report files); gemini_log.json notes when/what ('unchecked' until you have checked it), so it can be re-checked later.
final() writes the ONE file output/final.xlsx and the viewer shows the collected pages (green 'Gemini ✔')."""
import sys, os, re, json, difflib, html, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(ROOT))
import m_fix
W = re.compile('[က-အဣ-ဿ၌၍၏]+')
MARK = re.compile('^[-\\s]*(?:နိဿယ)?\\s*စာမျက်နှာ[\\s-]*([0-9၀-၉]+)[\\s-]*$', re.M)
BD = str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789')


def split_pages(text):
    parts = {}; ms = list(MARK.finditer(text))
    for i, m in enumerate(ms):
        parts[int(m.group(1).translate(BD))] = text[m.end():ms[i + 1].start() if i + 1 < len(ms) else len(text)].strip()
    return parts


def compare(base, new, freq, vocab=()):
    """returns (changes, safe_text, punctuation delta)"""
    tb = [(m.start(), m.end(), m.group()) for m in W.finditer(base)]; tn = [m.group() for m in W.finditer(new)]
    sm = difflib.SequenceMatcher(None, [t[2] for t in tb], tn, autojunk=False)
    ch = []; safe = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        old = ' '.join(t[2] for t in tb[i1:i2]); nw = ' '.join(tn[j1:j2])
        a = tb[i1][0] if i1 < len(tb) else len(base)
        b = tb[i2 - 1][1] if i2 > i1 else a
        ctx = base[max(0, a - 18):b + 18].replace('\n', ' ')
        if tag == 'replace' and i2 - i1 == j2 - j1:
            for k in range(i2 - i1):
                o, n = tb[i1 + k], tn[j1 + k]
                r = difflib.SequenceMatcher(None, o[2], n).ratio()
                if freq.get(n, 0) >= 3 and freq.get(o[2], 0) < 3 and r >= 0.6 and abs(len(o[2]) - len(n)) <= 3:
                    ch.append(('pali OK', o[2], n, ctx, n in vocab)); safe.append((o[0], o[1], n))
                else: ch.append(('check', o[2], n, ctx, False))
        elif tag == 'delete': ch.append(('missing', old, '', ctx, False))
        elif tag == 'insert': ch.append(('extra', '', nw, ctx, False))
        else:
            ch.append(('missing', old, '', ctx, False)); ch.append(('extra', '', nw, ctx, False))
    out = base
    for s, e, n in sorted(safe, reverse=True): out = out[:s] + n + out[e:]
    pd = len(re.findall('[၊။]', new)) - len(re.findall('[၊။]', base))
    return ch, out, pd


_PW = re.compile('([က-အဣ-ဿ၌၍၏]+)([ \t]*)([၊။]?)')


def restore_punct(base, gem):
    """Gemini puts ။ after a meaning (and drops some ၊) as its prompt says, but books written 'ပါဠိ-အနက်၊' (hyphen style) separate the units with ၊.
    For the words that are the same in the sheet page (base) and in Gemini's page:
      - inside a hyphen unit (the text since the last ၊ ။ line-break contains a '-'): the mark the SHEET has wins (၊ or ။) when it differs from Gemini's
      - anywhere: a ၊ that the sheet has and Gemini dropped is put back
    A word that has no mark in the sheet is never touched (Gemini's marks stay).  returns (new text, number of marks changed)"""
    A = [(m.group(1), m.group(3)) for m in _PW.finditer(base)]
    Bm = list(_PW.finditer(gem))
    sm = difflib.SequenceMatcher(None, [a for a, _ in A], [m.group(1) for m in Bm], autojunk=False)
    edits = []
    for a, b, n in sm.get_matching_blocks():
        for i in range(n):
            s_, m = A[a + i][1], Bm[b + i]
            g_ = m.group(3)
            if not s_ or s_ == g_: continue
            seg_start = max(gem.rfind(chr(10), 0, m.start()), gem.rfind('၊', 0, m.start()), gem.rfind('။', 0, m.start())) + 1
            hy = '-' in gem[seg_start:m.end(1)]
            if hy or (s_ == '၊' and not g_):
                edits.append((m, s_))
    out = gem
    for m, mark in sorted(edits, key=lambda x: -x[0].start()):
        if m.group(3): out = out[:m.start(3)] + mark + out[m.end(3):]
        else: out = out[:m.end(1)] + mark + out[m.end(1):]
    return out, len(edits)


def run(n, text, log=print):
    import openpyxl
    freq, _ = m_fix.lexicon()
    P = json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8'))
    pages = {p['num']: p for p in P['pages'] if p.get('num') is not None}
    vocab = set()
    for b in P['blocks']: vocab.update(W.findall(b['pali']))
    got = split_pages(text)
    if not got: raise SystemExit("no '--- နိဿယ စာမျက်နှာ N ---' markers found in Gemini's answer")
    logp = os.path.join(ROOT, 'gemini_log.json'); L = json.load(open(logp, encoding='utf-8')) if os.path.exists(logp) else {}
    stamp = time.strftime('%Y-%m-%d %H:%M'); cp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    C = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else {}
    before = set(C)
    for p in sorted(got):
        if p not in pages: log('page %d is not in this book - skipped' % p); continue
        base = pages[p]['body'] + (chr(10) + pages[p]['foot'] if pages[p].get('foot') else '')
        ch, _safe, pd = compare(base, got[p], freq, vocab)
        cnt = {}
        for c in ch: cnt[c[0]] = cnt.get(c[0], 0) + 1
        C[str(p)] = got[p]                                                   # a page pasted again replaces the older answer
        L.setdefault(str(n), {})[str(p)] = {'when': stamp, 'status': 'unchecked', 'changes': cnt}
        log('  page %d collected  (%s)' % (p, ', '.join('%s %d' % kv for kv in cnt.items()) or 'no word changes'))
    json.dump(C, open(cp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(L, open(logp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log('✔ %d pages collected in total for this book' % len(C))
    new_pages = sorted(p_ for p_ in got if p_ in pages and str(p_) not in before)
    log('  ➕ ဤစာမှ အသစ်ထည့်သော စာမျက်နှာ: %s (%d ခု)%s' % (_ranges(new_pages), len(new_pages), '' if new_pages else '  ← အသစ်မပါ! (အရင်ထည့်ပြီးသားစာကိုပဲ ပြန်ထည့်မိတာလား ကြည့်ပါ)'))
    cleanup_done(n, C, log, touched=set(got))
    return len(C)


def _pages_of(name, n):
    t = open(os.path.join(ROOT, 'output', 'gemini', name), encoding='utf-8').read()
    return [int(x) for x in re.findall(r'--- နိဿယ စာမျက်နှာ (\d+) ---', t)]


def _ranges(ps):
    out = []; a = b = None
    for x in list(ps) + [None]:
        if x is not None and b is not None and x == b + 1: b = x; continue
        if a is not None: out.append(str(a) if a == b else '%d-%d' % (a, b))
        a = b = x
    return ', '.join(out) or '-'


def _tokens(t): return set(re.findall('[က-အဣ-ဿ]+', t or ''))


def _fit(text, base):
    """how much of the pasted page is made of words of the sheet page (0..1): the same book gives 0.25-0.7, another book about 0.02-0.1"""
    a = _tokens(text)
    return len(a & _tokens(base)) / max(1, len(a))


def preview(n, text):
    """BEFORE anything is saved: which pages the pasted text holds, how many of them already exist (they would be REPLACED) and whether the pages fit THIS book.
    returns {'pages': [...], 'replace': [...], 'fit': mean fit, 'bad': [pages that do not fit], 'other': (sheet n, fit) of another book that fits much better, or None}"""
    got = split_pages(text)
    rows = {r['num']: r.get('text') for r in json.load(open(os.path.join(ROOT, 'sheets', '%03d.json' % n), encoding='utf-8'))['rows'] if r.get('num') is not None}
    cp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
    have = {int(k) for k in json.load(open(cp, encoding='utf-8'))} if os.path.exists(cp) else set()
    fits = {k: _fit(v, rows.get(k)) for k, v in got.items() if k in rows}
    mean = sum(fits.values()) / max(1, len(fits))
    bad = sorted(k for k, f in fits.items() if f < 0.15)
    other = None
    if fits and mean < 0.2:                                           # does another book that is being worked on fit better?
        import glob
        for f in glob.glob(os.path.join(ROOT, 'gold', 'gemini', '*_collected.json')) + glob.glob(os.path.join(ROOT, 'output', 'gemini', '*.txt')):
            m = int(os.path.basename(f)[:3])
            if m == n or not os.path.exists(os.path.join(ROOT, 'sheets', '%03d.json' % m)): continue
            r2 = {r['num']: r.get('text') for r in json.load(open(os.path.join(ROOT, 'sheets', '%03d.json' % m), encoding='utf-8'))['rows'] if r.get('num') is not None}
            f2 = sum(_fit(v, r2.get(k)) for k, v in got.items() if k in r2) / max(1, len(got))
            if f2 > mean + 0.15 and (other is None or f2 > other[1]): other = (m, f2)
    return {'pages': sorted(got), 'replace': sorted(k for k in got if k in have), 'fit': mean, 'bad': bad, 'other': other}


def cleanup_done(n, C, log=print, touched=None):
    """output/gemini/NNN_*.txt files (the files made for the Gemini app): a file whose nissaya pages are ALL in the collected answers is finished - it is deleted, so the folder only shows
    what is still to do.  A file with one page missing stays (the log says which page)."""
    import glob
    have = {int(k) for k in C}
    done = []; todo = []; empty_all = set(); rest_made = []; nl_ = chr(10)
    for f in sorted(glob.glob(os.path.join(ROOT, 'output', 'gemini', '%03d_*.txt' % n))):
        t = open(f, encoding='utf-8').read()
        parts_ = re.split('--- နိဿယ စာမျက်နှာ (\\d+) ---', t)                  # [before, num, text, num, text ...]
        pages_ = [int(parts_[k]) for k in range(1, len(parts_), 2) if re.sub(r'=+|အစု[^\n]*|\s', '', parts_[k + 1])]      # a page with NO text in the file (only junk was on it) has nothing to check: it is not waited for
        empty_all.update(int(parts_[k]) for k in range(1, len(parts_), 2) if int(parts_[k]) not in pages_)       # pages with no text from the start (only junk on them)
        miss = [k for k in pages_ if k not in have]
        if pages_ and not miss:
            os.remove(f); done.append(os.path.basename(f))
        elif pages_ and len(miss) < len(pages_):                       # Gemini answered SOME pages of this file and skipped the rest: the file is replaced by a '_rest' file with only the pages still missing
            j_ = t.find('===== နိဿယ =====')
            if j_ < 0: todo.append((os.path.basename(f), miss)); continue
            body = ''.join('--- နိဿယ စာမျက်နှာ %d ---%s%s' % (int(parts_[k]), nl_, parts_[k + 1].rstrip() + nl_ * 2) for k in range(1, len(parts_), 2) if int(parts_[k]) in miss)
            stem = re.sub(r'(_rest)+$', '', os.path.basename(f)[:-4]); nf = os.path.join(os.path.dirname(f), stem + '_rest.txt')
            open(nf, 'w', encoding='utf-8').write(t[:j_] + '===== နိဿယ =====' + nl_ + body)
            if os.path.abspath(nf) != os.path.abspath(f): os.remove(f)
            rest_made.append((os.path.basename(nf), miss)); todo.append((os.path.basename(nf), miss))
        else: todo.append((os.path.basename(f), miss))
    if empty_all:                                                       # remembered: these pages have no text in the sheet (nothing to check, nothing is waited for)
        ep = os.path.join(ROOT, 'gold', 'gemini', '%03d_empty.json' % n)
        old_ = set(json.load(open(ep, encoding='utf-8'))) if os.path.exists(ep) else set()
        json.dump(sorted(old_ | empty_all), open(ep, 'w'))
        log('  ○ မူရင်းကတည်းက စာမရှိသော စာမျက်နှာ (စစ်စရာမရှိ၊ စောင့်စရာမလို): %s' % ' '.join(map(str, sorted(empty_all))))
    for nm_, ms_ in rest_made: log('  ➜ Gemini က မစစ်ဘဲ ကျန်ခဲ့သော စာမျက်နှာများ (%s) ကို ဖိုင်အသစ် ထုတ်ပေးပြီး: %s  — ဒါကို Gemini ကို ပေးပါ' % (' '.join(map(str, ms_)), nm_))
    if done: log('  ✔ ပြီးသွားသော ဖိုင် ဖျက်ပြီး (%d): %s' % (len(done), ', '.join(done)))
    waiting = [t for t in todo if touched is None or not t[1] or len(t[1]) < 1 or any(k in touched for k in _pages_of(t[0], n))]
    if touched is not None: log('  ○ စောင့်နေသော ဖိုင် စုစုပေါင်း %d ခု' % len(todo))
    for name, miss in (todo if touched is None else waiting): log('  ○ မပြီးသေး: %s%s' % (name, ('  (မပါသေးသော စာမျက်နှာ: %s)' % ' '.join(map(str, miss[:12])) + (' ...' if len(miss) > 12 else '')) if miss and len(miss) < 60 else ''))


DOWNLOADS = os.path.join(os.path.expanduser('~'), 'Downloads')
_CHECKED = re.compile(r'^(\d{3})_.+_checked(?: \(\d+\))?\.txt$')
_ingest_seen = set()


def ingest_downloads(log=print, after=None):
    """The Gemini Canvas app downloads <NNN_..._pali..>_checked.txt into Downloads when every set of an uploaded file is checked.  Each such file is collected into its book (the number
    in the file name) exactly like the manual step 4, the finished input file in output/gemini is deleted by cleanup_done, and the downloaded file moves to gold/gemini/received/.
    A file that does not fit its book (another book fits much better) or has no page markers is left where it is and reported once."""
    import glob, shutil
    got_any = 0
    for f in sorted(glob.glob(os.path.join(DOWNLOADS, '*_checked*.txt'))):
        name = os.path.basename(f); m = _CHECKED.match(name)
        if not m: continue
        try:
            if time.time() - os.path.getmtime(f) < 3: continue                      # still being written
            key = (f, os.path.getmtime(f))
            if key in _ingest_seen: continue
            n = int(m.group(1))
            if not os.path.exists(os.path.join(ROOT, 'paired', '%03d.json' % n)) or not os.path.exists(os.path.join(ROOT, 'sheets', '%03d.json' % n)):
                _ingest_seen.add(key); continue
            text = open(f, encoding='utf-8-sig').read()
            pv = preview(n, text)
            if not pv['pages']:
                _ingest_seen.add(key); log("⚠ Downloads/%s — '--- နိဿယ စာမျက်နှာ N ---' စာကြောင်း မတွေ့ပါ၊ မထည့်ပါ" % name); continue
            if pv['other']:
                _ingest_seen.add(key); log('⛔ Downloads/%s — စာအုပ် %03d နှင့် မကိုက်ပါ (စာအုပ် %d နှင့် ပိုကိုက်သည်)၊ မထည့်ပါ' % (name, n, pv['other'][0])); continue
            log('⬇ Downloads/%s တွေ့သည် — စာအုပ် %03d ထဲ အလိုအလျောက် ထည့်နေသည် (စာမျက်နှာ %s)%s' % (name, n, _ranges(pv['pages']), ('  ⚠ အစားထိုးမည့် ' + _ranges(pv['replace'])) if pv['replace'] else ''))
            run(n, text, log)
            dest_dir = os.path.join(ROOT, 'gold', 'gemini', 'received'); os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, time.strftime('%Y%m%d_%H%M%S_') + name)
            shutil.move(f, dest); log('  ✔ ဖိုင်ကို gold/gemini/received/ ထဲ ရွှေ့ပြီး')
            got_any += 1
            if after:
                try: after(n)
                except BaseException as e: log('⚠ after-step (web တင်) အမှား: %s' % e)
        except BaseException as e:
            _ingest_seen.add((f, os.path.getmtime(f))); log('⚠ Downloads/%s မထည့်နိုင်ပါ: %r' % (name, e))
    return got_any


def final(n=None, log=print):
    """THE file for Google Sheets: output/final.xlsx - one worksheet per book (named like the Google Sheet tab), every collected Gemini page in it.
    columns: A page label as in the sheet | B text now in the sheet | C Gemini text (copy this column) | D what changed.  It is rewritten every time (always ONE file)."""
    import openpyxl, glob
    cat = {r['n']: r for r in json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8'))}
    freq, _ = m_fix.lexicon(); wb = openpyxl.Workbook(); wb.remove(wb.active); total = 0; gaps = []; nogem = 0
    for cp in sorted(glob.glob(os.path.join(ROOT, 'gold', 'gemini', '*_collected.json'))):
        k = int(os.path.basename(cp)[:3]); C = {int(a): b for a, b in json.load(open(cp, encoding='utf-8')).items()}
        if not C: continue
        rows = {r['num']: r for r in json.load(open(os.path.join(ROOT, 'sheets', '%03d.json' % k), encoding='utf-8'))['rows'] if r.get('num') is not None}
        gaps.append((cat[k]['sheet'], [p_ for p_ in sorted(rows) if p_ not in C]))
        ws = wb.create_sheet(re.sub(r'[\/*?:\[\]]', '_', cat[k]['sheet'])[:31]); ws.title = ws.title
        ws.append(['စာမျက်နှာ', 'ယခု sheet ထဲက စာသား', 'Gemini စစ်ပြီးစာသား (ဒီကော်လံကို ကူးသုံးပါ)', 'ပြင်ချက်'])
        for p in sorted(rows):
            if rows[p]['text'] is None: continue                          # an empty page of the sheet
            if p in C:
                ch, _s, pd = compare(rows[p]['text'] or '', C[p], freq)
                cnt = {}
                for c in ch: cnt[c[0]] = cnt.get(c[0], 0) + 1
                ws.append([rows[p]['label'], rows[p]['text'], C[p], ', '.join('%s %d' % kv for kv in cnt.items())]); total += 1
            else:                                                         # no Gemini answer for this page: the text that is in the sheet now (column C = column B, nothing changes)
                ws.append([rows[p]['label'], rows[p]['text'], rows[p]['text'], 'Gemini မစစ်ထား - sheet ထဲက စာအတိုင်း']); nogem += 1
        for col, wd in zip('ABCD', (16, 60, 60, 36)): ws.column_dimensions[col].width = wd
    if not wb.sheetnames: raise SystemExit('nothing collected yet - paste Gemini answers first')
    def ranges(ps):
        out = []; a = b = None
        for x in ps + [None]:
            if x is not None and b is not None and x == b + 1: b = x; continue
            if a is not None: out.append(str(a) if a == b else '%d-%d' % (a, b))
            a = b = x
        return ', '.join(out)
    gs = wb.create_sheet('မပါသော စာမျက်နှာ')                            # the pages of the sheet that are NOT in this file (never sent to / returned by Gemini)
    gs.append(['စာအုပ်', 'ဤဖိုင်ထဲ မပါသော နိဿယစာမျက်နှာ', 'အရေအတွက်']); gs.column_dimensions['A'].width = 22; gs.column_dimensions['B'].width = 70
    for name, ps in gaps:
        gs.append([name, ranges(ps) or '-', len(ps)])
        if ps: log('  မပါသော စာမျက်နှာ (%s): %s' % (name, ranges(ps)))
    path = os.path.join(ROOT, 'output', 'final.xlsx'); os.makedirs(os.path.dirname(path), exist_ok=True); wb.save(path)
    log('final.xlsx: Gemini စာမျက်နှာ %d + sheet စာအတိုင်း (Gemini မစစ်ထား) %d -> %s' % (total, nogem, os.path.relpath(path, os.path.dirname(ROOT)))); return path


if __name__ == '__main__':
    n = int(sys.argv[1]); src = sys.argv[2] if len(sys.argv) > 2 else 'clipboard'
    if src == 'clipboard':
        import tkinter; t = tkinter.Tk(); t.withdraw(); text = t.clipboard_get(); t.destroy()
    else: text = open(src, encoding='utf-8').read()
    run(n, text)
    if len(sys.argv) > 3 and sys.argv[3] == '--final': final()


def missing_pages(n):
    """nissaya pages of the sheet that Gemini has NOT checked and that wait in no file of output/gemini (nobody has sent them yet: a gap / the end of the database map ...). Only for books that are in progress
    (some page collected, or a file waiting) - a book nobody has started is left alone."""
    import glob
    cp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
    have = {int(k) for k in json.load(open(cp, encoding='utf-8'))} if os.path.exists(cp) else set()
    ep = os.path.join(ROOT, 'gold', 'gemini', '%03d_empty.json' % n)
    empty = set(json.load(open(ep, encoding='utf-8'))) if os.path.exists(ep) else set()
    files = glob.glob(os.path.join(ROOT, 'output', 'gemini', '%03d_*.txt' % n))
    waiting = set()
    for f in files: waiting.update(_pages_of(os.path.basename(f), n))
    if not have and not files: return [], waiting
    P = json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8'))
    allp = {p['num'] for p in P['pages'] if p.get('num') is not None and (p['body'] + p.get('foot', '')).strip()}
    pm = P.get('ppmap')
    if pm:          # only the nissaya pages that belong to a Pali page are shown on the web (and used for translation); pages after the last map entry appear nowhere, so Gemini need not check them
        shown = {q for v in pm.values() for q in range(v[0], v[1] + 1)}
        allp &= shown
    return sorted(allp - have - empty - waiting), waiting


def make_missing(n, log=print):
    """files (…_gap.txt) for the pages that nobody has sent to Gemini yet.  returns the number of files made."""
    miss, waiting = missing_pages(n)
    if not miss: return 0
    log('  ○ စာအုပ် %03d: Gemini မစစ်ရသေး၊ ဖိုင်ထဲလည်း မပါသေးသော စာမျက်နှာ %d ခု (%s) — ဖိုင်အသစ် ထုတ်နေသည်...' % (n, len(miss), _ranges(miss)))
    import m_bundle
    out, files = m_bundle.main(n, 1, 10 ** 6, 2, False, False, log, sets=10, nsy=7, maxchars=10000, exclude=waiting, suffix='_gap')
    if files: log('  ➜ ဖိုင်အသစ် %d ခု ထုတ်ပြီး (output/gemini): %s — Gemini app ထဲ တင်ပါ' % (len(files), ', '.join(files)))
    else: log('  ⚠ ဖိုင် မထွက်ပါ (စာမျက်နှာ %s သည် စာမရှိ / အမှိုက်သာ ဖြစ်နိုင်သည်)' % _ranges(miss))
    return len(files)
