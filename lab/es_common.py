"""PAPER ONLY. Exit-signal study (ES_) shared helpers. Cache only: data/cl/wn 1m GT candles + Scout winners/trades.csv (read-only)."""
import csv, json, glob, bisect, math, random, statistics as S, datetime as dt
W = list(csv.DictReader(open("/workspace/onchain-intel/winners/trades.csv")))
B1 = ("9PB1", "AH75", "5o3k", "zhYn")
fl = lambda x: float(x) if x not in ("", None) else None
ts_ = lambda s: int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
C = {}
for p in glob.glob("/workspace/lab/data/cl/wn/*.json"):
    d = json.load(open(p)); C[(d["mint"], d["t"])] = d
def trips():
    """trips with usable candles: dict(b, wallet, mint, t, te, rows, tsl, cost, act, i0)"""
    out = []
    for r in W:
        t = ts_(r["entry_time"]); d = C.get((r["mint"], t))
        if not d or len(d["rows"]) < 10: continue
        rows = [x for x in d["rows"] if x[4] and x[4] > 0]
        if not rows or rows[0][0] > t or rows[-1][0] < t: continue
        m = fl(r["mcap_at_entry_usd_approx"]); cost = 0.02 if (m and m >= 1e6) else 0.047
        tsl = [x[0] for x in rows]; i0 = bisect.bisect_left(tsl, t + 10 - 59)
        if i0 >= len(rows) - 1: continue
        out.append(dict(b="b1" if r["wallet"][:4] in B1 else "b2", wallet=r["wallet"][:4], mint=r["mint"], t=t, te=ts_(r["exit_time"]), rows=rows, tsl=tsl,
                        cost=cost, act=fl(r["pnl_pct_gross"]) / 100 - cost, i0=i0, sym=r["symbol"]))
    return out
def px(tr, T):
    i = bisect.bisect_right(tr["tsl"], T) - 1
    return tr["rows"][i][4] if i >= 0 else None
def boot(x, it=4000, seed=7, f=S.fmean):
    if len(x) < 2: return (None, None)
    r = random.Random(seed); ms = sorted(f(r.choices(x, k=len(x))) for _ in range(it))
    return ms[int(0.025 * it)], ms[int(0.975 * it)]
def summ(x):
    if not x: return dict(n=0)
    ci = boot(x); cim = boot(x, f=S.median)
    return dict(n=len(x), mean=round(S.fmean(x), 4), median=round(S.median(x), 4), ci_mean=[round(v, 4) for v in ci] if ci[0] is not None else None,
                ci_median=[round(v, 4) for v in cim] if cim[0] is not None else None, win=round(sum(v > 0 for v in x) / len(x), 3))
def feats(tr, T):
    """features at decision time T using only candles COMPLETED by T (start <= T-60). None if < 3 complete candles since entry."""
    rows, t = tr["rows"], tr["t"]; i0 = tr["i0"]; j = bisect.bisect_right(tr["tsl"], T - 60) - 1
    if j < i0 + 2: return None
    seg = rows[i0:j + 1]; e = rows[i0][4]; c = seg[-1][4]
    def vwin(end_t, n):   # volume in the n minutes ending at end_t (candle starts in (end_t-n*60, end_t])
        return sum(x[5] or 0 for x in seg if end_t - n * 60 < x[0] <= end_t)
    last = seg[-1][0]
    v3 = vwin(last, 3); v5 = vwin(last, 5)
    pk3 = max(sum(y[5] or 0 for y in seg if x[0] - 180 < y[0] <= x[0]) for x in seg) or 1e-9
    pkc = max(x[4] for x in seg); reds = 0
    for x in reversed(seg):
        if x[4] < x[1]: reds += 1
        else: break
    def wick(x): rng = x[2] - x[3]; return (x[2] - max(x[1], x[4])) / rng if rng > 0 else 0.0
    vol15 = vwin(last, 15) / 15; v1 = seg[-1][5] or 0
    return dict(vr3=v3 / pk3, dd_pk=c / pkc - 1, reds=reds, wick1=wick(seg[-1]), wick3=S.fmean(wick(x) for x in seg[-3:]), runup=c / e - 1,
                held_min=(T - t) / 60, v1_rel15=v1 / vol15 if vol15 > 0 else 0, ret5=c / (px(tr, T - 300 - 60) or c) - 1)
