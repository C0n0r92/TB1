#!/usr/bin/env python3
"""Backfill replay (Zero 2026-10-23; PAPER ONLY). Replays scan.py-style scoring on 1-min GeckoTerminal candles for a random
on-chain sample of pump.fun->PumpSwap graduations, then tests baseline radar / partial-guard radar / survivor-momentum grid
with backtest.simulate (costs unchanged) on DAY-split holdout (last 30% of Dublin nights, fixed before results).
Inputs: data/backfill/{migrations.jsonl,candles1m/,solusd_1h.json}; live calibration: /workspace/runner-radar/scanned.jsonl.
Outputs: out/backfill.json, out/bf_trades.csv, out/leaderboard_extra_BF.json, data/backfill/need_more.json."""
import collections, bisect, csv, json, math, os, random, statistics, sys, time, collections, datetime as dt
from labcore import load_config, night_of, atomic_write, iso, OUT, DUB, next_dublin_close, read_jsonl
import backtest as B, scoring
import survivor_momentum as SMM
BF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backfill"); C1 = os.path.join(BF, "candles1m")
K = 206_900_000 * 85.0            # PumpSwap migration reserves (tokens x SOL); calibrated by C_LIQ below
SUPPLY = 1e9
HOLDOUT_FRAC = 0.30               # pre-registered: last 30% of nights untouched
HOLDOUT_FIRST_NIGHT = "2026-10-14"
SCAN_STEP = 600                   # live radar cadence ~10.5 min
def ramp(x, lo, hi, pts): return 0.0 if x <= lo else float(pts) if x >= hi else pts * (x - lo) / (hi - lo)

# ---------- SOL/USD ----------
_sol = json.load(open(os.path.join(BF, "solusd_1h.json")))["rows"]; _solt = [r[0] for r in _sol]
_sold = json.load(open("/workspace/onchain-intel/data/solusd.json"))
def solusd(t):
    i = bisect.bisect_right(_solt, t - 3600) - 1          # last COMPLETED hour
    if i >= 0 and t - _solt[i] < 3 * 3600: return _sol[i][4]
    return _sold.get(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()) or 105.0

class Pool:
    def __init__(self, rows):
        self.r = rows; self.t = [x[0] for x in rows]
        self.cv = [0.0]
        for x in rows: self.cv.append(self.cv[-1] + x[5])
    def idx_done(self, T):                                 # number of candles complete by time T (start+60 <= T)
        return bisect.bisect_right(self.t, T - 60)
    def close_at(self, T):
        i = self.idx_done(T); return self.r[i - 1][4] if i else None
    def vol(self, T0, T1):                                 # complete candles with T0 <= start, start+60 <= T1
        a = bisect.bisect_left(self.t, T0); b = self.idx_done(T1); return self.cv[b] - self.cv[a] if b > a else 0.0
    def c5(self):                                          # 5-min candles (start-aligned)
        out = []
        for x in self.r:
            s = x[0] // 300 * 300
            if out and out[-1][0] == s: o = out[-1]; out[-1] = (s, o[1], max(o[2], x[2]), min(o[3], x[3]), x[4], o[5] + x[5])
            else: out.append((s, x[1], x[2], x[3], x[4], x[5]))
        return out

C_LIQ = 1.0
def liq_model(p, t): return C_LIQ * 2 * math.sqrt(K * p * solusd(t))

def feats(P, t, t0):
    p = P.close_at(t)
    if p is None: return None
    p5 = P.close_at(t - 300) or P.r[0][1]; p60 = P.close_at(t - 3600) or P.r[0][1]
    v5, vh1 = P.vol(t - 300, t), P.vol(t - 3600, t)
    liq = liq_model(p, t); mcap = p * SUPPLY
    return {"t": t, "price": p, "m5": 100 * (p / p5 - 1), "h1": 100 * (p / p60 - 1), "accel": v5 / (vh1 / 12) if vh1 > 0 else 0,
            "liq": liq, "mcap": mcap, "liq_mcap": liq / mcap, "age_h": (t - t0) / 3600, "last_trade_age": t - 60 - P.r[P.idx_done(t) - 1][0]}

