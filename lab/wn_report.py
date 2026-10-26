#!/usr/bin/env python3
"""out/winners.md from out/wn_profile.json + out/wn_results.json + out/.wn_rows.json"""
import json, datetime as dt
O = "/workspace/lab/out"; P = json.load(open(f"{O}/wn_profile.json")); R = json.load(open(f"{O}/wn_results.json"))
RW = {r["variant"]: r for r in json.load(open(f"{O}/.wn_rows.json"))["rows"]}
vt = len(json.load(open("/workspace/lab/data/variants_tried.json")))
f = lambda x, p=3: "—" if x is None else f"{x:+.{p}f}"
c = P["candles"]; L = []
def S_(d): return f"n={d['n']}, mean {f(d['mean'])}, median {f(d['median'])}, CI [{f((d['ci'] or [None])[0],2)}, {f((d['ci'] or [None,None])[1],2)}], win {d['win'] if d['win'] is not None else '—'}"
anyc = [k for k, r in RW.items() if r.get("candidate") == "yes"]
L += ["# Learning from winners (WN_), phase 2: PAPER ONLY", "", f"_Generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%MZ}. Data: Scout winners/ batch 1 (4 wallets, {P['n']} closed trades, partial). Code: wn_fetch.py, wn_profile.py, wn_rules.py, wn_report.py. Pre-registration: notes.md '2026-10-24T00:55Z winners (WN_)'._", "",
      "## Plain answer", "",
      ("Candidates: " + ", ".join(anyc)) if anyc else
      "**No rule distilled from the winners clears costs out of sample. No WN_ candidate.** The sample is tiny: 141 trades from 4 wallets, and only 64 of them won after 5% costs. Every pattern below rests on 10–60 trades and was picked on outcome, so treat each one as a hypothesis, not a finding. Turned into mechanical rules and run on ~199 graduated tokens the winners did NOT trade, the best rule (R2: fresh 5m pop, not already up >50% in 1h) loses about 5–8% per trade. That beats random entries (about −10 to −13%) but is still negative at 4.7% costs, and its 95% CI includes zero on the losing side. Excluding the nights the winners traded leaves too few trades (n ≤ 5) to say anything.", "",
      "## 1. What separates winning from losing entries (inside the 141; outcome-selected, small n)", "",
      "| feature | winners n | winners median | losers n | losers median |", "|---|---|---|---|---|"]
for k, v in P["contrast_all"].items(): L.append(f"| {k} | {v['n_win']} | {v['med_win']} | {v['n_lose']} | {v['med_lose']} |")
L += ["", "Notes:",
      "- Winning entries were in smaller (median mcap ≈ $38k vs $80k), quieter tokens: less 1h volume and fewer active 1m candles in the prior 30 min. They had *less* prior-1h run-up (n=25 vs 38 with data). **But the mcap gap is mostly a wallet-mix effect:** neodot trades about $7k curve coins and wins 24/40. Within each wallet the direction is mixed (benji's winners were the *bigger* coins), so a pooled 'small mcap wins' is not a dependable pattern.",
      "- Clustering: smart_co_buys_30m is 0 at the median for both groups. Winners did not need other smart wallets in the token.",
      "- No data for liquidity, holders or holder growth at entry: Scout's fields are BLANK because there are no free historical snapshots. Untested.",
      "- X buzz is untestable: x-intel first-mentions.jsonl starts 10-23 and mentions 0 of the winners' 141 mints.",
      f"- Pump.fun-curve entries: {P['pumpfun_entry']['True']['n']} trades, {P['pumpfun_entry']['True']['win']} wins, median {P['pumpfun_entry']['True']['med']}%. Post-migration: {P['pumpfun_entry']['False']['n']} trades, {P['pumpfun_entry']['False']['win']} wins, median {P['pumpfun_entry']['False']['med']}%. (Most of the curve entries are neodot's.)", ""]
L += ["Per wallet (median mcap: winners / losers; median hold min: winners / losers):", ""]
for w, cc in P["contrast_by_wallet"].items():
    m = cc["mcap_at_entry_usd_approx"]; h = cc["hold_min"]
    L.append(f"- {w}: {m['n_win']}W/{m['n_lose']}L; mcap {m['med_win']} / {m['med_lose']}; hold {h['med_win']} / {h['med_lose']}")
