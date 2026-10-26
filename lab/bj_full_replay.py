"""PAPER ONLY. Full-horizon copy replay of Scout's winners round trips (_benjitrades 32, bystevenr 38, onlyzhynx 31) with the four exit
families Zero asked for, 08:00 Dublin flat on/off, live entry filters on/off, three cost models. Supersedes the winners section in
cr_win_replay.py (out/.cr_win_section.md, kept). Inputs (read-only): data/cr/win, data/cr/wcandles (on-chain fills + GT candles).
Outputs: out/benji_full_replay.md, out/.bj_rows.json (staging for merge_extra.py), data/cr/bj_results.json, data/cr/bj_trades.json."""
import json, os, math, statistics, calendar, datetime as dt, random
import copy_fee_sensitivity as fs, scoring
from cr_rpc import WSOL
from cr_candles import flat_time
import cr_win_replay as W
LAB = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(LAB, "out"); CR = os.path.join(LAB, "data", "cr")
HOLDOUT = W.HOLDOUT                       # 2026-10-15 07:00 UTC, fixed before any CR result (last 9 of 30 Dublin nights)
BAL = 100.0; STOP_SLIP = 0.975; PUMP_FEE = 0.0125; V_SOL0 = 30.0
DELAY = 5
# exit families (triggers are on mark-to-market value net of exit cost, x = value / stake, as in all earlier CR/winners tests)
RULES = {
  "A_mirror": dict(sl=None, tps=[], be=False, trail=None, mirror=True),                         # (a) mirror his sell fractions, no stop
  "B_ladder": dict(sl=0.80, tps=[(1.4, 0.25), (2.0, 0.25), (6.0, 1.0)], be=True, trail=None, mirror=False),  # (b) current ladder, SL -20%, BE after TP1
  "C_live":   dict(sl=0.85, tps=[(1.5, 0.5)], be=False, trail=0.85, mirror=False),             # (c) new live: SL -15%, TP +50% half, then 15% trail
  "D_old":    dict(sl=0.75, tps=[(2.0, 0.5)], be=False, trail=None, mirror=True),              # (d) old: SL -25%, TP +100% half, mirror his sells
}
# cost models: round trip (one buy + one sell, gas included) + liquidity-scaled impact; extra sell legs add per-tx gas
COSTS = {"self5": dict(size=5.0, rt=0.047, leg=0.02), "self10": dict(size=10.0, rt=0.030, leg=0.02), "cf10": dict(size=10.0, rt=0.053, leg=0.015)}
LBL = ["_benjitrades", "bystevenr", "onlyzhynx"]
_imp = None
def imp():
    global _imp
    if _imp is None: _imp = fs.impact_only_fn(W.fit())
    return _imp

