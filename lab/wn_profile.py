#!/usr/bin/env python3
"""Phase 2 profile of winners/ trades (PAPER ONLY). -> out/wn_profile.json. Uses data/cl/wn candles (GT 1m) where present."""
import csv, json, os, glob, random, bisect, statistics as S, datetime as dt
from cl_sim import sim, boot, DEFAULT, DUB, OUT
W = list(csv.DictReader(open("/workspace/onchain-intel/winners/trades.csv")))
fl = lambda x: float(x) if x not in ("", None) else None
ts_ = lambda s: int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
LBL = {"9PB1": "benji", "AH75": "bystevenr", "5o3k": "neodot", "zhYn": "onlyzhynx"}
P = dict(n=len(W))
def med(x): return round(S.median(x), 4) if x else None
# 1) feature contrast winners (net5>0) vs losers, overall and per wallet
F = ["age_at_entry_h", "mcap_at_entry_usd_approx", "vol_1h_usd", "vol_6h_usd", "chg_5m_pct", "chg_1h_pct", "n_1m_candles_30m", "up_share_1m_30m",
     "size_in_usd", "hold_min", "smart_co_buys_30m", "avoid_co_buys_30m", "n_buys", "n_sells"]
def contrast(rs):
    out = {}
    for k in F:
        w = [fl(r[k]) for r in rs if fl(r["pnl_pct_net5"]) > 0 and fl(r[k]) is not None]; l = [fl(r[k]) for r in rs if fl(r["pnl_pct_net5"]) <= 0 and fl(r[k]) is not None]
        out[k] = dict(n_win=len(w), med_win=med(w), n_lose=len(l), med_lose=med(l))
    return out
P["contrast_all"] = contrast(W)
P["contrast_by_wallet"] = {LBL[k]: contrast([r for r in W if r["wallet"].startswith(k)]) for k in LBL}
P["pumpfun_entry"] = {v: dict(n=sum(1 for r in W if r["entry_via_pumpfun"] == v), win=sum(1 for r in W if r["entry_via_pumpfun"] == v and fl(r["pnl_pct_net5"]) > 0),
                              med=med([fl(r["pnl_pct_net5"]) for r in W if r["entry_via_pumpfun"] == v])) for v in ("True", "False")}
# 2) time of day (Dublin), 4h buckets
tod = {}
for r in W:
    h = dt.datetime.fromtimestamp(ts_(r["entry_time"]), DUB).hour // 4 * 4; tod.setdefault(h, []).append(fl(r["pnl_pct_net5"]))
P["tod_dublin"] = {f"{h:02d}-{h+4:02d}": dict(n=len(v), win=sum(x > 0 for x in v), med=med(v), mean=round(S.fmean(v), 2)) for h, v in sorted(tod.items())}
# 3) mcap / size buckets
def bucket(k, edges):
    o = {}
    for r in W:
        x = fl(r[k]);
        if x is None: continue
        b = next((f"<{e:g}" for e in edges if x < e), f">={edges[-1]:g}"); o.setdefault(b, []).append(fl(r["pnl_pct_net5"]))
    return {b: dict(n=len(v), win=sum(x > 0 for x in v), med=med(v), mean=round(S.fmean(v), 2)) for b, v in o.items()}
P["by_mcap"] = bucket("mcap_at_entry_usd_approx", [10e3, 30e3, 100e3, 1e6]); P["by_size_usd"] = bucket("size_in_usd", [150, 500, 2000])
P["by_hold"] = bucket("hold_min", [2, 10, 30, 120, 720])
# 4) candle-based: random entries same token (+-4h, same hold), fixed exits on their entries, post-exit drift
C = {}
for p in glob.glob("data/cl/wn/*.json"):
    d = json.load(open(p)); C[(d["mint"], d["t"])] = d
rnd = random.Random(17); actcap, rdrift30, rdrift120 = [], [], []; act, rand, fx_d, fx_q, drift30, drift120, cov = [], [], [], [], [], [], 0
q = dict(DEFAULT, sl=0.20, tp=0.30, hold_m=30)
for r in W:
    t = ts_(r["entry_time"]); d = C.get((r["mint"], t))
    if not d or len(d["rows"]) < 10: continue
    rows = [x for x in d["rows"] if x[4] and x[4] > 0]; tsl = [x[0] for x in rows]
    if not rows or rows[0][0] > t or rows[-1][0] < t: continue
    cov += 1; hold = fl(r["hold_min"]) * 60; a = fl(r["pnl_pct_gross"]) / 100 - 0.05; act.append(a); actcap.append(min(10, 1 + fl(r['pnl_pct_gross']) / 100) - 1 - 0.05)
    def px(T):
        i = bisect.bisect_right(tsl, T) - 1; return rows[i][4] if i >= 0 else None
    for _ in range(10):
        T = t + rnd.choice([-1, 1]) * rnd.uniform(300, 4 * 3600)
        if T < rows[0][0] or T + hold > rows[-1][0] + 600: continue
        p0, p1 = px(T), px(T + hold)
        if p0 and p1: rand.append(min(10, p1 / p0) - 1 - 0.05)
        if p0 and rows[-1][0] >= T + 1800 and px(T + 1800): rdrift30.append(px(T + 1800) / p0 - 1)
        if p0 and rows[-1][0] >= T + 7200 and px(T + 7200): rdrift120.append(px(T + 7200) / p0 - 1)
    cs = dict(rows=rows, supply=1e9)
    for cfg, L in ((DEFAULT, fx_d), (q, fx_q)):
        s = sim(cs, t, dict(cfg, cost_pump=0.05, cost_big=0.05))
        if s: L.append(s["ret"])
    te = ts_(r["exit_time"]); pe = px(te)
    if pe and rows[-1][0] >= te + 1800 and px(te + 1800): drift30.append(px(te + 1800) / pe - 1)
    if pe and rows[-1][0] >= te + 7200 and px(te + 7200): drift120.append(px(te + 7200) / pe - 1)
summ = lambda x: dict(n=len(x), mean=round(S.fmean(x), 4) if x else None, median=med(x), ci=boot(x), win=round(sum(v > 0 for v in x) / len(x), 3) if x else None)
P["candles"] = dict(trades_with_candles=cov, actual_net5=summ(act), random_same_token_same_hold_net5=summ(rand), actual_net5_capped10x=summ(actcap), random_time_drift_30m=summ(rdrift30), random_time_drift_120m=summ(rdrift120),
                    their_entries_fixed_exit_dflt_net5=summ(fx_d), their_entries_fixed_exit_quick_net5=summ(fx_q),
                    drift_30m_after_their_exit=summ(drift30), drift_120m_after_their_exit=summ(drift120))
json.dump(P, open(os.path.join(OUT, "wn_profile.json"), "w"), indent=1, default=str)
print(json.dumps(P["candles"], default=str, indent=1)); print(json.dumps(P["tod_dublin"])); print(json.dumps(P["by_mcap"])); print(json.dumps(P["by_hold"])); print(json.dumps(P["pumpfun_entry"]))