L += ["", "## 2. Entry timing vs random entries on the same tokens (GT 1m candles)", "",
      f"Trades with usable candles around entry: {c['trades_with_candles']}/{P['n']}. All figures are net of 5%.", "",
      f"- Their actual trades: {S_(c['actual_net5'])}",
      f"- Their actual trades, each capped at 10x (to compare with random): {S_(c['actual_net5_capped10x'])}",
      f"- Random time on the same token (±5 min–4 h), same hold: {S_(c['random_same_token_same_hold_net5'])}",
      f"- Their entries with a fixed SL25/TP50/2h exit: {S_(c['their_entries_fixed_exit_dflt_net5'])}",
      f"- Their entries with a fixed SL20/TP30/30m exit: {S_(c['their_entries_fixed_exit_quick_net5'])}", "",
      "**Read:** with fixed exits, their entries lose about 7% (the CI sits at or below 0). That is no better than this universe's random entries (−10 to −13%) by any margin worth trading. Their real results come from **exit and hold discretion**: letting a few runners go and cutting or flipping the rest. Entry selection alone does not carry the edge. Random-time windows on the same tokens include the pre-entry run-up, so that baseline is generous to random.", "",
      "## 3. Exits", "",
      f"- Price 30 min after their exit vs exit price: {S_(c['drift_30m_after_their_exit'])}",
      f"- 120 min after: {S_(c['drift_120m_after_their_exit'])}",
      f"- Baseline, random time on the same tokens, 30 min forward: {S_(c['random_time_drift_30m'])}; 120 min: {S_(c['random_time_drift_120m'])}",
      "- **Read:** after their exits the price keeps falling (median −15% at 30 min, −34% at 2 h; it rises after only 21–31% of exits). Random times on the same tokens give a median of about −1 to −2%. Their exits are well timed. That is a real skill, but it is discretionary: no simple rule here reproduces it. The default/quick fixed exits on their own entries lose.",
      "- By hold time (net5 %, n / wins / median): " + "; ".join(f"{k}: {v['n']}/{v['win']}/{v['med']}" for k, v in P["by_hold"].items()),
      "- Holds under 2 min win 75%. That is outcome-driven (fast flips of tokens that popped) and can't be used as a rule.", "",
      "## 4. Time of day (Dublin, entry) and size", "",
      "| bucket | n | wins | median net5 % | mean net5 % |", "|---|---|---|---|---|"]
for k, v in P["tod_dublin"].items(): L.append(f"| {k} | {v['n']} | {v['win']} | {v['med']} | {v['mean']} |")
L += ["", "By entry mcap: " + "; ".join(f"{k}: n={v['n']} w={v['win']} med={v['med']}" for k, v in P["by_mcap"].items()),
      "", "By size (USD): " + "; ".join(f"{k}: n={v['n']} w={v['win']} med={v['med']}" for k, v in P["by_size_usd"].items()),
      "", "Means are dominated by a few outliers in every bucket. With 2–43 trades per bucket, no time-of-day effect can be distinguished from noise.", ""]
L += ["## 5. Rules tested on tokens the winners did NOT trade (held out by date)", "",
      f"Universe: Lab backfill PumpSwap graduations with 1m candles (read-only), {R['universe']} tokens after removing {R['excluded_winner_mints']} winner mints. Holdout = tokens migrating after {dt.datetime.fromtimestamp(R['holdout_after'], dt.timezone.utc):%m-%d %H:%MZ}. Costs 4.7% (<$1M). $5 stake. First trigger per token.", "",
      "| variant | trades | mean | 95% CI | OOS n / mean | score/25 | lucky | candidate |", "|---|---|---|---|---|---|---|---|"]
for k, t in R["tests"].items():
    r = RW.get(k, {})
    if t.get("trades"): L.append(f"| {k} | {t['trades']} | {f(t['mean_ret'])} | [{f(t['ci_lo'],2)}, {f(t['ci_hi'],2)}] | {r.get('n_out_of_sample','—')} / {f(r.get('oos_mean_ret'))} | {r.get('score_total','—')} | {r.get('lucky_number','')} | {r.get('candidate','no')} |")
    else: L.append(f"| {k} | 0 | — | — | — | — | — | no |")
L += ["", "Random entry, same age window, every universe token: " + "; ".join(f"{rn}/{en}: n={v['n']} mean {f(v['mean'])}" for rn, d in R["controls"].items() for en, v in d.items()), ""]
L += ["## WHY THIS COULD FAIL / who is on the other side", "",
      "- **Selection on outcome:** winners/ was chosen for being profitable. Their edge is a few huge outliers: 3 of 4 have a negative median trade. A rule can copy their entry *conditions* but not their discretion: which coin, and when to hold the 10× runner.",
      "- **Small n:** 141 trades; feature contrasts rest on 25–77 trades each, and some fields cover <50%.",
      "- **Universe mismatch:** the backfill universe is post-migration PumpSwap pools only (first ~1000 traded minutes). neodot's curve-phase entries at ~$6.6k can't be replicated there. Post-migration mcap is bimodal (most tokens collapse to about $3k within 2 h).",
      "- **Other side:** for small post-migration pools, the counterparty is the bundlers and early holders unloading into any 5m pop. That's why 'momentum, not chased' still loses after 4.7%.",
      "- **Data:** mcap_at_entry is an approximation (current supply). Liquidity and holders at entry are unavailable. Fills on 1m closes are optimistic.", "",
      f"variants_tried (global) = {vt}.", "",
      "Out of scope here (another Lab job): copy-exit and neodot copy replay."]
open(f"{O}/winners.md", "w").write("\n".join(L)); print("ok")
