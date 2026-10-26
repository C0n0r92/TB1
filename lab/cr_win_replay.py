"""PAPER ONLY. Winners-batch copy replay: exit-rule comparison (a) copy ladder, (b) ladder + sell all-but-10% on the leader's first
sell, (c) mirror the leader's sells with a -20% stop; entry filters on/off; neodot at tiny sizes. Inputs: data/cr/win, data/cr/wcandles."""
import json, os, glob, math, statistics, calendar, datetime as dt
import copy_fee_sensitivity as fs, scoring
from cr_rpc import WSOL
from cr_candles import flat_time
CR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cr"); WD = os.path.join(CR, "win"); WC = os.path.join(CR, "wcandles")
HOLDOUT = calendar.timegm((2026, 10, 15, 7, 0, 0))      # same fixed split as the CR replay (chosen before results)
BAL = 100.0; STOP_SLIP = 0.975; PUMP_FEE = 0.0125       # pump.fun bonding curve: 0.95% protocol + 0.30% creator per side
V_SOL0, V_TOK_OFF = 30.0, 279_900_000.0                 # pump curve virtual reserves: vSOL = 30 + real SOL
LADDER = [(1.4, 0.25), (2.0, 0.25), (6.0, 1.0)]         # (x trigger, fraction of ORIGINAL position; 1.0 = the rest)
RULES = {"a10": dict(ladder=False, sl=0.8, be=False, mirror=True, sd=10),      # (a) mirror his sell fractions at +10/60/120 s, SL -20 %
         "a60": dict(ladder=False, sl=0.8, be=False, mirror=True, sd=60),
         "a120": dict(ladder=False, sl=0.8, be=False, mirror=True, sd=120),
         "b": dict(ladder=True, sl=0.8, be=True, on_first_sell=None, sd=5),       # (b) current ladder
         "c": dict(ladder=True, sl=0.8, be=True, on_first_sell=0.10, sd=5),       # (c) ladder + all but 10 % on his first sell
         "d": dict(ladder=False, sl=0.8, be=False, on_first_sell=0.10, runner=True, sd=5)}  # (d) no TPs; runner -> his final sell / BE stop
_fit = None
def fit():
    global _fit
    if _fit is None: _fit = fs.fit_cost(fs.load_quotes(), nboot=200)
    return _fit

def load():
    es = []
    for f in sorted(glob.glob(os.path.join(WD, "*.json"))):
        if os.path.basename(f).startswith("_"): continue
        e = json.load(open(f)); c = os.path.join(WC, os.path.basename(f))
        e["C"] = json.load(open(c)) if os.path.exists(c) else None
        es.append(e)
    return es

def drift_defaults(es):
    out = {}
    for L in {e["label"] for e in es}:
        ok = lambda v: 0.75 <= v <= 1.33
        b = [e["dpx"][d] for e in es if e["label"] == L and e.get("dpx") for d in ("5s",) if e["dpx"].get("5s_trade") and ok(e["dpx"][d])]
        s = [e["sell_dpx"]["5s"] for e in es if e["label"] == L and e.get("sell_dpx") and e["sell_dpx"].get("5s_trade") and ok(e["sell_dpx"]["5s"])]
        b2 = [e["dpx"]["2s"] for e in es if e["label"] == L and e.get("dpx") and e["dpx"].get("2s_trade") and ok(e["dpx"]["2s"])]
        s2 = [e["sell_dpx"]["2s"] for e in es if e["label"] == L and e.get("sell_dpx") and e["sell_dpx"].get("2s_trade") and ok(e["sell_dpx"]["2s"])]
        out[L] = {"buy": {"5s": statistics.median(b) if b else 1.0, "2s": statistics.median(b2) if b2 else 1.0},
                  "sell": {"5s": statistics.median(s) if s else 1.0, "2s": statistics.median(s2) if s2 else 1.0}, "nb": len(b), "ns": len(s)}
    return out

