"""Stage 4 (PAPER ONLY): replay copying the four leaders over ~30 days at self-copy costs. OLD rules vs NEW (live v2) rules.
Inputs: data/cr/cand/*.json (cr_enrich), data/cr/candles/*.json (cr_candles). Writes out/.cr_rows.json + out/copy_replay_30d.md
+ out/copy_fee_sensitivity.md (v3) + data/cr/replay_trades.json."""
import json, os, glob, math, time, statistics, calendar, datetime as dt, random
from zoneinfo import ZoneInfo
import copy_fee_sensitivity as fs, scoring
from cr_candles import flat_time, CD
from cr_enrich import CAND, LEAD, WSOL
LAB = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(LAB, "out"); CR = os.path.join(LAB, "data", "cr")
DUB = ZoneInfo("Europe/Dublin")
HOLDOUT = calendar.timegm((2026, 10, 15, 7, 0, 0))   # FIXED before any result was computed: last 9 of 30 Dublin nights (30%)
BAL = 100.0                                          # METHOD equity for drawdown / night-loss
LEADERS = list(LEAD)
RULES = {
  "OLD": dict(min_mcap=1e5, min_liq=0, min_age=0, max_chase=0.15, sl=0.75, tp=2.0, tp_frac=0.5, trail=None),
  "NEW": dict(min_mcap=1e6, min_liq=1e5, min_age=3600, max_chase=0.08, sl=0.85, tp=1.5, tp_frac=0.5, trail=0.85),
}
STOP_SLIP = 0.975          # stop fills 2.5% below the trigger unless the candle opens through it (gap -> open)
_fit = None
def fit():
    global _fit
    if _fit is None: _fit = fs.fit_cost(fs.load_quotes(), nboot=400)
    return _fit
def rt_self(liq): return max(0.005, fs.rt_pred(fit(), max(liq, 1e3), 5.0))
def side_cost(kind, liq):
    """per-side cost fraction (price impact + pool/route fees). SELF = Jupiter quote fit; CF = copyfomo ~5.3% round trip + pool impact."""
    r = rt_self(liq)
    return r / 2 if kind == "SELF" else (0.053 + max(0.0, r - rt_self(1e6))) / 2

def _iso(s): return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) if s else None

def load():
    es = []; P = json.load(open(os.path.join(CR, "gecko_pools.json"))) if os.path.exists(os.path.join(CR, "gecko_pools.json")) else {}
    for f in glob.glob(os.path.join(CAND, "*.json")):
        e = json.load(open(f)); cp = os.path.join(CD, f'{e["leader"]}_{e["mint"]}.json')
        e["candles"] = json.load(open(cp)) if os.path.exists(cp) else None
        e["age_src"] = "rpc" if e.get("age_s") is not None else None
        if e.get("age_s") is None and P.get("created:" + e["mint"]):
            e["age_s"] = e["buy"]["t"] - _iso(P["created:" + e["mint"]]); e["age_src"] = "gecko_pool_created_at"
        es.append(e)
    es.sort(key=lambda e: e["buy"]["t"])
    return es

def drift_defaults(es):
    b = {d: [e["dpx"][d] for e in es if e.get("dpx") and e["dpx"].get(d)] for d in ("2s", "5s")}
    s = {d: [x["sells"][0]["dpx"][d] for x in es if x.get("sells") and x["sells"][0].get("dpx") and x["sells"][0]["dpx"].get(d)] for d in ("2s", "5s")}
    return {"buy": {d: statistics.median(v) if v else 1.0 for d, v in b.items()}, "sell": {d: statistics.median(v) if v else 1.0 for d, v in s.items()},
            "n_buy": len(b["5s"]), "n_sell": len(s["5s"]), "raw_buy": b, "raw_sell": s}

def entry_filter(e, R, chase):
    if (e.get("pre_bal") or 0) > 1e-9: return "not_first_buy"
    if e["buy"]["usd"] < 50: return "leader_lt_50"
    if (e.get("mcap") or 0) < R["min_mcap"]: return "mcap"
    if R["min_liq"] and (e.get("liq") or 0) < R["min_liq"]: return "liq"
    if R["min_age"]:
        a = e.get("age_s")
        if a is None or a < R["min_age"]: return "age_lt_60m" if a is not None else "age_unknown"
    if chase > R["max_chase"]: return "chase"
    return None

