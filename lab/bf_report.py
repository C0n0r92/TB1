#!/usr/bin/env python3
"""Render out/backfill.md from out/backfill.json, out/bf_trades.csv, data/backfill/{per_pool.json,alive.json,mig_seen.jsonl}."""
import csv, json, os, statistics, collections, time
from labcore import OUT, iso
BF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backfill")
R = json.load(open(os.path.join(OUT, "backfill.json"))); cal = R["calibration"]
T = list(csv.DictReader(open(os.path.join(OUT, "bf_trades.csv")))) if os.path.exists(os.path.join(OUT, "bf_trades.csv")) else []
alive = json.load(open(os.path.join(BF, "alive.json"))) if os.path.exists(os.path.join(BF, "alive.json")) else {}
seen = [json.loads(l) for l in open(os.path.join(BF, "mig_seen.jsonl"))]
sigs = [json.loads(l) for l in open(os.path.join(BF, "mig_sigs.jsonl"))]
pp = json.load(open(os.path.join(BF, "per_pool.json")))
L = []; w = L.append
f = lambda x, n=2: "" if x is None or x == "" else (f"{x:+.{n}f}" if isinstance(x, float) else str(x))
pct = lambda x: "" if x is None or x == "" else f"{100*float(x):+.1f}%"
w("# Backfill replay: radar / partial guard / survivor momentum on ~4 weeks of PumpSwap graduations (PAPER ONLY)\n")
w(f"Generated {R['generated']} by `bf_replay.py` + `bf_report.py`. Paper only, no trades, no keys. Free public data only.\n")
w("## Data sources\n")
w("- **Universe**: every pump.fun to PumpSwap graduation is signed by the pump.fun migration account `39azUYFW…jUJjg`. I paged its full signature history with the free public Solana RPC (`getSignaturesForAddress`, api.mainnet-beta.solana.com; the radar uses this RPC too). Then I fetched a seeded random sample of txs per UTC day (`getTransaction`). I kept only real migrations: success, a `Migrate` instruction, no `already migrated` retry. The mint is the non-WSOL mint; the pool is the owner of the 206.9M-token vault.")
nsig = sum(1 for s in sigs if not s['err']); real = sum(1 for s in seen if s.get('ok')); fetched = sum(1 for s in seen if s.get('fetched'))
w(f"  - Signatures paged: {len(sigs):,}. Successful: {nsig:,} (about 1,700/day, but many are retries). Txs inspected: {fetched:,}. Real migrations: {real:,} ({100*real/max(fetched,1):.0f}%), so roughly {int(nsig*real/max(fetched,1)/28):,} graduations/day.")
w("- **Prices/volumes**: GeckoTerminal 1-min OHLCV (USD, base token), one call per pool from creation (first 1,000 traded minutes). A second forward call is made for signal pools whose data ends before the trade deadline. Gecko and DexScreener calls share one cross-process throttle: 6.5 s spacing (≤9/min) until 23:33Z, then 16 s (≤4/min combined) per Zero's budget request.")
w("- **SOL/USD**: GeckoTerminal hourly SOL/USDC (Raydium `Czfq3…`). Fallback: Scout's daily `data/solusd.json`.")
w("- **Survivorship probe**: DexScreener `tokens/v1` (30 mints per call) shows which sampled mints are still listed today.")
w("- **Not used**: X, Helius (Scout's key; I have no SendToAgent tool to ask Scout), Solscan, pump.fun and GMGN (blocked), Polymarket.\n")
w("## Universe size by day (Dublin noon-to-noon night of the migration)\n")
w("Days are UTC migration days. Columns: pools sampled; Gecko ok / 404 / empty; pools passing the radar prefilter at some 10-min scan between 15 min and 6 h; radar signals under the low / central / high imputation; partial-guard signals (central).\n")
w("| day | sampled | ok | 404 | empty | prefilter | sig low/central/high | guard central |"); w("|---|---|---|---|---|---|---|---|")
cov = R["coverage_by_day"]; sd = R["signals_by_day"]; gd = R["guard_signals_by_day"]
ppd = collections.Counter(p["day"] for p in pp if p["first_pre"])
# signals by migration day
mig_day = {p["pool"]: p["day"] for p in pp}
tot = collections.Counter()
for d in sorted(cov):
    c = cov[d]; n = sum(c.values()); tot.update(c); tot["n"] += n
    w(f"| {d} | {n} | {c.get('ok',0)} | {c.get('404',0)} | {c.get('empty',0)+c.get('bad',0)} | {ppd.get(d,0)} | {sd['low'].get(d,0)}/{sd['central'].get(d,0)}/{sd['high'].get(d,0)} | {gd['central'].get(d,0)} |")