def path(e, k):
    C = e["C"]; r1 = C["rows1"]; last = max([r[0] for r in r1] or [0])
    r15 = [r for r in C.get("rows15") or [] if r[0] > last]
    if C.get("rows15_ctx"):
        l2 = max([r[0] for r in r1 + r15] or [0]); r15 += [r for r in C["rows15_ctx"] if r[0] > l2]
    return [(r[0], r[0] + 60, [x * k for x in r[1:5]]) for r in r1] + [(r[0], r[0] + 900, [x * k for x in r[1:5]]) for r in r15]

FIRST_BUY_ONLY = os.environ.get('FIRST_BUY_ONLY') == '1'

def sim(e, rule, size, prio=0.0001, delay=5, DD=None, flat08=False, sdelay=None):
    R = RULES[rule]; t = e["t"]; d = f"{delay}s"; ps = e.get("ps")
    sdelay = R.get("sd", delay) if sdelay is None else sdelay; sdk = f"{sdelay}s" if sdelay in (2, 5) else "5s"
    if not e.get("leader_px"): return dict(status="no_pool_price")
    if not ps or not ps.get("fill"):    # entry routed through a pool we could not decode -> price off the leader's own avg fill, liq assumed $100k
        ps = dict(fill=e["leader_px"], qmint="USD", quote=None, curve=False, alt=[], synthetic=True)
    if (e.get("pre_bal") or 0) > 1e-9 and FIRST_BUY_ONLY: return dict(status="not_first_buy")   # default: copy the buy Scout's round trip starts on, even if he already held a bag
    if not e.get("C") or not e["C"].get("rows1"): return dict(status="no_candles")
    sol = fs.solpx(t); u = sol if ps["qmint"] == WSOL else 1.0
    dd = DD[e["label"]]
    drift = (e.get("dpx") or {}).get(d) if (e.get("dpx") or {}).get(d + "_trade") else dd["buy"][d]
    if not 0.75 <= drift <= 1.33: drift = dd["buy"][d]            # pool/route artefact -> leader median
    mid0 = ps["fill"] * u * drift
    curve = ps.get("curve")
    if curve:
        vsol0 = V_SOL0 + ps["quote"]; liq0 = 2 * vsol0 * sol
        def cost(mid, z): return PUMP_FEE + (z / sol) / (vsol0 * math.sqrt(max(mid / mid0, 1e-6)))
    else:
        liq0 = max([p["quote"] * (sol if p["qmint"] == WSOL else 1) + p["base"] * e["leader_px"] for p in [ps] + ps.get("alt", []) if p.get("quote")] or [1e5 if ps.get("synthetic") else 1e4])
        def cost(mid, z): return max(0.005, fs.rt_pred(fit(), max(liq0 * math.sqrt(max(mid / mid0, 1e-6)), 1e3), z)) / 2
    cb = cost(mid0, size); buypx = mid0 * (1 + cb); chase = buypx / e["leader_px"] - 1
    te = t + delay; gas1 = (prio + 0.000005) * sol
    tokens = size / buypx; held = 1.0; proceeds = 0.0; ntx = 1; peak_x = 0
    rows = [r for r in e["C"]["rows1"] if r[0] <= te]
    gref = rows[-1][4] if rows else e["C"]["rows1"][0][1]; k = mid0 / gref
    H = min(e["C"]["H"], flat_time(te)) if flat08 else e["C"]["H"]
    def xval(mid): return mid * (1 - cost(mid, size * max(held, 0.01))) / buypx
    def mid_for_x(x):
        m = buypx * x
        for _ in range(3): m = x * buypx / (1 - cost(m, size * max(held, 0.01)))
        return m
    caps = []
    def sell(q, mid, why):
        nonlocal held, proceeds, ntx
        q = min(q, held)
        if q <= 1e-12: return
        proceeds += tokens * q * mid * (1 - cost(mid, size * q)); held -= q; ntx += 1; caps.append((why, round(q, 3), round(xval(mid), 3)))
    ev = [("c", t1, ohlc) for t0, t1, ohlc in path(e, k) if t0 > (rows[-1][0] if rows else te - 60) and t1 <= H + 900]
    lb = e.get("entry_tokens") or 0; lsold = 0.0; first_sell = True; tp_i = 0; stop = R["sl"]; reason = "horizon"; last_mid = mid0
    for s in e.get("swaps") or []:
        if s["t"] + sdelay < H and s["t"] >= t: ev.append(("s", s["t"] + sdelay, s))
    P = path(e, k)
    def px_at(ts):                 # candle close of the bar containing ts (k-scaled) - used for sell delays > 5 s
        b = [(t0, t1, c) for t0, t1, c in P if t0 <= ts < t1]
        if not b: return None
        t0, t1, c = b[0]; w = (ts - t0) / (t1 - t0); return c[0] * (1 - w) + c[3] * w   # open->close interpolation
    ev.sort(key=lambda z: (z[1], 0 if z[0] == "s" else 1))
    for typ, ts, x in ev:
        if held <= 1e-9: break
        if typ == "s":
            if x["tokens"] > 0: lb += x["tokens"]; continue
            q = -x["tokens"]; pre = x.get("pre_bal") or lb
            fr = q / pre if pre > 0 else 1.0; lsold += q
            full = fr >= 0.95 or (pre - q) <= 0.05 * max(lb, 1e-9)
            pool = x.get("pool") or {}
            sd = (e.get("sell_dpx") or {}).get(sdk) if first_sell and (e.get("sell_dpx") or {}).get(sdk + "_trade") else dd["sell"][sdk]
            if not 0.75 <= sd <= 1.33: sd = dd["sell"][sdk]
            m = pool["fill"] * (fs.solpx(x["t"]) if pool.get("qmint") == WSOL else 1.0) * sd if pool.get("fill") else (x.get("avg_px") or last_mid) * sd
            if sdelay > 5:
                pc = px_at(ts)
                if pc: m = pc
            if R.get("mirror"):
                sell(1.0 if full else held * fr, m, "mirror_full" if full else "mirror_part")
                if full: reason = "mirror_full"
            elif first_sell and R.get("on_first_sell") is not None:
                sell(held - R["on_first_sell"], m, "leader_first_sell"); reason = "first_sell"
                if R.get("runner"):
                    if xval(m) > 1.0: stop = max(stop, 1.0)
                    if full: sell(held, m, "runner_final"); reason = "first_sell_full"
            elif R.get("runner") and full:
                sell(held, m, "runner_final"); reason = "runner_final_sell"
            first_sell = False; last_mid = m; continue
        o, h, l, c = x; last_mid = c
        if xval(l) <= stop:
            mo = o if xval(o) <= stop else mid_for_x(stop) * STOP_SLIP
            sell(held, mo, "stop_be" if stop >= 1.0 else "stop"); reason = "stop_be" if stop >= 1.0 else "stop"; break
        if R["ladder"]:
            while tp_i < len(LADDER) and held > 1e-9 and xval(h) >= LADDER[tp_i][0]:
                lv, fr = LADDER[tp_i]; mo = o if xval(o) >= lv else mid_for_x(lv)
                sell(held if fr >= 1.0 else min(fr, held), mo, f"tp{tp_i+1}"); tp_i += 1
                if R["be"]: stop = max(stop, 1.0)
            if held <= 1e-9: reason = "tp3"; break
        if ts >= H: break
    if held > 1e-9: sell(held, last_mid, "horizon" if not flat08 else "flat_0800")
    ntx += 1                                                  # closeAccount (rent back) - live closes emptied token accounts
    pnl = proceeds - size - gas1 * ntx
    return dict(status="ok", pnl=pnl, ret=pnl / size, t=t, reason=reason, chase=chase, k=k, liq=liq0, curve=curve, ntx=ntx, gas=gas1 * ntx,
                caps=caps, cost_buy=cb, tp=tp_i, px_src="leader_fill" if ps.get("synthetic") else "pool")

