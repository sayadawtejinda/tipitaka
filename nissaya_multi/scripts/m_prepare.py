# -*- coding: utf-8 -*-
"""ONE step for a book: the blue corrections for the viewer AND the files for Gemini (both made from the same alignment, so it is done once).
    python nissaya_multi/scripts/m_prepare.py <sheet n> [--per 2] [--sets 10] [--no-pali]       (stage 1; stage 2 = m_prepare.recheck(n) / python m_prepare.py <n> --recheck)
1. fix_on.json: the whole book  ->  m_pair.py  (paired/NNN.json with the blue corrections for the viewer)
2. m_bundle: output/gemini/NNN_<book>_pali<a>-<b>.txt  (the corrections are taken from step 1)
3. files whose nissaya pages are all collected from Gemini already are deleted again (cleanup), so only what is still to do stays."""
import sys, os, re, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def prepare_viewer(n, log=print):
    """STEP A - only the viewer data: the blue corrections + the junk cleaning (paired/NNN.json).  The Gemini files are NOT made here, so the junk can be cleaned
    in the viewer first (select junk -> rebuild) and the files for Gemini are made afterwards with prepare_files."""
    fp = os.path.join(ROOT, 'fix_on.json')
    d = json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else {}
    d[str(n)] = [1, 9999]; json.dump(d, open(fp, 'w', encoding='utf-8'))
    try: os.remove(os.path.join(ROOT, 'paired', '%03d_stage1.json' % n))
    except OSError: pass
    log('viewer ပြင်ချက်များ + အမှိုက်ရှင်းမှု တွက်နေသည် (စာအုပ်တစ်အုပ်လုံး ၅ မိနစ်ခန့်)...')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'm_pair.py'), str(n)], capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if r.returncode: raise RuntimeError('m_pair failed: ' + (r.stderr or r.stdout)[-500:])
    for line in r.stdout.splitlines():
        if 'out of order' in line or 'rows out' in line: log('   ' + line.strip()[:200])
    log('✔ viewer အတွက် ပြီးပါပြီ — viewer မှာ အမှိုက်ကို ရှင်းပါ (ရွေးပြီး "🗑" ၊ ပြီးရင် "🔄 ပြန်တွဲမည်")။ အမှိုက်ရှင်းပြီးမှ "Gemini ဖိုင် ထုတ်" ကိုနှိပ်ပါ')


def junk_pending(n):
    """rules chosen in the viewer that are not in paired/NNN.json yet"""
    p = os.path.join(ROOT, 'junk', '%03d.json' % n)
    if not os.path.exists(p): return 0
    d = json.load(open(p, encoding='utf-8'))
    now = [[r['text'], r.get('zone', 'both')] for r in d.get('rules', [])]
    return sum(1 for x in now if x not in d.get('built', now)) + sum(1 for x in d.get('built', now) if x not in now)


def prepare_files(n, per=2, sets=10, nopali=False, log=print, nsy=None, maxchars=10000):
    """STEP B - the Gemini files, made from the paired data that is on disk now (so after the junk was cleaned and the book was paired again)."""
    if not os.path.exists(os.path.join(ROOT, 'paired', '%03d.json' % n)):
        raise RuntimeError('viewer ပြင်ဆင်ချက် မရှိသေးပါ — အရင် "viewer ပြင်ဆင်" ကိုနှိပ်ပါ')
    k = junk_pending(n)
    if k: raise RuntimeError('viewer မှာ ရွေးထားသော အမှိုက်စည်းမျဉ်း %d ခု ပြန်မတွဲရသေးပါ — viewer ထဲက "🔄 ပြန်တွဲမည်" ကို အရင်နှိပ်ပါ' % k)
    try: no_map = not json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8')).get('ppmap')
    except Exception: no_map = False
    if no_map:                                            # paired data made before the content-based page map existed: make it again once (junk rules are applied by m_pair itself)
        log('စာမျက်နှာမြေပုံ မရှိသေးသောကြောင့် ပြန်တွက်နေသည် (၅ မိနစ်ခန့်)...')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'm_pair.py'), str(n)], capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        if r.returncode: raise RuntimeError('m_pair failed: ' + (r.stderr or r.stdout)[-500:])
    import glob
    for f in glob.glob(os.path.join(ROOT, 'output', 'gemini', '%03d_*.txt' % n)): os.remove(f)          # the old files of this book are made again below
    log('Gemini ဖိုင်များ ခွဲနေသည်...')
    import m_bundle
    m_bundle.main(n, 1, 9999, per, False, nopali, log, sets=sets, nsy=nsy, maxchars=maxchars)
    cp = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)
    if os.path.exists(cp):
        import m_gcheck
        m_gcheck.cleanup_done(n, json.load(open(cp, encoding='utf-8')), log)
    log('✔ ပြီးပါပြီ — output/gemini ထဲက ဖိုင်များကို Gemini ဖြင့် စစ်ပါ')


