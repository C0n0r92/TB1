#!/usr/bin/env python3
"""out/confluence.md from out/cl_results.json + out/.cl_rows.json (+ events.json structure stats)."""
import json, os, statistics as S, collections, datetime as dt
LAB = "/workspace/lab"; OUT = f"{LAB}/out"
R = json.load(open(f"{OUT}/cl_results.json")); RW = {r["variant"].replace("_LOOKAHEAD", ""): r for r in json.load(open(f"{OUT}/.cl_rows.json"))["rows"]}
E = json.load(open(f"{LAB}/data/cl/events.json"))
vt = json.load(open(f"{LAB}/data/variants_tried.json")); NV = len(vt); NCL = sum(1 for v in vt.values() if str(v).startswith("CL_"))
f = lambda x, p=3: "—" if x is None else f"{x:+.{p}f}"
def line(k):
    t = R["tests"][k]; r = RW.get(k, {})
    if not t.get("trades"): return f"| CL_{k} | {t.get('n_events',0)} | 0 | — | — | — | — | — | {t['lookahead'] if isinstance(t['lookahead'], str) else ('LOOKAHEAD' if t['lookahead'] else 'PIT')} | no |"
    la = "LOOKAHEAD" if t["lookahead"] else "PIT"
    return (f"| {k} | {t['n_events']} | {t['trades']} | {f(t['mean_ret'])} | [{f(t['ci_lo'],2)}, {f(t['ci_hi'],2)}] | {t['win_rate']:.0%} | "
            f"{t['n_out']} / {f(t['oos_mean'])} | {r.get('score_total','—')} (nights {r.get('nights','—')}) | {la} | {r.get('candidate','no')} |")
L = []
main = [k for k in R["tests"] if "__" not in k]
best_pit = [k for k in main if not R["tests"][k].get("lookahead") and R["tests"][k].get("trades")]
anyok = [k for k in R["tests"] if RW.get(k, {}).get("candidate") == "yes"]
L += ["# Confluence / clustering test (CL_) — phase 1, PAPER ONLY", "",
      f"_Generated {dt.datetime.utcnow():%Y-%m-%dT%H:%MZ}. Pre-registration: notes.md section '2026-10-24T00:10Z confluence (CL_) phase 1'. Code: cl_events.py, cl_fetch.py, cl_sim.py, cl_run.py, cl_report.py._", "",
      "## Plain answer", "",
      ("**Something cleared the bar:** " + ", ".join(anyok)) if anyok else
      "**Nothing clears costs out of sample. No CL_ variant is a candidate.** The point-in-time-clean set (EB_PIT, N≥2/30m) has 76 trades at a mean of " + f(R['tests']['CL_EB_PIT_n2_w30']['mean_ret']) + " per trade (CI entirely below 0). Its held-out part (n=" + str(R['tests']['CL_EB_PIT_n2_w30']['n_out']) + ") averages " + f(R['tests']['CL_EB_PIT_n2_w30']['oos_mean']) + ". That is *worse* than its own controls: the first buyer's entry, single-wallet copies, the same token at a random time, and the same time on other tokens. N≥3 is worse again. Confluence here mostly means one sniper operator firing several keys within seconds, and the copier is its exit liquidity. Leader confluence can't be tested (1–2 events), SMART4 has 8 events (LOOKAHEAD), and every EB_ALL/LEAD/SMART4 row is LOOKAHEAD and can never become a candidate. All data covers about 1–2 days, so stability scores are capped.", ""]
L += ["## Lookahead status of each signal set", "",
      "| set | wallets | status | why |", "|---|---|---|---|",
      "| LEAD | 4 copy leaders (_benjitrades, bystevenr, pointfarmcap, ExactTallTakin) + BtheBezel/cosby/zelda89 from trader_swaps.csv | **LOOKAHEAD** | picked from the fomo leaderboard over the same window as their swaps |",
      "| SMART4 | Scout `smart` (4 radar_early_trader) | **LOOKAHEAD** | every recorded buy comes before date_added (10-23 20–21h) |",
      "| EB_ALL | Scout `early_buyer` (187, 35 with buys) | **LOOKAHEAD** | wallets picked for being early in 100x runners; all buys counted |",
      "| EB_PIT | same, point-in-time | **PIT** | a wallet counts only from its runner's peak_at + 1h (when 'early in a 100x' became knowable); runner mints excluded |", ""]
L += ["## Results at the pre-registered default exit", "",
      "Default: entry = close of the minute containing (Nth buy + 10 s), else the next open within 10 min. SL −25% / TP +50% / 2 h time stop / 08:00 Dublin flat / 12 h cap. A drop to ≤0.2× counts as a rug, capped at −90%. Cost 4.7% round trip if entry mcap < $1M, else 2%. $5 stake, $100 equity. Holdout = signals after the 60th-percentile signal time (PIT: " + dt.datetime.utcfromtimestamp(R["holdout_after_pit"]).strftime("%m-%d %H:%MZ") + ").", "",
      "| test | events | trades (with candles) | mean/trade | 95% CI | win | OOS n / mean | score/25 | status | candidate |", "|---|---|---|---|---|---|---|---|---|---|"]
