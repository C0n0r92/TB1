#!/usr/bin/env python3
"""Write reports/lab-YYYY-MM-DD.md (Dublin date) from out/summary.json (+ out/guard_eval.md). PAPER ONLY; proposals only.
Sundays (Dublin) add the weekly review (METHOD.md rule 5). Keeps out/history/summary-<day>.json for decay tracking."""
import glob, json, os, sys, datetime
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "out/summary.json")))
a, lb, c = S["accrual"], S["leaderboard"], S["config"]
now_d = datetime.datetime.now(ZoneInfo("Europe/Dublin")); day = now_d.date().isoformat()
if len(sys.argv) > 1: day = sys.argv[1]
sunday = datetime.date.fromisoformat(day).weekday() == 6 or "--weekly" in sys.argv
f = lambda v, p=False: "-" if v in ("", None) else (f"{v*100:.0f}%" if p else (f"{v:+.2f}" if isinstance(v, float) else str(v)))
by = {v["variant"]: v for v in lb}

# WHY THIS COULD FAIL / who is on the other side (METHOD rule 4), by variant prefix
FAIL = {
 "GUARD": ("Guards were calibrated on ONE evening (27 coins, provisional labels) -> overfit; operators adapt within days "
           "(more holders via airdrop wallets, LP 'burn' then dev sells supply, fresh funder wallets beat known-rugger lists). "
           "Replay of pre-guard rows uses holder data fetched after the scan (optimistic).",
           "Launch operators/bundlers who sell into radar-style momentum buyers; snipers who bought at launch."),
 "A_": ("Momentum score selects coins already up a lot; 2%/side + slippage + gap-through stops eat small edges.",
        "Early buyers and bundlers taking profit into late momentum."),
 "LADDER": ("Few coins ever reach 2x, so the ladder mostly behaves like the stop; the trail gives back 30% on spikes that reverse in one candle.",
            "Same as the base rule; ladders only change exits."),
 "REENTRY": ("A second entry after a pump buys from people who were early; second legs on memecoins are rarer than they look on charts.",
             "Holders of the first leg distributing into the bounce."),
 "COPY": ("Leader P&L comes from their own logs (survivorship, 'marketing' wins); our fill lags theirs; they may exit through us.",
          "The leader themself (front-running followers), and everyone who bought before the leader's public call."),
 "CHUNK": ("Paper entries at logged DexScreener price; live fills during pumps are worse; tiny sample.", "Same as the radar."),
 "CLUSTER": ("Smart-wallet clusters may be one operator with many wallets; the 3rd buy can be the top.", "The cluster wallets themselves."),
}
def why(name):
    for k, v in FAIL.items():
        if name.startswith(k) or k in name: return v
    return ("Small sample; costs; regime change.", "Earlier buyers.")

L = [f"# Lab daily report: {day} (PAPER ONLY)", "",
     f"Generated {S['generated']}. ${c['costs']['bet_usd']:.0f}/trade, fee {c['costs']['fee_per_side']*100:.0f}%/side + ${c['costs']['fixed_cost_usd']} fixed, "
     f"slippage {c['costs']['base_slippage']*100:.1f}% + {c['costs']['impact_mult']}x size/liquidity, gap-through stops fill at candle close, "
     f"rugs capped at {c['costs']['rug_max_recovery']*100:.0f}% recovery, max {c['sim']['max_open']} open, flat by 08:00 Dublin. "
     f"OOS = signals after {a.get('split','-')}. Variants tried so far (multiple testing): **{a.get('variants_tried','?')}**. Method: METHOD.md.", "",
     "## Data", "",
     f"- {a['signals']} radar signals over {a['span_h']} h ({a['first']} → {a['last']}); {a['distinct_tokens']} tokens scanned, {a['scan_runs']} scans.",
     f"- Chunk live buys {a['chunk_buys']}; copyfomo skips {a['copyfomo_skips']} / copies {a['copyfomo_copies']}; intel snapshots {a['intel_snapshots']}; liquidity polls {a['liq_polls']}.", ""]
# ---- guarded radar forward test
L += ["## Guarded radar (rugguard live since ~21:13Z 2026-10-23)", "",
      "| variant | closed | open/pending | win | mean | net $ | MC DD p50/p95 | guard rejects (score>=55) | scout verdicts | OOS |", "|---|---|---|---|---|---|---|---|---|---|"]
for k, v in by.items():
    if k.startswith(("GUARD", "CHUNKPAPER")):
        L.append(f"| {k} | {v['trades']} | {v['open']}/{v['pending']} | {f(v['win_rate'],1)} | {f(v['mean_ret'],1)} | {f(v['net_profit_after_costs'])} | "
                 f"{f(v['mc_dd_p50'],1)}/{f(v['mc_dd_p95'],1)} | {v.get('guard_rejects') or '-'} | {v.get('scout_verdicts') or '-'} | {v['holds_out_of_sample']} |")
L += ["", "GUARD_live = only rows scanned with rugguard on (the true forward test). GUARD_replay* recompute the guard for pre-guard rows; "
      "only GUARD_replay_pit uses holder data captured <= 15 min after the scan.", ""]
ge = os.path.join(HERE, "out/guard_eval.md")
if os.path.exists(ge):
    g = open(ge).read().split("## per-token")[0].split("\n", 2)[-1]
    L += ["### Guard evaluation vs labels (out/guard_eval.md)", "", g.strip(), ""]
bp = os.path.join(HERE, "out/benji_probation.md")
if os.path.exists(bp):
    L += ["## _benjitrades probation (out/benji_probation.md)", ""] + [l for l in open(bp).read().splitlines()[2:] if not l.startswith("# ")] + [""]