w(f"| **total** | {tot['n']} | {tot['ok']} | {tot['404']} | {tot['empty']+tot['bad']} | {sum(ppd.values())} | {R['n_signals']['low']}/{R['n_signals']['central']}/{R['n_signals']['high']} | {R['n_guard_signals']['central']} |")
w(f"\n{tot['unfetched']} sampled pools still have no candles (fetcher queue). Sampling/prefilter columns are keyed by UTC migration day; the signal columns by the signal's Dublin night (the IS/OOS key), so a row can show signals with no prefilter pool on the same line.\n")
w("## Survivorship bias\n")
n_ok = tot["ok"]; n_no = tot["404"] + tot["empty"] + tot["bad"]
w(f"- **Universe bias: none by construction.** The sample comes from on-chain migration txs, not from a listing. Dead coins are included at their true rate.")
w(f"- **Data gaps**: {n_no} of {n_ok+n_no} fetched pools ({100*n_no/max(1,n_ok+n_no):.1f}%) have no Gecko candles (404 or empty). They are excluded, and this is the only data-driven survivorship leak. A pool with no Gecko candles mostly never traded after migration, so it could not have reached the radar's $50k mcap / $15k liq prefilter anyway; the leak into the signal set is therefore about zero.")
spans = [p["span_h"] for p in pp]; n1 = [p["n1m"] for p in pp]
if pp:
    w(f"- **How fast graduations die**: median {statistics.median(n1):.0f} traded minutes in the first 16.7 h. {sum(x < 60 for x in n1)/len(n1):.0%} traded in fewer than 60 distinct minutes. {sum(p['peak_mcap'] >= 50000 for p in pp)/len(pp):.0%} ever printed ≥ $50k mcap. {R['pools']['reach_prefilter']/max(1,R['pools']['n']):.0%} passed the radar prefilter at a scan.")
if alive and T:
    def alive_ok(m): a = alive.get(m) or {}; return a.get("liq", 0) and a["liq"] >= 5000
    for v in ("BF_A_radar_central",):
        tr = [t for t in T if t["variant"] == v and t["status"] == "closed"]
        al = [t for t in tr if alive_ok(t["mint"])]; de = [t for t in tr if not alive_ok(t["mint"])]
        if tr:
            m = lambda xs: statistics.fmean(float(t["ret"]) for t in xs) if xs else None
            w(f"- **What a survivor-only universe would have shown.** I checked which sampled mints DexScreener still lists today with ≥ $5k liquidity. Of {len(tr)} closed baseline (central) trades, {len(al)} are on such coins. Mean net return: survivors {pct(m(al))}, the rest {pct(m(de))}, all {pct(m(tr))}. So building the backfill from coins still listed today would have overstated the mean by **{100*((m(al) or 0)-(m(tr) or 0)):+.1f} pp/trade**. That is the bias this design avoids.")
    la = sum(1 for p in pp if alive_ok(p['mint'])); w(f"- Share of all sampled graduations still listed with ≥ $5k liquidity today: {la}/{len(pp)} ({100*la/max(1,len(pp)):.1f}%).")