L += [line(k) for k in main]
L += ["", "Coverage (events → events with candles; EB_ALL/LEAD-only tokens are still being fetched at ≤5 req/min, so EB_ALL is a partial read): " + "; ".join(f"{k} {v['events']}→{v['with_candles']}" for k, v in R["coverage"].items()), ""]
L += ["## Controls", "", "| set | signal mean | first-buyer entry | same token, random time (±4h) | same time, other tokens |", "|---|---|---|---|---|"]
for k, c in R["controls"].items():
    s = R["tests"].get(f"CL_{k}", {}); fb = R["tests"].get(f"CL_{k}_firstbuyer", {})
    L.append(f"| {k} | {f(s.get('mean_ret'))} (n={s.get('trades',0)}) | {f(fb.get('mean_ret'))} (n={fb.get('trades',0)}) | {f(c['same_token_random_time']['mean'])} (n={c['same_token_random_time']['n']}) | {f(c['same_time_other_tokens']['mean'])} (n={c['same_time_other_tokens']['n']}) |")
sn = R["tests"].get("CL_EB_PIT_single_noncluster", {})
L += ["", f"Single-wallet copies on EB_PIT tokens with no 2-wallet cluster: n={sn.get('trades',0)}, mean {f(sn.get('mean_ret'))}, CI [{f(sn.get('ci_lo'),2)}, {f(sn.get('ci_hi'),2)}].", ""]
L += ["## Neighbour sweep (one parameter at a time around the default; PIT sets)", "", "| variant | trades | mean | OOS n/mean | score | lucky flag |", "|---|---|---|---|---|---|"]
for k, t in R["tests"].items():
    if "__" in k and t.get("trades"):
        r = RW.get(k, {}); L.append(f"| {k} | {t['trades']} | {f(t['mean_ret'])} | {t['n_out']}/{f(t['oos_mean'])} | {r.get('score_total','—')} | {r.get('lucky_number','')} |")
# structure
ev = E["events"]["EB_PIT_n2_w30"]["events"]
gaps = [e["t"] - e["t_first"] for e in ev]; days = collections.Counter(dt.datetime.utcfromtimestamp(e["t"]).strftime("%m-%d") for e in ev)
ws = collections.Counter(w for e in ev for w in e["wallets"])
L += ["", "## Why the PIT 'confluence' isn't independent smart money", "",
      f"- {len(ev)} EB_PIT N≥2/30m events, by day: {dict(days)}. Gap between 1st and Nth buy: median {S.median(gaps):.0f} s, {sum(g<=5 for g in gaps)}/{len(gaps)} within 5 s.",
      f"- Only {len(ws)} distinct wallets appear; the top ones: " + ", ".join(f"{w[:6]}…×{n}" for w, n in ws.most_common(6)) + ". Six of the nine were early in the same runner (ogkimchi, ranks 5–18, 1–2 s after launch), and two share the vanity prefix q2… That looks like one operator's sniper fleet firing together early on the bonding curve (median entry mcap ≈ $22k, all 4.7%-cost trades).",
      "- So 'N wallets agree' here is really 'one bot fired on several keys'. Scout's NOTES say the same thing: do not use clusters as a buy signal.", ""]
L += ["## WHY THIS COULD FAIL / who is on the other side", "",
      "- **Who's on the other side:** these wallets buy in the same second as the signal. A copier enters at least 10 s and one candle later, after the snipers' own buys have moved the price, so the copier is the exit liquidity for the sniper fleet and the migration bundlers.",
      "- **Sample:** every PIT event is on 10-23 (about 2 Dublin nights). The N≥2 holdout (n=32) is later in that same day, not a new regime, and N≥3 has only 5 held-out trades. The one positive sweep cell (N≥3, delay 120 s: n=11, +0.079) is flagged as a single lucky number, because its neighbours at 10 s and 60 s are negative.",
      "- **Selection:** the larger EB_ALL and LEAD sets were picked using the same window (LOOKAHEAD) and can never be candidates.",
      "- **Execution:** fills are on 1-minute candle closes. The real slippage at same-second sniper entries is worse than the 4.7% assumed (the 7% sensitivity case is in the sweep).",
      "- **Survivorship:** tokens with no GT candles (dead or rugged before indexing) drop out, which biases results upward.", ""]
L += [f"## Multiple testing", "", f"variants_tried (global, data/variants_tried.json) = {NV}; CL_ configs this run = {NCL}.", ""]
open(f"{OUT}/confluence.md", "w").write("\n".join(L)); print("\n".join(L)[:3000])
