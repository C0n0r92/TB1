#!/usr/bin/env python3
"""Mid-cap Solana momentum (PAPER research only). Data from midcap_fetch.py (cache data/midcap/, no network here).
Universe (point-in-time as far as free data allows): token age > 7 d, mcap $5M-$200M, liquidity > $500k at the SIGNAL bar.
Rules: close > EMA(L) and close > highest high of previous N bars -> enter next bar OPEN. Stop fixed % (from entry) or
ATR(14) chandelier (highest high since entry - k*ATR). Exit also on close < EMA -> next bar open. Max 3 open, 10% of
starting equity per trade (cap is 15%). Cost 0.3% or 0.5% per side. Holdout: last 30% of days, read ONLY for the
settings fixed on in-sample (phase 2)."""
import json, math, os, random, statistics, sys, time, datetime as dt, glob
import scoring
from labcore import LAB, night_of
D = os.path.join(LAB, "data", "midcap"); OH = os.path.join(D, "ohlcv"); OUT = os.path.join(LAB, "out")
EQ, STAKE_F = 1000.0, 0.10; STAKE = EQ * STAKE_F; MAX_OPEN = 3; DAY = 86400
EMAS, NS = (50, 100, 200), (12, 24, 48)
STOPS = [("pct", 0.08), ("pct", 0.12), ("pct", 0.20), ("atr", 2.0), ("atr", 3.0), ("atr", 4.0)]
COSTS = (0.003, 0.005)

def ema(xs, L):
    a = 2 / (L + 1); out = []; e = None
    for x in xs: e = x if e is None else e + a * (x - e); out.append(e)
    return out

def atr(H, Lo, C, n=14):
    tr = [H[0] - Lo[0]] + [max(H[i] - Lo[i], abs(H[i] - C[i - 1]), abs(Lo[i] - C[i - 1])) for i in range(1, len(C))]
    out, a = [], None
    for x in tr: a = x if a is None else a + (x - a) / n; out.append(a)
    return out

def load():
    meta = {p["mint"]: p for p in json.load(open(os.path.join(D, "prefilter.json")))}
    toks = {}
    for m, p in meta.items():
        f = os.path.join(OH, f"rows_{m}.json")
        if not os.path.exists(f): continue
        rows = [r for r in json.load(open(f)) if r[4] > 0]
        if len(rows) < 260: continue
        T = [int(r[0]) for r in rows]; O, H, Lo, C, V = ([float(r[k]) for r in rows] for k in (1, 2, 3, 4, 5))
        mc_now = p.get("mcap") or p.get("fdv") or p.get("ds_mcap") or 0; px_now = C[-1]
        if not mc_now or not px_now: continue
        supply = mc_now / px_now                                                  # assumes constant supply (no unlock/burn)
        liq_now = max(p.get("ds_liq_total") or 0, p.get("liq") or 0)
        births = [T[0]]
        try: births.append(dt.datetime.fromisoformat(p["pool_created"].replace("Z", "+00:00")).timestamp())
        except Exception: pass
        if p.get("ds_first_pair_ms"): births.append(p["ds_first_pair_ms"] / 1000)
        toks[m] = dict(sym=p.get("symbol"), T=T, O=O, H=H, L=Lo, C=C, V=V, supply=supply, liq_now=liq_now, px_now=px_now,
                       birth=min(births), atr=atr(H, Lo, C), ema={L: ema(C, L) for L in EMAS}, e20=ema(C, 20))
    sol = None
    f = os.path.join(OH, "rows_SOL.json")
    if os.path.exists(f): sol = {int(r[0]): float(r[4]) for r in json.load(open(f))}
    return toks, sol

def eligible(k, i):
    t = k["T"][i]; c = k["C"][i]
    if t - k["birth"] < 7 * DAY: return False
    mc = c * k["supply"]
    liq = k["liq_now"] * math.sqrt(c / k["px_now"])                               # CPMM: pool $ value ~ sqrt(price) if LP unchanged
    return 5e6 <= mc <= 2e8 and liq > 5e5

