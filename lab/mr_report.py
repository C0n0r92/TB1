"""Report + leaderboard staging for mr_dip.py (PAPER research)."""
import json, os, datetime as dt
import numpy as np, pandas as pd
import scoring
from mr_dip import DUB, OUT, D, LIQ, stats, book, nightly, night_key, gen_trades, load_tf, regime_series, TICKET

def pct(x, d=2): return "n/a" if x is None else f"{x*100:+.{d}f}%"
def ci(s): return "n/a" if not s or s["n"] == 0 else f"{pct(s['mean'])} [{pct(s['lo'])}, {pct(s['hi'])}]"

def score_row(name, cfg, r, cost, lucky, n_tried):
    bk = r["bk"]; closed = [{"ret": t["ret"], "is_oos": t["is_oos"], "t": t["t_in"].timestamp(), "pnl": 10 * t["ret"]} for t in bk]
    rets = [t["ret"] for t in bk]; st = stats(rets)
    mc = scoring.mc_drawdown([c["pnl"] for c in closed], 100.0) if closed else None
    sc = scoring.score({"trades": len(bk), "mean_ret": st["mean"], "ci_lo": st["lo"] if st["n"] else -1}, None, closed, mc)
    ins = [c for c in closed if not c["is_oos"]]; oos = [c for c in closed if c["is_oos"]]; so = stats([c["ret"] for c in oos])
    in_pnl = sum(c["pnl"] for c in ins); out_pnl = sum(c["pnl"] for c in oos)
    if len(oos) < 20: hold = f"insufficient (n_out={len(oos)}<20)"
    else: hold = "yes" if (in_pnl > 0 and so["mean"] > 0 and so["lo"] > 0) else "no"
    eq = np.cumsum([c["pnl"] for c in closed]); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq])) if len(eq) else 0
    pn = sorted(c["pnl"] for c in closed)
    cand = "yes" if sc["score_total"] >= 18 and len(bk) >= 50 and hold == "yes" else "no"
    return {"variant": f"{name}_{cost}", "trades": len(bk), "win_rate": round(st.get("win", 0) or 0, 3), "net_profit_after_costs": round(sum(pn), 2),
            "max_drawdown": round(dd, 2), "holds_out_of_sample": hold, "n_in_sample": len(ins), "n_out_of_sample": len(oos),
            "mean_ret": round(st["mean"], 5) if st["n"] else None, "median_ret": round(st.get("med", 0), 5) if st["n"] else None,
            "ci95_mean_ret": f"[{st['lo']:+.4f},{st['hi']:+.4f}]" if st["n"] else "", "oos_mean_ret": round(so["mean"], 5) if so["n"] else None,
            "in_net_pnl": round(in_pnl, 2), "out_net_pnl": round(out_pnl, 2), **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
            "net_ex_best_trade": round(sum(pn[:-1]), 2) if pn else 0, "mc_dd_p5": round(mc[0], 4) if mc else None, "mc_dd_p50": round(mc[1], 4) if mc else None,
            "mc_dd_p95": round(mc[2], 4) if mc else None, "candidate": cand, "lucky_number": lucky, "family": f"mr_dip_{cfg['tf']}",
            "note": f"PAPER long-only z-dip, night book 20-08 Dublin, max 3 open, 10%/trade, cost {cost} ({'0.3%' if cost=='lo' else '0.6%+2x$15/liq+0.1% stop slip'} rt); IS-selected of {n_tried}; see out/mean_reversion.md"}

