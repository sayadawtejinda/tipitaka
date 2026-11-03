"""Gale-Church style paragraph alignment (length ratio + rare shared letter n-grams) for the commentary books.
align(P, M, c, df, nP, lex_ok) -> list of beads (i0, i1, j0, j1): Pali items i0..i1-1 <-> Myanmar items j0..j1-1.
Items are dicts with 'len' and 'grams' (set)."""
import math

BEADS = [(1, 1, 0.0), (1, 0, 4.0), (0, 1, 4.0), (2, 1, 1.5), (1, 2, 1.5), (2, 2, 2.5), (3, 1, 3.0), (1, 3, 3.0), (3, 2, 3.5), (2, 3, 3.5)]
import os
S2 = 120.0
CAP = float(os.environ.get('SBS_CAP', '15'))
LEX_BETA = 0.6

def lencost(l1, l2, c):
    if l1 == 0 and l2 == 0: return 0.0
    d = (l2 - c * l1) / math.sqrt(max(l1, 40) * S2)
    return min(0.5 * d * d, CAP)         # -log of a gaussian up to a constant; capped so that one badly sized paragraph cannot drag the rest

def align(P, M, c, df, nP, lex_ok=None, use_end=True):
    n, m = len(P), len(M)
    pl = [0]
    for x in P: pl.append(pl[-1] + x['len'])
    ml = [0]
    for x in M: ml.append(ml[-1] + x.get('elen', x['len']))
    INF = 1e18
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    lexcache = {}
    thr = max(3, nP // 8)

    def lex(i0, i1, j0, j1):
        if i1 - i0 < 1 or j1 - j0 < 1: return 0.0
        key = (i0, i1, j0, j1)
        if key in lexcache: return lexcache[key]
        v = 0.0
        if lex_ok is None or all(lex_ok[j] for j in range(j0, j1)):
            gp = set().union(*(P[i]['grams'] for i in range(i0, i1)))
            gm = set().union(*(M[j]['grams'] for j in range(j0, j1)))
            for g in gp & gm:
                if df.get(g, 99) <= thr: v += math.log(1 + nP / df[g])
        if use_end and any(M[j].get('tp') is not None and i0 <= M[j]['tp'] < i1 for j in range(j0, j1)): v += 60.0
        if use_end and any(M[j].get('endm') for j in range(j0, j1)) and any(P[i].get('pend') for i in range(i0, i1)): v += 8.0
        lexcache[key] = v
        return v

    for i in range(n + 1):
        for j in range(m + 1):
            cur = cost[i][j]
            if cur >= INF: continue
            for di, dj, pen in BEADS:
                ni, nj = i + di, j + dj
                if ni > n or nj > m: continue
                v = cur + pen + lencost(pl[ni] - pl[i], ml[nj] - ml[j], c) - LEX_BETA * lex(i, ni, j, nj)
                if v < cost[ni][nj]:
                    cost[ni][nj] = v; back[ni][nj] = (i, j)
    beads, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]
        beads.append((pi, i, pj, j)); i, j = pi, pj
    return beads[::-1]
