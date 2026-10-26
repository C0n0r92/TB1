"""PAPER ONLY. Inflow-spike test (IF_*), Zero 2026-10-24. Cache only, zero API calls.
PROXY: no historical per-trade buy/sell or buyer data exists in Lab's cache (GT 1-min OHLCV has only total USD volume).
Signal proxy on data/backfill/candles1m (on-chain sampled PumpSwap graduations, unbiased universe):
  vol(last W complete 1-min bars)/W >= R x max(vol(prior 30 min)/30, $50/min)  AND window is green (close > open of window start)
  [green = proxy for net buying; buyer-count part NOT testable]  AND modelled liq >= $20k AND age since migration >= 5 min.
Entry at T+delay (T = close of the last signal bar): price interpolated inside the next bar (open + d/60 x (close-open)).
Exits: sell-all TP / SL / max hold; stop checked first in every bar; stop that gaps fills at min(stop, close) (or open if it opened through).
TP fills at the level (or the open if it gapped above). Costs per side: 2% fee + 0.5% + 2 x stake/liq (liq model ~ sqrt(price)).
Stake 0.04 SOL (solusd(t)); net_base = after 2%/side+slippage; net_p1/net_p5 add 2 x (0.0001|0.0005 + 0.000005 SOL)/0.04.
Max 3 open, one position per pool, 60-min re-entry cooldown. Holdout: Dublin nights >= 2026-10-14 (pre-registered in bf_replay)."""
import json, os, glob, math, statistics, random, bisect, collections
import bf_replay as BR
from labcore import night_of
C1 = BR.C1; HOLD_NIGHT = BR.HOLDOUT_FIRST_NIGHT
WS = (1, 3, 5); RS = (2.0, 3.0, 5.0); DELAYS = (5, 15, 30)
FAST = [(tp, sl, h) for tp in (0.08, 0.10, 0.15, 0.20) for sl in (0.08, 0.10, 0.15) for h in (5, 10, 15, 30)]
EXITS = FAST + [(0.20, 0.15, 60)]
STAKE_SOL = 0.04; FEE = 0.02; BS = 0.005; IMP = 2.0; PRIOR = 30; MINLIQ = 20000; MINAGE = 300
P1 = 2 * (0.0001 + 0.000005) / STAKE_SOL; P5 = 2 * (0.0005 + 0.000005) / STAKE_SOL

def load():
    P = []
    for f in sorted(glob.glob(os.path.join(C1, "*.json"))):
        d = json.load(open(f))
        if d.get("status") != "ok" or d.get("kind") != "mig" or not d.get("rows"): continue
        m = collections.OrderedDict()
        for t, o, h, l, c, v in sorted(d["rows"], key=lambda x: x[0]):
            if t in m: a = m[t]; m[t] = [a[0], max(a[1], h), min(a[2], l), c, a[4] + v]
            else: m[t] = [o, h, l, c, v]
        rows = [(t, *x) for t, x in m.items()]
        P.append({"pool": d["pool"], "mint": d["mint"], "t0": d["t_mig"], "rows": rows, "day": d["day"]})
    return P

def signals(p, W, R):
    """chronological signal times T (bar-close) for one pool, using only bars complete by T."""
    rows = p["rows"]; t = [r[0] for r in rows]; cv = [0.0]
    for r in rows: cv.append(cv[-1] + r[5])
    out = []
    for i in range(len(rows)):
        T = rows[i][0] + 60
        if T - p["t0"] < MINAGE: continue
        a = bisect.bisect_left(t, T - 60 * W); b = i + 1
        vw = cv[b] - cv[a]
        pa = bisect.bisect_left(t, T - 60 * (W + PRIOR)); pri_min = min(PRIOR, (T - 60 * W - max(p["t0"], T - 60 * (W + PRIOR))) / 60)
        if pri_min < 2: continue
        vp = cv[a] - cv[pa]
        if vw / W < R * max(vp / pri_min, 50.0): continue
        o_start = rows[a][1] if a < len(rows) else rows[i][1]
        if not rows[i][4] > o_start: continue
        sol = BR.solusd(T); liq = 2 * math.sqrt(BR.K * rows[i][4] * sol)
        if liq < MINLIQ: continue
        out.append((T, i, liq, sol))
    return out