def filt(e):
    sc = e.get("scout") or {}
    age = float(sc["age_at_entry_h"]) if sc.get("age_at_entry_h") not in (None, "") else None
    mcap = float(sc["mcap_at_entry_usd_approx"]) if sc.get("mcap_at_entry_usd_approx") not in (None, "") else None
    return dict(age_ok=age is not None and age >= 1.0, mcap_ok=(mcap or 0) >= 1e6, age=age, mcap=mcap)

def stats(tr, size):
    pn = [x["pnl"] for x in tr]; n = len(pn)
    if not n: return dict(n=0)
    closed = [{"t": x["t"], "pnl": x["pnl"], "ret": x["ret"], "is_oos": x["t"] >= HOLDOUT} for x in tr]
    st = {"trades": n, "mean_ret": statistics.fmean([x["ret"] for x in tr])}
    lo, hi = fs.boot_ci(pn) if n > 1 else (None, None)
    if lo is not None: st["ci_lo"] = lo / size
    mc = scoring.mc_drawdown(pn, BAL, 1000); sc = scoring.score(st, None, closed, mc)
    oos = [c["pnl"] for c in closed if c["is_oos"]]
    return dict(n=n, ev=statistics.fmean(pn), ev_pct=st["mean_ret"], med=statistics.median(pn), med_pct=statistics.median([x["ret"] for x in tr]),
                total=sum(pn), ex_best=sum(pn) - max(pn), ci=(lo, hi), win=sum(p > 0 for p in pn) / n, mc=mc, sc=sc,
                n_oos=len(oos), oos_net=sum(oos), oos_ev=statistics.fmean(oos) if oos else None, best=max(pn))