cc = os.path.join(HERE, "out/copy_candidates.md")
if os.path.exists(cc):
    L += ["## Copy candidates + stake test (out/copy_candidates.md)", ""] + [l for l in open(cc).read().splitlines()[2:] if not l.startswith("# ")] + [""]
cf = os.path.join(HERE, "out/copyfomo_tests.md")
if os.path.exists(cf):
    L += ["## Copyfomo leader tests (out/copyfomo_tests.md)", ""] + [l for l in open(cf).read().splitlines()[2:] if not l.startswith("# ")] + [""]
# ---- leaderboard
L += ["## Leaderboard", "",
      "| variant | trades (in/out) | win | mean | CI95 mean | net $ | maxDD $ | MC DD p5/p50/p95 | score /25 | lucky | rug | OOS |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for v in lb:
    L.append(f"| {v['variant']} | {v['trades']} ({v['n_in_sample']}/{v['n_out_of_sample']}) | {f(v['win_rate'],1)} | {f(v['mean_ret'],1)} | {v['ci95_mean_ret'] or '-'} | "
             f"{f(v['net_profit_after_costs'])} | {f(v['max_drawdown'])} | {f(v['mc_dd_p5'],1)}/{f(v['mc_dd_p50'],1)}/{f(v['mc_dd_p95'],1)} | "
             f"{v['score_total']} | {v['lucky_number']} | {f(v['rug_rate'],1)} | {v['holds_out_of_sample']} |")
cands = [v for v in lb if v.get("candidate") == "yes"]
near = sorted([v for v in lb if v["trades"] and (v["net_profit_after_costs"] or 0) > 0], key=lambda v: -v["score_total"])[:3]
L += ["", "## Candidates (need score >= 18/25, >= 50 trades, holds OOS)", ""]
L += [f"- **{v['variant']}** ({v['score_total']}/25)" for v in cands] or ["- None yet."]
for v in (cands or near):
    w, other = why(v["variant"])
    L += ["", f"### {v['variant']}: WHY THIS COULD FAIL" + ("" if v in cands else " (profitable so far, NOT a candidate)"), "",
          f"- {w}", f"- Who is on the other side: {other}",
          f"- Sample: {v['trades']} trades over {v.get('nights','?')} night(s); net without its best trade {f(v.get('net_ex_best_trade'))}; lucky-number check: {v['lucky_number']}; "
          f"MC drawdown p95 {f(v['mc_dd_p95'],1)} of equity."]
L += ["", "## Caveats", "",
      "- Fewer than ~50 closed trades (and < 20 OOS) is noise. Labels are PROVISIONAL until 24 h after first scan (relabel.py).",
      "- 'uncovered' = no point-in-time intel at signal time; excluded, not counted.",
      "- COPY* rows use Scout's trader_trades.csv (leaders' own round trips) with assumed 5% copy lag and $20k pool depth.",
      "- Entry at signal-time price + modelled slippage; real fills during pumps may be worse."]
# ---- weekly review (Sundays)
hist = os.path.join(HERE, "out/history"); os.makedirs(hist, exist_ok=True)
json.dump({"day": day, "leaderboard": lb}, open(os.path.join(hist, f"summary-{day}.json"), "w"))
if sunday:
    old = sorted(p for p in glob.glob(os.path.join(hist, "summary-*.json")) if p[-15:-5] <= (datetime.date.fromisoformat(day) - datetime.timedelta(days=6)).isoformat())
    prev = {v["variant"]: v for v in json.load(open(old[-1]))["leaderboard"]} if old else {}
    surv = [v["variant"] for v in lb if str(v["holds_out_of_sample"]).startswith(("yes", "weak"))]
    decayed = [k for k, v in by.items() if k in prev and prev[k].get("mean_ret") not in ("", None) and v.get("mean_ret") not in ("", None)
               and v["mean_ret"] < prev[k]["mean_ret"] - 0.05]
    pv = by.get("CHUNKPAPER_all", {}); bt = by.get("GUARD_live", {})
    ranked = sorted([v for v in lb if v["trades"] and v["trades"] >= 10], key=lambda v: (-v["score_total"], -(v["net_profit_after_costs"] or 0)))
    L += ["", "## Weekly review (Sunday)", "",
          f"- Survived (holds OOS yes/weak): {', '.join(surv) or 'none'}",
          f"- Paper vs backtest: Chunk paper {pv.get('trades',0)} trades mean {f(pv.get('mean_ret'),1)} vs GUARD_live backtest {bt.get('trades',0)} trades mean {f(bt.get('mean_ret'),1)}",
          f"- Decayed vs {old[-1][-15:-5] if old else 'n/a'} (mean return down > 5 pts): {', '.join(decayed) or ('none' if prev else 'no week-old snapshot yet')}",
          f"- Double down on: {ranked[0]['variant'] + ' (' + str(ranked[0]['score_total']) + '/25)' if ranked else 'nothing (no variant with >= 10 trades)'}",
          f"- Drop: {ranked[-1]['variant'] + ' (' + str(ranked[-1]['score_total']) + '/25)' if len(ranked) > 1 else 'n/a'}",
          f"- Variants tried to date: {a.get('variants_tried')} (the best of many noisy tries looks good by chance)."]
os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
p = os.path.join(HERE, f"reports/lab-{day}.md"); tmp = p + ".tmp"; open(tmp, "w").write("\n".join(L) + "\n"); os.replace(tmp, p); print(p)
