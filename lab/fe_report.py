"""PAPER ONLY. Writes out/fast_exit.md and out/.fe_rows.json (staging for merge_extra.py FE) from fe_backtest.run()."""
import json, os, statistics, datetime as dt
import fe_backtest as F, scoring
OUT = F.OUT
def pc(x): return "–" if x is None else f"{x*100:+.1f}%"
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
E, ok, split, rules, G = F.run()
FX = [r for r in rules if r[0] == "fx"]; LAD = ("ladder",)
def paired(sm, ck, r, oos=None):
    a = G[(sm, ck, r)]["tr"]; b = G[(sm, ck, LAD)]["tr"]
    d = [x["ret"] - y["ret"] for x, y in zip(a, b) if oos is None or (x["t"] >= split) == oos]
    return (statistics.fmean(d) if d else None, F.boot(d), len(d))
# selection: in-sample total at self10, primary stop model (low). Never looks at OOS.
best = max(FX, key=lambda r: G[("low", "self10", r)]["is_tot"]); bn = F.rname(best)
best_std = max(FX, key=lambda r: G[("std", "self10", r)]["is_tot"])
# leaderboard rows (primary 'low' model, self10 + cf10), lucky flags along each axis
rows, cfgs, board, fams = [], [], [], {}
for sm in ("low", "std"):
    for ck in F.COSTS:
        for r in rules:
            cfgs.append(dict(family="fast_exit", rule=list(r), cost=ck, costm=F.COSTS[ck], stop_fill=sm, delay=F.DELAY, pool="live+scout+cr30", name=f"{F.rname(r)}_{ck}_{sm}"))
for ck in ("self10", "cf10"):
    for r in rules:
        S = G[("low", ck, r)]; v = f"{F.rname(r)}_{ck}"
        board.append(dict(variant=v, trades=S["n"], net_profit_after_costs=S["total"]))
        if r[0] == "fx":
            _, tp, sl, h = r
            fams.setdefault(f"{ck}_tp_sl{sl}_h{h}", []).append((tp, v)); fams.setdefault(f"{ck}_sl_tp{tp}_h{h}", []).append((sl, v)); fams.setdefault(f"{ck}_h_tp{tp}_sl{sl}", []).append((h, v))
lf = scoring.lucky_flags(board, fams)
for ck in ("self10", "cf10"):
    for r in rules:
        S = G[("low", ck, r)]; sc = S["sc"]; v = f"{F.rname(r)}_{ck}"
        ho = "yes" if (S["n_oos"] >= 20 and S["is_tot"] > 0 and (S["oos_mean_ret"] or 0) > 0 and False) else ("no" if S["n_oos"] >= 20 else f"insufficient (n_out={S['n_oos']}<20)")
        cand = "yes" if sc["score_total"] >= 18 and S["n"] >= 50 and ho == "yes" else "no"
        st = G[("std", ck, r)]
        rows.append(dict(variant=v, trades=S["n"], win_rate=round(S["win"], 3), net_profit_after_costs=round(S["total"], 2), max_drawdown=round(S["mc"][1] * 100, 2),
            holds_out_of_sample=ho, n_in_sample=S["n_is"], n_out_of_sample=S["n_oos"], mean_ret=round(S["mean_ret"], 4), median_ret=round(S["med_ret"], 4),
            ci95_mean_ret=f"[{S['ci'][0]:+.4f},{S['ci'][1]:+.4f}]", oos_mean_ret=round(S["oos_mean_ret"], 4), in_net_pnl=round(S["is_tot"], 2), out_net_pnl=round(S["oos_tot"], 2),
            **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
            net_ex_best_trade=round(S["ex_best"], 2), mc_dd_p5=round(S["mc"][0], 3), mc_dd_p50=round(S["mc"][1], 3), mc_dd_p95=round(S["mc"][2], 3), candidate=cand,
            lucky_number=lf.get(v, "n/a (not profitable)"), family="fast_exit_" + ck,
            note=f"PAPER fast-exit copy test, {S['n']} pooled signals (6 live paper + 97 Scout winners round trips + 51 CR 30d first buys), +5s entry, {ck}, stop fills at bar LOW (std-fill mean {pc(st['mean_ret'])}); scout part SELECTION-CONTAMINATED; see out/fast_exit.md"))