w("\n## Which score inputs could be recreated\n")
fa = cal["feature_agreement"]
w(f"I checked the replay against the live radar on tonight's {cal['n_rows']} scanned rows ({cal['n_pairs']} pairs). Each row was rebuilt from 1-min Gecko candles at the same timestamp.\n")
w("| scan.py input | status | live vs replay |"); w("|---|---|---|")
w(f"| price, mcap (price × 1e9 supply) | **recreated** | price median error {100*fa['price']['median_rel_err']:.1f}%, mcap {100*fa['mcap']['median_rel_err']:.1f}% |")
w(f"| pair age | **recreated** (on-chain migration time) | exact |")
w(f"| vol accel v5/(vh1/12) | **recreated** | corr {fa['accel']['corr']:.2f}, median abs error {fa['accel']['median_abs_err']:.2f} |")
w(f"| m5 / h1 price change | **recreated** (rolling 5 m / 60 m on 1-min closes) | m5 median abs error {fa['m5']['median_abs_err']:.1f} pp (Pearson corr {fa['m5']['corr']:.2f}, dragged down by DexScreener outliers like +2,002%), h1 corr {fa['h1']['corr']:.2f}, median abs error {fa['h1']['median_abs_err']:.1f} pp |")
w(f"| liquidity | **approximated**: constant-product model 2·√(206.9M·85·p·SOLUSD) × {cal['c_liq']:.3f} (fitted on live) | median error {100*fa['liq_from_candle_price']['median_rel_err']:.1f}%; p10–p90 of the live/model ratio {cal['c_liq_p10_p90'][0]:.2f}–{cal['c_liq_p10_p90'][1]:.2f}. **Blind to third-party LP adds or removes** |")
w("| mint/freeze authority | **recreated** (pump.fun mints are always revoked; +8) | – |")
w("| buy ratio 5m / 1h (6+4 pts), sells≫buys reject | **missing** (needs per-tx side counts) | – |")
w("| unique-buyer growth (12 pts) | **missing** | – |")
w("| top10 % (0–12 pts, >35% reject), insiders (−5), rugged | **missing** | – |")
w("| copycat ticker count (−8) | **missing** (needs the live token set at that time) | – |")
w("| discovery: DexScreener boosts/profiles, Gecko trending, top-25-by-accel health budget | **missing**. The replay scans *every* graduation, the live radar only the ones it discovered | – |")
w("| rugguard: holders, mcap/holder, wash ratio, danger, LP lock, creator %, creator tokens, Scout launch verdict | **missing** | – |")
w("| rugguard: age ≥ 45 min, m5 crash/spike, −6 dip, liq drop ≥ 30% vs scan in 90 min | **recreated** (liq drop goes through the model, i.e. a price drop of about 51%) | – |")
mm = cal["missing_mass"]
w(f"\n**Missing mass.** On live rows, live pre-guard score minus the reconstructable part (computed from the live features) gives a median of {mm['p50']:.1f} pts (p10 {mm['p10']:.1f}, p90 {mm['p90']:.1f}). It correlates {cal['corr_known_vs_missing']:+.2f} with the known part. The known part from candles vs from live features: corr {cal['known_pts_live_vs_replay']['corr']:.2f}, median abs error {cal['known_pts_live_vs_replay']['median_abs_err']:.1f} pts.")
w(f"\n**Imputation** (pre-registered, a constant added to the known part): low = p50 {R['imputations']['low']:.1f}, **central = rate-matched {R['imputations']['central']:.1f}**, high = p90 {R['imputations']['high']:.1f}. Rate-matched means the smallest constant whose replay pass count equals the live pass count ({cal['live_pass_rows']} rows) on the calibration rows.")
c = cal["confusion_rate_matched"]
w(f"Row-level agreement with central: live pass & replay pass {c.get('liveP_repP',0)}, live pass & replay fail {c.get('liveP_repF',0)}, live fail & replay pass {c.get('liveF_repP',0)}, both fail {c.get('liveF_repF',0)}. **So the replay reproduces the pass *rate*, but only about 60% of the individual pass/fail calls.** Treat every result below as a test of a radar-*like* rule, not of the exact live radar.\n")
w("## Results (costs as harness: 2%/side + $0.05/tx, liquidity-scaled slippage on the model liq, gap-through stops, max 3 open, flat 08:00 Dublin)\n")
w(f"Holdout = nights {R['holdout_nights'][0]}…{R['holdout_nights'][-1]} (the last 9 of 28 nights). It was fixed before any result. No rule was tuned on in-sample: the radar rule is scan.py's own, and the SM grid and centre cell (T30/X20/cap100) were pre-registered in survivor_momentum.py. Variants tried after this run: **{R['variants_tried']}**.\n")
w("| variant | cand | closed | IS n | IS net $ | IS mean | OOS n | OOS net $ | OOS mean | OOS CI95 mean | rug % | score /25 | MC dd p95 | nights +/n | lucky |"); w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
board = {r["variant"]: r for r in json.load(open(os.path.join(OUT, "leaderboard_extra_BF.json")))}
order = [k for k in R["cells"] if not k.startswith("BF_SM")] + sorted([k for k in R["cells"] if k.startswith("BF_SM")], key=lambda k: -(R["cells"][k]["score"]["score_total"] or 0))
for k in order:
    c = R["cells"][k]; i, o = c["in"], c["out"]; b = board.get(k, {})
    ci = f"[{100*o['ci_lo']:+.0f}%,{100*o['ci_hi']:+.0f}%]" if o.get("ci_lo") is not None else ""
    w(f"| {k} | {c['n_cand']} | {c['closed']} | {i.get('trades',0)} | {f(i.get('net_pnl'))} | {pct(i.get('mean_ret'))} | {o.get('trades',0)} | {f(o.get('net_pnl'))} | {pct(o.get('mean_ret'))} | {ci} | {(f"{100*float(b['rug_rate']):.0f}%") if b.get('rug_rate') not in ('', None) else ''} | {c['score']['score_total']} | {c['mc_dd'][2]} | {c['nights_profitable']}/{c['nights']} | {b.get('lucky_number','')} |")