# ----------------------------------------------------------------------------------------------- report
LBL = ["_benjitrades", "bystevenr", "onlyzhynx"]          # neodot handed to Lab 2 (01:16 scope change)
RN = ["a10", "a60", "a120", "b", "c", "d"]
import random
def boot_mean(x, n=4000, seed=11):
    if len(x) < 2: return (None, None)
    rnd = random.Random(seed); m = sorted(statistics.fmean(rnd.choices(x, k=len(x))) for _ in range(n)); return m[int(.025 * n)], m[int(.975 * n) - 1]
def passes(e, r):
    fl = filt(e); liq_ok = (r.get("liq") or 0) >= 1e5 and r.get("px_src") == "pool"
    return fl["age_ok"] and fl["mcap_ok"] and liq_ok
def leader_own(es):
    v = [float(e["scout"]["pnl_pct_net5"]) / 100 for e in es if (e.get("scout") or {}).get("pnl_pct_net5") not in (None, "")]
    s = [float(e["scout"]["pnl_sol_net5"]) for e in es if (e.get("scout") or {}).get("pnl_sol_net5") not in (None, "")]
    if not v: return None
    return dict(n=len(v), mean=statistics.fmean(v), med=statistics.median(v), win=sum(x > 0 for x in v) / len(v), sol=sum(s), sol_ex=sum(s) - max(s))
def g(x, p=2): return "–" if x is None else f"{x:+.{p}f}"

