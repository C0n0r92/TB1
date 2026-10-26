#!/usr/bin/env python3
"""PAPER ONLY. ES tasks 1-2: matched post-pump control for winner-exit drift + candle-only exit features vs held moments. -> out/es_control.json"""
import json, math, random, bisect, statistics as S, collections
from es_common import trips, px, summ, boot, feats
T_ = trips(); sells = collections.defaultdict(list)
for tr in T_: sells[tr["mint"]].append(tr["te"])
def state(tr, T):
    p = px(tr, T); e = tr["rows"][tr["i0"]][4]
    lo = [x[4] for x in tr["rows"] if T - 3600 <= x[0] <= T - 60]
    if not p or not lo: return None
    return math.log(p / e), math.log(p / min(lo + [p]))
TOL = 0.15; res = {}
for b in ("b1", "b2"):
    R = {}
    for H in (1800, 7200):
        ex, same, pool, diffs, diffs_pool, nm = [], [], [], [], [], 0
        # pool of all candidate moments in this batch (cross-token control)
        P = []
        bt = [tr for tr in T_ if tr["b"] == b]
        for tr in bt:
            for x in tr["rows"][tr["i0"]:]:
                T = x[0] + 59
                if tr["rows"][-1][0] < T + H: break
                if any(abs(T - s) < 900 for s in sells[tr["mint"]]): continue
                st = state(tr, T)
                if st: P.append((st, px(tr, T + H) / px(tr, T) - 1, tr["mint"]))
        for tr in bt:
            te = tr["te"]
            if te <= tr["t"] + 60 or tr["rows"][-1][0] < te + H: continue
            st = state(tr, te); pe = px(tr, te)
            if not st or not pe: continue
            d = px(tr, te + H) / pe - 1; ex.append(d)
            m = [v for (s, v, mt) in P if mt == tr["mint"] and abs(s[0] - st[0]) < TOL and abs(s[1] - st[1]) < TOL]
            if m: same.append(S.fmean(m)); diffs.append(d - S.fmean(m)); nm += 1
            mp = [v for (s, v, mt) in P if abs(s[0] - st[0]) < TOL and abs(s[1] - st[1]) < TOL]
            if mp: diffs_pool.append(d - S.median(mp))
            pool += [S.median(mp)] if mp else []
        allm = [v for (s, v, mt) in P]
        R[f"{H//60}m"] = dict(exit_drift=summ(ex), matched_same_token=summ(same), n_exits_matched_same=nm, paired_diff_same=summ(diffs),
                               matched_pool_median=summ(pool), paired_diff_pool=summ(diffs_pool), unmatched_all_moments=summ(random.Random(1).sample(allm, min(3000, len(allm)))))
    # features: exits vs held moments
    rnd = random.Random(3); FE = {"exit": [], "held": []}; per = []
    for tr in [x for x in T_ if x["b"] == b]:
        if tr["te"] - tr["t"] < 300: continue
        f = feats(tr, tr["te"])
        if not f: continue
        hs = []
        if tr["te"] - tr["t"] >= 900:
            for _ in range(5):
                T = rnd.uniform(tr["t"] + 300, tr["te"] - 300); g = feats(tr, T)
                if g: hs.append(g)
        FE["exit"].append(f); FE["held"] += hs; per.append((f, hs))
    E = {}
    for k in FE["exit"][0]:
        a = [f[k] for f in FE["exit"]]; h = [g[k] for g in FE["held"]]
        if not h: continue
        auc = (sum((x > y) + 0.5 * (x == y) for x in a for y in h)) / (len(a) * len(h))
        sd = S.pstdev(a + h) or 1e-9; dd = (S.fmean(a) - S.fmean(h)) / sd
        # trip-bootstrap CI of AUC
        r = random.Random(5); aucs = []
        for _ in range(300):
            s = r.choices(per, k=len(per)); A = [f[k] for f, _ in s]; Hh = [g[k] for _, hs in s for g in hs]
            if Hh: aucs.append(sum((x > y) + 0.5 * (x == y) for x in A for y in Hh) / (len(A) * len(Hh)))
        aucs.sort()
        E[k] = dict(exit_median=round(S.median(a), 3), held_median=round(S.median(h), 3), auc=round(auc, 3), auc_ci=[round(aucs[7], 3), round(aucs[292], 3)], cohen_d=round(dd, 2))
    R["features"] = dict(n_exit=len(FE["exit"]), n_held=len(FE["held"]), eff=E)
    res[b] = R
json.dump(res, open("/workspace/lab/out/es_control.json", "w"), indent=1)
print(json.dumps(res, indent=1))