import csv as _csv, statistics as _S
TR = [t for t in _csv.DictReader(open(os.path.join(OUT, "bf_trades.csv"))) if t["status"] == "closed"]
ls = cal.get("live_staircase", {})
w("\n## Post-hoc diagnostic: bot 'staircase' pumps (NOT a tested rule)\n")
w("stair20 = the share of up-closing 1-min candles among the 20 before the signal. A staircase pump shows steady up-ticks on flat volume, then one candle of about −99%. It was found by reading the worst trades *after* the results, so any filter built on it is in-sample until a fresh holdout tests it.\n")
w("| variant | stair20 < 0.7: n / mean / ≤−80% | 0.7–0.85 | ≥ 0.85 |"); w("|---|---|---|---|")
for v in [k for k in R["cells"] if not k.startswith("BF_SM")] + ["BF_SM_T30_X20_cap100_LIQMODEL"]:
    cells = []
    for lo, hi in [(0, .7), (.7, .85), (.85, 1.01)]:
        x = [float(t["ret"]) for t in TR if t["variant"] == v and t.get("stair20") and lo <= float(t["stair20"]) < hi]
        cells.append(f"{len(x)} / {100*_S.fmean(x):+.0f}% / {sum(r <= -0.8 for r in x)}" if x else "0")
    w(f"| {v} | " + " | ".join(cells) + " |")
w(f"\nOn live calibration rows, {ls.get('n_rows_stair85')} of {ls.get('n_rows_with_stair')} had stair20 ≥ 0.85. The live (guarded) radar passed {ls.get('live_pass')} of them; most were rejected as 'too young' (the 45-min age guard). Their median top10 ({ls.get('top10_median')}%) is no higher than the median of the other rows ({ls.get('top10_median_nonstair')}%), so the missing top10 input would *not* have removed them.\n")
open(os.path.join(OUT, "backfill_body.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L)[:200])