def report():
    es = [e for e in load() if e.get("src") == "scout" and e["label"] in LBL]; DD = drift_defaults(es); L = []; W = L.append; res = {}
    W("## Winners batch 1 — Scout's round trips for benji / bystevenr / onlyzhynx, full hold horizons (PAPER ONLY)\n")
    W("_cr_win_replay.py. Scout's trades re-priced on-chain (public RPC): entry = leader's buy tx pool, +5 s with measured drift (artefacts outside 0.75–1.33 → leader median); "
      "his later buys/sells from his token account's signatures up to his exit + 2 min; price path = GeckoTerminal 1-min candles (15-min beyond 16.5 h) rescaled to the on-chain fill; "
      "horizon = min(his exit + 24 h, entry + 7 d), marked to market; stops gap through (open) else trigger × 0.975; self-copy costs (fitted Jupiter round trip vs pool liquidity, ≥0.5 %/side; "
      "pump.fun curve fee 1.25 %/side + curve impact on curve entries), prio 0.0001 SOL per tx + closeAccount tx. "
      "Rules: **a10/a60/a120** mirror his sell fractions at +10/60/120 s (price = candle at that moment; open→close interpolated), SL −20 %; **b** current ladder (+40 %→25 %, +100 %→25 %, +500 % rest; SL −20 %, breakeven after TP1); "
      "**c** b + sell all but 10 % on his first sell (+5 s); **d** no TPs, SL −20 %, sell all but 10 % on his first sell, runner exits on his final full sell / breakeven stop (if first sell filled above entry) / horizon. "
      "**Filters** = live entry filters: Scout's age_at_entry_h ≥ 1 h (blank/negative = fail), Scout's mcap_at_entry ≥ $1M, and liquidity ≥ $100k computed by us from the entry pool's on-chain reserves "
      "(Scout's liquidity column is blank; trades whose pool we could not decode count as FAIL). 08:00 = live flat at 08:00 Dublin applied (no entries 07:45–08:00 not applied). "
      "Held-out = entries ≥ 2026-10-15 07:00 UTC (fixed in advance) — **selection-contaminated**: Scout chose these wallets using these trades._\n")
    cov = {}
    for e in es:
        r = sim(e, "b", 10, 0.0001, 5, DD); cov.setdefault(e["label"], {}).setdefault(r["status"], 0); cov[e["label"]][r["status"]] += 1
    W("Coverage: " + "; ".join(f"**{k}** " + ", ".join(f"{a} {b}" for a, b in sorted(v.items())) for k, v in cov.items()) + "\n")
    for lab in LBL:
        E = [e for e in es if e["label"] == lab]; o = leader_own(E); res[lab] = {"own": o, "grid": {}, "out": []}
        W(f"### {lab}\n")
        if o: W(f"Leader's own (Scout, net of 5 %, his size): n={o['n']}, mean {o['mean']*100:+.1f} %, **median {o['med']*100:+.1f} %**, win {o['win']*100:.0f} %, total {o['sol']:+.1f} SOL, **ex-best {o['sol_ex']:+.1f} SOL**.\n")
        W("| filters | 08:00 flat | rule | n | mean $10 | median $10 | total $5 / $10 / $13 | ex-best $10 | win | Δ vs b $10 [95% CI] | in-sample n / total $10 | held-out n / total $10 |")
        W("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for fil in (False, True):
            for fl8 in (False, True):
                S = {}
                for ru in RN:
                    for z in (5, 10, 13):
                        S[(ru, z)] = [(e, r) for e in E for r in [sim(e, ru, z, 0.0001, 5, DD, fl8)] if r["status"] == "ok"]
                keep = {id(e) for e, r in S[("b", 10)] if (not fil) or passes(e, r)}
                for ru in RN:
                    T = {z: [r for e, r in S[(ru, z)] if id(e) in keep] for z in (5, 10, 13)}
                    t10 = T[10]
                    if not t10: W(f"| {'on' if fil else 'off'} | {'on' if fl8 else 'off'} | {ru} | 0 | | | | | | | | |"); continue
                    p = [r["pnl"] for r in t10]; bb = [r["pnl"] for e, r in S[("b", 10)] if id(e) in keep]
                    diff = [x - y for x, y in zip(p, bb)]; ci = boot_mean(diff)
                    ins = [r["pnl"] for r in t10 if r["t"] < HOLDOUT]; oos = [r["pnl"] for r in t10 if r["t"] >= HOLDOUT]
                    W(f"| {'on' if fil else 'off'} | {'on' if fl8 else 'off'} | {ru} | {len(p)} | {g(statistics.fmean(p))} | {g(statistics.median(p))} | "
                      f"{g(sum(r['pnl'] for r in T[5]))} / {g(sum(p))} / {g(sum(r['pnl'] for r in T[13]))} | {g(sum(p) - max(p))} | {sum(x > 0 for x in p) / len(p) * 100:.0f}% | "
                      f"{g(statistics.fmean(diff))} [{g(ci[0])}, {g(ci[1])}] | {len(ins)} / {g(sum(ins))} | {len(oos)} / {g(sum(oos))} |")
                    res[lab]["grid"][f"{int(fil)}{int(fl8)}_{ru}"] = dict(n=len(p), mean=statistics.fmean(p), med=statistics.median(p), total=sum(p), ex_best=sum(p) - max(p),
                        tot5=sum(r["pnl"] for r in T[5]), tot13=sum(r["pnl"] for r in T[13]), diff=statistics.fmean(diff), ci=ci, n_is=len(ins), is_tot=sum(ins), n_oos=len(oos), oos_tot=sum(oos))
        # outliers
        top = sorted(E, key=lambda e: -float(e["scout"]["pnl_sol_net5"] or 0))[:5]
        W(f"\nTop outliers ({lab}) — our % return per rule at $10 (no 08:00 flat | with 08:00 flat):\n")
        W("| token | entry (UTC) | his net5 SOL / % | " + " | ".join(RN) + " | passes filters (age / mcap / liq) |"); W("|---|---|---|" + "---|" * len(RN) + "---|")
        for e in top:
            cells = []
            for ru in RN:
                r0 = sim(e, ru, 10, 0.0001, 5, DD, False); r1 = sim(e, ru, 10, 0.0001, 5, DD, True)
                cells.append(f"{r0['ret']*100:+.0f}% | {r1['ret']*100:+.0f}%" if r0["status"] == "ok" else r0["status"])
            rb = sim(e, "b", 10, 0.0001, 5, DD); fl = filt(e)
            lq = f"${rb['liq']/1e3:.0f}k{'' if rb.get('px_src') == 'pool' else ' (pool unknown)'}" if rb["status"] == "ok" else "?"
            W(f"| {e.get('symbol')} | {dt.datetime.fromtimestamp(e['t'], dt.timezone.utc):%m-%d %H:%M}{' (held-out)' if e['t'] >= HOLDOUT else ''} | {float(e['scout']['pnl_sol_net5']):+.1f} / {float(e['scout']['pnl_pct_net5']):+.0f}% | "
              + " | ".join(cells) + f" | {'Y' if fl['age_ok'] else 'n'} ({fl['age']}) / {'Y' if fl['mcap_ok'] else 'n'} ({(fl['mcap'] or 0)/1e6:.1f}M) / {lq} |")
            res[lab]["out"].append(dict(sym=e.get("symbol"), sol=float(e["scout"]["pnl_sol_net5"]), ret={ru: sim(e, ru, 10, 0.0001, 5, DD, False).get("ret") for ru in RN},
                                        ret08={ru: sim(e, ru, 10, 0.0001, 5, DD, True).get("ret") for ru in RN}, passes=fl["age_ok"] and fl["mcap_ok"] and (rb.get("liq") or 0) >= 1e5 and rb.get("px_src") == "pool"))
        W("\n(Each rule cell shows 'no flat | flat'.)\n")
    ks = [r["k"] for e in es for r in [sim(e, "b", 10, 0.0001, 5, DD)] if r["status"] == "ok"]
    if len(ks) > 3:
        q = statistics.quantiles(ks, n=4); W(f"Validation: candle→on-chain rescale k median {statistics.median(ks):.3f} (IQR {q[0]:.3f}–{q[2]:.3f}); measured drift samples (buy/sell, +5 s medians): "
            + "; ".join(f"{k}: n={v['nb']}/{v['ns']}, {v['buy']['5s']:.3f}/{v['sell']['5s']:.3f}" for k, v in sorted(DD.items())) + ".\n")
    W("neodot (fresh launches): handed to Lab 2 at 01:16; not replayed here. Post-selection check: 0 completed round trips since Scout's cut (6 swaps, 3 still open).\n")
    return "\n".join(L), res

if __name__ == "__main__":
    md, res = report()
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", ".cr_win_section.md"), "w").write(md)
    json.dump(res, open(os.path.join(CR, "win_results.json"), "w"), default=str, indent=1)
    print(md)