def known_pts(f):
    """Reconstructable part of scan.score: accel 18, m5 12 (-10 chase), h1 8, liq/mcap 10, +8 revoked (pump mints), age 5/2."""
    m = ramp(f["m5"], 2, 20, 12) - (10 if f["m5"] > 60 else 0)
    return (ramp(f["accel"], 1, 3, 18) + m + ramp(f["h1"], 0, 150, 8) + ramp(f["liq_mcap"], 0.05, 0.2, 10) + 8
            + (5 if 0.5 <= f["age_h"] <= 3 else 2))

def pass_pre(f): return 0.25 <= f["age_h"] <= 6 and 50_000 <= f["mcap"] <= 2_000_000 and f["liq"] >= 15_000

def load_pool(pool):
    p = os.path.join(C1, pool + ".json")
    if not os.path.exists(p): return None, "unfetched"
    d = json.load(open(p))
    if d.get("status") != "ok": return None, d.get("status")
    return d, "ok"

# ---------- calibration on tonight's live scans ----------
def calibrate():
    global C_LIQ
    live = read_jsonl("/workspace/runner-radar/scanned.jsonl"); rows = []
    for r in live:
        d, st = load_pool(r["pair"])
        if not d: continue
        t = dt.datetime.fromisoformat(r["ts"]).timestamp(); P = Pool(d["rows"])
        if P.t[0] > t - 600 or d.get("fetched_at", 0) < t + 60: continue   # need candles before the scan, fetched after it
        t0 = t - r["age_h"] * 3600
        f = feats(P, t, t0)
        if not f: continue
        rows.append((r, f)); r["_stair"] = stair(P, t)
    cs = [r["liq"] / (2 * math.sqrt(K * r["price"] * solusd(dt.datetime.fromisoformat(r["ts"]).timestamp()))) for r, f in rows if r["price"] and r["liq"]]
    C_LIQ = statistics.median(cs) if cs else 1.0
    out = {"n_rows": len(rows), "n_pairs": len({r["pair"] for r, _ in rows}), "c_liq": C_LIQ,
           "c_liq_p10_p90": [sorted(cs)[int(.1 * len(cs))], sorted(cs)[int(.9 * len(cs))]] if cs else None}
    def err(a, b): return statistics.median([abs(x - y) for x, y in zip(a, b)]) if a else None
    def corr(a, b):
        if len(a) < 3: return None
        ma, mb = statistics.fmean(a), statistics.fmean(b); sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((y - mb) ** 2 for y in b))
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else None
    cmp = {}
    for k in ("m5", "h1", "accel"):
        a = [r["features"][k] for r, f in rows]; b = [f[k] for r, f in rows]
        cmp[k] = {"median_abs_err": err(a, b), "corr": corr(a, b)}
    for k in ("price", "mcap", "liq"):
        a = [r[k] for r, f in rows]; b = [liq_model(r["price"], f["t"]) if k == "liq" else f[k] for r, f in rows]   # liq: model at the LIVE price
        cmp[k] = {"median_rel_err": statistics.median([abs(y / x - 1) for x, y in zip(a, b) if x]) if a else None}
    b2 = [f["liq"] for r, f in rows]; a2 = [r["liq"] for r, f in rows]
    cmp["liq_from_candle_price"] = {"median_rel_err": statistics.median([abs(y / x - 1) for x, y in zip(a2, b2) if x]) if a2 else None}
    out["feature_agreement"] = cmp
    st = [r for r, f in rows if r.get("_stair") is not None and r["_stair"] >= 0.85]
    out["live_staircase"] = {"n_rows_stair85": len(st), "n_rows_with_stair": sum(r.get("_stair") is not None for r, f in rows),
        "live_pass": sum(1 for r in st if not r.get("rejects") and r.get("score", 0) >= 55),
        "top10_median": statistics.median([r["top10"] for r in st if r.get("top10") is not None]) if any(r.get("top10") is not None for r in st) else None,
        "top10_median_nonstair": statistics.median([r["top10"] for r, f in rows if r.get("top10") is not None and r.get("_stair") is not None and r["_stair"] < 0.85]) if rows else None,
        "rejects": collections.Counter(x.split(" ")[0] for r in st for x in r.get("rejects", [])).most_common(6)}
    # missing mass: live score (pre-guard) minus the reconstructable part computed from the LIVE features
    miss, kn_live, kn_rep, live_sc = [], [], [], []
    for r, f in rows:
        fl = {**r["features"], "age_h": r["age_h"]}
        if r["features"].get("liq_mcap") is None: continue
        kl = known_pts(fl); pre = r["score"] + ((r.get("guard") or {}).get("guard_penalty") or 0)
        if any("launch" in x.lower() or "scout" in x.lower() for x in r.get("reasons", [])): pass
        miss.append(pre - kl); kn_live.append(kl); kn_rep.append(known_pts(f)); live_sc.append(pre)
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]
    out["missing_mass"] = {"n": len(miss), "p10": q(miss, .1), "p50": q(miss, .5), "p90": q(miss, .9), "max": max(miss), "min": min(miss)} if miss else None
    out["known_pts_live_vs_replay"] = {"median_abs_err": err(kn_live, kn_rep), "corr": corr(kn_live, kn_rep)}
    out["corr_known_vs_missing"] = corr(kn_live, miss)
    # pass/fail confusion: live (score>=55 pre-guard, no scan.py rejects) vs replay with central imputation
    imp = out["missing_mass"]["p50"] if miss else 0
    conf = collections.Counter()
    for r, f in rows:
        scan_rej = [x for x in r["rejects"] if not any(k in x for k in ("young", "holder", "crash", "spike", "liquidity fell", "danger", "LP only", "creator", "wash", "mcap per holder", "launch", "Scout", "scout"))]
        live_pass = (r["score"] + ((r.get("guard") or {}).get("guard_penalty") or 0)) >= 55 and not scan_rej
        rep_pass = pass_pre(f) and known_pts(f) + imp >= 55
        conf[f"live{'P' if live_pass else 'F'}_rep{'P' if rep_pass else 'F'}"] += 1
    out["confusion_p50"] = dict(conf)
    # rate-matched imputation: smallest constant whose replay pass count >= live pass count on the same rows
    def lp(r):
        rej = [x for x in r["rejects"] if any(k in x for k in ("sells", "top10", "rugged", "health", "authority"))]
        return (r["score"] + ((r.get("guard") or {}).get("guard_penalty") or 0)) >= 55 and not rej
    nl = sum(lp(r) for r, f in rows); rm = None
    for i in range(0, 400):
        v = i / 10
        if sum(pass_pre(f) and known_pts(f) + v >= 55 for r, f in rows) >= nl: rm = v; break
    out["live_pass_rows"] = nl; out["imp_rate_matched"] = rm
    conf = collections.Counter()
    for r, f in rows: conf[f"live{'P' if lp(r) else 'F'}_rep{'P' if pass_pre(f) and known_pts(f) + (rm or 0) >= 55 else 'F'}"] += 1
    out["confusion_rate_matched"] = dict(conf)
    out["missing_components"] = "buy ratio 5m (6) + 1h (4), buyer growth (12), top10 (0-12), insiders (-5), copycats (-8); scan.py rejects top10>35 / sells>>buys / rugged unobservable"
    return out

