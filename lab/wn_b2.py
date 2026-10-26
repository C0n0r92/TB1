#!/usr/bin/env python3
"""PAPER ONLY. Winners batch-2 replication + exit-rule study. Batch 1 (benji/bystevenr/neodot/onlyzhynx) = discovery,
batch 2 (HMDW/B1uH/82uF/HJp8, other wallets, found independently) = held out. Exit rules picked on batch 1 only.
Costs real: 4.7% if approx mcap < $1M else 2%; stop/trail exits get extra 2 pts slip. Uses data/cl/wn 1m GT candles.
-> out/wn_b2.json, out/wn_b2.md"""
import csv, json, os, glob, random, bisect, statistics as S, datetime as dt
from cl_sim import sim, boot, DEFAULT, OUT
W = list(csv.DictReader(open("/workspace/onchain-intel/winners/trades.csv")))
B1 = ("9PB1", "AH75", "5o3k", "zhYn")
fl = lambda x: float(x) if x not in ("", None) else None
ts_ = lambda s: int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
C = {}
for p in glob.glob("data/cl/wn/*.json"):
    d = json.load(open(p)); C[(d["mint"], d["t"])] = d
med = lambda x: round(S.median(x), 4) if x else None
summ = lambda x: dict(n=len(x), mean=round(S.fmean(x), 4) if x else None, median=med(x), ci=[round(v, 4) if v is not None else None for v in boot(x)], win=round(sum(v > 0 for v in x) / len(x), 3) if x else None)
def trail(rows, t, cost, trail_p, arm, sl=0.25, tmax=6 * 3600):
    """enter at close of candle at/after t+10s; exit on close <= peak*(1-trail) once peak >= entry*(1+arm) (arm=0: always armed),
    hard stop close <= entry*(1-sl), time stop tmax / end of data."""
    tsl = [x[0] for x in rows]; i = bisect.bisect_left(tsl, t + 10 - 59)
    if i >= len(rows): return None
    e = rows[i][4]; pk = e
    for x in rows[i + 1:]:
        c = x[4]
        if x[0] - rows[i][0] > tmax: return c / e - 1 - cost
        pk = max(pk, x[2] or c)
        if c <= e * (1 - sl): return c / e - 1 - cost - 0.02
        if pk >= e * (1 + arm) and c <= pk * (1 - trail_p): return min(c / e, 10) - 1 - cost - 0.02
    return rows[-1][4] / e - 1 - cost
RULES = [(tp, arm) for tp in (0.15, 0.2, 0.3, 0.4) for arm in (0, 0.2, 0.5, 1.0)]
res = {}
for b in ("b1", "b2"):
    rs = [r for r in W if (r["wallet"][:4] in B1) == (b == "b1")]
    act, fxd, fxq, d30, d120, rd30, rd120, tr = [], [], [], [], [], [], [], {k: [] for k in RULES}; cov = 0; rnd = random.Random(17)
    for r in rs:
        t = ts_(r["entry_time"]); d = C.get((r["mint"], t))
        if not d or len(d["rows"]) < 10: continue
        rows = [x for x in d["rows"] if x[4] and x[4] > 0]; tsl = [x[0] for x in rows]
        if not rows or rows[0][0] > t or rows[-1][0] < t: continue
        cov += 1; m = fl(r["mcap_at_entry_usd_approx"]); cost = 0.02 if (m and m >= 1e6) else 0.047
        act.append(fl(r["pnl_pct_gross"]) / 100 - cost)
        px = lambda T: rows[bisect.bisect_right(tsl, T) - 1][4] if bisect.bisect_right(tsl, T) > 0 else None
        cs = dict(rows=rows, supply=1e9)
        for cfg, L in ((DEFAULT, fxd), (dict(DEFAULT, sl=0.20, tp=0.30, hold_m=30), fxq)):
            s = sim(cs, t, dict(cfg, cost_pump=cost, cost_big=cost))
            if s: L.append(s["ret"])
        for k in RULES:
            v = trail(rows, t, cost, *k)
            if v is not None: tr[k].append(v)
        te = ts_(r["exit_time"]); pe = px(te)
        if pe and rows[-1][0] >= te + 1800: d30.append(px(te + 1800) / pe - 1)
        if pe and rows[-1][0] >= te + 7200: d120.append(px(te + 7200) / pe - 1)
        for _ in range(10):
            T = t + rnd.uniform(0, 4 * 3600); p0 = px(T)
            if p0 and rows[-1][0] >= T + 1800: rd30.append(px(T + 1800) / p0 - 1)
            if p0 and rows[-1][0] >= T + 7200: rd120.append(px(T + 7200) / p0 - 1)
    res[b] = dict(trades=len(rs), with_candles=cov, actual_realcost=summ(act), fixed_dflt_SL25TP50_2h=summ(fxd), fixed_quick_SL20TP30_30m=summ(fxq),
                  drift30_after_exit=summ(d30), drift120_after_exit=summ(d120), random_drift30=summ(rd30), random_drift120=summ(rd120),
                  trail={f"trail{int(a*100)}_arm{int(c*100)}": summ(v) for (a, c), v in tr.items()})
best = max(res["b1"]["trail"].items(), key=lambda kv: (kv[1]["mean"] if kv[1]["mean"] is not None else -9))
res["picked_on_b1"] = best[0]; res["picked_b2"] = res["b2"]["trail"][best[0]]
json.dump(res, open(os.path.join(OUT, "wn_b2.json"), "w"), indent=1)
print(json.dumps({b: {k: v for k, v in res[b].items() if k != "trail"} for b in ("b1", "b2")}, indent=1))
for k in res["b1"]["trail"]: print(k, res["b1"]["trail"][k]["n"], res["b1"]["trail"][k]["mean"], res["b1"]["trail"][k]["median"], "| b2", res["b2"]["trail"][k]["n"], res["b2"]["trail"][k]["mean"], res["b2"]["trail"][k]["median"], res["b2"]["trail"][k]["ci"])
print("picked", best[0], res["picked_b2"])
