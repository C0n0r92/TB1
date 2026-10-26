"""Write out/benji_full_replay.md from data/cr/bj_results.json (PAPER ONLY)."""
import json, os, datetime as dt
LAB = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(LAB, "data/cr/bj_results.json")))
VT = len(json.load(open(os.path.join(LAB, "data/variants_tried.json"))))
LBL = ["_benjitrades", "bystevenr", "onlyzhynx"]; RU = ["A_mirror", "B_ladder", "C_live", "D_old"]; CK = ["self5", "self10", "cf10"]
def g(x, p=2): return "–" if x is None else f"{x:+.{p}f}"
def pc(x): return "–" if x is None else f"{x*100:+.0f}%"
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%m-%d %H:%M")
G = R["grid"]; L = []; w = L.append
def table(lab, cks):
    w("| exit | cost | horizon | filters | n | net $ | ex-best $ | mean | median | win | in-sample n / $ | held-out n / $ (10-15 07Z) | alt last-30% n / $ | score/25 |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for ru in RU:
        for ck in cks:
            for fl in ("full", "flat"):
                for fi in ("all", "filt"):
                    v = G[f"{lab}|{ck}|{fl}|{fi}|{ru}"]
                    if not v.get("n"): w(f"| {ru} | {ck} | {'full' if fl=='full' else '08:00 flat'} | {'on' if fi=='filt' else 'off'} | 0 | | | | | | | | | |"); continue
                    w(f"| {ru} | {ck} | {'full' if fl=='full' else '08:00 flat'} | {'on' if fi=='filt' else 'off'} | {v['n']} | {g(v['total'])} | {g(v['ex_best'])} | {pc(v['mean_ret'])} | {pc(v['med_ret'])} | {v['win']:.0%} | {v['n_is']} / {g(v['is_tot'])} | {v['n_oos']} / {g(v['oos_tot'])} | {v['alt_n_oos']} / {g(v['alt_oos_tot'])} | {v['sc']['score_total']} |")
b = lambda k: G[k]
A = b("_benjitrades|self10|full|filt|A_mirror"); A0 = b("_benjitrades|self10|full|all|A_mirror"); Ac = b("_benjitrades|cf10|full|all|A_mirror"); Af = b("_benjitrades|self10|flat|filt|A_mirror")
O = R["outliers"]["_benjitrades"]; si = O[0]
Ld = R["leader"]["_benjitrades"]
w("# Benji full-horizon copy replay (PAPER / BACKTEST ONLY)")
w(f"_Lab, {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%MZ}. Script: bj_full_replay.py + bj_report.py. Data: data/cr/win + data/cr/wcandles (on-chain fills from free public RPC, GeckoTerminal candles). No Scout/Helius credits, no X reads. This supersedes the winners section in out/.cr_win_section.md, which is kept. That section had stale coverage and only SELF fitted costs. variants_tried after merge: **{VT}**._")
w("")
w("## Answer")
w(f"**Mostly no.** Mirroring his sells catches his biggest outlier only when we hold the full horizon with **no stop and no 08:00 flat**. Even then the result is not usable:")
w(f"- **SI (+595 SOL to him).** He built that position from {si['n_buys']} buys over {float(si['hold'])/1440:.1f} days. A copy of his first buy with pure mirror and full horizon makes **{pc(si['cells']['A_mirror|0'][0])}**. With the 08:00 Dublin flat it makes **{pc(si['cells']['A_mirror|1'][0])}**, and every stop rule (B, C, D) is stopped out first at about −17% to −27%.")
w("- **CRAWL 10-04 (+90 SOL).** Captured by mirror (A +116%) and by old rule D (+108%). Ladder B only gets +33% (BE stop after TP1), and live rule C is stopped out at −17%. The other two SI outliers (+37 and +33 SOL) are lost or small under every rule.")
w(f"- **All of benji's covered trips after costs, filters off.** Mirror loses: n={A0['n']}, self $10 {g(A0['total'])} $, copyfomo $10 {g(Ac['total'])} $, median trade {pc(A0['med_ret'])}. Every other rule loses too.")
w(f"- **With live entry filters on, he leaves n={A['n']}, all in-sample.** Mirror at full horizon makes {g(A['total'])} $ at self $10, but without the best trade it is {g(A['ex_best'])} $. That is SI by itself. With the 08:00 flat it falls to {g(Af['total'])} $. The pre-registered hold-out has **0** benji trades, so this is not tested out of sample, and the METHOD score is {A['sc']['score_total']}/25 (needs ≥18 and n ≥50).")
w(f"- **His own record has the same shape.** Scout's net5 for these {Ld['n']} trips is {Ld['net5']:+.0f} SOL, but without the best trade it is **{Ld['ex_best']:+.0f} SOL**. His record after the hold-out date is {Ld['net5_oos']:+.1f} SOL on {Ld['n_oos']} trips. Copying him is effectively a bet that another SI happens and that we hold it without a stop or a night flat.")
w("- **No exit family is a candidate for any of the three leaders.** onlyzhynx and bystevenr are positive in-sample only because of 1–2 outliers we could not have filtered for: none of onlyzhynx's trades pass the live filters, and only 1–2 of bystevenr's do. Held-out results are negative or flat.")
w("")
w("## Coverage and setup")
w("| leader | Scout trips | simulated | no candles | pass live filters | his pre-held bag at entry | drift clamped/missing → median | priced off his own fill (no pool decode) | held-out (≥10-15 07Z) | fails: age / mcap / liq / chase |")
w("|---|---|---|---|---|---|---|---|---|---|")
for lab in LBL:
    c = R["cov"][lab]; f = c["fail_reasons"]
    w(f"| {lab} | {R['leader'][lab]['n']} | {c.get('ok',0)} | {c.get('no_candles',0)} | {c['pass_filters']} | {c['pre_bal_gt0']} | {c['drift_clamped']} | {c['synthetic_px']} | {c['n_oos_fixed']} | {f.get('age',0)} / {f.get('mcap',0)} / {f.get('liq',0)} / {f.get('chase',0)} |")
w("")
w("**Entry**")
w("- We copy the buy where Scout's round trip starts, 5 s after his fill. Fill price is his measured 5 s pool drift; anything missing or outside 0.75–1.33 is clamped to his median (benji buy ×1.000, sell ×0.978). Later buys he makes are **not** copied.")
w("- Live filters: token age ≥60 min and mcap ≥$1M (Scout's entry-time fields), pool liquidity ≥$100k (decoded on chain; trades priced off his own fill fail this), and chase ≤8% (our 5 s mid vs his fill).")
w("")
w("**Costs (round trip + liquidity-scaled impact)**")
w("- self $5 = 4.7%, self $10 = 3.0%, copyfomo $10 = 5.3%. Impact is fitted from out/copy_fee_sensitivity and decays as √(price/entry); pump.fun curve impact is used on the curve.")
w("- Each extra sell leg adds $0.02 (self) or $0.015 (copyfomo).")
w(f"- The realized entry round trip comes out at those figures. Median benji self $5 / $10 / copyfomo: {R['rt0']['_benjitrades|self5']['med']:.1%} / {R['rt0']['_benjitrades|self10']['med']:.1%} / {R['rt0']['_benjitrades|cf10']['med']:.1%}. Impact at $5–10 into ≥$100k pools is close to zero. The cost that matters is the 5 s delay and the stop slippage: stops fill at the bar open on a gap, otherwise at trigger ×0.975.")
w("")
w("**Exit rules** (triggers on marked value net of exit cost)")
w("- (a) **A_mirror**: sell his sell fraction of our position, all of it once he sells ≥95%. No stop.")
w("- (b) **B_ladder**: TP +40% sells 25% and +100% sells 25%, the rest at +500%; breakeven stop after TP1; −20% hard stop, as in the earlier ladder tests.")
w("- (c) **C_live**: SL −15%; TP +50% sells half; then a 15% trail from the peak on the rest.")
w("- (d) **D_old**: SL −25%; TP +100% sells half; mirror his sells on the rest.")
w("- Horizon is min(his exit + 24 h, entry + 7 d). The 08:00 variant flattens at the next 08:00 Dublin.")
w("")
w("**Hold-out**")
w("- Primary: fixed 2026-10-15 07:00 UTC, chosen before any CR result (the last 9 of 30 Dublin nights).")
w("- Secondary, not pre-registered: each leader's last 30% of covered entries by time (benji from 10-02 04Z).")
w("- Both are **selection-contaminated**: Scout picked these wallets because of these trades.")
w("")
w("## Outliers: what each rule kept (self $10, % of stake)")
w("| leader | token | entry UTC | his net5 SOL | his buys | passes filters | A mirror full | A mirror 08:00 | B ladder | C live | D old |")
w("|---|---|---|---|---|---|---|---|---|---|---|")
for lab in LBL:
    for x in R["outliers"][lab][:4]:
        c = x["cells"]
        f = lambda k: f"{pc(c[k][0])} ({c[k][1]})" if c[k][0] is not None else c[k][1]
        w(f"| {lab} | {x['sym']} | {iso(x['t'])} | {x['sol']:+.1f} | {x['n_buys']} | {'yes' if x['passes'] else 'no'} | {f('A_mirror|0')} | {f('A_mirror|1')} | {f('B_ladder|0')} | {f('C_live|0')} | {f('D_old|0')} |")
w("")
w("The 08:00 flat column is shown for A only. B, C and D are almost always stopped out before 08:00, so their flat and full results are the same.")
w("")
w("## _benjitrades: full grid ($ PnL; self $5 rows on a $5 stake)")
table("_benjitrades", CK)
w("")
w("## bystevenr")
table("bystevenr", ["self10", "cf10"])
w("")
w("## onlyzhynx (no trade passes the live filters)")
table("onlyzhynx", ["self10", "cf10"])
w("")
w("The full self $5 grid for bystevenr and onlyzhynx is in data/cr/bj_results.json. All 144 configurations are in leaderboard.csv as CR_BJ_* (rows with n=0 are omitted).")
w("")
sc = A["sc"]; sc0 = A0["sc"]
w("## METHOD score (25-point)")
w("| row | OOS risk | drawdown | trades | edge | stability | total | nights + / all |")
w("|---|---|---|---|---|---|---|---|")
for nm, v in (("benji A_mirror self$10 full, filters ON (best-looking)", A), ("benji A_mirror self$10 full, filters OFF", A0), ("benji C_live (live rule) self$10, filters ON", b("_benjitrades|self10|full|filt|C_live")), ("onlyzhynx C_live self$10 full (highest any-leader total)", b("onlyzhynx|self10|full|all|C_live"))):
    s = v["sc"]; w(f"| {nm} | {s['sc_oos_risk']} | {s['sc_drawdown']} | {s['sc_trades']} | {s['sc_edge']} | {s['sc_stability']} | **{s['score_total']}** | {s['nights_profitable']}/{s['nights']} |")
w("")
w("Nothing reaches 18/25. Nothing has ≥50 trades or ≥20 held-out trades. **No candidate.**")
w("")
w("## WHY THIS COULD FAIL")
w("- **One trade is the whole result.** Benji's own +550 SOL is −45 SOL without SI. The only positive benji copy row loses money once SI is removed. Any rule that might miss the next SI (a stop, a night flat, a filter, a late entry) turns the strategy negative. A no-stop mirror also takes the full loss on every rug.")
w("- **Selection bias.** Scout chose these three wallets because of these trades, so every \"in-sample\" number here is inflated by construction. The fixed hold-out has 1 benji trade (0 with filters on). After the hold-out date, his own record is negative (−25 SOL on 2 trips) and so are onlyzhynx's (−64 SOL) and bystevenr's (−20 SOL).")
w("- **We don't copy his averaging.** SI came from 29 buys over 3.9 days. Copying only his first buy sizes us the opposite way to him: small when he is most confident. A model that copies his adds is untested.")
w("- **Price path.** GT 1-min, then 15-min candles of one pool are rescaled to our fill. Fills of 21 of 31 benji trades use his median drift, and 6 trades are priced off his own fill (no pool decode). Stop fills on 15-min bars after the first day are coarse, so a stop and a TP inside one bar resolve stop-first.")
w("- **Four trips have no candles** (benji PUMPERS, bystevenr UP×2, onlyzhynx Minibot; GT has no pool data for them. A GT retry recovered buni and Cardback). They are excluded rather than marked as losses, which probably biases the results up.")
w("- **Costs are the team's stated round-trip figures, not fills we measured on these tokens.** The 5 s delay is assumed: copyfomo is often slower, and Chunk reports 3-min entry windows being missed.")
w("- **Who is on the other side.** On SI and CRAWL, he is often the size that moves price, and our copy buys right behind him. When he takes profit, followers like us are the exit liquidity, and our 5 s-later sell fills below his print (sell drift ×0.978). On the losers, the other side is the deployer and early holders.")
w("")
w("## Next")
w("- Deprioritize copying benji as a strategy. If anything, run a paper-forward log of his *new* trips after 10-24 with mirror and no flat, and score it only once there are ≥20 trips.")
w("- Untested: copying his adds (DCA-mirror) at a capped size. That is the only mechanism that could have captured SI, and a forward test is the only clean way to check it.")
open(os.path.join(LAB, "out/benji_full_replay.md"), "w").write("\n".join(L) + "\n"); print("ok", len(L))