def write(res, best, hurst_rows, neighbours, row_for):
    L = []; stage = []; n_tried = len(res)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    # ---------- whole-grid view (multiple testing)
    grid = []
    for name, (cfg, out, split, nk) in res.items():
        for cost in ("lo", "hi"):
            tr = out[(True, cost)]; i = [t["ret"] for t in tr if not t["is_oos"]]; o = [t["ret"] for t in tr if t["is_oos"]]
            tr24 = out[(False, cost)]; i24 = [t["ret"] for t in tr24 if not t["is_oos"]]; o24 = [t["ret"] for t in tr24 if t["is_oos"]]
            grid.append({**{k: cfg[k] for k in ("tf", "L", "zin", "N", "stop", "regime")}, "name": name, "cost": cost, "n_is": len(i), "n_oos": len(o),
                         "is": np.mean(i) if i else np.nan, "oos": np.mean(o) if o else np.nan, "is24": np.mean(i24) if i24 else np.nan, "oos24": np.mean(o24) if o24 else np.nan,
                         "n_is24": len(i24), "n_oos24": len(o24)})
    G = pd.DataFrame(grid); G.to_csv(os.path.join(OUT, "mr_grid.csv"), index=False)
    sol = load_tf("1h")["SOL"][1]
    L.append(f"# Mean reversion (Ernest Chan style), long-only z-score dip buys, liquid Solana tokens ({now}, PAPER research only)\n")
    L.append("Scope: single-token long-only dip buys only (pairs dropped per Zero/parent 00:04Z; Lab 2 owns pairs; no pairs code was written). "
             "Script: mr_dip.py + mr_report.py; candles: mr_fetch.py -> data/mr_candles/. Grid: out/mr_grid.csv.\n")
    L.append("## Headline\n"); headline_at = len(L); L.append("")
    # ---------- universe
    L.append("## Universe and data\n")
    L.append("Top Solana-ecosystem tokens by 24h volume from CoinGecko (category solana-ecosystem, fetched 2026-10-24 00:0xZ, data/mr_candles/cg_solana_top.json), "
             "dropping stables, wrapped/bridged assets (wSOL, cbBTC, WBTC, ZEC, HYPE...), LSTs (JitoSOL), tokenized stocks and multichain non-SPL tokens (ENA, LINK, AAVE, INJ, STRK, CAKE...), plus Zero's POPCAT.\n")
    L.append("| token | source | 1h bars | 15m bars | 5m bars | assumed pool liq (hi-cost slippage) |\n|---|---|---|---|---|---|")
    counts = {}
    for tf in ("1h", "15m", "5m"):
        for s, (src, df) in load_tf(tf).items(): counts.setdefault(s, {"src": src})[tf] = (len(df), df.index[0].date(), df.index[-1].date())
    for s, c in sorted(counts.items()):
        f = lambda tf: f"{c[tf][0]} ({c[tf][1]}..{c[tf][2]})" if tf in c else "-"
        L.append(f"| {s} | {'Binance spot USDT (proxy)' if c['src']=='bn' else 'GeckoTerminal top pool'} | {f('1h')} | {f('15m')} | {f('5m')} | ${LIQ.get(s, 2e6)/1e6:.1f}M |")
    L.append("\n- **Survivorship**: the list is TODAY's top 20 by volume. Tokens that were liquid 6-12 months ago and then died (and would have produced the worst 'dips') are not in it, "
             "and today's winners are. That biases dip-buying UP (dips in survivors recovered by construction). Treat any positive result as an upper bound.\n"
             "- **Proxy**: Binance prices are a proxy for Jupiter fills; on-chain prices lag/lead CEX by seconds and the CEX dip may be shallower on-chain. GeckoTerminal tokens use one pool's OHLCV (15m resampled from 5m).\n"
             "- Costs: 'lo' = 0.15%/side (0.3% round trip); 'hi' = 0.30%/side + 2 x $15 / pool liquidity per side + 0.1% extra on % stops (about 0.6-0.7% round trip). At $10-15 tickets size slippage is <0.01% on these pools, so fees dominate.\n")
    # ---------- hurst
    H = pd.DataFrame(hurst_rows); H.to_csv(os.path.join(OUT, "mr_hurst.csv"), index=False)
    L.append("## Does mean reversion exist? (in-sample only)\n")
    L.append("Hurst on log price (H < 0.5 = mean reverting, 0.5 = random walk), variance ratio of returns VR(q) (< 1 = reverting), ADF p-value on log price (< 0.05 = stationary), "
             "half-life of the price level (bars), and half-life of the deviation from the 50-bar mean (what the strategy actually trades).\n")
    L.append("| tf | tokens | median H | tokens H<0.45 | median VR(2) | median VR(4) | median VR(16) | tokens VR(4)<0.9 | ADF p<0.05 | median price half-life (days) | median dev50 half-life (bars) |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for tf, g in H.groupby("tf", sort=False):
        bd = {"1h": 24, "15m": 96, "5m": 288}[tf]
        L.append(f"| {tf} | {len(g)} | {g.H.median():.3f} | {(g.H<0.45).sum()} | {g.VR2.median():.3f} | {g.VR4.median():.3f} | {g.VR16.median():.3f} | {(g.VR4<0.9).sum()} | {(g.adf_p.dropna()<0.05).sum()}/{g.adf_p.notna().sum()} | "
                 f"{np.median([x for x in g.hl_price_bars if np.isfinite(x)] or [np.inf])/bd:.0f} | {g.hl_dev50.median():.1f} |")
    L.append("\nPer token (1h): " + ", ".join(f"{r.sym} H={r.H:.2f} VR4={r.VR4:.2f}" for r in H[H.tf=='1h'].itertuples()) + "\n")
    # ---------- regime / grid summary
    L.append(f"## Whole grid ({n_tried} variants: tf x L 20/50 x z 2/2.5 x N(4) x stop z<=-4 / -5% x regime off / SOL>4h EMA50 / 4h EMA50 slope up), all signals, night window 20:00-08:00 Dublin\n")
    L.append("| tf | cost | variants | median IS mean/trade | median OOS mean/trade | variants OOS>0 | variants IS>0 & OOS>0 | best OOS (any, look-ahead pick!) | median 24h OOS mean |\n|---|---|---|---|---|---|---|---|---|")
    for (tf, cost), g in G.groupby(["tf", "cost"], sort=False):
        L.append(f"| {tf} | {cost} | {len(g)} | {pct(g['is'].median())} | {pct(g.oos.median())} | {(g.oos>0).sum()} | {((g['is']>0)&(g.oos>0)).sum()} | {pct(g.oos.max())} | {pct(g.oos24.median())} |")
    L.append("\nRegime filter effect (median over variants, hi cost, night window):\n")
    L.append("| tf | regime | median IS | median OOS | median IS trades |\n|---|---|---|---|---|")
    for (tf, rg), g in G[G.cost == "hi"].groupby(["tf", "regime"], sort=False):
        L.append(f"| {tf} | {rg} | {pct(g['is'].median())} | {pct(g.oos.median())} | {int(g.n_is.median())} |")
    # gross (zero cost) check for the whole grid, approximated by adding back lo-cost fees
    L.append("\nGross (before any fee) median OOS mean per trade ~ lo-cost median + 0.30 pts: " +
             ", ".join(f"{tf} {pct(G[(G.tf==tf)&(G.cost=='lo')].oos.median()+0.003)}" for tf in ("1h", "15m", "5m")) + ".\n")
    # ---------- best per family
    L.append("## Best variant per family (selected on IN-SAMPLE hi-cost mean per trade, night window, >= 50 IS trades), then held out\n")
    heads = []
    for tf in ("1h", "15m", "5m"):
        name = best[tf]; cfg, r = row_for(name)
        nb = neighbours(cfg); nbm = [G[(G.name == n) & (G.cost == "hi")]["is"].iloc[0] for n in nb if n in set(G.name)]
        prof = r["hi"]["bk_is"]["mean"] is not None and r["hi"]["all_is"]["mean"] > 0
        lucky = ("yes" if prof and any(not (m > 0) for m in nbm) else "no") if prof else "n/a (not profitable IS)"
        L.append(f"### {tf}: `{name}`\n")
        L.append(f"Entry z <= -{cfg['zin']} vs {cfg['L']}-bar mean (next open); exit at z >= 0 or after {cfg['N']} bars (next open), stop {'z <= -4' if cfg['stop']=='z4' else '-5% intrabar'}; regime {cfg['regime']}. "
                 f"Neighbours (one parameter away, IS hi-cost mean): {', '.join(pct(m) for m in nbm)} -> lucky_number = {lucky}.\n")
        L.append("| cost | sample | IS trades | IS mean [95% CI] | OOS trades | OOS mean [95% CI] | OOS win | 24h all-signals IS / OOS mean |\n|---|---|---|---|---|---|---|---|")
        for cost in ("lo", "hi"):
            x = r[cost]
            L.append(f"| {cost} | all signals (night) | {x['all_is']['n']} | {ci(x['all_is'])} | {x['all_oos']['n']} | {ci(x['all_oos'])} | {pct(x['all_oos'].get('win'),0)} | {pct(x['a24_is']['mean'])} / {pct(x['a24_oos']['mean'])} |")
            L.append(f"| {cost} | book max 3, 10% | {x['bk_is']['n']} | {ci(x['bk_is'])} | {x['bk_oos']['n']} | {ci(x['bk_oos'])} | {pct(x['bk_oos'].get('win'),0)} | |")
        L.append("\nNightly book return (10%/trade, max 3 open, % of wallet), hi cost:\n")
        L.append("| window | period | nights/days | mean | p5 | median | p95 | best | worst | share > 0 | nights with trades (share > 0 of those) | P(>= +10%) | P(<= -20%) |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for lab, k in (("night 20-08", "n_is"), ("night 20-08", "n_oos"), ("24h", "d_is"), ("24h", "d_oos")):
            n = r["hi"][k]
            L.append(f"| {lab} | {'IS' if k.endswith('is') else 'OOS'} | {n['nights']} | {pct(n['mean'],3)} | {pct(n['p05'])} | {pct(n['p50'])} | {pct(n['p95'])} | {pct(n['best'])} | {pct(n['worst'])} | {n['pos']:.0%} | {n['active']} ({n['pos_active']:.0%}) | {n['P+10']:.1%} | {n['P-20']:.1%} |")
        rows = []
        for cost in ("hi", "lo"):
            rows.append(score_row(name, cfg, r[cost], cost, lucky, n_tried))
        sr = rows[0]
        L.append(f"\nScore (hi cost, night book): {sr['score_total']}/25 (oos_risk {sr['sc_oos_risk']}, drawdown {sr['sc_drawdown']}, trades {sr['sc_trades']}, edge {sr['sc_edge']}, stability {sr['sc_stability']}); "
                 f"MC p95 DD {pct(sr['mc_dd_p95'],1)} of wallet; holds OOS: {sr['holds_out_of_sample']}; candidate: {sr['candidate']}. Net ex best trade {sr['net_ex_best_trade']:+.2f}% of wallet.\n")
        stage += rows; heads.append((tf, name, r, sr))
        # exits mix
        ex = pd.Series([t["reason"] for t in r["hi"]["tr"]]).value_counts().to_dict()
        L.append(f"Exit mix (all signals, hi): {ex}.\n")
    # ---------- benchmark
    L.append("## Benchmark: buy-and-hold SOL\n")
    L.append("| window | SOL B&H | SOL 20:00-08:00 only (100% exposure), mean/night | same at 30% exposure (3 x 10%), P(+10%) / P(-20%) |\n|---|---|---|---|")
    for tf in ("1h", "15m", "5m"):
        cfg, out, split, nk = res[best[tf]]
        for per, m in (("IS", sol.index < split), ("OOS", sol.index >= split)):
            s = sol[m]
            if tf != "1h": s = s[s.index >= load_tf(tf)["SOL"][1].index[0]]
            bh = s.c.iloc[-1] / s.o.iloc[0] - 1
            loc = s.index.tz_convert(DUB); nr = {}
            for k, g in s.groupby([night_key(t) for t in s.index]):
                gl = g.index.tz_convert(DUB); sel = g[(gl.hour >= 20) | (gl.hour < 8)]
                if len(sel) > 4: nr[k] = sel.c.iloc[-1] / sel.o.iloc[0] - 1
            v = np.array(list(nr.values()))
            L.append(f"| {tf} window {per} ({s.index[0].date()}..{s.index[-1].date()}) | {pct(bh,1)} | {pct(v.mean(),3)} | {(0.3*v>=0.10).mean():.1%} / {(0.3*v<=-0.20).mean():.1%} |")
    # ---------- why fail
    L.append("\n## WHY THIS COULD FAIL / who is on the other side\n")
    L.append("- The other side of a dip buy on SOL/JUP/WIF 5m-1h bars is CEX market makers and perp-funded momentum/liquidation flow: dips in these tokens are mostly information (BTC/SOL beta moves, unlocks, news) or forced liquidations that keep going. MMs already harvest the sub-minute bounce; what is left at 5m+ is closer to a random walk (H ~ 0.5, VR ~ 1) and fees eat it.\n"
             "- Survivorship (today's top 20) inflates every dip-buy number. Binance prices are a proxy for on-chain fills (Jupiter routes on thinner pools for GT tokens; MEW/USELESS/GRASS/POPCAT depth is a few $M).\n"
             f"- Multiple testing: {n_tried} configs in this study (plus every variant ever tried in the Lab registry); the IS winner is expected to look good by luck. Held-out results are the only ones that count.\n"
             "- Regime shifts: a 2-month OOS that was a SOL down/up-trend changes everything; long-only dip buying is short volatility and loses big in trending sell-offs (stop exits cluster on the same nights across tokens since they all carry SOL beta, so 3 open positions are not 3 independent bets).\n")
    L.append("## Not done / data-pending\n- Pairs (WIF/BONK, JUP/RAY, SOL/JTO, Kalman/rolling OLS, long-short and long-laggard): dropped from this task, Lab 2 owns it. No pairs code exists in /workspace/lab.\n"
             "- 5m/15m history is ~3 months (OOS ~4 weeks); 1h is 12 months (6 for GT tokens). On-chain fill check vs Binance not done.\n")
    # headline
    hl = []
    for tf, name, r, sr in heads:
        x = r["hi"]; n = x["n_oos"]
        hl.append(f"- **{tf}** best IS `{name}`: IS {ci(x['all_is'])} on {x['all_is']['n']} trades, OOS {ci(x['all_oos'])} on {x['all_oos']['n']} (hi cost); lo cost OOS {ci(r['lo']['all_oos'])}. "
                  f"Score {sr['score_total']}/25, candidate {sr['candidate']}. OOS nightly book mean {pct(n['mean'],3)}, P(+10%) {n['P+10']:.1%}, P(-20%) {n['P-20']:.1%}.")
    L[headline_at] = "\n".join(hl) + "\n"
    open(os.path.join(OUT, "mean_reversion.md"), "w").write("\n".join(L) + "\n")
    cfgs = [{k: c[k] for k in ("family", "tf", "L", "zin", "N", "stop", "regime", "name")} for c, *_ in res.values()]
    json.dump({"rows": stage, "variant_configs": cfgs}, open(os.path.join(OUT, ".mr_rows.json"), "w"), default=str, indent=0)
    import csv
    with open(os.path.join(OUT, "mr_trades_best.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["tf", "variant", "cost", "sym", "t_in", "t_out", "ret", "reason", "is_oos", "in_book"])
        for tf, name, r, sr in heads:
            for cost in ("lo", "hi"):
                bk = {(t["sym"], t["t_in"]) for t in r[cost]["bk"]}
                for t in r[cost]["tr"]: w.writerow([tf, name, cost, t["sym"], t["t_in"], t["t_out"], round(t["ret"], 6), t["reason"], t["is_oos"], (t["sym"], t["t_in"]) in bk])
    print("\n".join(hl))
