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


def publish(n, build=True, dry=False, log=print):
    if build:
        log('web ဖိုင် ထုတ်နေသည် (m_final)...')
        r = subprocess.run([sys.executable, os.path.join(HERE, 'm_final.py'), str(n)], cwd=os.path.dirname(REPO) if False else REPO, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        if r.returncode: raise RuntimeError('m_final failed: ' + (r.stderr or r.stdout)[-600:])
        log((r.stdout.strip().splitlines() or [''])[-1])
    metas = [f for f in os.listdir(os.path.join(ROOT, 'web')) if f.endswith('.meta.json')]
    meta = None
    for f in metas:
        m = json.load(open(os.path.join(ROOT, 'web', f), encoding='utf-8'))
        if m['sheet'] == n: meta = m
    if not meta: raise RuntimeError('no web file for sheet %d - build it first' % n)
    book, edition, fname = meta['book'], meta['edition'], meta['file']
    src = os.path.join(ROOT, 'web', fname + '.html')
    if not os.path.exists(src): raise RuntimeError('missing ' + src)
    data = os.path.join(REPO, 'data')
    dst = os.path.join(data, fname + '.html')
    shutil.copy2(src, dst)
    paths = ['data/%s.html' % fname]
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
        if nums:                                          # 'ပြည် (ပ)' -> 'ပြည်မူ (ပ)' (edition + volume; the reader shows only the volume that has the page)
            mm_ = re.match(r'^(.*?)\s*(\([^)]*\))\s*$', edition)
            if mm_ and mm_.group(1).strip(): b_ = mm_.group(1).strip(); ent['label'] = (b_ if b_.endswith('မူ') else b_ + 'မူ') + ' ' + mm_.group(2)
    except Exception: pass
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