def sim(e, rule, ck, DD, flat08=False):
    R = RULES[rule]; K = COSTS[ck]; size = K["size"]; t = e["t"]; d = f"{DELAY}s"; ps = e.get("ps")
    if not e.get("leader_px"): return dict(status="no_pool_price")
    if not ps or not ps.get("fill"):
        ps = dict(fill=e["leader_px"], qmint="USD", quote=None, curve=False, alt=[], synthetic=True)
    if not e.get("C") or not e["C"].get("rows1"): return dict(status="no_candles")
    sol = fs.solpx(t); u = sol if ps["qmint"] == WSOL else 1.0
    dd = DD[e["label"]]
    drift = (e.get("dpx") or {}).get(d) if (e.get("dpx") or {}).get(d + "_trade") else None
    clamped = drift is None or not 0.75 <= drift <= 1.33
    if clamped: drift = dd["buy"][d]                             # missing or outside 0.75-1.33 -> leader median
    mid0 = ps["fill"] * u * drift; curve = ps.get("curve"); base = K["rt"] / 2
    if curve:
        vsol0 = V_SOL0 + ps["quote"]; liq0 = 2 * vsol0 * sol
        def cost(mid, z): return base + (z / sol) / (vsol0 * math.sqrt(max(mid / mid0, 1e-6)))
    else:
        liq0 = max([p["quote"] * (sol if p["qmint"] == WSOL else 1) + p["base"] * e["leader_px"] for p in [ps] + ps.get("alt", []) if p.get("quote")] or [1e5 if ps.get("synthetic") else 1e4])
        def cost(mid, z): return base + imp()(max(liq0 * math.sqrt(max(mid / mid0, 1e-6)), 1e3), z)
    cb = cost(mid0, size); buypx = mid0 * (1 + cb); chase = mid0 / e["leader_px"] - 1   # price chase vs his fill, cost-independent
    te = t + DELAY; tokens = size / buypx; held = 1.0; proceeds = 0.0; legs = 0
    rows = [r for r in e["C"]["rows1"] if r[0] <= te]
    gref = rows[-1][4] if rows else e["C"]["rows1"][0][1]; k = mid0 / gref
    H = min(e["C"]["H"], flat_time(te)) if flat08 else e["C"]["H"]
    def xval(mid): return mid * (1 - cost(mid, size * max(held, 0.01))) / buypx
    def mid_for_x(x):
        m = buypx * x
        for _ in range(3): m = x * buypx / (1 - cost(m, size * max(held, 0.01)))
        return m
    exits = []
    def sell(q, mid, why):
        nonlocal held, proceeds, legs
        q = min(q, held)
        if q <= 1e-12: return
        proceeds += tokens * q * mid * (1 - cost(mid, size * q)); held -= q; legs += 1; exits.append(why)
    P = W.path(e, k)
    ev = [("c", t1, ohlc) for t0, t1, ohlc in P if t0 > (rows[-1][0] if rows else te - 60) and t1 <= H + 900]
    for s in e.get("swaps") or []:
        if s["t"] + DELAY < H and s["t"] >= t: ev.append(("s", s["t"] + DELAY, s))
    ev.sort(key=lambda z: (z[1], 0 if z[0] == "s" else 1))
    lb = e.get("entry_tokens") or 0; first_sell = True; tp_i = 0; stop = R["sl"]; last_mid = mid0; peak = None; reason = "horizon"; nsells = 0
    for typ, ts, x in ev:
        if held <= 1e-9: break
        if typ == "s":
            if x["tokens"] > 0: lb += x["tokens"]; continue
            q = -x["tokens"]; pre = x.get("pre_bal") or lb; fr = q / pre if pre > 0 else 1.0
            full = fr >= 0.95 or (pre - q) <= 0.05 * max(lb, 1e-9); pool = x.get("pool") or {}
            sd = (e.get("sell_dpx") or {}).get(d) if first_sell and (e.get("sell_dpx") or {}).get(d + "_trade") else dd["sell"][d]
            if sd is None or not 0.75 <= sd <= 1.33: sd = dd["sell"][d]
            m = pool["fill"] * (fs.solpx(x["t"]) if pool.get("qmint") == WSOL else 1.0) * sd if pool.get("fill") else (x.get("avg_px") or last_mid) * sd
            nsells += 1; first_sell = False; last_mid = m
            if R["mirror"]:
                sell(held if full else held * fr, m, "mirror_full" if full else "mirror_part")
                if full: reason = "mirror_full"
                continue
            x = (m, m, m, m)                 # non-mirror rules: his sell print is a real price tick -> stops/targets see it too
        o, h, l, c = x; last_mid = c
        # stop / trail checked before targets in the same candle
        lvl = None
        if peak is not None and R["trail"]: lvl = max(stop or 0, peak * R["trail"])
        elif stop is not None: lvl = stop
        if lvl is not None and xval(l) <= lvl:
            mo = o if xval(o) <= lvl else mid_for_x(lvl) * STOP_SLIP
            why = "trail" if peak is not None else ("stop_be" if lvl >= 1.0 else "stop")
            sell(held, mo, why); reason = why; break
        while tp_i < len(R["tps"]) and held > 1e-9 and xval(h) >= R["tps"][tp_i][0]:
            lv, fr = R["tps"][tp_i]; mo = o if xval(o) >= lv else mid_for_x(lv)
            sell(held if fr >= 1.0 else min(fr, held), mo, f"tp{tp_i+1}"); tp_i += 1
            if R["be"]: stop = max(stop, 1.0)
            if R["trail"]: peak = max(peak or 0, lv)
        if held <= 1e-9: reason = f"tp{tp_i}"; break
        if peak is not None: peak = max(peak, xval(h))
        if ts >= H: break
    if held > 1e-9:
        why = "flat_0800" if flat08 and H < e["C"]["H"] else "horizon"; sell(held, last_mid, why); reason = why
    extra = max(0, legs - 1) * K["leg"]
    pnl = proceeds - size - extra
    return dict(status="ok", pnl=pnl, ret=pnl / size, t=t, reason=reason, rt0=2 * cb + 2 * K["leg"] / size * 0, chase=chase, liq=liq0, curve=bool(curve), legs=legs, k=k,
                clamped=clamped, px_src="leader_fill" if ps.get("synthetic") else "pool", exits=exits, his_sells=nsells)

