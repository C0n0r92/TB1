"""PAPER ONLY. Fast-exit test (Zero, 2026-10-24): fixed TP (sell all) x stop x max hold on every recorded copy signal with price data,
vs the current ladder (TP +40%/25%, +100%/25%, rest +500%, breakeven after TP1, -20% hard stop), same trades.
Signal pool (read-only inputs):
  live  : selfcopy paper entries (bot detection time) incl. copylive Bert/CLAUDIA/FARTBOY, 1-min GT candles in data/fe (fe_fetch.py)
  scout : Scout's winners round trips (_benjitrades/bystevenr/onlyzhynx) data/cr/win + data/cr/wcandles (bj_full_replay inputs)
  cr30  : 30-day copy-replay first buys data/cr/cand + data/cr/candles (cr_exit4 inputs); (leader, mint) already in scout dropped
Entry = 5 s after the signal (measured on-chain drift where available, else leader median). Triggers on mark-to-market value net of exit
cost (x = value/stake, same convention as all CR/BJ tests). Stop checked before target in each bar. Stop fill models:
  low = the bar's LOW (brief: gaps through to the low; conservative, primary)   std = open if gapped else trigger x 0.975 (METHOD calibration)
Costs: self10 3.0% rt, self5 4.7% rt, cf10 (copyfomo) 5.3% rt, each + liquidity-scaled impact (Jupiter-quote fit, liq ~ sqrt(price)),
+ per-extra-sell gas. Holdout = latest 30% of pooled signals by time (split fixed before results)."""
import json, os, glob, math, statistics, calendar, random, datetime as dt
import copy_fee_sensitivity as fs, scoring
import cr_win_replay as W, cr_replay as R
from cr_rpc import WSOL
import bj_full_replay as BJ
LAB = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(LAB, "out"); FE = os.path.join(LAB, "data", "fe")
DELAY = 5; BAL = 100.0
COSTS = {"self10": dict(size=10.0, rt=0.030, leg=0.02), "self5": dict(size=5.0, rt=0.047, leg=0.02), "cf10": dict(size=10.0, rt=0.053, leg=0.015)}
TPS = (0.08, 0.12, 0.20, 0.30); SLS = (0.08, 0.10, 0.15); HOLDS = (10, 20, 45)
LADDER = [(1.4, 0.25), (2.0, 0.25), (6.0, 1.0)]
def iso(s): return calendar.timegm(dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").timetuple())
def okd(v, d): return v if v and 0.75 <= v <= 1.33 else d

def events():
    E = []; imp = fs.impact_only_fn(W.fit())
    # --- scout round trips
    es = [e for e in W.load() if e.get("src") == "scout"]; DD = W.drift_defaults(es); seen = set()
    for e in es:
        if not e.get("C") or not e["C"].get("rows1") or not e.get("leader_px"): continue
        ps = e.get("ps") or {}; t = e["t"]; sol = fs.solpx(t)
        if ps.get("fill"):
            u = sol if ps["qmint"] == WSOL else 1.0; dr = (e.get("dpx") or {}).get("5s") if (e.get("dpx") or {}).get("5s_trade") else None
            mid0 = ps["fill"] * u * okd(dr, DD[e["label"]]["buy"]["5s"])
            liq = max([p["quote"] * (sol if p["qmint"] == WSOL else 1) + p["base"] * e["leader_px"] for p in [ps] + ps.get("alt", []) if p.get("quote")] or [1e4]); syn = False
        else: mid0 = e["leader_px"] * DD[e["label"]]["buy"]["5s"]; liq = 1e5; syn = True
        r1 = e["C"]["rows1"]; te = t + DELAY; ref = [r for r in r1 if r[0] <= te]; gref = ref[-1][4] if ref else r1[0][1]; k = mid0 / gref
        bars = [(a, b, o) for a, b, o in W.path(e, k) if a > (ref[-1][0] if ref else te - 60)]
        E.append(dict(src="scout", label=e["label"], mint=e["mint"], sym=e.get("symbol"), t=t, mid0=mid0, liq=liq, bars=bars, H=e["C"]["H"], syn=syn, chase=mid0 / e["leader_px"] - 1)); seen.add((e["label"], e["mint"]))
    # --- 30-day copy replay first buys
    cs = R.load(); DD2 = R.drift_defaults(cs)
    for e in cs:
        C = e.get("candles")
        if not C or C.get("status") != "ok" or not C.get("rows") or (e["leader"], e["mint"]) in seen: continue
        t = e["buy"]["t"]; ps = e.get("ps") or {}
        if ps.get("fill") and ps.get("qmint"):
            mid0 = ps["fill"] * (fs.solpx(t) if ps["qmint"] == WSOL else 1.0) * okd((e.get("dpx") or {}).get("5s"), DD2["buy"]["5s"]); syn = False
        elif e.get("leader_px"): mid0 = e["leader_px"] * DD2["buy"]["5s"]; syn = True
        else: continue
        rows = C["rows"]; te = t + DELAY; ref = [r for r in rows if r[0] <= te]; gref = ref[-1][4] if ref else rows[0][1]; k = mid0 / gref
        bars = [(r[0], r[0] + 60, [x * k for x in r[1:5]]) for r in rows if r[0] > (ref[-1][0] if ref else te - 60)]
        E.append(dict(src="cr30", label=e["leader"], mint=e["mint"], sym=None, t=t, mid0=mid0, liq=e.get("liq") or 1e5, bars=bars, H=C["H"], syn=syn or not e.get("liq"),
                      chase=mid0 / e["leader_px"] - 1 if e.get("leader_px") else 0.0)); seen.add((e["leader"], e["mint"]))
    # --- live paper entries (selfcopy) with fresh 1-min GT candles
    names = {"HgBRWfYx": "Bert", "2j5SaS7x": "CLAUDIA", "y1AZt42v": "FARTBOY"}
    for l in open("/workspace/selfcopy/paper-trades.jsonl"):
        try: r = json.loads(l)
        except Exception: continue
        if r.get("event") != "entry": continue
        p = os.path.join(FE, r["mint"] + ".json")
        if not os.path.exists(p): continue
        C = json.load(open(p)); t = iso(r["ts"]) - (r.get("delay_s") or 0)          # bot's detection time = our signal
        mid0 = r["entry_px"] / (1 + (r.get("impact_pct") or 0)); te = t + DELAY; rows = C["rows1"]
        ref = [x for x in rows if x[0] <= te]
        if not ref or te - ref[-1][0] > 6 * 3600: E.append(dict(src="live", label=r["leader"], mint=r["mint"], sym=names.get(r["mint"][:8]), t=t, nodata=True)); continue
        k = mid0 / ref[-1][4]
        bars = [(x[0], x[0] + 60, [v * k for v in x[1:5]]) for x in rows if x[0] > ref[-1][0]]
        E.append(dict(src="live", label=r["leader"], mint=r["mint"], sym=names.get(r["mint"][:8], r["mint"][:6]), t=t, mid0=mid0, liq=r.get("liq") or 1e5, bars=bars,
                      H=C["fetched"] - 120, syn=False, chase=r.get("chase") or 0.0))
    return E, imp

def sim(e, rule, ck, imp, stopm="low"):
    """rule: ('fx', tp, sl, hold_min) or ('ladder',)"""
    K = COSTS[ck]; size = K["size"]; mid0 = e["mid0"]; liq0 = e["liq"]; base = K["rt"] / 2
    def cost(mid, z): return base + imp(max(liq0 * math.sqrt(max(mid / mid0, 1e-6)), 1e3), z)
    buypx = mid0 * (1 + cost(mid0, size)); tokens = size / buypx; held = 1.0; proceeds = 0.0; legs = 0
    def xv(m): return m * (1 - cost(m, size * max(held, .01))) / buypx
    def mfor(x):
        m = buypx * x
        for _ in range(3): m = x * buypx / (1 - cost(m, size * max(held, .01)))
        return m
    def sell(q, m):
        nonlocal held, proceeds, legs
        q = min(q, held)
        if q > 1e-12: proceeds += tokens * q * m * (1 - cost(m, size * q)); held -= q; legs += 1
    te = e["t"] + DELAY
    if rule[0] == "fx": _, tp, sl, hm = rule; tps = [(1 + tp, 1.0)]; stop = 1 - sl; be = False; Hend = te + 60 * hm
    else: tps = LADDER; stop = 0.80; be = True; Hend = e["H"]
    trunc = e["H"] < Hend - 60 and rule[0] == "fx"; last = mid0; reason = "time"; tp_i = 0
    for a, b, (o, h, l, c) in e["bars"]:
        if a >= Hend: break
        if xv(l) <= stop:
            if stopm == "low": mo = l
            else: mo = o if xv(o) <= stop else mfor(stop) * 0.975
            sell(held, mo); reason = "stop_be" if stop >= 1 else "stop"; break
        while tp_i < len(tps) and held > 1e-9 and xv(h) >= tps[tp_i][0]:
            lv, fr = tps[tp_i]; sell(held if fr >= 1 else fr, o if xv(o) >= lv else mfor(lv)); tp_i += 1
            if be: stop = max(stop, 1.0)
        last = c
        if held <= 1e-9: reason = f"tp{tp_i}"; break
    if held > 1e-9: sell(held, last); reason = "time" if rule[0] == "fx" else "horizon"
    pnl = proceeds - size - max(0, legs - 1) * K["leg"]
    return dict(pnl=pnl, ret=pnl / size, t=e["t"], reason=reason, trunc=trunc, src=e["src"], mint=e["mint"], label=e["label"])

def boot(x, n=4000, seed=11):
    if len(x) < 2: return (None, None)
    rnd = random.Random(seed); m = sorted(statistics.fmean(rnd.choices(x, k=len(x))) for _ in range(n)); return m[int(.025 * n)], m[int(.975 * n) - 1]

def rname(r): return "FE_ladder" if r[0] == "ladder" else f"FE_tp{int(r[1]*100):02d}_sl{int(r[2]*100):02d}_h{r[3]:02d}"

def run():
    E, imp = events(); ok = [e for e in E if not e.get("nodata")]
    ts = sorted(e["t"] for e in ok); split = ts[int(len(ts) * 0.7)]
    rules = [("fx", a, b, c) for a in TPS for b in SLS for c in HOLDS] + [("ladder",)]
    G = {}
    for sm in ("low", "std"):
        for ck in COSTS:
            for ru in rules:
                tr = [sim(e, ru, ck, imp, sm) for e in ok]; S = BJ.stats(tr, COSTS[ck]["size"], split); S["trunc"] = sum(x["trunc"] for x in tr)
                S["reasons"] = {z: sum(x["reason"] == z for x in tr) for z in {x["reason"] for x in tr}}
                S["by_src"] = {s: (sum(1 for x in tr if x["src"] == s), sum(x["pnl"] for x in tr if x["src"] == s)) for s in ("live", "scout", "cr30")}
                S["tr"] = tr; G[(sm, ck, ru)] = S
    return E, ok, split, rules, G

if __name__ == "__main__":
    E, ok, split, rules, G = run()
    print(len(E), len(ok), dt.datetime.utcfromtimestamp(split))
    for sm in ("low", "std"):
        for ck in ("self10", "cf10"):
            lad = G[(sm, ck, ("ladder",))]
            best = sorted([r for r in rules if r[0] == "fx"], key=lambda r: -G[(sm, ck, r)]["is_tot"])[:3]
            print(sm, ck, "ladder", round(lad["mean_ret"], 4), round(lad["is_tot"], 2), round(lad["oos_tot"], 2))
            for r in best: S = G[(sm, ck, r)]; print("  ", rname(r), S["n"], round(S["mean_ret"], 4), "IS", round(S["is_mean_ret"], 4), "OOS", round(S["oos_mean_ret"], 4), S["n_is"], S["n_oos"])
