"""PAPER ONLY. Zero's priority exit test on the 30-day CR copy replay (data/cr/cand + data/cr/candles).
Only leader first-buys passing the live entry filters (age >= 60 min, mcap >= $1M, liq >= $100k). Entry at +5 s priced from measured drift.
(a) mirror: sell the leader's sell fraction at +10/60/120 s (price = 1-min candle at that moment, open->close interpolated, k-scaled), SL -20 %
(b) ladder: +40 % sell 25 %, +100 % sell 25 %, +500 % the rest; SL -20 %, breakeven after TP1
(c) ladder + on his first sell (+5 s) sell all but 10 % of the original; runner stays on the ladder/BE stop
(d) no TPs: SL -20 %; on his first sell (+5 s) sell all but 10 %; runner exits on his final (full) sell or a breakeven stop
    (BE only if the first sell filled above our entry, else the -20 % stop stays), or the 08:00 flat.
All rules: flat 08:00 Dublin (live rule; candles end there), stops gap through (open) else trigger*0.975, +1 closeAccount tx."""
import json, os, sys, math, random, statistics, datetime as dt
import cr_replay as R, copy_fee_sensitivity as fs
from cr_candles import flat_time
from cr_enrich import WSOL
def ok_dr(v, dflt): return v if v and 0.75 <= v <= 1.33 else dflt     # measured drifts outside +-25..33% are pool/route artefacts -> leader median
LADDER = [(1.4, 0.25), (2.0, 0.25), (6.0, 1.0)]

def prep(e, DD, delay=5):
    t = e["buy"]["t"]; ps = e["ps"]
    if not ps or not ps.get("fill") or not ps.get("qmint"): return None, "no_pool_price"
    if (e.get("pre_bal") or 0) > 1e-9: return None, "not_first_buy"
    if (e.get("mcap") or 0) < 1e6: return None, "mcap"
    if (e.get("liq") or 0) < 1e5: return None, "liq"
    if e.get("age_s") is None: return None, "age_unknown"
    if e["age_s"] < 3600: return None, "age_lt_60m"
    C = e.get("candles")
    if not C or C["status"] != "ok" or not C["rows"]: return None, "no_candles"
    te = t + delay; lt = dt.datetime.fromtimestamp(te, R.DUB)
    if (lt.hour, lt.minute) >= (7, 45) and lt.hour < 8: return None, "no_entry_0745"
    return t, None

def sim(e, rule, size, DD, sd=10, prio=0.0001, delay=5):
    t = e["buy"]["t"]; ps = e["ps"]; d = f"{delay}s"
    u = fs.solpx(t) if ps["qmint"] == WSOL else 1.0
    mid0 = ps["fill"] * u * ok_dr((e.get("dpx") or {}).get(d), DD["buy"][d]); liq0 = e["liq"]
    def cost(mid): return R.side_cost("SELF", liq0 * math.sqrt(max(mid / mid0, 1e-6)))
    cb = cost(mid0); buypx = mid0 * (1 + cb); chase = buypx / e["leader_px"] - 1; te = t + delay
    rows = e["candles"]["rows"]; ref = [r for r in rows if r[0] <= te]; gref = ref[-1][4] if ref else rows[0][1]; k = mid0 / gref
    gas = (prio + 0.000005) * fs.solpx(t); H = flat_time(te)
    tokens = size / buypx; held = 1.0; proceeds = 0.0; ntx = 1
    def xv(mid): return mid * (1 - cost(mid)) / buypx
    def m_for(x):
        m = buypx * x
        for _ in range(3): m = x * buypx / (1 - cost(m))
        return m
    def px_at(ts):
        b = [r for r in rows if r[0] <= ts]
        if not b: return mid0
        r = b[-1]
        if ts < r[0] + 60: w = (ts - r[0]) / 60; return (r[1] * (1 - w) + r[4] * w) * k
        return r[4] * k
    def sell(q, mid):
        nonlocal held, proceeds, ntx
        q = min(q, held)
        if q > 1e-12: proceeds += tokens * q * mid * (1 - cost(mid)); held -= q; ntx += 1
    sells = [s for s in (e.get("sells") or []) if s["t"] >= t and s.get("tokens") and s.get("pre_bal")]
    lag = sd if rule == "a" else 5
    def sell_px(s):
        if rule == "a" and sd > 5: return px_at(s["t"] + sd)
        pool = s.get("pool") or {}
        dr = ok_dr((s.get("dpx") or {}).get("5s"), DD["sell"]["5s"])
        if pool.get("fill") and pool.get("qmint"): return pool["fill"] * (fs.solpx(s["t"]) if pool["qmint"] == WSOL else 1.0) * dr
        return s["avg_px"] * DD["sell"]["5s"]
    path = [r for r in rows if r[0] > (ref[-1][0] if ref else te - 60) and r[0] < H]
    ev = [("c", r[0] + 60, r) for r in path] + [("s", s["t"] + lag, s) for s in sells if s["t"] + lag < H]
    ev.sort(key=lambda z: (z[1], 0 if z[0] == "s" else 1))
    stop = 0.8; tp_i = 0; nsell = 0; reason = "flat_0800"; last_s = len(sells)
    for typ, ts, x in ev:
        if held <= 1e-9: break
        if typ == "s":
            nsell += 1; full = x["tokens"] >= 0.95 * x["pre_bal"]; fr = 1.0 if full else x["tokens"] / x["pre_bal"]; m = sell_px(x)
            if rule == "a":
                sell(held * fr, m)
                if full: reason = "mirror_full"
            elif rule in ("c", "d") and nsell == 1:
                sell(held - 0.10, m); reason = "first_sell"
                if rule == "d" and xv(m) > 1.0: stop = max(stop, 1.0)
                if rule == "d" and full: sell(held, m); reason = "first_sell_full"
            elif rule == "d" and full:
                sell(held, m); reason = "runner_final_sell"
            continue
        o, h, l, c = [v * k for v in x[1:5]]
        if xv(l) <= stop:
            mo = o if xv(o) <= stop else m_for(stop) * R.STOP_SLIP; sell(held, mo); reason = "stop_be" if stop >= 1 else "stop"; break
        if rule in ("b", "c"):
            while tp_i < 3 and held > 1e-9 and xv(h) >= LADDER[tp_i][0]:
                lv, fr = LADDER[tp_i]; mo = o if xv(o) >= lv else m_for(lv)
                sell(held if fr >= 1 else fr, mo); tp_i += 1; stop = max(stop, 1.0); reason = f"tp{tp_i}"
    if held > 1e-9:
        last = [r for r in rows if r[0] < H]; sell(held, last[-1][4] * k if last else mid0)
    ntx += 1
    pnl = proceeds - size - gas * ntx
    return dict(pnl=pnl, ret=pnl / size, t=t, reason=reason, chase=chase, mint=e["mint"], oos=t >= R.HOLDOUT, nsells=len(sells))