def candidates(toks, L, N, stop, cost):
    out = []
    for m, k in toks.items():
        T, O, H, Lo, C, E, A = k["T"], k["O"], k["H"], k["L"], k["C"], k["ema"][L], k["atr"]
        n = len(C)
        for i in range(max(L, N, 20), n - 1):
            if not (C[i] > E[i] and C[i] > max(H[i - N:i])): continue
            if T[i + 1] - T[i] > 3 * 3600: continue                               # data gap: next bar not ~1 h later
            if not eligible(k, i): continue
            j = i + 1; entry = O[j]; hh = H[j]
            st = entry * (1 - stop[1]) if stop[0] == "pct" else entry - stop[1] * A[i]
            ex = None; why = "end"
            for q in range(j, n):
                if stop[0] == "atr" and q > j: st = max(st, hh - stop[1] * A[q - 1])
                if Lo[q] <= st: ex = (T[q], min(O[q], st) if q > j else min(entry, st) if O[q] <= st else st); why = "stop"; break
                hh = max(hh, H[q])
                if C[q] < E[q] and q + 1 < n: ex = (T[q + 1], O[q + 1]); why = "ema"; break
            if ex is None: ex = (T[-1], C[-1])
            ret = ex[1] * (1 - cost) / (entry * (1 + cost)) - 1
            out.append(dict(mint=m, sym=k["sym"], t=T[j], exit_t=ex[0], ret=ret, pnl=STAKE * ret, why=why, vol=k["V"][i]))
    return out

from zoneinfo import ZoneInfo
DUB = ZoneInfo("Europe/Dublin")
def _dub_min(t): d = dt.datetime.fromtimestamp(t, DUB); return d.hour * 60 + d.minute

def oc_live(toks, cost, window=True):
    """Pre-registered baseline = Chunk's runner-radar/oldcoins.py rule (read-only copy of the logic): 7d+/5-200M/liq>=500k/
    vol24>=1M; close > EMA50 > EMA200, close > prior-24-bar high, bar volume > prior-20-bar mean; enter next open (only
    21:00-07:30 Dublin when window=True); stop = max(breakout-bar low, entry-8%); half off at +15%; then exit on close <
    EMA20; flat at the 07:00-08:00 Dublin bar close (Chunk: 07:45) when window=True. Intrabar: stop checked before TP."""
    out = []
    for m, k in toks.items():
        T, O, H, Lo, C, V = k["T"], k["O"], k["H"], k["L"], k["C"], k["V"]
        E50, E200, E20 = k["ema"][50], k["ema"][200], k["e20"]
        n = len(C)
        for i in range(220, n - 1):
            if not (C[i] > E50[i] > E200[i] and C[i] > max(H[i - 24:i]) and V[i] > sum(V[i - 20:i]) / 20): continue
            if sum(V[i - 23:i + 1]) < 1e6 or T[i + 1] - T[i] > 3 * 3600 or not eligible(k, i): continue
            j = i + 1
            if window:
                mm = _dub_min(T[j])
                if not (mm >= 21 * 60 or mm < 7 * 60 + 30): continue
            e = O[j]; stop = max(Lo[i], e * 0.92)
            if stop >= e: stop = e * 0.92
            tp = e * 1.15; rem = 1.0; got = 0.0; why = "end"; ex_t = T[-1]
            for q in range(j, n):
                if Lo[q] <= stop:
                    px = min(O[q], stop) if q > j else stop; got += rem * px; rem = 0; why = "stop"; ex_t = T[q]; break
                if rem == 1.0 and H[q] >= tp: got += 0.5 * tp; rem = 0.5; continue
                if rem < 1.0 and C[q] < E20[q]: got += rem * C[q]; rem = 0; why = "trail"; ex_t = T[q]; break
                if window and q > j and _dub_min(T[q]) == 7 * 60:      # bar 07:00-08:00 Dublin -> flat at its close
                    got += rem * C[q]; rem = 0; why = "eod"; ex_t = T[q] + 3600; break
            if rem: got += rem * C[-1]
            ret = got * (1 - cost) / (e * (1 + cost)) - 1
            out.append(dict(mint=m, sym=k["sym"], t=T[j], exit_t=ex_t, ret=ret, pnl=STAKE * ret, why=why, vol=V[i]))
    return out

