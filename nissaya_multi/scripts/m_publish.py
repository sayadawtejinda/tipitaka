# -*- coding: utf-8 -*-
"""ONE command that puts a nissaya edition on the web page (GitHub: sayadawtejinda/tipitaka, branch main):
    python nissaya_multi/scripts/m_publish.py <sheet n> [--no-build] [--dry]
1. builds the web file with m_final.py   (web/<book>_<edition>.html, the name is made by itself: book id + edition slug, e.g. mula_vi_01_bhurakyi)
2. copies it to  data/<book>_<edition>.html  of the tipitaka repository
3. data/nissaya_editions.json : the editions of that book that the web page offers (the original  data/<book>.html  if it exists, then this edition) - made by itself
4. data/nissaya_books.json : the book id is added if it is not in the list yet
5. git: fetch (pull --rebase if the web has newer commits), commit ONLY those files, push.
--dry shows everything and does not commit / push.   The web page (index.html) reads nissaya_editions.json by itself, so nothing else has to be edited."""
import sys, os, re, json, shutil, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); REPO = os.path.dirname(ROOT)
URL = 'https://sayadawtejinda.github.io/tipitaka/'


def git(*args, check=True, log=print):
    r = subprocess.run(['git'] + list(args), cwd=REPO, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode:
        raise RuntimeError('git %s failed: %s' % (' '.join(args), (r.stderr or r.stdout).strip()[:600]))
    return r



def nice_label(edition):
    """label shown in the reader:  'Z05 044 ဦးဗုဓ် (ပ)-ပဒမာလာ' -> 'ဦးဗုဓ် (ပ)'  (the sheet code and the book title after the volume are dropped);  'ပြည် (ပ)' -> 'ပြည်မူ (ပ)' (edition + volume)"""
    e = edition.strip(); e2 = re.sub(r'^Z\d+\s+\d+\s+', '', e).strip(); z = e2 != e
    e2 = re.sub(r'^(.*?\([^)]*\))\s*[-–—].*$', lambda m_: m_.group(1), e2)
    mm = re.match(r'^(.*?)\s*(\([^)]*\))\s*$', e2)
    if mm and mm.group(1).strip():
        b = mm.group(1).strip()
        return (b if (z or b.endswith('မူ')) else b + 'မူ') + ' ' + mm.group(2)
    return e2

def _put_one(n, meta, dry, log):
    data = os.path.join(REPO, 'data')
    book, fname = meta['book'], meta['file']
    edition = meta.get('edition')
    if not edition:                                       # no edition name on the sheet: the nissaya book name of the db (nsy_books.name), like m_final does
        try:
            import sqlite3; _f = [r for r in json.load(open(os.path.join(ROOT, 'catalog.json'), encoding='utf-8')) if r['n'] == n][0]['final']
            _q = sqlite3.connect(os.path.join(REPO, '%s_nsy.db' % _f['db'])).execute('select name from nsy_books where id=?', (_f['nsy_id'],)).fetchone(); edition = _q[0] if _q else None
        except Exception: edition = None
    edition = edition or ('နိဿယ-%s' % n)                  # last resort: a plain label
    src = os.path.join(ROOT, 'web', fname + '.html')
    if not os.path.exists(src): raise RuntimeError('missing ' + src)
    dst = os.path.join(data, fname + '.html')
    shutil.copy2(src, dst)
    paths = ['data/%s.html' % fname]
    if not dry:                                           # a copy of everything that goes to the web is kept in Downloads/Nissaya_Final/published_multi/ (the user's one home for the final files)
        try:
            keep = os.path.join(os.path.expanduser('~'), 'Downloads', 'Nissaya_Final', 'published_multi'); os.makedirs(keep, exist_ok=True)
            shutil.copy2(src, os.path.join(keep, fname + '.html'))
            mp = os.path.join(ROOT, 'web', fname + '.meta.json')
            if os.path.exists(mp): shutil.copy2(mp, os.path.join(keep, fname + '.meta.json'))
            log('final ဖိုင် သိမ်းပြီး: ' + os.path.join(keep, fname + '.html'))
        except Exception as e: log('(final ဖိုင် မသိမ်းနိုင်ပါ: %s)' % e)
    # editions of this book offered by the web page
    ep = os.path.join(data, 'nissaya_editions.json')
    editions = json.load(open(ep, encoding='utf-8')) if os.path.exists(ep) else {}
    lst = [e for e in editions.get(book, []) if e['file'] != fname]
    orig = os.path.join(data, book + '.html')
    if os.path.exists(orig) and '[စာမျက်နှာ-' in open(orig, encoding='utf-8').read(200000 * 10) and not any(e['file'] == book for e in lst):
        lst.insert(0, {'label': 'မူလနိဿယ', 'file': book})
    ent = {'label': edition, 'file': fname}
    try:                                                  # Pali pages this file covers: the reader shows an edition only on the pages it has (e.g. vol.1 and vol.2 of one book)
        nums = [int(x.translate(str.maketrans('၀၁၂၃၄၅၆၇၈၉', '0123456789'))) for x in re.findall(r'\[စာမျက်နှာ-([၀-၉]+)\]', open(src, encoding='utf-8').read())]
        if nums: ent['from'], ent['to'] = min(nums), max(nums)
        try:
            import m_edpages; ent['pg'] = m_edpages.page_ranges(open(src, encoding='utf-8').read())          # only pages that really have text (a button on an empty page is wrong)
        except Exception: pass
    except Exception: pass
    ent['label'] = nice_label(edition)
    lst.append(ent)
    editions[book] = lst
    json.dump(editions, open(ep, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    paths.append('data/nissaya_editions.json')
    bp = os.path.join(data, 'nissaya_books.json')
    books = json.load(open(bp, encoding='utf-8'))
    ids = books if isinstance(books, list) else books.get('books', [])
    if book not in ids:
        ids.append(book); ids.sort()
        json.dump(books if isinstance(books, list) else books, open(bp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        paths.append('data/nissaya_books.json')
    log('web သို့ တင်မည့် ဖိုင်: ' + ', '.join(paths) + '  [မူ: ' + ' / '.join(e['label'] for e in lst) + ']')
    return paths, lst


def publish(n, build=True, dry=False, log=print, only_books=None):
    if build:
        log('web ဖိုင် ထုတ်နေသည် (m_final)...')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'm_final.py'), str(n)], cwd=os.path.dirname(REPO) if False else REPO, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        if r.returncode: raise RuntimeError('m_final failed: ' + (r.stderr or r.stdout)[-600:])
        log((r.stdout.strip().splitlines() or [''])[-1])
    metas = [f for f in os.listdir(os.path.join(ROOT, 'web')) if f.endswith('.meta.json')]
    mlist = []
    for f in metas:
        m = json.load(open(os.path.join(ROOT, 'web', f), encoding='utf-8'))
        if m['sheet'] == n and (not only_books or m['book'] in only_books): mlist.append(m)
    if not mlist: raise RuntimeError('no web file for sheet %d - build it first' % n)
    paths = []; lst = []
    for meta in mlist:                                    # one web file per book of the sheet
        p_, l_ = _put_one(n, meta, dry, log); paths += [x for x in p_ if x not in paths]; lst += l_
    book = '+'.join(m['book'] for m in mlist); fname = '+'.join(m['file'] for m in mlist)         # for the commit message
    if dry: log('(dry run - commit / push မလုပ်ပါ)'); return paths
    st = git('status', '--porcelain', '--', *paths).stdout.strip()
    if not st: log('ပြောင်းလဲမှု မရှိ - web ပေါ်မှာ အတူတူပင် ရှိပြီးသား'); return paths
    git('fetch', 'origin', log=log)
    behind = int(git('rev-list', '--count', 'HEAD..origin/main').stdout.strip() or 0)
    if behind:
        log('web ပေါ်မှာ ပိုသစ်သော commit %d ခု ရှိ - ယူနေသည်...' % behind)
        r = git('pull', '--rebase', '--autostash', check=False)
        if r.returncode:
            git('rebase', '--abort', check=False); raise RuntimeError('git pull --rebase မအောင်မြင်ပါ: ' + (r.stderr or r.stdout).strip()[:500])
    git('add', '--', *paths)
    git('commit', '-m', 'Nissaya edition: %s (%s) published' % (book, fname), '--', *paths)
    git('push')
    # the nissaya download page (nissaya_downloads.html) lists every edition: rebuild its list (dates come from git, so AFTER the commit) and push it
    try:
        subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'nissaya_build_downloads.py')], cwd=REPO, check=True, capture_output=True, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        if git('status', '--porcelain', '--', 'data/nissaya_downloads.json').stdout.strip():
            git('add', '--', 'data/nissaya_downloads.json'); git('commit', '-m', 'Nissaya download list updated', '--', 'data/nissaya_downloads.json'); git('push')
    except Exception as e:
        log('(ဒေါင်းလုတ်စာရင်း မပြောင်းနိုင်ပါ: %s - python scripts/nissaya_build_downloads.py ကို ကိုယ်တိုင် run ပါ)' % e)
    log('✔ web ပေါ် တင်ပြီးပါပြီ — %s  (browser မှာ Ctrl+Shift+R နှိပ်ပါ၊ GitHub Pages ပြောင်းဖို့ ၁-၂ မိနစ် ကြာနိုင်)' % URL)
    return paths


if __name__ == '__main__':
    a = sys.argv[1:]
    n = int([x for x in a if not x.startswith('--')][0])
    try: publish(n, '--no-build' not in a, '--dry' in a)
    except RuntimeError as e: print('အမှား:', e); sys.exit(1)