def passes(e, r):
    fl = W.filt(e)
    return fl["age_ok"] and fl["mcap_ok"] and (r.get("liq") or 0) >= 1e5 and r.get("px_src") == "pool" and r["chase"] <= 0.08

def boot(x, n=4000, seed=11):
    if len(x) < 2: return (None, None)
    rnd = random.Random(seed); m = sorted(statistics.fmean(rnd.choices(x, k=len(x))) for _ in range(n)); return m[int(.025 * n)], m[int(.975 * n) - 1]

def stats(tr, size, split):
    pn = [r["pnl"] for r in tr]; n = len(pn)
    if not n: return dict(n=0)
    closed = [{"t": r["t"], "pnl": r["pnl"], "ret": r["ret"], "is_oos": r["t"] >= split} for r in tr]
    rets = [r["ret"] for r in tr]; lo, hi = boot(rets)
    st = {"trades": n, "mean_ret": statistics.fmean(rets)}
    if lo is not None: st["ci_lo"] = lo
    mc = scoring.mc_drawdown(pn, BAL, 1000); sc = scoring.score(st, None, closed, mc)
    ins = [c for c in closed if not c["is_oos"]]; oos = [c for c in closed if c["is_oos"]]
    return dict(n=n, mean=statistics.fmean(pn), mean_ret=st["mean_ret"], med_ret=statistics.median(rets), total=sum(pn), ex_best=sum(pn) - max(pn),
                ci=(lo, hi), win=sum(p > 0 for p in pn) / n, mc=mc, sc=sc, n_is=len(ins), is_tot=sum(c["pnl"] for c in ins),
                n_oos=len(oos), oos_tot=sum(c["pnl"] for c in oos), oos_mean_ret=statistics.fmean([c["ret"] for c in oos]) if oos else None,
                is_mean_ret=statistics.fmean([c["ret"] for c in ins]) if ins else None)

def g(x, p=2): return "–" if x is None else f"{x:+.{p}f}"
def pc(x): return "–" if x is None else f"{x*100:+.1f}%"
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")