def sim_one(e, R, kind, size, prio, delay, DD):
    """-> dict(status, pnl, ret, t, exit_t, reason...). Mid-price space in USD."""
    t = e["buy"]["t"]; d = f"{delay}s"; ps = e["ps"]
    if not ps or not ps.get("fill") or not ps.get("qmint"): return dict(status="no_pool_price", t=t)
    u = fs.solpx(t) if ps["qmint"] == WSOL else 1.0
    drift = (e.get("dpx") or {}).get(d) or DD["buy"][d]
    mid0 = ps["fill"] * u * drift; liq0 = e.get("liq") or 1e4
    cb = side_cost(kind, liq0); buypx = mid0 * (1 + cb)
    chase = buypx / e["leader_px"] - 1
    why = entry_filter(e, R, chase)
    if why: return dict(status="filtered", why=why, t=t, chase=chase)
    te = t + delay
    lt = dt.datetime.fromtimestamp(te, DUB)
    if (lt.hour, lt.minute) >= (7, 45) and lt.hour < 8: return dict(status="filtered", why="no_entry_0745", t=t)
    C = e.get("candles")
    if not C or C["status"] != "ok" or not C["rows"]: return dict(status="no_candles", t=t)
    rows = C["rows"]
    ref = [r for r in rows if r[0] <= te]
    gref = ref[-1][4] if ref else rows[0][1]          # Gecko close of the entry minute (or first open) ~ mid at entry
    k = mid0 / gref                                   # Gecko level -> our mid level (pool / quote-unit mismatch); reported
    gas = (prio + 0.000005) * fs.solpx(t) if kind == "SELF" else 0.015          # $ per transaction
    tokens = size / buypx; held = 1.0; proceeds = 0.0; ntx = 1; tp_done = False; peak = None
    H = flat_time(te); sells = [s for s in (e.get("sells") or []) if s["t"] >= t]
    def liq_at(mid): return liq0 * math.sqrt(max(mid / mid0, 1e-6))
    def xval(mid): return tokens * held * mid * (1 - side_cost(kind, liq_at(mid))) / (size * held)   # value/basis of what is held
    def sell(frac_of_held, mid, why_):
        nonlocal held, proceeds, ntx
        q = held * frac_of_held; proceeds += tokens * q * mid * (1 - side_cost(kind, liq_at(mid))); held -= q; ntx += 1
        return why_
    def mid_for_x(x):   # invert xval approximately (cost evaluated at the trigger level, 2 iterations)
        m = mid0 * x
        for _ in range(3): m = x * size / (tokens * (1 - side_cost(kind, liq_at(m))))
        return m
    reason = None; exit_t = None
    # events: candle minutes strictly after the entry minute; mirrored leader sells at s.t + delay
    si = 0; path = [r for r in rows if r[0] > (ref[-1][0] if ref else te - 60)]
    events = [("c", r[0] + 60, r) for r in path if r[0] < H] + [("s", s["t"] + delay, s) for s in sells if s["t"] + delay < H]
    events.sort(key=lambda z: (z[1], 0 if z[0] == "s" else 1))
    for typ, ts, ev in events:
        if held <= 1e-9: break
        if typ == "s":
            if not ev.get("tokens") or not ev.get("pre_bal"): continue
            fr = 1.0 if ev["tokens"] >= 0.95 * ev["pre_bal"] else ev["tokens"] / ev["pre_bal"]
            pool = ev.get("pool") or {}
            if pool.get("fill") and pool.get("qmint"):
                sd = ((ev.get("dpx") or {}).get(d)) or DD["sell"][d]
                m = pool["fill"] * (fs.solpx(ev["t"]) if pool["qmint"] == WSOL else 1.0) * sd
            else: m = ev["avg_px"] * DD["sell"][d]
            r_ = sell(fr, m, "mirror_full" if fr == 1.0 else "mirror_part")
            if fr == 1.0: reason, exit_t = r_, ts
            continue
        o, h, l, c = [x * k for x in ev[1:5]]
        # stop / trail (checked before TP, previous peak)
        stop_x = R["sl"]
        if tp_done and R["trail"]: stop_x = max(stop_x, R["trail"] * peak)
        if xval(l) <= stop_x:
            mo = o if xval(o) <= stop_x else mid_for_x(stop_x) * STOP_SLIP
            reason = sell(1.0, mo, "trail" if (tp_done and R["trail"] and stop_x > R["sl"]) else "stop"); exit_t = ts; break
        if not tp_done and xval(h) >= R["tp"]:
            mo = o if xval(o) >= R["tp"] else mid_for_x(R["tp"])
            sell(R["tp_frac"], mo, "tp"); tp_done = True; peak = xval(h)
        elif tp_done: peak = max(peak, xval(h))
    if held > 1e-9:
        last = [r for r in rows if r[0] < H]
        m = (last[-1][4] * k) if last else mid0
        reason = reason or ("flat_0800" if not sells or sells[-1]["t"] + delay < H else "flat_0800"); sell(1.0, m, reason); exit_t = exit_t or H
    pnl = proceeds - size - ntx * gas
    return dict(status="closed", t=te, exit_t=exit_t, pnl=pnl, ret=pnl / size, reason=reason, tp=tp_done, chase=chase, k=k, liq=liq0,
                ntx=ntx, gas=ntx * gas, cost_rt=2 * cb, mint=e["mint"], leader=e["leader"])

