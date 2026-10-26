#!/usr/bin/env python3
"""Report for oc_backtest.py -> out/oldcoins_backtest.md + out/.mc_oc_rows.json (PAPER research only)."""
import json, os, statistics, time, math, collections, datetime as dt
import oc_backtest as ob, scoring
from labcore import LAB, iso, atomic_write
OUT = os.path.join(LAB, "out")

def f(v, k=2, pc=True):
    if v is None: return "-"
    return f"{v*100:+.{k}f}%" if pc else f"{v:+.{k}f}"

def st(tr):
    r = [t["ret"] for t in tr]
    if not r: return dict(n=0)
    lo, hi = ob.boot_mean(r)
    return dict(n=len(r), mean=statistics.fmean(r), med=statistics.median(r), win=sum(x > 0 for x in r) / len(r), lo=lo, hi=hi, book=sum(t["pnl"] for t in tr))

def method(tr, dOOS):
    closed = [dict(t=t["t"], pnl=t["pnl"], ret=t["ret"], is_oos=ob.bookday(t["t"]) in dOOS) for t in tr]
    s = st(tr); mc = scoring.mc_drawdown([t["pnl"] for t in tr], 1.0, 1000, 7) if tr else None
    sc = scoring.score(dict(trades=s["n"], mean_ret=s.get("mean"), ci_lo=s.get("lo") if s.get("lo") is not None else -1), None, closed, mc)
    return sc, mc