def main():
    es = [e for e in W.load() if e.get("src") == "scout" and e["label"] in LBL]; DD = W.drift_defaults(es)
    res = {"grid": {}, "outliers": {}, "cov": {}}; trades_dump = []
    # per-leader alternative split: last 30% of that leader's covered entries by time (secondary, NOT pre-registered)
    alt_split = {}
    for lab in LBL:
        ts = sorted(e["t"] for e in es if e["label"] == lab and e.get("C") and e["C"].get("rows1"))
        alt_split[lab] = ts[int(len(ts) * 0.7)] if ts else HOLDOUT
    G = {}
    for lab in LBL:
        E = [e for e in es if e["label"] == lab]
        for ck in COSTS:
            for fl8 in (False, True):
                for ru in RULES:
                    G[(lab, ck, fl8, ru)] = [(e, sim(e, ru, ck, DD, fl8)) for e in E]
    cov = {}
    for lab in LBL:
        c = {}
        for e, r in G[(lab, "self10", False, "A_mirror")]: c[r["status"]] = c.get(r["status"], 0) + 1
        ok = [(e, r) for e, r in G[(lab, "self10", False, "A_mirror")] if r["status"] == "ok"]
        c["pass_filters"] = sum(passes(e, r) for e, r in ok); c["pre_bal_gt0"] = sum((e.get("pre_bal") or 0) > 1e-9 for e in es if e["label"] == lab)
        c["drift_clamped"] = sum(r["clamped"] for e, r in ok); c["synthetic_px"] = sum(r["px_src"] != "pool" for e, r in ok)
        c["n_oos_fixed"] = sum(e["t"] >= HOLDOUT for e, r in ok); c["n_oos_alt"] = sum(e["t"] >= alt_split[lab] for e, r in ok)
        c["fail_reasons"] = {}
        for e, r in ok:
            fl = W.filt(e)
            for k_, bad in (("age", not fl["age_ok"]), ("mcap", not fl["mcap_ok"]), ("liq", not ((r.get("liq") or 0) >= 1e5 and r.get("px_src") == "pool")), ("chase", r["chase"] > 0.08)):
                if bad: c["fail_reasons"][k_] = c["fail_reasons"].get(k_, 0) + 1
        cov[lab] = c
    res["cov"] = cov; res["alt_split"] = {k: iso(v) for k, v in alt_split.items()}
    rows = []; cfgs = []
    for (lab, ck, fl8, ru), lst in G.items():
        for fil in (False, True):
            keep = [(e, r) for e, r in lst if r["status"] == "ok" and (not fil or passes(e, r))]
            tr = [r for e, r in keep]; size = COSTS[ck]["size"]
            S = stats(tr, size, HOLDOUT); S2 = stats(tr, size, alt_split[lab])
            key = f"{lab}|{ck}|{'flat' if fl8 else 'full'}|{'filt' if fil else 'all'}|{ru}"
            res["grid"][key] = dict(S, alt_n_oos=S2.get("n_oos"), alt_oos_tot=S2.get("oos_tot"), alt_oos_mean_ret=S2.get("oos_mean_ret"),
                                    alt_is_tot=S2.get("is_tot"), reasons={x: sum(r["reason"] == x for r in tr) for x in set(r["reason"] for r in tr)})
            for e, r in keep: trades_dump.append(dict(key=key, sym=e.get("symbol"), mint=e["mint"], t=e["t"], pnl=r["pnl"], ret=r["ret"], reason=r["reason"], chase=r["chase"], liq=r["liq"]))
            name = f"CR_BJ_{lab.strip('_')}_{ru.split('_')[0]}_{ck}_{'flat08' if fl8 else 'full'}_{'filt' if fil else 'nofilt'}"
            cfg = dict(family="benji_full_replay", leader=lab, exit=ru, cost=ck, flat08=fl8, filters=fil, delay=DELAY, rules=RULES[ru], costm=COSTS[ck], name=name)
            cfgs.append(cfg)
            if not S["n"]:
                rows.append(dict(variant=name, trades=0, family="benji_full_replay", candidate="no", score_total=None, note="no trades")); continue
            sc = S["sc"]; ho = "yes" if (S["n_oos"] >= 20 and S["is_tot"] > 0 and (S["oos_mean_ret"] or 0) > 0) else f"insufficient (n_out={S['n_oos']}<20)" if S["n_oos"] < 20 else "no"
            cand = "yes" if sc["score_total"] >= 18 and S["n"] >= 50 and ho == "yes" else "no"
            rows.append(dict(variant=name, trades=S["n"], win_rate=round(S["win"], 3), net_profit_after_costs=round(S["total"], 2),
                max_drawdown=round(S["mc"][1] * BAL, 2) if S["mc"] else None, holds_out_of_sample=ho, n_in_sample=S["n_is"], n_out_of_sample=S["n_oos"],
                mean_ret=round(S["mean_ret"], 3), median_ret=round(S["med_ret"], 3), ci95_mean_ret=f"[{g(S['ci'][0])},{g(S['ci'][1])}]" if S["ci"][0] is not None else "",
                oos_mean_ret=round(S["oos_mean_ret"], 3) if S["oos_mean_ret"] is not None else None, in_net_pnl=round(S["is_tot"], 2), out_net_pnl=round(S["oos_tot"], 2),
                **{k_: sc[k_] for k_ in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
                net_ex_best_trade=round(S["ex_best"], 2), mc_dd_p5=round(S["mc"][0], 3), mc_dd_p50=round(S["mc"][1], 3), mc_dd_p95=round(S["mc"][2], 3),
                candidate=cand, lucky_number="n/a (exit-rule grid)", family="benji_full_replay",
                note=f"PAPER full-horizon replay of Scout's {lab} round trips; exit {ru}, {ck}, {'08:00 flat' if fl8 else 'full horizon'}, filters {'on' if fil else 'off'}; SELECTION-CONTAMINATED (Scout picked wallet on these trades); see out/benji_full_replay.md"))
    # outliers
    for lab in LBL:
        E = [e for e in es if e["label"] == lab]
        top = sorted(E, key=lambda e: -float((e.get("scout") or {}).get("pnl_sol_net5") or 0))[:5]
        out = []
        for e in top:
            cell = {}
            for ru in RULES:
                for fl8 in (False, True):
                    r = sim(e, ru, "self10", DD, fl8); cell[f"{ru}|{int(fl8)}"] = r
            rb = cell["A_mirror|0"]
            out.append(dict(sym=e.get("symbol"), t=e["t"], sol=float(e["scout"]["pnl_sol_net5"]), pct=float(e["scout"]["pnl_pct_net5"]),
                            n_buys=e["scout"].get("n_buys"), hold=e["scout"].get("hold_min"), cells={k_: (v.get("ret"), v.get("reason")) if v["status"] == "ok" else (None, v["status"]) for k_, v in cell.items()},
                            passes=passes(e, rb) if rb["status"] == "ok" else None, filt=W.filt(e), liq=rb.get("liq"), chase=rb.get("chase")))
        res["outliers"][lab] = out
    res["drift"] = {k: v for k, v in DD.items()}
    res["rt0"] = {}
    for lab in LBL:
        for ck in COSTS:
            v = sorted(r["rt0"] for e, r in G[(lab, ck, False, "A_mirror")] if r["status"] == "ok")
            vf = sorted(r["rt0"] for e, r in G[(lab, ck, False, "A_mirror")] if r["status"] == "ok" and passes(e, r))
            res["rt0"][f"{lab}|{ck}"] = dict(med=statistics.median(v) if v else None, p90=v[int(.9 * len(v))] if v else None, med_filt=statistics.median(vf) if vf else None)
    res["leader"] = {}
    for lab in LBL:
        E = [e for e in es if e["label"] == lab]; sol = lambda e: float((e.get("scout") or {}).get("pnl_sol_net5") or 0)
        res["leader"][lab] = dict(n=len(E), net5=sum(map(sol, E)), net5_is=sum(sol(e) for e in E if e["t"] < HOLDOUT), n_oos=sum(e["t"] >= HOLDOUT for e in E),
                                  net5_oos=sum(sol(e) for e in E if e["t"] >= HOLDOUT), best=max(map(sol, E)), ex_best=sum(map(sol, E)) - max(map(sol, E)))
    json.dump(res, open(os.path.join(CR, "bj_results.json"), "w"), default=str, indent=1)
    json.dump(trades_dump, open(os.path.join(CR, "bj_trades.json"), "w"), default=str)
    json.dump(dict(rows=rows, variant_configs=cfgs), open(os.path.join(OUT, ".bj_rows.json"), "w"), default=str, indent=0)
    print("done", len(rows))

if __name__ == "__main__": main()