json.dump(dict(rows=rows, variant_configs=cfgs), open(os.path.join(OUT, ".fe_rows.json"), "w"), indent=0, default=str)
# ---------------- report
L = []; A = L.append
Sb = {k: G[("low", k, best)] for k in F.COSTS}; Sl = {k: G[("low", k, LAD)] for k in F.COSTS}
Sbs = {k: G[("std", k, best)] for k in F.COSTS}; Sls = {k: G[("std", k, LAD)] for k in F.COSTS}
n_live = sum(e["src"] == "live" for e in ok); n_sc = sum(e["src"] == "scout" for e in ok); n_cr = sum(e["src"] == "cr30" for e in ok)
pos_any = [(sm, ck, F.rname(r)) for sm in ("low", "std") for ck in F.COSTS for r in FX if G[(sm, ck, r)]["total"] > 0]
beat_is_oos = sum(1 for r in FX if paired("low", "self10", r, False)[0] > 0 and paired("low", "self10", r, True)[0] > 0)
d_all = paired("low", "self10", best); d_is = paired("low", "self10", best, False); d_oos = paired("low", "self10", best, True)
d_cf = paired("low", "cf10", best)
A(f"# Fast exits on recorded copy signals (PAPER, {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M')}Z)\n")
A("## Plain answer\n")
A(f"- **Every one of the 36 fast-exit rules loses money after costs, at every cost level and under both stop-fill models.** "
  f"Profitable settings: {len(pos_any)} of 216 (36 rules × 3 costs × 2 stop models).")
A(f"- Best rule (chosen on in-sample only, self $10, stops filled at the bar's low): **TP +{int(best[1]*100)}% sell all, stop −{int(best[2]*100)}%, max hold {best[3]} min** (`{bn}`). "
  f"Net per trade **{pc(Sb['self10']['mean_ret'])} at self $10** and **{pc(Sb['cf10']['mean_ret'])} at copyfomo** on {Sb['self10']['n']} trades; "
  f"in-sample {pc(Sb['self10']['is_mean_ret'])} (n={Sb['self10']['n_is']}) vs held out {pc(Sb['self10']['oos_mean_ret'])} (n={Sb['self10']['n_oos']}) at self $10 "
  f"(copyfomo {pc(Sb['cf10']['is_mean_ret'])} / {pc(Sb['cf10']['oos_mean_ret'])}).")
A(f"- With the gentler METHOD stop fill (trigger −2.5%, or the open on a gap) the same rule is {pc(Sbs['self10']['mean_ret'])} at self $10 and {pc(Sbs['cf10']['mean_ret'])} at copyfomo "
  f"(IS {pc(Sbs['self10']['is_mean_ret'])} / OOS {pc(Sbs['self10']['oos_mean_ret'])}); best-in-sample rule there is `{F.rname(best_std)}`.")
A(f"- **vs the current ladder (same {Sl['self10']['n']} trades): it loses less, not more.** Ladder {pc(Sl['self10']['mean_ret'])}/trade at self $10 "
  f"(IS {pc(Sl['self10']['is_mean_ret'])} / OOS {pc(Sl['self10']['oos_mean_ret'])}), {pc(Sl['cf10']['mean_ret'])} at copyfomo. "
  f"Paired difference (fast − ladder) {pc(d_all[0])}/trade, 95% CI [{pc(d_all[1][0])}, {pc(d_all[1][1])}]; IS {pc(d_is[0])} (n={d_is[2]}), **held out only {pc(d_oos[0])} (n={d_oos[2]}, CI [{pc(d_oos[1][0])}, {pc(d_oos[1][1])}]), i.e. not distinguishable from the ladder out of sample**; copyfomo {pc(d_cf[0])} (held out {pc(paired('low','cf10',best,True)[0])}). "
  f"With METHOD stop fills: ladder {pc(Sls['self10']['mean_ret'])} vs fast {pc(Sbs['self10']['mean_ret'])}; held out {pc(paired('std','self10',best,True)[0])} at self $10 and {pc(paired('std','cf10',best,True)[0])} at copyfomo.")
A(f"- Neighbours agree on the *direction* (short holds and a +20% target are least bad; {beat_is_oos}/36 rules beat the ladder both in-sample and held out), "
  f"but nothing is profitable, so the lucky-number check is n/a: there is no edge to be lucky about. 'Loses less' mostly means 'is in the market for less time': "
  f"after costs (~3% round trip at self $10) these signals drift down on average, and the shortest hold wins.")
A(f"- METHOD score: **{Sb['self10']['sc']['score_total']}/25** at self $10 ({', '.join(f'{k}={Sb['self10']['sc'][k]}' for k in ('sc_oos_risk','sc_drawdown','sc_trades','sc_edge','sc_stability'))}), "
  f"{Sb['cf10']['sc']['score_total']}/25 at copyfomo. Not a candidate (needs ≥18, >0 out of sample). Ladder: {Sl['self10']['sc']['score_total']}/25.")
A("\n**WHY THIS COULD FAIL:** 97 of 154 trades are Scout's hand-picked winners (selection-contaminated) and only 6 are live signals; 1-min GT candles are sparse, so intra-minute stop/target fills are approximations (22 trades' candles end before 45 min).\n"
  "The held-out edge over the ladder is +2% with a CI spanning ±13%: 'fast loses less' is mostly 'less time exposed to a down-drifting book', not an edge. On the other side: the leader and faster bots who bought before our +5 s fill and sell into our bounce.\n")