def run(es, leader, rule, kind, size, prio, delay, DD):
    R = RULES[rule]; tr = []; skips = {}; open_ = []; night_pnl = {}
    for e in es:
        if leader != "ALL" and e["leader"] != leader: continue
        r = sim_one(e, R, kind, size, prio, delay, DD)
        if r["status"] != "closed": skips[r.get("why", r["status"])] = skips.get(r.get("why", r["status"]), 0) + 1; continue
        lead_open = [x for x in open_ if x["leader"] == e["leader"] and x["exit_t"] > r["t"]]
        if len(lead_open) >= 3: skips["max_open_3"] = skips.get("max_open_3", 0) + 1; continue
        n = scoring.night_of(r["t"])
        realized = sum(x["pnl"] for x in tr if scoring.night_of(x["t"]) == n and x["leader"] == e["leader"] and x["exit_t"] <= r["t"])
        if realized <= -0.20 * BAL: skips["night_loss_halt"] = skips.get("night_loss_halt", 0) + 1; continue
        open_.append(r); tr.append(r)
    return tr, skips

def summarize(tr, size):
    pn = [x["pnl"] for x in tr]; n = len(pn)
    closed = [{"t": x["t"], "pnl": x["pnl"], "ret": x["ret"], "is_oos": x["t"] >= HOLDOUT} for x in tr]
    st = {"trades": n, "mean_ret": statistics.fmean([x["ret"] for x in tr]) if n else None}
    lo, hi = fs.boot_ci(pn) if n else (None, None)
    if n > 1: st["ci_lo"] = lo / size
    mc = scoring.mc_drawdown(pn, BAL, 1000) if pn else None
    sc = scoring.score(st, None, closed, mc)
    oos = [c["pnl"] for c in closed if c["is_oos"]]; ins = [c["pnl"] for c in closed if not c["is_oos"]]
    return dict(n=n, ev=statistics.fmean(pn) if n else None, ev_pct=st["mean_ret"], med=statistics.median(pn) if n else None, total=sum(pn),
                ex_best=(sum(pn) - max(pn)) if n else 0.0, ci=(lo, hi), win=(sum(p > 0 for p in pn) / n) if n else None, mc=mc, sc=sc,
                n_in=len(ins), in_net=sum(ins), n_oos=len(oos), oos_net=sum(oos), oos_ev=statistics.fmean(oos) if oos else None,
                tp=sum(x["tp"] for x in tr), reasons={r: sum(x["reason"] == r for x in tr) for r in {x["reason"] for x in tr}},
                cost=statistics.fmean([x["cost_rt"] + x["gas"] / size for x in tr]) if n else None)

SIZES = (5.0, 10.0, 13.0); PRIOS = (0.0001, 0.0005); DELAYS = (2, 5)
HEAD = dict(prio=0.0001, delay=5)          # live config: 0.0001 SOL priority (HARD cap); 5 s = slow end of the 2-5 s window

def f(x, p=2, pct=False, sign=True):
    if x is None: return "–"
    return (f"{x*100:+.1f}%" if sign else f"{x*100:.1f}%") if pct else (f"{x:+.{p}f}" if sign else f"{x:.{p}f}")

def main():
    es = load(); DD = drift_defaults(es)
    grid = []
    for L in LEADERS + ["ALL"]:
        for rule in RULES:
            for z in SIZES:
                for pr in PRIOS:
                    for d in DELAYS:
                        tr, sk = run(es, L, rule, "SELF", z, pr, d, DD); grid.append(dict(L=L, rule=rule, kind="SELF", size=z, prio=pr, delay=d, tr=tr, sk=sk, S=summarize(tr, z)))
                tr, sk = run(es, L, rule, "CF", z, 0.0, 5, DD); grid.append(dict(L=L, rule=rule, kind="CF", size=z, prio=0.0, delay=5, tr=tr, sk=sk, S=summarize(tr, z)))
    json.dump([dict({k: v for k, v in g.items() if k != "tr"}, trades=[{k: v for k, v in x.items()} for x in g["tr"]]) for g in grid],
              open(os.path.join(CR, "replay_grid.json"), "w"), default=str)
    return es, DD, grid

def cell(grid, L, rule, kind="SELF", size=5.0, prio=HEAD["prio"], delay=HEAD["delay"]):
    for g in grid:
        if g["L"] == L and g["rule"] == rule and g["kind"] == kind and g["size"] == size and (kind == "CF" or (g["prio"] == prio and g["delay"] == delay)): return g

if __name__ == "__main__":
    es, DD, grid = main()
    for L in LEADERS + ["ALL"]:
        for rule in RULES:
            for z in SIZES:
                S = cell(grid, L, rule, size=z)["S"]
                print(L, rule, z, S["n"], f(S["ev"]), f(S["ev_pct"], pct=True), f(S["total"]), "oos", S["n_oos"], f(S["oos_net"]), S["sc"]["score_total"])
