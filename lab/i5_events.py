"""PAPER ONLY. Builds I5 event sets from cached data only (no network). Writes nothing outside data/i5."""
import json, glob, os, math, bisect, csv, statistics, calendar, datetime as dt
LAB = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(LAB, "data")
_sol = json.load(open(os.path.join(D, "backfill", "solusd_1h.json")))["rows"]; _solt = [r[0] for r in _sol]
def solpx(t):
    i = max(0, min(len(_sol) - 1, bisect.bisect_right(_solt, t) - 1)); return _sol[i][4]
def liq_pump(p_usd, t):
    """PumpSwap pool from a pump.fun graduation (~85 SOL + 206.9M tokens, LP burned, no LP adds): x*y=k -> liq = 2*sqrt(k*p)."""
    return 2 * math.sqrt(85 * solpx(t) * 206.9e6 * max(p_usd, 0))
def T(s): return calendar.timegm(dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").timetuple())

# ---------------- idea 2: graduations
def graduations():
    ev = []; empty = 0
    for f in glob.glob(os.path.join(D, "backfill", "candles1m", "*.json")):
        x = json.load(open(f))
        if x.get("kind") != "mig": continue
        if x.get("status") != "ok" or not x.get("rows"): empty += 1; continue
        rows = [r for r in x["rows"] if r[4] and r[4] > 0]
        if not rows: empty += 1; continue
        t0 = x["t_mig"]; p0 = rows[0][1]
        ev.append(dict(t=t0, bars=rows, step=60, liq=liq_pump(p0, t0), key=x["mint"], src="grad", pool=x["pool"], H=rows[-1][0] + 60,
                       vol5=sum(r[5] for r in rows if r[0] < t0 + 300 and len(r) > 5), p_mig=p0))
    return ev, empty

def grad_filtered(ev, wait_min=5, min_liq=40000, min_vol5=20000):
    """Filtered entry (proxy filters, labelled): wait `wait_min` after migration, then require reconstructed pool liq >= min_liq
    (price-implied; LP burned at graduation so 'LP intact' holds by construction) and first-`wait_min` volume >= min_vol5
    (buyer-interest proxy for the holder filter: no point-in-time holder counts in cache). Signal = close of minute wait_min."""
    out = []
    for e in ev:
        ts = e["t"] - e["t"] % 60 + wait_min * 60          # end of the wait window (bar boundary)
        pre = [r for r in e["bars"] if r[0] < ts]
        if not pre: continue
        p = pre[-1][4]; vol = sum(r[5] for r in pre if len(r) > 5); liq = liq_pump(p, ts)
        if liq >= min_liq and vol >= min_vol5:
            out.append(dict(e, t=ts, liq=liq, src="grad_f"))
    return out

# ---------------- idea 1: consensus buys
def roster():
    R = json.load(open("/workspace/selfcopy/roster.json"))["leaders"]; return {l["wallet"]: (l["label"], T(l["added"])) for l in R}
def live15():
    return ["bystevenr", "ew4ue-flip", "ExactTallTakin", "_benjitrades", "zeropnl", "Cented", "decu", "Schoen", "West", "Rilsio", "KOREAN", "Doji", "bust", "Mel", "KingSolomon"]
def leader_buys():
    """All observed buys by roster leaders from read-only sources, each tagged point-in-time (after the wallet's roster 'added') or not."""
    W = roster(); lab2w = {v[0]: (k, v[1]) for k, v in W.items()}; B = []
    for l in open("/workspace/selfcopy/paper-trades.jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if (r.get("event") == "leader_swap" and r.get("side") == "buy") or (r.get("event") == "skip" and r.get("mint")):
            lb = r.get("leader"); t = T(r["ts"]); add = lab2w.get(lb, (None, 0))[1]
            B.append(dict(t=t, leader=lb, mint=r["mint"], src="selfcopy", pit=t >= add))
    for r in csv.DictReader(open("/workspace/onchain-intel/trader_swaps.csv")):
        if r["side"] != "buy": continue
        t = T(r["timestamp"]); add = lab2w.get(r["trader"], (None, 9e12))[1]
        B.append(dict(t=t, leader=r["trader"], mint=r["mint"], src="trader_swaps", pit=t >= add))
    for f in ("scan1.json", "scan2.json", "scan3.json"):
        p = os.path.join("/workspace/runner-radar/kolscan", f)
        try: d = json.load(open(p))
        except Exception: continue
        for name, v in (d.items() if isinstance(d, dict) else []):
            if not isinstance(v, dict): continue
            for s in v.get("swaps", []):
                if s.get("side") == "buy":
                    lb = W.get(v.get("wallet"), (name, 0))[0]; add = W.get(v.get("wallet"), (None, 9e12))[1]
                    B.append(dict(t=s["ts"], leader=lb, mint=s["mint"], src="kolscan_" + f, pit=s["ts"] >= add))
    return B
def consensus(B, n=3, w_min=30, live_only=True, pit_only=True):
    L = set(live15()); ev = []; by = {}
    for b in B:
        if live_only and b["leader"] not in L: continue
        if pit_only and not b["pit"]: continue
        by.setdefault(b["mint"], []).append(b)
    for m, v in by.items():
        v.sort(key=lambda x: x["t"])
        for b in v:
            ls = {x["leader"] for x in v if b["t"] - w_min * 60 <= x["t"] <= b["t"]}
            if len(ls) >= n: ev.append(dict(t=b["t"], mint=m, leaders=sorted(ls))); break
    return ev
def cl_proxy(setname):
    """Scout early-buyer confluence events (data/cl/events.json, CL_ phase 1) with CL candles; pump coins -> liq via pump curve."""
    import cl_sim
    E = json.load(open(os.path.join(D, "cl", "events.json")))["events"][setname]; S = cl_sim.load_series(); out = []
    for e in E["events"]:
        s = S.get(e["mint"])
        if not s or not s["rows"]: continue
        rows = s["rows"]; ref = [r for r in rows if r[0] <= e["t"]] or rows[:1]
        liq = liq_pump(ref[-1][4], e["t"]) if e["mint"].endswith("pump") else 1e5
        out.append(dict(t=e["t"], bars=rows, step=60, liq=liq, key=e["mint"], src="cl_" + setname))
    return out, E["lookahead"]