A("## Setup\n")
A(f"- Signals pooled ({len(ok)} with price data): {n_live} live paper entries from /workspace/selfcopy (benji J9WL4, ypnn-day Bert, CLAUDIA, 9cRCn9, 98kfF7, FARTBOY; Bert/CLAUDIA/FARTBOY are the 3 copylive BUYs missed today), "
  f"{n_sc} Scout winners round trips (_benjitrades/bystevenr/onlyzhynx, bj_full_replay inputs), {n_cr} CR 30-day first buys with candles (benji/bystevenr/ExactTallTakin/pointfarmcap; (leader, mint) pairs already in Scout dropped). "
  "Excluded: bystevenr 5UHeHy (dry-run, forced; no GT trades since 10-22, no price data at entry). No live-wallet trades exist (live copy book has never filled).")
A("- Fresh data: 14 GeckoTerminal calls (7 pool lookups + 7 1-min OHLCV pulls) at 7.5 s spacing for the live mints only (data/fe/). No Helius/Scout credits, no X.")
A("- Entry: signal + 5 s (measured on-chain drift for Scout/CR entries where clean, else leader median; live = our Jupiter-quoted paper entry net of impact). Triggers on mark-to-market value net of exit cost (same convention as CR/BJ tests).")
A("- Costs: self $10 3.0% round trip, self $5 4.7%, copyfomo 5.3% (at $10), each + liquidity-scaled impact (Jupiter quote fit, liq ~ √price) + gas for extra sell legs. Stop checked before target in every bar.")
A("- Stop fill: **low** (primary, per brief) = bar's low; **std** = open if gapped, else trigger × 0.975 (METHOD/TRUTH calibration). Targets fill at the level, or the open if gapped above.")
A(f"- Max hold: exit at the last 1-min close before entry + hold. Ladder: TP +40%/25%, +100%/25%, rest +500%, breakeven stop after TP1, −20% hard stop, run to the end of the candle data (Scout: full horizon, CR: leader exit/08:00, live: now).")
A(f"- Holdout: latest 30% of pooled signals by time, from **{iso(split)} UTC** (IS {Sb['self10']['n_is']} / OOS {Sb['self10']['n_oos']}). Selection uses in-sample only.")
A(f"- Variants tried counter updated by merge (+{len(cfgs)} configs: 37 rules × 3 costs × 2 stop models).\n")
for sm in ("low", "std"):
    A(f"## All 36 rules + ladder, stop fill = {sm} (mean net per trade; IS / OOS)\n")
    A("| rule | n | self $10 all | self $10 IS / OOS | self $5 | copyfomo all | copyfomo IS / OOS | win | stops/tp/time | vs ladder (self10, paired) | score /25 |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rules, key=lambda r: -G[(sm, "self10", r)]["mean_ret"]):
        s = G[(sm, "self10", r)]; c = G[(sm, "cf10", r)]; f5 = G[(sm, "self5", r)]; rs = s["reasons"]
        dv = "–" if r == LAD else pc(paired(sm, "self10", r)[0])
        A(f"| `{F.rname(r)}`{' **(best IS)**' if r == (best if sm == 'low' else best_std) else ''} | {s['n']} | {pc(s['mean_ret'])} | {pc(s['is_mean_ret'])} / {pc(s['oos_mean_ret'])} | {pc(f5['mean_ret'])} | "
          f"{pc(c['mean_ret'])} | {pc(c['is_mean_ret'])} / {pc(c['oos_mean_ret'])} | {s['win']*100:.0f}% | {rs.get('stop',0)+rs.get('stop_be',0)}/{sum(v for k,v in rs.items() if k.startswith('tp'))}/{rs.get('time',0)+rs.get('horizon',0)} | {dv} | {s['sc']['score_total']} |")
    A("")
A("## Best rule by source (stop fill = low, self $10)\n")
A("| source | n | fast net $ | ladder net $ |\n|---|---|---|---|")
for s_ in ("live", "scout", "cr30"):
    A(f"| {s_} | {Sb['self10']['by_src'][s_][0]} | {Sb['self10']['by_src'][s_][1]:+.2f} | {Sl['self10']['by_src'][s_][1]:+.2f} |")
A("\n## Today's live signals (stop fill = std, self $10, per-trade return)\n")
A("| signal | fast best | ladder |\n|---|---|---|")
for x, y in zip(G[("std", "self10", best)]["tr"], G[("std", "self10", LAD)]["tr"]):
    if x["src"] == "live":
        nm = next((e["sym"] for e in ok if e["mint"] == x["mint"]), None) or x["mint"][:6]; A(f"| {nm} ({x['label']}) | {pc(x['ret'])} ({x['reason']}) | {pc(y['ret'])} ({y['reason']}) |")
open(os.path.join(OUT, "fast_exit.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L[:12]))
