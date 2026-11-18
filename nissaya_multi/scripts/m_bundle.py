# -*- coding: utf-8 -*-
"""File(s) for the Gemini app: SETS of (Pali pages + ALL their nissaya pages), many sets in ONE file.
    python nissaya_multi/scripts/m_bundle.py <sheet n> <first Pali page> <last Pali page> [--per 2] [--sets 10] [--prompt] [--raw] [--no-pali]
  --per N     Pali pages in one set (default 2)
  --nsy N     instead of --per: Pali pages are added to a set until it holds N-1..N+1 nissaya pages
  --maxc N    with --nsy: at most N characters in one set (default 10000)
  --sets M    sets in one file (default 10); a longer range gives several files
  --prompt    put the text of gemini_prompt.txt in front of every set (for the plain chat box; the Gemini app has its own prompt)
  --raw       the plain cleaned OCR text instead of the tool-corrected text;  --no-pali  without the blue Pali corrections
Each set starts with  '===== အစု i / M ====='  - the Gemini app splits the file at these lines and checks one set per click.
Every NISSAYA page goes into the files once: a Pali page is taken only when it brings a nissaya page that no earlier Pali page brought (several Pali pages pointing to one nissaya page:
only the first one is used). Pali pages that bring nothing new are left out and listed in the log; nissaya pages that no Pali page brings are listed too.
Output: nissaya_multi/output/gemini/NNN_<book>_pali<first>-<last>.txt
Uses paired/NNN.json (run '① ဖိုင်အသစ် ဖတ်မည်' first so it is up to date)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
FOOT = "(ထွက်ရလဒ်ထဲတွင် '--- နိဿယ စာမျက်နှာ N ---' စာကြောင်းများကို ထိုအတိုင်း ထည့်ထားပါ။)"
NL = chr(10)


def main(n, lo, hi, per=2, raw=False, nopali=False, log=print, sets=10, with_prompt=False, nsy=None, maxchars=10000, exclude=None, suffix='', outdir=None):
    """exclude = nissaya pages that are NOT given again (they wait in other files); suffix = ends the file names (e.g. '_gap' for the pages nobody has sent yet)"""
    P = json.load(open(os.path.join(ROOT, 'paired', '%03d.json' % n), encoding='utf-8'))
    prompt = open(os.path.join(ROOT, 'gemini_prompt.txt'), encoding='utf-8').read().strip()
    pages = {p['num']: p for p in P['pages'] if p.get('num') is not None}
    out = outdir or os.path.join(ROOT, 'output', 'gemini'); os.makedirs(out, exist_ok=True)
    keys = sorted(((k.split('|')[0], int(k.split('|')[1])) for k in P['ppmap']), key=lambda x: (x[0], x[1]))
    keys = [(b, p) for b, p in keys if lo <= p <= hi]
    TEXT = {}
    if not raw and keys:
        import m_tool
        rr = [P['ppmap']['%s|%s' % k] for k in keys]
        a, z = min(r[0] for r in rr), max(r[1] for r in rr)
        fp = P['stats'].get('fix_pages')
        if fp and fp[0] <= a and fp[1] >= z:                              # the viewer data already holds the corrections of these pages (made at the same time): no second alignment
            payload = P; log('  (ပြင်ချက်များကို viewer ဒေတာမှ ယူသည် - ထပ်မတွက်ပါ)')
        else:
            payload = m_tool.run_corrections(n, a, z, log)
        for pg_ in payload['pages']:
            if pg_.get('num') is not None and a <= pg_['num'] <= z:
                TEXT[pg_['num']] = m_tool.apply_page(pg_, True, not nopali, False, True)[0]
    blocks_by = {}
    for b in P['blocks']: blocks_by.setdefault((b['book'], b['page']), []).append(b)
    # the aim is to check every NISSAYA page ONCE: a Pali page is taken only when it brings a nissaya page that no Pali page before it has brought (a Pali page whose nissaya page was
    # already given - e.g. Pali 121, 122, 123 all pointing to nissaya 194 - is left out, nothing is checked twice)
    kept = []; skipped = []; seen = set(); fresh = {}
    gp_ = os.path.join(ROOT, 'gold', 'gemini', '%03d_collected.json' % n)             # nissaya pages Gemini has already checked and collected (④) are not given again
    done_ = set()
    if os.path.exists(gp_):
        seen = {int(k) for k in json.load(open(gp_, encoding='utf-8'))}; done_ = set(seen)
        log('  (%d nissaya pages are already checked by Gemini - left out)' % len(seen))
    if exclude: seen.update(exclude); done_.update(exclude)
    for g in keys:
        r = P['ppmap']['%s|%s' % g]
        new = [k for k in range(r[0], r[1] + 1) if k in pages and k not in seen]
        empty_ = [k for k in new if not (TEXT.get(k) or (pages[k]['body'] + pages[k].get('foot', ''))).strip()]       # nothing left on the page after the junk is taken away: nothing to check
        if empty_: log('  nissaya page(s) %s: empty after the junk is removed - left out' % ' '.join(map(str, empty_))); seen.update(empty_); new = [k for k in new if k not in empty_]
        if new: kept.append(g); fresh[g] = new
        else: skipped.append(g[1])
        seen.update(range(r[0], r[1] + 1))
    if skipped: log('  Pali pages left out (their nissaya pages are already in another set): %s' % ' '.join(str(x) for x in skipped))
    keys = kept
    # a nissaya page that no Pali page points to (a gap of the database map, pages before the first / after the last mapped one: colophon, index ...) and that is not collected / excluded yet:
    # it goes into the set of the Pali page just before it (the first Pali page for pages before the map starts) - only if that Pali page is in the requested range
    all_keys = sorted(((k.split('|')[0], int(k.split('|')[1])) for k in P['ppmap']), key=lambda x: (x[0], x[1]))
    for k in sorted(pages):
        if k in seen: continue
        if not (pages[k]['body'] + pages[k].get('foot', '')).strip(): seen.add(k); continue          # nothing on the page at all
        before = [g for g in all_keys if P['ppmap']['%s|%s' % g][0] <= k]
        g = before[-1] if before else all_keys[0]
        if not (lo <= g[1] <= hi): continue
        if g not in kept: kept.append(g); fresh[g] = []
        fresh[g] = sorted(set(fresh[g]) | {k}); seen.add(k)
        log('  nissaya page %d: no Pali page points to it - put with Pali page %d' % (k, g[1]))
    kept = sorted(set(kept), key=lambda x: (x[0], x[1])); keys = kept
    built = []                                                           # one text per set

    def text_of(grp, nums):
        pali = (NL * 2).join('[ပါဠိ %s စာမျက်နှာ %d]' % g + NL + NL.join(b['pali'] for b in sorted(blocks_by.get(g, []), key=lambda b: b['i'])) for g in grp)
        nsy_t = (NL * 2).join('--- နိဿယ စာမျက်နှာ %d ---' % k + NL + (TEXT.get(k) or (pages[k]['body'] + (NL + pages[k]['foot'] if pages[k].get('foot') else ''))) for k in nums)
        head = (prompt + NL + FOOT + NL * 2) if with_prompt else ''
        return head + '===== ပါဠိ =====' + NL + pali + NL * 2 + '===== နိဿယ =====' + NL + nsy_t + NL
    MAXP = 10                                                            # never more than 10 nissaya pages in one set
    parts_ = []
    if nsy:                                                              # sets by the number of NISSAYA pages (nsy .. nsy+1) AND at most maxchars characters: Pali pages are added while both limits hold
        lo_n, hi_n = nsy, min(nsy + 1, MAXP)
        groups = []; cur = []; cn = []
        for g in keys:
            add = [k for k in fresh[g] if k not in cn]
            if cur and (len(cn) + len(add) > hi_n or len(text_of(cur + [g], cn + add)) > maxchars):
                groups.append((cur, cn)); cur = []; cn = []; add = list(fresh[g])
            cur.append(g); cn = cn + add
            if len(cn) >= lo_n: groups.append((cur, cn)); cur = []; cn = []
        if cur: groups.append((cur, cn))
    else:
        groups = []
        for q in range(0, len(keys), per):
            grp = keys[q:q + per]; nums = []
            for g in grp: nums += [k for k in fresh[g] if k not in nums]
            groups.append((grp, nums))
    for grp, nums in groups:
        if len(text_of(grp, nums)) <= maxchars and len(nums) <= MAXP or len(nums) <= 1: parts_.append((grp, nums)); continue
        # too big for one set (one Pali page that brings many nissaya pages, e.g. Pali page 1 = the introduction): the nissaya pages go into several sets that all carry the Pali page(s)
        chunk = []; made = 0
        for k in nums:
            if chunk and (len(chunk) >= MAXP or len(text_of(grp, chunk + [k])) > maxchars): parts_.append((grp, chunk)); chunk = []; made += 1
            chunk.append(k)
        if chunk: parts_.append((grp, chunk)); made += 1
        log('  Pali page %s: %d nissaya pages -> %d sets' % (grp[0][1], len(nums), made))
    for grp, nums in parts_:
        built.append((grp, text_of(grp, nums)))
    big = [len(t) for g, t in built if len(t) > maxchars]
    if big: log('  %d set(s) over %d characters (one nissaya page alone is too long): %s' % (len(big), maxchars, big))
    delivered = {k for g in keys for k in fresh[g]}
    if keys:
        r_all = [P['ppmap']['%s|%s' % g] for g in kept]
        lo_p, hi_p = min(r[0] for r in r_all), max(r[1] for r in r_all)
        lo_p = min([lo_p] + sorted(delivered)[:1]); hi_p = max([hi_p] + sorted(delivered)[-1:])
        lost = [k for k in range(lo_p, hi_p + 1) if k in pages and k not in delivered]
        if lost: log('  nissaya pages that no Pali page of this range brings (not in any set): %s' % ' '.join(str(x) for x in lost))
    files = []
    for j in range(0, len(built), sets):
        chunk = built[j:j + sets]
        first, last = chunk[0][0][0], chunk[-1][0][-1]
        name = '%03d_%s_pali%d-%d%s.txt' % (n, first[0], first[1], last[1], suffix)
        body = NL.join('===== အစု %d / %d =====' % (k + 1, len(chunk)) + NL + t for k, (g, t) in enumerate(chunk))
        open(os.path.join(out, name), 'w', encoding='utf-8').write(body)
        files.append(name)
        log('  %s : %d sets (Pali pages %d-%d), %d characters' % (name, len(chunk), first[1], last[1], len(body)))
    log('%d file(s), %d sets -> %s' % (len(files), len(built), out))
    return out, files


if __name__ == '__main__':
    a = sys.argv[1:]
    val = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    pos = [x for i, x in enumerate(a) if not x.startswith('--') and not (i > 0 and a[i - 1] in ('--per', '--sets', '--nsy', '--maxc'))]
    n, lo = int(pos[0]), int(pos[1]); hi = int(pos[2]) if len(pos) > 2 else lo
    main(n, lo, hi, val('--per', 2), '--raw' in a, '--no-pali' in a, sets=val('--sets', 10), with_prompt='--prompt' in a, nsy=val('--nsy', 0) or None, maxchars=val('--maxc', 10000))