# ---------- replay one pool ----------
def replay(m, P, imps):
    t0 = m["t_mig"]; out = {k: None for k in imps}; guard = {k: None for k in imps}; prevs = []; first_pre = None; maxkn = 0
    t = (int(t0 + 900) // SCAN_STEP + 1) * SCAN_STEP
    while t <= t0 + 6 * 3600 and t <= P.t[-1] + 3600:
        f = feats(P, t, t0)
        if f and f["last_trade_age"] <= 1800 and pass_pre(f):
            if first_pre is None: first_pre = t
            kn = known_pts(f); maxkn = max(maxkn, kn)
            # partial rugguard: age>=45 min, m5 crash/spike, -6 dip, liq drop >=30% vs a prefilter scan in last 90 min
            grej = f["age_h"] < 0.75 or f["m5"] <= -50 or f["m5"] >= 150 or any(q["liq"] * 0.7 >= f["liq"] for q in prevs if t - q["t"] <= 5400)
            gpen = 6 if -50 < f["m5"] <= -25 else 0
            for k, v in imps.items():
                if out[k] is None and kn + v >= 55: out[k] = {**f, "score": round(kn + v, 1), "known": round(kn, 1)}
                if guard[k] is None and not grej and kn + v - gpen >= 55: guard[k] = {**f, "score": round(kn + v - gpen, 1), "known": round(kn, 1)}
            prevs.append(f)
        t += SCAN_STEP
    return out, guard, first_pre, maxkn

def stair(P, t):
    """POST-HOC DIAGNOSTIC (not a rule): share of up-closing 1-min candles among the last 20 complete before t.
    Bot 'staircase' pumps (steady up-ticks on flat volume, then one -99% candle) score high here; the live radar's
    missing top10/holder inputs are what would normally reject them."""
    i = P.idx_done(t); w = P.r[max(0, i - 20):i]
    return sum(x[4] > x[1] for x in w) / len(w) if len(w) >= 10 else None

def entry(m, f): return {"t": f["t"], "price": f["price"], "liq": f["liq"], "token": m["mint"], "pair": m["pool"], "age_h": f["age_h"],
                         "mcap": f["mcap"], "score": f["score"], "symbol": m["mint"][:6], "day": night_of(f["t"])}

def sm_decide(e, cs, T, X, cap):
    t_in = e["t"] + T * 60; ec = [c for c in cs if c[0] >= t_in]
    if not ec or ec[0][0] - t_in > 1800: return "fail", "dead", {}
    t_dec, p = ec[0][0], ec[0][1]; chg = p / e["price"] - 1; info = {"t_dec": t_dec, "chg": chg}
    if chg <= 0: return "fail", "price not up", info
    if cap is not None and chg > cap: return "fail", "chase cap", info
    liq = liq_model(p, t_dec); lr = liq / e["liq"] - 1; info.update(liq=liq, liq_chg=lr, liq_src="ESTIMATE model")
    if lr < X: return "fail", "liq", info
    if liq < SMM.SANITY["min_liq"]: return "fail", "sanity liq", info
    if p * SUPPLY / liq > SMM.SANITY["max_mcap_liq"]: return "fail", "sanity mcap/liq", info
    return "pass", "", info

def run(cfg, V, ents, C5, now, split_nights, T=None, X=None, cap=None):
    res, dec = [], []
    for e in ents:
        cs = C5[e["pair"]]
        if T is not None:
            st, why, info = sm_decide(e, cs, T, X, cap); dec.append({"e": e, "status": st, "why": why, **info})
            if st != "pass": continue
        else: info = {}; dec.append({"e": e, "status": "pass"})
        r = B.simulate(cfg, V, e, cs, {}, now); r["e"] = e; r["info"] = info; res.append(r)
    res.sort(key=lambda r: (r.get("t_entry", r["e"]["t"]), -(r["e"].get("score") or 0)))
    oe, trades = [], []
    for r in res:
        if r["status"] in ("closed", "open"):
            oe = [x for x in oe if x > r["t_entry"]]
            if len(oe) >= cfg["sim"]["max_open"]: r.update(status="skip", why="max_open")
            else: oe.append(r["exit_t"] or 1e18)
        r["t"] = r["e"]["t"]; r["is_oos"] = night_of(r["t"]) in split_nights; trades.append(r)
    return trades, dec

def main():
    cfg = load_config(); now = time.time()
    cal = calibrate()
    migs = read_jsonl(os.path.join(BF, "migrations.jsonl"))
    mm = cal["missing_mass"] or {"p10": 10, "p50": 20, "p90": 30}
    imps = {"low": mm["p50"], "central": cal["imp_rate_matched"] if cal.get("imp_rate_matched") is not None else mm["p50"], "high": mm["p90"]}   # pre-registered
    st_by_day = collections.defaultdict(collections.Counter); pools = {}; C5 = {}; need_more = []
    sig = {k: [] for k in imps}; gsig = {k: [] for k in imps}; pre_cnt = collections.Counter(); per_pool = []
    for m in migs:
        d, st = load_pool(m["pool"]); st_by_day[m["day"]][st] += 1
        if not d: continue
        P = Pool(d["rows"]); C5[m["pool"]] = P.c5()
        o, g, fp, mk = replay(m, P, imps)
        per_pool.append({"mint": m["mint"], "pool": m["pool"], "day": m["day"], "n1m": len(d["rows"]), "first_pre": fp, "max_known": round(mk, 1),
                         "peak_mcap": max(x[2] for x in d["rows"]) * SUPPLY, "span_h": (d["rows"][-1][0] - m["t_mig"]) / 3600})
        if fp: pre_cnt[m["day"]] += 1
        for k in imps:
            if o[k]: sig[k].append({**entry(m, o[k]), "stair": stair(P, o[k]["t"])})
            if g[k]: gsig[k].append({**entry(m, g[k]), "stair": stair(P, g[k]["t"])})
        e = o["central"] or g["central"]
        if e and len(d["rows"]) >= 1000:
            dl = min(e["t"] + 24 * 3600, next_dublin_close(e["t"] + 3600))
            if d["rows"][-1][0] + 60 < dl: need_more.append({"pool": m["pool"], "last": d["rows"][-1][0], "deadline": dl})
    atomic_write(os.path.join(BF, "need_more.json"), json.dumps(need_more))
    nights = sorted({night_of(m["t_mig"]) for m in migs if load_pool(m["pool"])[0]})
    # PRE-REGISTERED (23:20Z 10-23, before any result): window nights 2026-09-25..2026-10-22 = 28; last ceil(30%) = 9 -> 10-14..10-22
    hold = {n for n in nights if n >= HOLDOUT_FIRST_NIGHT} | {HOLDOUT_FIRST_NIGHT}; nh = 9
    base = {k: v for k, v in cfg["variants"][0].items() if k != "name"}
    specs = []
    for k in imps:
        specs.append(({**base, "name": f"BF_A_radar_{k}", "bf_rule": "radar_replay_v1", "bf_imp": k}, sig[k], None, None, None))
        specs.append(({**base, "name": f"BF_G_partialguard_{k}", "bf_rule": "partialguard_replay_v1", "bf_imp": k}, gsig[k], None, None, None))
    for T in SMM.TS:
        for X in SMM.XS:
            for cap in SMM.CAPS:
                V = {**base, "name": "BF_" + SMM.vname(T, X, cap, "_LIQMODEL"), "entry_delay_min": T, "survive_max_dd": -1.0, "survive_max_up": 99,
                     "survive_min_liq_ratio": 0, "min_score": 0, "sm_liq_up": X, "sm_cap": cap, "bf_rule": "sm_replay_v1", "bf_imp": "central"}
                specs.append((V, sig["central"], T, X, cap))
    DRY = os.environ.get("BF_DRY") == "1"          # dry: don't touch shared data/variants_tried.json
    n_tried = len(specs) if DRY else scoring.variants_tried([s[0] for s in specs])
    split_t = min([e["t"] for e in sig["central"] if e["day"] in hold] or [now])
    rows, cells, trades_out = [], {}, []
    for V, U, T, X, cap in specs:
        trades, dec = run(cfg, V, U, C5, now, hold, T, X, cap)
        dd = [{"status": d["status"] if d["status"] != "fail" else "fail", **d} for d in dec]
        for d in dd: d.setdefault("status", "pass")
        row = SMM.board_row(cfg, V, trades, [{"status": d["status"]} for d in dec] + [{"status": "no_liq"}] * 0, split_t, n_tried)
        row["family"] = "backfill"; row["uncovered"] = 0
        cl = [t for t in trades if t["status"] == "closed"]
        bi = B.stats(cfg, [t for t in cl if not t["is_oos"]]); bo = B.stats(cfg, [t for t in cl if t["is_oos"]])
        row["note"] = (f"PAPER BACKFILL replay (random on-chain graduations sample, ~3.5%/day); imputation={V['bf_imp']}; "
                       f"liq=MODEL; holdout=last {nh} nights; {len(U)} candidate signals")
        rows.append(row)
        cells[V["name"]] = {"n_cand": len(U), "decisions": dict(collections.Counter(d["status"] for d in dec)),
                            "closed": len(cl), "in": {k: bi.get(k) for k in ("trades", "net_pnl", "mean_ret", "median_ret", "win_rate", "rug_rate", "ci_lo", "ci_hi")},
                            "out": {k: bo.get(k) for k in ("trades", "net_pnl", "mean_ret", "median_ret", "win_rate", "rug_rate", "ci_lo", "ci_hi")},
                            "score": {k: row[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                            "mc_dd": [row["mc_dd_p5"], row["mc_dd_p50"], row["mc_dd_p95"]], "net_ex_best": row["net_ex_best_trade"],
                            "nights": row["nights"], "nights_profitable": row["nights_profitable"],
                            "exits": dict(collections.Counter(t.get("exit") for t in cl)), "skipped": dict(collections.Counter(t.get("why") for t in trades if t["status"] == "skip"))}
        for t in trades:
            trades_out.append({"variant": V["name"], "mint": t["e"]["token"], "pool": t["e"]["pair"], "signal_ts": iso(t["e"]["t"]), "night": t["e"]["day"],
                               "oos": t["is_oos"], "status": t["status"], "score_hat": t["e"]["score"], "age_h": round(t["e"]["age_h"], 2),
                               "mcap": round(t["e"]["mcap"]), "liq_model": round(t["e"]["liq"]), "exit": t.get("exit", ""), "ret": round(t.get("ret", 0), 3),
                               "pnl": round(t.get("pnl", 0), 2), "rug": t.get("rug", ""), "stair20": t["e"].get("stair")})
    fam = {}
    for T in SMM.TS:
        for X in SMM.XS: fam[f"T{T}_X{int(X*100)}:cap"] = [(9.0 if c is None else c, "BF_" + SMM.vname(T, X, c, "_LIQMODEL")) for c in SMM.CAPS]
        for c in SMM.CAPS: fam[f"T{T}_cap{SMM.capname(c)}:X"] = [(X, "BF_" + SMM.vname(T, X, c, "_LIQMODEL")) for X in SMM.XS]
    for X in SMM.XS:
        for c in SMM.CAPS: fam[f"X{int(X*100)}_cap{SMM.capname(c)}:T"] = [(T, "BF_" + SMM.vname(T, X, c, "_LIQMODEL")) for T in SMM.TS]
    fam["radar:imp"] = [(i, f"BF_A_radar_{k}") for i, k in enumerate(imps)]; fam["guard:imp"] = [(i, f"BF_G_partialguard_{k}") for i, k in enumerate(imps)]
    lf = scoring.lucky_flags(rows, fam)
    for r in rows: r["lucky_number"] = lf.get(r["variant"], "n/a (0 trades)" if not r["trades"] else "n/a (<5 trades)")
    atomic_write(os.path.join(OUT, "leaderboard_extra_BF.json"), json.dumps(rows, indent=0, default=str))
    # survivorship / coverage
    days = sorted(st_by_day)
    rep = {"generated": iso(now), "calibration": cal, "imputations": imps, "nights": nights, "holdout_nights": sorted(hold), "split_t": iso(split_t),
           "migrations_sampled": len(migs), "coverage_by_day": {d: dict(st_by_day[d]) for d in days},
           "prefilter_pass_by_day": dict(pre_cnt), "signals_by_day": {k: dict(collections.Counter(e["day"] for e in v)) for k, v in sig.items()},
           "guard_signals_by_day": {k: dict(collections.Counter(e["day"] for e in v)) for k, v in gsig.items()},
           "n_signals": {k: len(v) for k, v in sig.items()}, "n_guard_signals": {k: len(v) for k, v in gsig.items()},
           "need_more_candles": len(need_more), "variants_tried": n_tried, "cells": cells,
           "pools": {"n": len(per_pool), "reach_prefilter": sum(1 for p in per_pool if p["first_pre"]),
                     "median_n1m": statistics.median([p["n1m"] for p in per_pool]) if per_pool else None,
                     "capped_1000": sum(p["n1m"] >= 1000 for p in per_pool)}}
    atomic_write(os.path.join(OUT, "backfill.json"), json.dumps(rep, indent=1, default=str))
    json.dump(per_pool, open(os.path.join(BF, "per_pool.json"), "w"))
    if trades_out:
        with open(os.path.join(OUT, "bf_trades.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(trades_out[0].keys())); w.writeheader(); w.writerows(trades_out)
    print(json.dumps({"cal": {k: cal[k] for k in ("n_rows", "n_pairs", "c_liq", "missing_mass", "confusion_p50", "confusion_rate_matched", "imp_rate_matched", "known_pts_live_vs_replay")},
                      "imps": imps, "n_sig": rep["n_signals"], "n_gsig": rep["n_guard_signals"], "pools": rep["pools"], "hold": sorted(hold), "tried": n_tried}, default=str, indent=0))

if __name__ == "__main__":
    main()