def boot_mean(x, n=4000, seed=11):
    if len(x) < 2: return (None, None)
    rnd = random.Random(seed); m = sorted(statistics.fmean(rnd.choices(x, k=len(x))) for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n) - 1]

def main(leaders):
    es = R.load(); DD = R.drift_defaults(es); out = {}
    for L in leaders:
        E = [e for e in es if e["leader"] == L]; keep, why = [], {}
        for e in E:
            t, w = prep(e, DD)
            if w: why[w] = why.get(w, 0) + 1
            else: keep.append(e)
        out[L] = dict(cand=len(E), skipped=why, n=len(keep), n_is=sum(e["buy"]["t"] < R.HOLDOUT for e in keep), n_oos=sum(e["buy"]["t"] >= R.HOLDOUT for e in keep), res={})
        rules = [("a10", "a", 10), ("a60", "a", 60), ("a120", "a", 120), ("b", "b", 0), ("c", "c", 0), ("d", "d", 0)]
        for z in (5, 10, 13):
            S = {nm: [sim(e, r, z, DD, sd) for e in keep] for nm, r, sd in rules}
            for nm in S:
                tr = S[nm]; p = [x["pnl"] for x in tr]
                if not p: continue
                diff = [x["pnl"] - y["pnl"] for x, y in zip(tr, S["b"])]
                oo = [x for x in tr if x["oos"]]; od = [x["pnl"] - y["pnl"] for x, y in zip(tr, S["b"]) if x["oos"]]
                out[L]["res"][f"{nm}_{z}"] = dict(n=len(p), mean=statistics.fmean(p), med=statistics.median(p), total=sum(p), ex_best=sum(p) - max(p),
                    win=sum(v > 0 for v in p) / len(p), diff_mean=statistics.fmean(diff), diff_ci=boot_mean(diff), n_oos=len(oo), oos_total=sum(x["pnl"] for x in oo),
                    oos_diff=sum(od), chase_gt8=sum(x["chase"] > 0.08 for x in tr), reasons={r: sum(x["reason"] == r for x in tr) for r in {x["reason"] for x in tr}},
                    trades=[(x["mint"][:6], round(x["pnl"], 2), x["reason"], x["oos"]) for x in tr])
    return out

if __name__ == "__main__":
    o = main(sys.argv[1:] or ["_benjitrades"]); json.dump(o, open(os.path.join(R.CR, "exit4.json"), "w"), indent=1, default=str)
    for L, v in o.items():
        print(L, "cand", v["cand"], "kept", v["n"], "IS", v["n_is"], "OOS", v["n_oos"], v["skipped"])
        for k_, r in v["res"].items():
            ci = r["diff_ci"]
            print(f"  {k_:8} n={r['n']} mean={r['mean']:+.2f} med={r['med']:+.2f} tot={r['total']:+.2f} exbest={r['ex_best']:+.2f} win={r['win']:.0%} "
                  f"d_vs_b={r['diff_mean']:+.2f} CI=[{ci[0] if ci[0] is None else round(ci[0],2)},{ci[1] if ci[1] is None else round(ci[1],2)}] oos n={r['n_oos']} tot={r['oos_total']:+.2f} d={r['oos_diff']:+.2f} chase>8%={r['chase_gt8']} {r['reasons']}")
