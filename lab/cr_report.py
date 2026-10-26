"""Stage 5 (PAPER ONLY): reports + staged leaderboard rows from cr_replay grid.
Writes out/copy_replay_30d.md, out/copy_fee_sensitivity.md (v3; v2 kept at .bak-v2), out/.cr_rows.json, out/.fs_rows_v3.json."""
import json, os, statistics, datetime as dt, collections
import cr_replay as R, copy_fee_sensitivity as fs
from cr_enrich import load_swaps, LEAD, WIN0
from copy_candidates import maxdd
OUT = R.OUT; f = R.f
def fm(x): return R.f(x)
def ci(S): return f"[{fm(S['ci'][0])}, {fm(S['ci'][1])}]" if S["ci"][0] is not None else "–"
def holds(S, tr):
    if S["n_oos"] < 20: return f"insufficient (n_out={S['n_oos']}<20)"
    o = [x["pnl"] for x in tr if x["t"] >= R.HOLDOUT]
    return "yes" if S["in_net"] > 0 and S["oos_ev"] > 0 and fs.boot_ci(o)[0] > 0 else "no"
def row(name, g, note, family):
    S = g["S"]; z = g["size"]; tr = g["tr"]; sc = S["sc"]; n = S["n"]
    oos = [x["ret"] for x in tr if x["t"] >= R.HOLDOUT]
    mc = S["mc"] or (0, 0, 0)
    return {"variant": name, "trades": n, "win_rate": round(S["win"], 3) if n else "", "net_profit_after_costs": round(S["total"], 2),
            "max_drawdown": round(maxdd([x["pnl"] for x in tr]), 2), "holds_out_of_sample": holds(S, tr), "n_in_sample": S["n_in"], "n_out_of_sample": S["n_oos"],
            "mean_ret": round(S["ev_pct"], 3) if n else "", "median_ret": round(statistics.median([x["ret"] for x in tr]), 3) if n else "",
            "ci95_mean_ret": f"[{S['ci'][0]/z:+.2f},{S['ci'][1]/z:+.2f}]" if S["ci"][0] is not None else "",
            "oos_mean_ret": round(statistics.fmean(oos), 3) if oos else "", "in_net_pnl": round(S["in_net"], 2), "out_net_pnl": round(S["oos_net"], 2),
            **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
            "net_ex_best_trade": round(S["ex_best"], 2), "mc_dd_p5": round(mc[0], 3), "mc_dd_p50": round(mc[1], 3), "mc_dd_p95": round(mc[2], 3),
            "nights": sc["nights"], "nights_profitable": sc["nights_profitable"],
            "candidate": "yes" if sc["score_total"] >= 18 and n >= 50 and S["n_oos"] >= 20 and holds(S, tr) == "yes" else "no",
            "lucky_number": "n/a (cost/rule sweep)", "family": family, "note": note}