def portfolio(cands):
    cands.sort(key=lambda c: (c["t"], -c["vol"]))
    open_, taken = [], []
    for c in cands:
        open_ = [o for o in open_ if o["exit_t"] > c["t"]]
        if len(open_) >= MAX_OPEN or any(o["mint"] == c["mint"] for o in open_): continue
        open_.append(c); taken.append(c)
    return taken

def boot(rets, iters=5000, seed=7):
    if len(rets) < 2: return (None, None)
    r = random.Random(seed); b = sorted(statistics.fmean(r.choices(rets, k=len(rets))) for _ in range(iters))
    return b[int(.025 * iters)], b[int(.975 * iters) - 1]

def stats(tr):
    rets = [t["ret"] for t in tr]
    if not tr: return dict(trades=0, mean_ret=None, net_pnl=0.0)
    lo, hi = boot(rets); eq = pk = EQ; dd = 0
    for t in sorted(tr, key=lambda t: t["exit_t"]): eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(trades=len(tr), mean_ret=statistics.fmean(rets), median_ret=statistics.median(rets), win_rate=sum(r > 0 for r in rets) / len(rets),
                net_pnl=sum(t["pnl"] for t in tr), ci_lo=lo if lo is not None else -1, ci_hi=hi, max_dd=dd,
                ex_best=sum(t["pnl"] for t in tr) - max(t["pnl"] for t in tr), sd=statistics.pstdev(rets))

def name(L, N, stop=None, cost=None):
    if L == "OC": return f"MC_OC_live{'' if N else '_24h'}_c{stop * 1000:g}"
    return f"MC_ema{L}_n{N}_{stop[0]}{stop[1]:g}_c{cost * 1000:g}"