def prepare(n, per=2, sets=10, nopali=False, log=print, nsy=None, maxchars=10000):
    """both steps in a row (old behaviour; command line)"""
    prepare_viewer(n, log)
    prepare_files(n, per, sets, nopali, log, nsy, maxchars)


def recheck(n, log=print):
    """STAGE 2 - after Gemini, before the web: the blue corrections are made again on the text that is now in final.xlsx (Gemini's pages, the sheet text for the others), so the Pali
    errors that are STILL there show up. Only the viewer data (paired/NNN.json) is made; the Gemini files are not touched.  (Stage 1, 'prepare', makes the same viewer data from the sheet text.)"""
    fp = os.path.join(ROOT, 'fix_on.json')
    d = json.load(open(fp, encoding='utf-8')) if os.path.exists(fp) else {}
    d[str(n)] = [1, 9999]; json.dump(d, open(fp, 'w', encoding='utf-8'))
    pp_ = os.path.join(ROOT, 'paired', '%03d.json' % n); s1 = os.path.join(ROOT, 'paired', '%03d_stage1_fixes.json' % n)
    if os.path.exists(pp_):                                                      # keep the Pali-spelling proposals made on the SHEET text (stage 1), to be able to say which of them Gemini has already put right
        try:
            O = json.load(open(pp_, encoding='utf-8'))
            if not O['stats'].get('use_gemini'):
                import shutil; shutil.copy(pp_, os.path.join(ROOT, 'paired', '%03d_stage1.json' % n))        # the whole stage-1 data: the WEB build needs it (its text base is the sheet text, not the Gemini text)
                json.dump({str(p['num']): [q for q in p.get('fixes', []) if q['kind'] in ('pali', 'lex', 'missing') and q.get('old')] for p in O['pages'] if p.get('num') is not None}, open(s1, 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception as e: log('   (stage 1 ပြင်ချက်စာရင်း မသိမ်းနိုင်: %s)' % e)
    log('Gemini စာဖြင့် ပါဠိအမှား ပြန်စစ်နေသည် (၅ မိနစ်ခန့်)...')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'm_pair.py'), str(n)], capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8', M_USE_GEMINI='1'))
    if r.returncode: raise RuntimeError('m_pair failed: ' + (r.stderr or r.stdout)[-500:])
    for line in r.stdout.splitlines():
        if line.startswith('text of'): log('   ' + line.strip())
    P = json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8'))
    from collections import Counter
    if os.path.exists(s1):                                                       # a stage-1 proposal whose wrong word is no longer in the Gemini text of that page = Gemini put it right
        S1 = json.load(open(s1, encoding='utf-8')); gp = set(P['stats'].get('gemini_pages') or []); nfix = 0
        for p in P['pages']:
            if p.get('num') in gp:
                words = set(w for w in re.split(r'[^က-ဿၐ-႟]+', p.get('text') or '') if w)
                seen_ = set(); fx = []
                for q in S1.get(str(p['num']), []):
                    k_ = (q['old'], q['new'])
                    if k_ in seen_ or q['old'] == q['new'] or (q['old'] in (p.get('text') or '') if re.search(r'\s', q['old']) else q['old'] in words): continue
                    seen_.add(k_); fx.append({'old': q['old'], 'new': q['new'], 'kind': q['kind']})
                p['gem_fixed'] = fx; nfix += len(fx)
        P['stats']['gem_fixed_total'] = nfix
        json.dump(P, open(os.path.join(ROOT, 'paired', '%03d.json' % n), 'w', encoding='utf-8'), ensure_ascii=False)
        log('   Gemini က ပါဠိအမှား %d ခု ပြင်ပြီးသား (stage 1 အကြံပြုချက်များထဲက)' % nfix)
    c = Counter(q['kind'] for p in P['pages'] for q in p.get('fixes', []))
    log('✔ ပြီးပါပြီ — viewer မှာ ကြည့်ပါ (Gemini စာဖြင့် ပြထားသည်၊ Gemini ပြင်ပြီးစာရင်းနှင့် ကျန်နေသေးသော အပြာပြင်ချက် နှစ်ခုလုံးကို မြင်ရမည်)။ ပါဠိ(အပြာ) ပြင်ချက် ကျန်: %d ခု' % c.get('pali', 0))


if __name__ == '__main__':
    a = sys.argv[1:]
    val = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    if '--recheck' in sys.argv: recheck(int([x for x in a if not x.startswith('--')][0])); sys.exit()
    prepare(int([x for x in a if not x.startswith('--') and not (a.index(x) > 0 and a[a.index(x) - 1] in ('--per', '--sets'))][0]), val('--per', 2), val('--sets', 10), '--no-pali' in a)