def main():
    res, toks, solpx = ob.main()
    L = [f"# Older-coins breakout backtest: Chunk's live rules (OC_live) + in-sample tuning ({iso(time.time())}, PAPER ONLY, research only)", ""]
    # universe facts
    elig = collections.Counter()
    tmax = max(k["T"][-1] for k in toks.values())
    for m, k in toks.items():
        for i in range(220, len(k["T"])):
            if k["T"][i] >= tmax - 60 * ob.DAY and ob.mm.eligible(k, i): elig[m] += 1
    n15 = sum(1 for m, k in toks.items() if k.get("m15") and elig[m])
    L += [f"Universe: {len(toks)} Solana tokens with >= 260 1h bars after exclusions (stables/LSTs/wrapped, tokenized stocks, avoid.csv); "
          f"{len(elig)} were point-in-time eligible (age >= 7 d, mcap $5-200M, liq >= $500k) for at least one hour of the last 60 days; {n15} of those also have 15m candles. "
          "vol24 >= $1M is applied at the signal bar.", ""]
    B = {}
    for tf in ("1h", "15m"):
        x = res[tf]; B[tf] = x
    # ---------- 1. live-rule backtest
    L += ["## 1. Live rule (OC_live) backtest", "",
          "Rules as coded in /workspace/runner-radar/oldcoins.py plus Zero's 23:39 update: stop = breakout-bar low clamped to 2.5%-8% below entry (1h) / 2.5%-6% (15m). "
          "Activity filter = the live spec in oldcoins.py (23:40 version; trades-log.md itself states no threshold): $ volume of the last 4 closed candles >= $150k on 1h / >= $40k on 15m, "
          "plus the universe thin-activity skip (liq/mcap > 0.4 AND vol24/liq < 0.05). Activity thresholds {0, 75k, 150k, 300k, 600k} (1h) and {0, 20k, 40k, 80k, 160k} (15m) are in the sweep. "
          "Entries 21:00-07:30 Dublin at the next bar open, flat 07:45 Dublin "
          "(1h: mid of the 07:00 bar; 15m: close of the 07:30 bar). 10% of book per trade, max 3 open, one position per token, 1h and 15m books run separately and combined.", "",
          "Costs per side: c0.3 / c0.5 = flat bands; real_P0.0001 / real_P0.0005 = pool fee from the Jupiter-quote fit (max(0.25%, (1.85% - 1.78% x log10(liq/$100k))/2); ~0.3%/side at $500k) "
          "+ 2 x size/liq + (priority + 0.000005 SOL) x SOL price / ticket, ticket = 10% x 0.928 SOL (~$9-11); chunk_1pct = Chunk's own model (1% + 2 x size/liq). "
          "The priority fee is the biggest real cost at a ~$10 ticket: 0.0005 SOL is ~0.55%/side. /workspace/selfcopy/quotes.jsonl does not exist, so the quotes are Lab's own 24 read-only Jupiter quotes (data/fs_quotes/quotes.jsonl).", ""]
    L += ["| book | cost | days (IS/OOS) | trades (IS/OOS) | mean ret/trade | median | win | 95% CI mean | book P&L per night IS | per night OOS | total book |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for tf in ("1h", "15m"):
        x = B[tf]
        for c, e in x["bands"].items():
            s = st(e["tr"])
            L.append(f"| {tf} | {c}{' (main)' if c == ob.MAIN else ''} | {len(x['days'])} ({len(x['dIS'])}/{len(x['dOOS'])}) | {s['n']} ({e['nI']}/{e['nO']}) | {f(s.get('mean'))} | {f(s.get('med'))} | "
                     f"{'-' if not s['n'] else f'{s[chr(119)+chr(105)+chr(110)]:.0%}'} | [{f(s.get('lo'))}, {f(s.get('hi'))}] | {f(e['is_pd'], 3)} | {f(e['oos_pd'], 3)} | {f(s.get('book'))} |")
    # exits + concentration
    for tf in ("1h", "15m"):
        tr = B[tf]["live"]["tr"]; why = collections.Counter(t["why"] for t in tr); by = collections.Counter(t["sym"] for t in tr)
        pn = sorted((t["ret"] for t in tr), reverse=True)
        L.append(f"- {tf} live exits: {dict(why)}; tokens traded {len(by)}, most-traded {by.most_common(3)}; best 3 trades {', '.join(f(v, 1) for v in pn[:3])}; "
                 f"without the best trade: total {f(sum(t['pnl'] for t in tr) - max([t['pnl'] for t in tr] or [0]))} of book; median cost/side {f(statistics.median([t['cost'] for t in tr]) if tr else None)}.")
        sc, mc = method(tr, B[tf]["dOOS"])
        L.append(f"  METHOD score {sc['score_total']}/25 (oos {sc['sc_oos_risk']}, dd {sc['sc_drawdown']}, n {sc['sc_trades']}, edge {sc['sc_edge']}, stab {sc['sc_stability']}); "
                 f"MC drawdown p50/p95 {mc[1]*100 if mc else 0:.1f}% / {mc[2]*100 if mc else 0:.1f}% of book; activity filter off changes trades {len(tr)} -> {len(B[tf]['noact']['tr'])}.")
    cb = res["combined"]["tr"]; s = st(cb)
    L += [f"- Combined 1h+15m live book on the 15m window ({len(res['combined']['days'])} nights, shared max 3): {s['n']} trades, mean {f(s.get('mean'))}/trade, total {f(s.get('book'))} of book.", ""]
    # ---------- 2. nightly distribution
    L += ["## 2. Nightly return distribution at 10% per trade (night = 20:00-08:00 Dublin; entries 21:00-07:30, flat 07:45)", "",
          "Unit = one night of the whole book (sum of 10% x trade return of every trade entered that night; nights with no trade = 0). "
          "Block bootstrap: 5,000 resamples of the actual nights in blocks of 3 consecutive nights (a night is resampled whole, so coins that move together on a night stay together). "
          "CI = 2.5-97.5% across resamples. 30-night = compounded 30 nights drawn the same way.", "",
          "| book | cost | nights | trades/night | nights with 0 trades | median night | p10 | p90 | mean night [95% CI] | P(night >= +10%) [CI] | P(night <= -20%) [CI] | worst / best night | 30 nights median (p10, p90) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ND = {}
    for nm, tr, days in [("1h", B["1h"]["live"]["tr"], B["1h"]["days"]), ("15m", B["15m"]["live"]["tr"], B["15m"]["days"]), ("1h+15m", cb, res["combined"]["days"])]:
        for c in ("c0.3", "c0.5", ob.MAIN):
            if nm == "1h+15m":
                if c != ob.MAIN: continue
                t2 = tr
            else: t2 = B[nm]["bands"][c]["tr"]
            nv, nn = ob.nightly(t2, days); d = ob.night_dist(nv, nn); ND[(nm, c)] = d
            if not d: continue
            L.append(f"| {nm} | {c} | {d['n_nights']} | {d['trades_per_night']:.2f} | {d['zero_trade_share']:.0%} | {f(d['med'])} | {f(d['p10'])} | {f(d['p90'])} | "
                     f"{f(d['mean'], 3)} [{f(d['ci']['mean'][0], 3)}, {f(d['ci']['mean'][1], 3)}] | {d['p_up10']:.1%} [{d['ci']['p_up10'][0]:.0%}, {d['ci']['p_up10'][1]:.0%}] | "
                     f"{d['p_dn20']:.1%} [{d['ci']['p_dn20'][0]:.0%}, {d['ci']['p_dn20'][1]:.0%}] | {f(d['worst'])} / {f(d['best'])} | {f(d['m30'], 1)} ({f(d['p10_30'], 1)}, {f(d['p90_30'], 1)}) |")
    L += ["", "Arithmetic of the cap: with 10% per trade and max 3 open, a +10% night needs the open trades to average about +33% (3 trades) or +100% (1 trade) in one night; "
          "a -20% night needs ~-67% on 3 trades at once, which a 2.5-8% stop only allows through a gap/rug past the stop. "
          "The 1h rule fires well under once a night on this universe, so most nights are flat.", ""]
    # ---------- 3. tuning
    L += ["## 3. In-sample tuning vs the live rule", "",
          "Tuned on in-sample nights only (first 70% of nights per timeframe), cost real_P0.0005. Grid per timeframe: stop clamp low {1.5, 2.5, 4%} x clamp high (1h {5, 8, 12%}; 15m {4, 6, 9%}) "
          "x TP-half {+5, +10, +15, +25%, none} x volume multiple {>0, >1, >1.5, >2, >3 x prior-20 mean} x activity {0, 50, 75, 90%} x entry hours "
          "{live window, all hours, 18-24, 00-06, 06-12, 12-18 UTC} = 5,400 configs. Book is still flat at 07:45 Dublin in every config. "
          "Selection: max (IS mean book P&L per night - 1 s.e.), >= 30 IS trades (1h) / >= 20 (15m), not a lucky number (every one-step neighbour also IS-profitable with >= 5 trades). "
          "Improvement only if the paired OOS night difference (tuned - live) has a block-bootstrap 95% CI above 0.", ""]
    L += ["| tf | config | IS trades | IS per night | OOS trades | OOS per night | OOS mean ret/trade | OOS diff vs live per night [95% CI] | verdict | lucky? | live rule's IS rank |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for tf in ("1h", "15m"):
        x = B[tf]
        for nm, e, P, lk in (("OC_live", x["live"], ob.LIVE[tf], x["lucky_live"]), ("best tuned", x["tuned"], x["best"]["P"], x["lucky_best"])):
            so = st([t for t in e["tr"] if ob.bookday(t["t"]) in x["dOOS"]])
            dm, dci = x["diff"]
            verdict = "" if nm == "OC_live" else ("BEATS live OOS beyond noise" if dci[0] is not None and dci[0] > 0 else "does NOT clearly beat live OOS")
            L.append(f"| {tf} | {nm}: {ob.pname(tf, P)} | {e['nI']} | {f(e['is_pd'], 3)} | {e['nO']} | {f(e['oos_pd'], 3)} | {f(so.get('mean'))} | "
                     + ("-" if nm == "OC_live" else f"{f(dm, 3)} [{f(dci[0], 3)}, {f(dci[1], 3)}]") + f" | {verdict} | {'yes' if lk else 'no'} | {x['rank_live'] if nm == 'OC_live' else 1}/{x['n_grid']} |")
    L += ["", f"Multiple testing: {B['1h']['n_grid'] + B['15m']['n_grid']} configs were scored in-sample; the best IS number is biased up by selection. Treat the tuned rows as hypotheses for forward paper only.", ""]
    for tf in ("1h", "15m"):
        for lab, key, P in (("OC_live", "nbl", ob.LIVE[tf]), ("best tuned", "nb", B[tf]["best"]["P"])):
            L += [f"Neighbour sweep, {tf} {lab} ({ob.pname(tf, P)}), one step per dimension (includes stop clamp low/high and activity threshold):", "",
                  "| changed | value | IS trades | IS per night | OOS trades | OOS per night |", "|---|---|---|---|---|---|"]
            for d, Q, isr, e in B[tf][key]:
                L.append(f"| {d} | {Q[d]} | {isr['nI']} | {f(isr['is_pd'], 3)} | {e['nO']} | {f(e['oos_pd'], 3)} |")
            L.append("")
    # benchmarks
    sol = []
    for tf in ("1h",):
        dO = B[tf]["dOOS"]; dI = B[tf]["dIS"]
        t_a = dt.datetime.fromisoformat(dI[0] + "T20:00:00+01:00").timestamp(); t_s = dt.datetime.fromisoformat(dO[0] + "T20:00:00+01:00").timestamp(); t_e = tmax
        L += [f"Benchmarks (1h window): SOL buy-and-hold IS {f(ob_load_sol(solpx, t_a, t_s))}, OOS {f(ob_load_sol(solpx, t_s, t_e))}; "
              f"equal-weight buy-and-hold of tokens eligible at the window start: IS {f(bh(toks, t_a, t_s))}, OOS {f(bh(toks, t_s, t_e))} (book uses <= 30% of capital, so compare x0.3).", ""]
    L += ["## WHY THIS COULD FAIL", "",
          "- Universe is discovered from pools that are big NOW (GeckoTerminal top pools + DexScreener); tokens that were $5-200M earlier and since died are under-represented (survivorship, flatters any long rule).",
          "- Point-in-time mcap = today's supply x past price; point-in-time liquidity = today's liquidity scaled by sqrt(price) (no LP history). Both are approximations.",
          "- Trade counts are small (tens, not hundreds); every CI above is wide and the OOS window is ~2-3 weeks of one market regime.",
          "- Live 1h trades use the most recent bars from a fresh fetch (and size 5%, not 10%); fills are next-bar-open, while live enters at the live price a few minutes after the close.",
          "- GeckoTerminal omits no-trade bars; thin pools give stale highs/lows. 15m history is limited for thin pools (~20 days).",
          "- Costs: priority fee dominates at a ~$10 ticket; failed transactions, MEV sandwiching on a 15% slippage setting, and Banana Gun's own fee (not in Chunk's model) would add more.", "",
          "Who is on the other side: breakout buyers on 1h/15m charts are the most crowded retail signal in memecoins; the sellers are holders and market-makers distributing into "
          "the volume spike, plus bots that fade breakouts on thin books. A rule this public has no structural edge unless the costs are tiny.", ""]
    L += ["## Data notes", "",
          "- The brief says Chunk trades these rules LIVE at 10% on 1h and 15m. The files say otherwise: oldcoins.py logs 'PAPER scanner output; this script never trades', size_pct = 5% (0.0464 SOL), "
          "trades-log.md shows live buys PAUSED (paper only) and the oldcoins book's first scan at 00:36 Dublin with one 15m paper entry (ANTFUN). This backtest uses 10% as asked.",
          "- oldcoins-paper.jsonl has 1 setup + 1 entry so far: too little to compare with the backtest.", ""]
    atomic_write(os.path.join(OUT, "oldcoins_backtest.md"), "\n".join(L) + "\n")
    # leaderboard rows
    rows = []
    for tf in ("1h", "15m"):
        x = B[tf]
        for nm, e, P in (("OC_live", x["live"], ob.LIVE[tf]), ("tuned", x["tuned"], x["best"]["P"])):
            for c in ("c0.3", "c0.5", ob.MAIN):
                ee = x["bands" if nm == "OC_live" else "tbands"][c]; tr = ee["tr"]; s = st(tr); sc, mc = method(tr, x["dOOS"])
                so = st([t for t in tr if ob.bookday(t["t"]) in x["dOOS"]])
                rows.append({"variant": f"MC_{nm}_{tf}_{c}", "trades": s["n"], "win_rate": round(s.get("win") or 0, 3), "net_profit_after_costs": round((s.get("book") or 0) * 100, 2),
                             "max_drawdown": round(mc[1] if mc else 0, 3), "holds_out_of_sample": f"insufficient (n_out={so['n']}<20)" if so["n"] < 20 else ("yes" if (so.get("lo") or -1) > 0 else "no"),
                             "n_in_sample": ee["nI"], "n_out_of_sample": ee["nO"], "mean_ret": round(s.get("mean") or 0, 4), "median_ret": round(s.get("med") or 0, 4),
                             "ci95_mean_ret": f"[{(s.get('lo') or 0):+.3f},{(s.get('hi') or 0):+.3f}]", "oos_mean_ret": round(so.get("mean") or 0, 4),
                             **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                             "mc_dd_p50": round(mc[1], 3) if mc else "", "mc_dd_p95": round(mc[2], 3) if mc else "", "nights": sc["nights"], "nights_profitable": sc["nights_profitable"],
                             "candidate": "yes" if sc["score_total"] >= 18 and s["n"] >= 50 and so["n"] >= 20 and (so.get("lo") or -1) > 0 else "no",
                             "lucky_number": "yes" if (x["lucky_live"] if nm == "OC_live" else x["lucky_best"]) else "no", "family": "oldcoins_breakout",
                             "note": f"PAPER backtest {ob.pname(tf, P)}; net_profit = % of book at 10%/trade; see out/oldcoins_backtest.md"})
    cfgs = [dict(P, tf=tf, family="oldcoins_breakout", name=f"MC_OCgrid_{ob.pname(tf, P)}") for tf in ("1h", "15m")
            for P in [dict(zip(ob.DIMS, v)) for v in __import__("itertools").product(*[ob.GRID[tf][d] for d in ob.DIMS])]]
    json.dump({"rows": rows, "variant_configs": cfgs}, open(os.path.join(OUT, ".mc_oc_rows.json"), "w"), default=str)
    print("wrote out/oldcoins_backtest.md", len(rows), "rows")

def ob_load_sol(solpx, a, b): return solpx(b) / solpx(a) - 1
def bh(toks, a, b):
    import bisect; r = []
    for k in toks.values():
        i = bisect.bisect_left(k["T"], a); j = bisect.bisect_right(k["T"], b) - 1
        if 220 <= i < len(k["T"]) and j > i and ob.mm.eligible(k, i): r.append(k["C"][j] / k["O"][i] - 1)
    return statistics.fmean(r) if r else None

if __name__ == "__main__":
    main()