def main():
    toks, sol = load()
    allT = sorted({t for k in toks.values() for t in k["T"]})
    # first day any token is eligible-with-EMA200-warmup -> last day; split at 70 %
    t0 = min(k["T"][200] for k in toks.values()); t1 = max(allT)
    split = t0 + 0.7 * (t1 - t0)
    grid = [(L, N, s, c) for c in COSTS for L in EMAS for N in NS for s in STOPS]
    res = {}
    for g in grid:
        tr = portfolio(candidates(toks, *g))
        for t in tr: t["is_oos"] = t["t"] >= split
        res[g] = tr
    OCK = [("OC", w, c) for w in (True, False) for c in (0.003, 0.005, 0.01)]
    for g in OCK:
        tr = portfolio(oc_live(toks, g[2], g[1]))
        for t in tr: t["is_oos"] = t["t"] >= split
        res[g] = tr
    # ---------- phase 1: in-sample only ----------
    IS = {g: stats([t for t in res[g] if not t["is_oos"]]) for g in grid}
    def is_ok(g): s = IS[g]; return s["trades"] >= 5 and s["net_pnl"] > 0
    def neigh(g):
        L, N, s, c = g; out = []
        li, ni, si = EMAS.index(L), NS.index(N), STOPS.index(s)
        for d in (-1, 1):
            if 0 <= li + d < 3: out.append((EMAS[li + d], N, s, c))
            if 0 <= ni + d < 3: out.append((L, NS[ni + d], s, c))
            if 0 <= si + d < 6 and STOPS[si + d][0] == s[0]: out.append((L, N, STOPS[si + d], c))
        return out
    lucky = {g: (is_ok(g) and not all(is_ok(x) for x in neigh(g))) for g in grid}
    nb_ok = {g: sum(is_ok(x) for x in neigh(g)) / len(neigh(g)) for g in grid}
    # selection on the 0.5 % cost (conservative) grid: IS mean ret, require >=30 IS trades and no lucky flag
    sel_pool = [g for g in grid if g[3] == 0.005 and IS[g]["trades"] >= 30 and not lucky[g] and IS[g]["mean_ret"] is not None]
    if not sel_pool: sel_pool = [g for g in grid if g[3] == 0.005 and IS[g]["trades"] >= 10]
    best = max(sel_pool, key=lambda g: (IS[g]["mean_ret"] - IS[g]["sd"] / math.sqrt(IS[g]["trades"]), IS[g]["trades"]))
    json.dump(dict(L=best[0], N=best[1], stop=list(best[2]), fixed_at=time.time(), split=split), open(os.path.join(D, "fixed_settings.json"), "w"))
    # ---------- phase 2: holdout read for the fixed settings (both costs) + neighbours ----------
    chosen = [best, (best[0], best[1], best[2], 0.003)]
    def full(g):
        tr = res[g]; closed = sorted(tr, key=lambda t: t["exit_t"]); st = stats(tr)
        si, so = stats([t for t in tr if not t["is_oos"]]), stats([t for t in tr if t["is_oos"]])
        mc = scoring.mc_drawdown([t["pnl"] for t in closed], EQ, 1000, 7) if closed else None
        st2 = dict(st, ci_lo=si.get("ci_lo", -1)) if False else st
        sc = scoring.score(st2, so, closed, mc)
        return st, si, so, mc, sc
    def bh(t_a, t_b):
        rs = []
        for k in toks.values():
            ia = next((i for i, t in enumerate(k["T"]) if t >= t_a), None); ib = max((i for i, t in enumerate(k["T"]) if t <= t_b), default=None)
            if ia is None or ib is None or ib <= ia or not eligible(k, ia): continue
            rs.append(k["C"][ib] / k["O"][ia] - 1)
        s = None
        if sol:
            ks = sorted(sol); a = next((x for x in ks if x >= t_a), None); b = max((x for x in ks if x <= t_b), default=None)
            if a and b: s = sol[b] / sol[a] - 1
        return (statistics.fmean(rs) if rs else None, statistics.median(rs) if rs else None, len(rs), s)
    bh_is, bh_oos = bh(t0, split), bh(split, t1)
    iso = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
    pct = lambda x: "n/a" if x is None else f"{x * 100:+.1f}%"
    L_ = ["# Mid-cap Solana momentum (1h) - PAPER research, first read", "",
          f"Run {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Tokens with usable 1h history: {len(toks)}. "
          f"Window {iso(t0)} -> {iso(t1)}; in-sample {iso(t0)} -> {iso(split)}, HELD-OUT {iso(split)} -> {iso(t1)} (last 30% of days, read only after settings were fixed on in-sample).",
          f"Grid: EMA {EMAS} x N {NS} x stops {['%s %g' % s for s in STOPS]} x cost/side {COSTS} = {len(grid)} variants. "
          f"Sizing: ${STAKE:.0f} (10% of ${EQ:.0f} paper) per trade, max {MAX_OPEN} open, entry next-bar open, no same-token stacking; simultaneous signals ranked by signal-bar $ volume.", ""]
    st, si, so, mc, sc = full(best)
    L_ += ["## Short answer", "",
           f"- Fixed on in-sample (0.5%/side cost, >= 30 IS trades, no lucky flag, best mean minus 1 s.e.): **{name(*best)}**.",
           f"- In-sample: {si['trades']} trades, mean {pct(si['mean_ret'])}/trade, median {pct(si.get('median_ret'))}, win {si.get('win_rate', 0) * 100:.0f}%, net ${si['net_pnl']:+.2f}, CI [{pct(si.get('ci_lo'))}, {pct(si.get('ci_hi'))}].",
           f"- Held-out: {so['trades']} trades, mean {pct(so['mean_ret'])}/trade, median {pct(so.get('median_ret'))}, win {(so.get('win_rate') or 0) * 100:.0f}%, net ${so['net_pnl']:+.2f}, CI [{pct(so.get('ci_lo'))}, {pct(so.get('ci_hi'))}].",
           f"- Score {sc['score_total']}/25 (oos {sc['sc_oos_risk']}, dd {sc['sc_drawdown']}, n {sc['sc_trades']}, edge {sc['sc_edge']}, stab {sc['sc_stability']}); MC DD p95 {mc[2] * 100 if mc else 0:.1f}% of ${EQ:.0f}; nights +{sc['nights_profitable']}/{sc['nights']}.",
           ]
    cand = sc["score_total"] >= 18 and st["trades"] >= 50 and so["trades"] >= 20 and (so.get("ci_lo") or -1) > 0
    L_ += [f"- Candidate (>= 18/25, >= 50 trades, >= 20 OOS trades with OOS CI low > 0): **{'YES' if cand else 'NO'}**.", ""]
    L_ += ["## Benchmarks (same windows)", "", "| window | strategy net (% of $1,000) | universe buy&hold equal-weight mean / median (n) | SOL |", "|---|---|---|---|",
           f"| in-sample | {si['net_pnl'] / EQ * 100:+.1f}% | {pct(bh_is[0])} / {pct(bh_is[1])} ({bh_is[2]}) | {pct(bh_is[3])} |",
           f"| held-out | {so['net_pnl'] / EQ * 100:+.1f}% | {pct(bh_oos[0])} / {pct(bh_oos[1])} ({bh_oos[2]}) | {pct(bh_oos[3])} |", "",
           "Strategy exposure is at most 30% of equity (3 x 10%), buy&hold is 100% invested; compare per-$ via mean/trade vs buy&hold if needed.", ""]
    L_ += ["## In-sample grid (0.5%/side; 0.3% in brackets) - mean/trade, trades, IS net $, neighbour share profitable, lucky flag", "",
           "| EMA | N | stop | IS trades | IS mean (0.3%) | IS net $ (0.3%) | IS CI low | neighbours profitable | lucky |", "|---|---|---|---|---|---|---|---|---|"]
    for Lx in EMAS:
        for Nx in NS:
            for s in STOPS:
                g5, g3 = (Lx, Nx, s, 0.005), (Lx, Nx, s, 0.003); a, b = IS[g5], IS[g3]
                L_.append(f"| {Lx} | {Nx} | {s[0]} {s[1]:g} | {a['trades']} | {pct(a['mean_ret'])} ({pct(b['mean_ret'])}) | {a['net_pnl']:+.0f} ({b['net_pnl']:+.0f}) | "
                          f"{pct(a.get('ci_lo')) if a['trades'] > 1 else 'n/a'} | {nb_ok[g5] * 100:.0f}% | {'YES' if lucky[g5] else ''}{' *' if g5 == best else ''} |")
    prof5 = sum(is_ok(g) for g in grid if g[3] == 0.005); prof3 = sum(is_ok(g) for g in grid if g[3] == 0.003)
    L_ += ["", f"In-sample profitable variants: {prof5}/54 at 0.5%/side, {prof3}/54 at 0.3%/side. Lucky-number flags (profitable with an unprofitable neighbour): {sum(lucky[g] for g in grid if g[3] == 0.005)} at 0.5%.", ""]
    rows = []
    L_ += ["## Fixed settings, both costs, full METHOD row", "", "| variant | trades | IS n / mean | OOS n / mean | OOS CI | net $ | ex-best $ | MC DD p95 | score | exits stop/ema/end |", "|---|---|---|---|---|---|---|---|---|---|"]
    for g in chosen:
        st, si, so, mc, sc = full(g); tr = res[g]
        L_.append(f"| {name(*g)} | {st['trades']} | {si['trades']} / {pct(si['mean_ret'])} | {so['trades']} / {pct(so['mean_ret'])} | [{pct(so.get('ci_lo'))}, {pct(so.get('ci_hi'))}] | "
                  f"{st['net_pnl']:+.2f} | {st.get('ex_best', 0):+.2f} | {mc[2] * 100 if mc else 0:.1f}% | {sc['score_total']} ({sc['sc_oos_risk']},{sc['sc_drawdown']},{sc['sc_trades']},{sc['sc_edge']},{sc['sc_stability']}) | "
                  f"{sum(t['why'] == 'stop' for t in tr)}/{sum(t['why'] == 'ema' for t in tr)}/{sum(t['why'] == 'end' for t in tr)} |")
        cand = sc["score_total"] >= 18 and st["trades"] >= 50 and so["trades"] >= 20 and (so.get("ci_lo") or -1) > 0
        rows.append({"variant": name(*g), "trades": st["trades"], "win_rate": round(st.get("win_rate", 0), 3), "net_profit_after_costs": round(st["net_pnl"], 2),
                     "max_drawdown": round(st.get("max_dd", 0), 2), "holds_out_of_sample": ("yes" if (so.get("ci_lo") or -1) > 0 else "no" if so["trades"] >= 20 else f"insufficient (n_out={so['trades']}<20)"),
                     "n_in_sample": si["trades"], "n_out_of_sample": so["trades"], "mean_ret": round(st["mean_ret"] or 0, 4), "median_ret": round(st.get("median_ret") or 0, 4),
                     "ci95_mean_ret": f"[{st['ci_lo']:+.3f},{st['ci_hi']:+.3f}]", "rug_rate": "", "open": 0, "skipped": "", "pending": "", "no_candles": "", "uncovered": "", "filtered_out": "",
                     "oos_mean_ret": round(so["mean_ret"], 4) if so["trades"] else "", "in_net_pnl": round(si["net_pnl"], 2), "out_net_pnl": round(so["net_pnl"], 2),
                     **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                     "net_ex_best_trade": round(st.get("ex_best", 0), 2), "mc_dd_p5": round(mc[0], 3) if mc else "", "mc_dd_p50": round(mc[1], 3) if mc else "", "mc_dd_p95": round(mc[2], 3) if mc else "",
                     "nights": sc["nights"], "nights_profitable": sc["nights_profitable"], "candidate": "yes" if cand else "no", "lucky_number": "yes" if lucky[g] else "no",
                     "variants_tried": "", "family": "midcap_momentum", "guard_rejects": "", "scout_verdicts": "", "reentry_none": "",
                     "note": f"PAPER 1h mid-cap momentum; settings fixed on IS before holdout read; ${STAKE:.0f}/trade of ${EQ:.0f}; survivorship-biased universe (today's top-volume list)"})
    L_ += ["", "## Pre-registered baseline OC_live (Chunk's runner-radar oldcoins.py rule, not tuned) vs the tuned fixed point", "",
           "OC_live = 1h close > EMA50 > EMA200, close > prior 24-bar high, volume > 20-bar mean, 24 h volume >= $1M; entry next open 21:00-07:30 Dublin; stop max(breakout low, -8%); half off +15%; rest out on close < EMA20; flat at the 07:00 Dublin bar close (Chunk flattens 07:45). Chunk books 1%/side + 2x size/liq; shown at 0.3%, 0.5% and 1%/side. '_24h' = same rule without the night window/flatten (for information).", "",
           "| variant | trades | IS n / mean | OOS n / mean | OOS CI | OOS net $ | net $ | MC DD p95 | score | exits |", "|---|---|---|---|---|---|---|---|---|---|"]
    for g in OCK + chosen:
        st, si, so, mc, sc = full(g); tr = res[g]
        ex = {}
        for t in tr: ex[t["why"]] = ex.get(t["why"], 0) + 1
        L_.append(f"| {name(*g)}{' (tuned)' if g in chosen else ''} | {st['trades']} | {si['trades']} / {pct(si['mean_ret'])} | {so['trades']} / {pct(so['mean_ret'])} | "
                  f"[{pct(so.get('ci_lo'))}, {pct(so.get('ci_hi'))}] | {so['net_pnl']:+.2f} | {st['net_pnl']:+.2f} | {mc[2] * 100 if mc else 0:.1f}% | {sc['score_total']} | {ex} |")
        if g in OCK:
            cand = sc["score_total"] >= 18 and st["trades"] >= 50 and so["trades"] >= 20 and (so.get("ci_lo") or -1) > 0
            rows.append(dict(rows[0], variant=name(*g), trades=st["trades"], win_rate=round(st.get("win_rate", 0), 3) if st["trades"] else "",
                             net_profit_after_costs=round(st["net_pnl"], 2), max_drawdown=round(st.get("max_dd", 0), 2),
                             holds_out_of_sample=("yes" if (so.get("ci_lo") or -1) > 0 and so["trades"] >= 20 else "no" if so["trades"] >= 20 else f"insufficient (n_out={so['trades']}<20)"),
                             n_in_sample=si["trades"], n_out_of_sample=so["trades"], mean_ret=round(st["mean_ret"] or 0, 4), median_ret=round(st.get("median_ret") or 0, 4),
                             ci95_mean_ret=f"[{st.get('ci_lo', 0):+.3f},{(st.get('ci_hi') or 0):+.3f}]", oos_mean_ret=round(so["mean_ret"], 4) if so["trades"] else "",
                             in_net_pnl=round(si["net_pnl"], 2), out_net_pnl=round(so["net_pnl"], 2),
                             **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                             net_ex_best_trade=round(st.get("ex_best", 0), 2), mc_dd_p5=round(mc[0], 3) if mc else "", mc_dd_p50=round(mc[1], 3) if mc else "",
                             mc_dd_p95=round(mc[2], 3) if mc else "", nights=sc["nights"], nights_profitable=sc["nights_profitable"], candidate="yes" if cand else "no",
                             lucky_number="n/a (pre-registered)", note="PAPER pre-registered baseline = Chunk oldcoins.py rule (OC_live) replayed on Lab's 1h cache; survivorship-biased universe"))
    oc5 = stats([t for t in res[("OC", True, 0.005)] if t["is_oos"]]); tb5 = stats([t for t in res[best] if t["is_oos"]])
    beats = (tb5["mean_ret"] or -9) > (oc5["mean_ret"] or -9) and tb5["net_pnl"] > oc5["net_pnl"]
    L_ += ["", f"**Does the tuned version beat OC_live out of sample (0.5%/side)?** {'Yes' if beats else 'No'}: tuned OOS {tb5['trades']} trades, mean {pct(tb5['mean_ret'])}, net ${tb5['net_pnl']:+.2f}; "
           f"OC_live OOS {oc5['trades']} trades, mean {pct(oc5['mean_ret'])}, net ${oc5['net_pnl']:+.2f}. With these OOS counts the difference is "
           f"{'not' if min(tb5['trades'], oc5['trades']) < 30 else 'only weakly'} distinguishable from noise (see CIs)."]
    # neighbour read (IS + OOS) for the fixed point, 0.5 %
    L_ += ["", "## Neighbours of the fixed point (0.5%/side) - read after fixing, for robustness only", "", "| variant | IS n / mean | OOS n / mean |", "|---|---|---|"]
    for g in neigh(best):
        a = stats([t for t in res[g] if not t["is_oos"]]); b = stats([t for t in res[g] if t["is_oos"]])
        L_.append(f"| {name(*g)} | {a['trades']} / {pct(a['mean_ret'])} | {b['trades']} / {pct(b['mean_ret'])} |")
    tr = res[best]; top = sorted(tr, key=lambda t: -t["pnl"])[:5]
    L_ += ["", "## Lottery check (fixed point, 0.5%)", "", "Top 5 trades: " + ", ".join(f"{t['sym']} {t['ret'] * 100:+.0f}%" for t in top) +
           f". Net without top 3: ${sum(t['pnl'] for t in tr) - sum(t['pnl'] for t in top[:3]):+.2f}. Distinct tokens traded: {len({t['mint'] for t in tr})}.", ""]
    L_ += open(os.path.join(LAB, "midcap_momentum_caveats.md")).read().splitlines()
    open(os.path.join(OUT, "midcap_momentum.md"), "w").write("\n".join(L_) + "\n")
    vc = [dict(name=name(*g), family="midcap_momentum", ema=g[0], n=g[1], stop=list(g[2]), cost=g[3], stake_f=STAKE_F, max_open=MAX_OPEN) for g in grid]
    json.dump({"rows": rows, "variant_configs": vc}, open(os.path.join(OUT, ".mc_rows.json"), "w"))
    print("wrote out/midcap_momentum.md;", name(*best), "rows", len(rows))

if __name__ == "__main__": main()