def main():
    es, DD, grid = R.main()
    sw = load_swaps()
    cov = {}
    for L in LEAD:
        s = sw[L]; d = {dt.datetime.utcfromtimestamp(x["t"]).date() for x in s}
        cov[L] = dict(n=len(s), csv=sum(x["src"] == "csv" for x in s), rpc=sum(x["src"] == "rpc" for x in s), days=len(d),
                      first=min(x["t"] for x in s) if s else None, last=max(x["t"] for x in s) if s else None,
                      cands=sum(e["leader"] == L for e in es))
    ts = lambda t: dt.datetime.utcfromtimestamp(t).strftime("%m-%d %H:%M") if t else "–"
    # validation stats
    ks = [x["k"] for g in grid if g["L"] == "ALL" and g["kind"] == "SELF" and g["size"] == 5.0 and g["prio"] == 0.0001 and g["delay"] == 5 for x in g["tr"]]
    q = lambda v, p: sorted(v)[int(p * (len(v) - 1))] if v else None
    agesrc = collections.Counter(e.get("age_src") or "none" for e in es)
    L5 = R.LEADERS + ["ALL"]
    md = ["# Copy replay, 30 days — OLD vs NEW rules at real self-copy costs (PAPER ONLY)", "",
          f"_Generated {dt.datetime.utcnow():%Y-%m-%d %H:%M} UTC by cr_replay.py / cr_report.py. Paper/backtest only; nothing was traded._", ""]
    # verdict
    pos = []
    for L in R.LEADERS:
        for rule in R.RULES:
            for z in (5.0, 10.0):
                S = R.cell(grid, L, rule, size=z)["S"]
                if S["n"] and S["ev"] > 0: pos.append((L, rule, z, S))
    md += ["## Verdict", ""]
    if not pos: md += ["**No leader is positive after costs under either rule set** (self-copy, live config prio 0.0001 SOL, 5 s delay, $5 or $10)."]
    else:
        for L, rule, z, S in pos:
            md.append(f"- {L} {rule} ${z:.0f}: EV {fm(S['ev'])}/trade on n={S['n']}, CI {ci(S)}, OOS n={S['n_oos']} net {fm(S['oos_net'])}, score {S['sc']['score_total']}/25"
                      + (" — CI includes 0, not a demonstrated edge" if S["ci"][0] is None or S["ci"][0] <= 0 else ""))
    for _p in (".cr_win_answers.md", ".cr_win_section.md"):        # Scout winners batch 1 = centre of this report (cr_win_replay.py)
        _f = os.path.join(OUT, _p)
        if os.path.exists(_f): md += ["", open(_f).read()]
    md += ["", "---", "", "# Part B — the original four leaders, OLD vs NEW rules (30 days)"]
    md += ["", "## Headline: self-copy, prio 0.0001 SOL (live HARD cap), 5 s delay", "",
           "| leader | rules | size | trades | EV $/trade | EV % | median $ | total $ | ex-best $ | 95% CI mean $ | win | held-out n / net $ / EV $ | MC DD p95 ($100) | score /25 | exits (stop/trail/tp-half/mirror/flat) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for L in L5:
        for rule in R.RULES:
            for z in R.SIZES:
                S = R.cell(grid, L, rule, size=z)["S"]; r = S["reasons"]
                ex = f"{r.get('stop',0)}/{r.get('trail',0)}/{S['tp']}/{r.get('mirror_full',0)}/{r.get('flat_0800',0)}"
                md.append(f"| {L} | {rule} | ${z:.0f}{' (not allowed live)' if z > 10 else ''} | {S['n']} | {fm(S['ev'])} | {f(S['ev_pct'], pct=True)} | {fm(S['med'])} | {fm(S['total'])} | {fm(S['ex_best'])} | {ci(S)} | "
                          f"{f(S['win'], pct=True, sign=False)} | {S['n_oos']} / {fm(S['oos_net'])} / {fm(S['oos_ev'])} | {f(S['mc'][2], pct=True, sign=False) if S['mc'] else '–'} | {S['sc']['score_total']} | {ex} |")
    md += ["", "## Copyfomo (≈5.3% round trip + pool impact, $0.015/tx, 5 s) side by side with self-copy", "",
           "| leader | rules | size | n | self EV $ | copyfomo EV $ | self total $ | copyfomo total $ | self avg cost RT | copyfomo avg cost RT |", "|---|---|---|---|---|---|---|---|---|---|"]
    for L in L5:
        for rule in R.RULES:
            for z in R.SIZES:
                a = R.cell(grid, L, rule, size=z)["S"]; b = R.cell(grid, L, rule, "CF", size=z)["S"]
                md.append(f"| {L} | {rule} | ${z:.0f} | {a['n']}/{b['n']} | {fm(a['ev'])} | {fm(b['ev'])} | {fm(a['total'])} | {fm(b['total'])} | {f(a['cost'], pct=True, sign=False)} | {f(b['cost'], pct=True, sign=False)} |")
    md += ["", "## Sensitivity (ALL leaders pooled): priority fee × delay", "", "| rules | size | prio SOL | delay | n | EV $ | total $ | CI |", "|---|---|---|---|---|---|---|---|"]
    for rule in R.RULES:
        for z in R.SIZES:
            for pr in R.PRIOS:
                for d in R.DELAYS:
                    S = R.cell(grid, "ALL", rule, size=z, prio=pr, delay=d)["S"]
                    md.append(f"| {rule} | ${z:.0f} | {pr} | {d} s | {S['n']} | {fm(S['ev'])} | {fm(S['total'])} | {ci(S)} |")
    md += ["", "## Entry funnel (why candidates were not copied; headline cell, $5)", "", "| leader | rules | candidates | copied | skipped by reason |", "|---|---|---|---|---|"]
    for L in L5:
        for rule in R.RULES:
            g = R.cell(grid, L, rule, size=5.0)
            md.append(f"| {L} | {rule} | {sum(1 for e in es if L == 'ALL' or e['leader'] == L)} | {g['S']['n']} | {', '.join(f'{k} {v}' for k, v in sorted(g['sk'].items(), key=lambda kv: -kv[1]))} |")
    md += ["", "## Data coverage", "", "| leader | swaps in window | from Scout csv | from public RPC | UTC days with swaps | first – last swap (UTC) | first-buy candidates (≥$50, mcap ≥$100k) |", "|---|---|---|---|---|---|---|"]
    for L, c in cov.items():
        md.append(f"| {L} | {c['n']} | {c['csv']} | {c['rpc']} | {c['days']} | {ts(c['first'])} – {ts(c['last'])} | {c['cands']} |")
    db = DD["raw_buy"]["5s"]; dsl = DD["raw_sell"]["5s"]
    md += ["", "## Validation", "",
           f"- Gecko→on-chain level factor k (our entry mid / Gecko close of the entry minute), copied trades: n={len(ks)}, p10 {q(ks,.1) or 0:.3f}, median {q(ks,.5) or 0:.3f}, p90 {q(ks,.9) or 0:.3f}. k≈1 means Gecko candles and on-chain fills agree.",
           f"- Measured 5 s buy drift (pool fill after delay / leader fill): n={len(db)}, median {statistics.median(db) if db else 1:.4f}" + (f", p90 {q(db,.9):.4f}" if db else "") + f". Candidates without a measurement use the median ({DD['buy']['5s']:.4f}).",
           f"- Measured 5 s sell drift: n={len(dsl)}, median {DD['sell']['5s']:.4f}.",
           f"- Token-age source for the NEW 60-min filter: {dict(agesrc)} (rpc = pool account history; gecko = GeckoTerminal pool_created_at of the top pool; none = unknown → filtered as age_unknown).",
           ""]
    md += ["## Method", "",
           "- **Signals:** every leader swap in the 30-day window (Scout's trader_swaps.csv + my public-RPC extension). Candidate = leader's first swap in a mint is a buy ≥ $50 at mcap ≥ $100k, and the on-chain pre-balance is 0 (live's first_buy rule).",
           "- **Entry price:** the pool fill price (|Δquote vault| / |Δbase vault|) of the last trade in the leader's pool within slot+12 (5 s) or slot+5 (2 s), from getBlock; plus our own cost per side. Chase = our fill / leader fill − 1 (live definition).",
           "- **Costs:** self-copy = Jupiter-quote fit from data/fs_quotes/quotes.jsonl (round trip = 1.85% − 1.78%·log10(liq/$100k), floor 0.5%) + (prio + 5000 lamports) × SOL per tx. Copyfomo = 5.3% round trip + pool impact above the $1M-liq level + $0.015/tx.",
           "- **Path:** GeckoTerminal 1-min OHLCV of the token's pool, rescaled to the on-chain entry level (k). Stops gap through: fill at trigger × 0.975 or the candle open if it opened through. Stop is checked before TP within a candle; trailing stop uses the prior peak.",
           "- **Exits:** OLD = SL −25%, TP +100% sells half; NEW = SL −15%, TP +50% sells half, then 15% trail from peak on the rest. Both mirror the leader's sells (assumption: a leader sell ≥ 95% of their balance = full exit, otherwise we sell the same fraction) at the leader's sell time + delay. Everything is flat at the next 08:00 Dublin (live close_hour); no entries 07:45–08:00; ≤3 open per leader; a night halts at −$20.",
           f"- **Held-out split:** fixed before any result: trades at/after {dt.datetime.utcfromtimestamp(R.HOLDOUT):%Y-%m-%d %H:%M} UTC (last 9 of 30 Dublin nights ≈ 30%).",
           "- **METHOD score:** scoring.score (OOS risk, MC p95 drawdown on $100, trade count, edge, night stability), 5 each, /25. Candidate needs ≥18, ≥50 trades, and holding out of sample.", ""]
    md += ["## Caveats", "",
           "- **Small samples.** Trade counts per leader are tiny; most CIs straddle zero, and no held-out cell reaches 20 trades. Treat any sign as anecdotal.",
           "- **Missing benji wallet.** benji's TRUTH buy came from a wallet we don't have; the mapped wallet may not be his main one (mapping confidence: benji low, bystevenr low, pointfarmcap medium-low, ExactTallTakin medium).",
           "- **Partial history.** Scout's csv is capped; my RPC extension finished for benji only (bystevenr partial, pointfarmcap/ExactTallTakin csv only) because free mainnet-beta RPC is ~0.4 calls/s.",
           "- **1-minute candles** hide intra-minute wicks; stop fills use a 2.5% slip or the gap open, which may be kind on fast rugs.",
           "- **Drift** is measured from the pool's next trades where a block was fetched, else the median; real Jupiter routing may differ.",
           "- **$13 is not allowed live** (live.py HARD cap max_usd=10); shown for comparison only.",
           "- **Selfcopy is LIVE with real money for benji** — this paper result says nothing to justify sizing up.", ""]
    open(os.path.join(OUT, "copy_replay_30d.md"), "w").write("\n".join(md))
    # fee sensitivity v3
    fz = ["# Copy fee sensitivity v3 — self-copy vs copyfomo on the 30-day on-chain replay (PAPER ONLY)", "",
          f"_Generated {dt.datetime.utcnow():%Y-%m-%d %H:%M} UTC. Supersedes v2 (kept at out/copy_fee_sensitivity.md.bak-v2; v1 at copy_fee_sensitivity_v1.md). v2 costed the leaders' own round trips; v3 re-prices every copy from on-chain fills + Gecko 1-min paths (see out/copy_replay_30d.md) under both rule sets. Cost model reused from v2: Jupiter quotes in data/fs_quotes/quotes.jsonl._", "",
          "## Cost model (round trip, per $ traded)", "", "| pool liquidity | self $5 (prio 0.0001) | self $10 | self $5 (prio 0.0005) | copyfomo $5 |", "|---|---|---|---|---|"]
    sol = fs.solpx(es[-1]["buy"]["t"]) if es else 150
    for liq in (5e4, 1e5, 3e5, 1e6, 3e6):
        g = lambda z, pr: f"{(2*R.side_cost('SELF', liq) + 2*(pr+5e-6)*sol/z)*100:.2f}%"
        fz.append(f"| ${liq/1e3:,.0f}k | {g(5,1e-4)} | {g(10,1e-4)} | {g(5,5e-4)} | {(2*R.side_cost('CF', liq) + 2*0.015/5)*100:.2f}% |")
    fz += ["", "## EV per trade by leader, rule set and cost model (5 s delay unless noted)", "",
           "| leader | rules | size | n | self p0.0001 5s | self p0.0001 2s | self p0.0005 5s | copyfomo | Δ self−copyfomo $/trade |", "|---|---|---|---|---|---|---|---|---|"]
    for L in L5:
        for rule in R.RULES:
            for z in R.SIZES:
                a = R.cell(grid, L, rule, size=z); b = R.cell(grid, L, rule, size=z, delay=2); c = R.cell(grid, L, rule, size=z, prio=0.0005); d = R.cell(grid, L, rule, "CF", size=z)
                dd = (a["S"]["ev"] - d["S"]["ev"]) if a["S"]["n"] and d["S"]["n"] else None
                fz.append(f"| {L} | {rule} | ${z:.0f} | {a['S']['n']} | {fm(a['S']['ev'])} | {fm(b['S']['ev'])} | {fm(c['S']['ev'])} | {fm(d['S']['ev'])} | {fm(dd)} |")
    fz += ["", "Reading: self-copy saves roughly the cost-model gap per trade vs copyfomo; it does not turn a negative-EV leader positive unless the copyfomo column was already near zero. Full per-cell stats (CI, held-out, score) in out/copy_replay_30d.md and leaderboard rows CR_* / FS_*.", ""]
    open(os.path.join(OUT, "copy_fee_sensitivity.md"), "w").write("\n".join(fz))
    # staged rows
    cr, crc, fsr, fsc = [], [], [], []
    for L in R.LEADERS:
        for rule in R.RULES:
            for z in R.SIZES:
                g = R.cell(grid, L, rule, size=z); nm = f"CR_{L}_{rule.lower()}_self{z:.0f}"
                cr.append(row(nm, g, f"PAPER 30d on-chain copy replay, {rule} rules, self-copy ${z:.0f} prio 0.0001 5s; see out/copy_replay_30d.md", "copy_replay_30d"))
                crc.append(dict(R.RULES[rule], name=nm, leader=L, size=z, prio=0.0001, delay=5, kind="SELF", family="copy_replay_30d"))
                for kind, pr, d, short in (("SELF", 0.0001, 2, "p1_2s"), ("SELF", 0.0005, 5, "p5_5s"), ("CF", 0.0, 5, "ref")):
                    g = R.cell(grid, L, rule, kind, size=z, prio=pr, delay=d); nm = f"FS_{L}_{rule.lower()}_{short}{z:.0f}"
                    fsr.append(row(nm, g, f"PAPER copy fee sweep v3 (on-chain replay), {rule} rules, {kind} ${z:.0f} prio {pr} {d}s; see out/copy_fee_sensitivity.md", "copy_fee_sensitivity"))
                    fsc.append(dict(R.RULES[rule], name=nm, leader=L, size=z, prio=pr, delay=d, kind=kind, family="copy_fee_sensitivity", v=3))
    json.dump({"rows": cr, "variant_configs": crc}, open(os.path.join(OUT, ".cr_rows.json"), "w"), indent=0)
    json.dump({"rows": fsr, "variant_configs": fsc}, open(os.path.join(OUT, ".fs_rows_v3.json"), "w"), indent=0)
    print("rows", len(cr), len(fsr)); return es, DD, grid, cov

if __name__ == "__main__":
    main()