def cside(liq, usd): return FEE + BS + IMP * usd / max(liq, 1000.0)

def trade(p, sig, d, ex):
    T, i, liq0, sol = sig; rows = p["rows"]; tp, sl, hm = ex; usd = STAKE_SOL * sol
    te = T + d; j = bisect.bisect_right([r[0] for r in rows], te - 60)        # first bar whose end > te
    j = max(j, i + 1)
    if j >= len(rows) or rows[j][0] > te + 600: return None                 # no trading right after the signal -> no fill (dead coin)
    b = rows[j]
    frac = min(max((te - b[0]) / 60, 0), 1) if b[0] <= te else 0
    e = b[1] + frac * (b[4] - b[1]) if b[0] <= te else b[1]
    lq = lambda px: 2 * math.sqrt(BR.K * px * sol)
    buy = e * (1 + cside(lq(e), usd)); st, tg = e * (1 - sl), e * (1 + tp); tend = te + 60 * hm
    xp, why, tx = None, None, None
    for k in range(j, len(rows)):
        t0, o, h, l, c, v = rows[k]
        if t0 >= tend: xp, why, tx = rows[k - 1][4] if k > j else e, "time", tend; break
        oo = o if k > j else e
        if l <= st: xp = oo if oo <= st else min(st, c); why, tx = "stop", t0 + 60; break
        if h >= tg: xp = max(oo, tg) if oo >= tg else tg; why, tx = "tp", t0 + 60; break
    if xp is None: xp, why, tx = rows[-1][4], "time_eod", min(tend, rows[-1][0] + 60)
    nb = xp * (1 - cside(lq(xp), usd)) / buy - 1
    return {"t": T, "te": te, "tx": tx, "pool": p["pool"], "ret_g": xp / e - 1, "net_base": nb, "net_p1": nb - P1, "net_p5": nb - P5,
            "why": why, "oos": night_of(T) >= HOLD_NIGHT}

def run_variant(P, SIG, W, R, d, ex):
    ev = sorted((s[0], pi, s) for pi, p in enumerate(P) for s in SIG[(W, R)][pi])
    open_until = []; last_pool = {}; out = []
    for T, pi, s in ev:
        open_until = [x for x in open_until if x > T]
        if len(open_until) >= 3: continue
        pl = P[pi]["pool"]
        if pl in last_pool and T < last_pool[pl]: continue
        tr = trade(P[pi], s, d, ex)
        if not tr: continue
        out.append(tr); open_until.append(tr["tx"]); last_pool[pl] = max(tr["tx"], T + 3600)
    return out

def boot(x, n=2000, seed=11):
    if len(x) < 2: return (None, None)
    rnd = random.Random(seed); m = sorted(statistics.fmean(rnd.choices(x, k=len(x))) for _ in range(n)); return m[int(.025 * n)], m[int(.975 * n) - 1]

def stats(tr, key="net_p1"):
    def s(x):
        r = [t[key] for t in x]
        if not r: return {"n": 0}
        lo, hi = boot(r)
        return {"n": len(r), "mean": statistics.fmean(r), "median": statistics.median(r), "win": sum(v > 0 for v in r) / len(r), "ci": (lo, hi),
                "sd": statistics.pstdev(r) if len(r) > 1 else 0}
    return s(tr), s([t for t in tr if not t["oos"]]), s([t for t in tr if t["oos"]])

if __name__ == "__main__":
    import time; t0 = time.time()
    P = load(); print("pools", len(P))
    SIG = {(W, R): [signals(p, W, R) for p in P] for W in WS for R in RS}
    for k, v in SIG.items(): print(k, sum(map(len, v)), "signals in", sum(1 for x in v if x), "pools")
    G = {}
    for W in WS:
        for R in RS:
            for d in DELAYS:
                for ex in EXITS: G[(W, R, d, ex)] = run_variant(P, SIG, W, R, d, ex)
    print("sim", round(time.time() - t0, 1), "s")
    import pickle; pickle.dump((P and {"n_pools": len(P), "days": sorted({p['day'] for p in P}), "span": (min(p['t0'] for p in P), max(p['rows'][-1][0] for p in P))}, G), open("out/.if_grid.pkl", "wb"))
