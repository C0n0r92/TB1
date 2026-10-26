#!/usr/bin/env python3
"""Fee sensitivity of the copy sims (PAPER ONLY, no network, research only; Zero 2026-10-23 late).
Same copy rules as copy_candidates.py (first buy per coin, leader buy >= $50, mcap >= $100k, TP +100% sells half, SL -25%,
max chase 15%, remainder exits with the leader), $5 per copy, 4 leaders. Two cost models:
  REF  = copyfomo as in copy_candidates.py (central): 2%/side service fee, $0.015/side gas billed back, slippage 0.5% + 2 x stake/$20k,
         stop fills 2.5% below the trigger, 10 s copy lag (approx mode: +2% entry drift), exit at the leader's sell price.
  JUP  = self-run Jupiter copier: 0.30%/side explicit swap fee (pool LP fee ~0.25% + route; Jupiter Metis/swap API platform fee 0),
         per-tx cost = priority fee P (swept $0.005/$0.02/$0.05) + $0.0005 base fee, one tx per buy and per sell leg (TP adds a leg),
         ATA rent assumed refunded on close; slippage = harness model 0.5% + 2 x stake / liq(mcap) with
         liq(mcap) = 0.41 * sqrt($70k * mcap) (constant-product pool seeded with ~20.6% of a pump.fun supply at ~$70k graduation);
         copy delay 2 s or 5 s: approx-mode entry drift = 2% x delay/10 s (central) and the same adverse drift on the exit
         (we sell after the leader); path mode (1-min candles) interpolates the candle at t+delay. Stop fills 2.5% below trigger.
  JUP pessimistic band: liq/2, base slip 1.0%/side, drift = full 2% on entry AND exit regardless of delay, fee 0.5%/side, P = $0.05.
Writes out/copy_fee_sensitivity.md, out/leaderboard_extra_FS.json (rows FS_*)."""
import json, math, os, random, statistics, sys, time
import copy_candidates as cc
import scoring
from labcore import LAB, iso, atomic_write

LEADERS = ["_benjitrades", "bystevenr", "pointfarmcap", "ExactTallTakin"]
STAKE, BAL = 5.0, 91.0

def model(name, **kw):
    m = dict(name=name, fee=0.02, fixed_entry=0.015, fixed_leg=0.015, fixed_extra_leg=False, liq_fn=lambda mc: 20_000, base_slip=0.005,
             sl_slip=0.025, delay=10, drift_in=0.02, drift_out=0.0)
    m.update(kw); return m

def jliq(mc, k=1.0): return k * 0.41 * math.sqrt(70_000 * max(mc or 100_000, 1))

def jup(delay, prio, pess=False):
    if pess:
        return model(f"JUP_{delay}s_P{prio:.3f}_pess", fee=0.005, fixed_entry=prio + 0.0005, fixed_leg=prio + 0.0005, fixed_extra_leg=True,
                     liq_fn=lambda mc: jliq(mc, 0.5), base_slip=0.01, delay=delay, drift_in=0.02, drift_out=0.02)
    d = 0.02 * delay / 10
    return model(f"JUP_{delay}s_P{prio:.3f}", fee=0.003, fixed_entry=prio + 0.0005, fixed_leg=prio + 0.0005, fixed_extra_leg=True,
                 liq_fn=jliq, base_slip=0.005, delay=delay, drift_in=d, drift_out=d)

REF = model("REF_copyfomo")

def sim(tr, M):
    S = cc.S
    if tr["usd"] < S["min_buy_usd"]: return {"status": "skip_small_buy"}
    if tr["ret"] is None: return {"status": "open_leader"}
    c = cc.candles(tr["mint"], tr["t"]); sup = cc.supply(tr["mint"]); fl = []
    p_l = cc.price_at(c, tr["t"]) if c else None
    ref = tr["lf"] or p_l
    if c and tr["lf"] and p_l and abs(p_l / tr["lf"] - 1) > 0.3: c, p_l = [], None
    mcap = ref * sup if (ref and sup) else None
    if mcap is not None and mcap < S["min_mcap"]: return {"status": "skip_mcap"}
    liq = M["liq_fn"](mcap)
    s = min(S["max_slip"], M["base_slip"] + S["impact"] * STAKE / liq)
    fee, d = M["fee"], M["delay"]
    if c and ref and cc.price_at(c, tr["t"] + d):
        mode = "path"; p_e = cc.price_at(c, tr["t"] + d)
        if p_e / ref - 1 > S["chase"]: return {"status": "skip_chase"}
        entry = p_e * (1 + s); exit_lead = ref * (1 + tr["ret"]) * (1 - M["drift_out"])
        tp_px, sl_px = entry * (1 + S["tp"]), entry * (1 + S["sl"]); legs, rem, t_out = [], 1.0, tr["t_exit"]
        for x in c:
            if x[0] + 60 <= tr["t"] + d or x[0] >= tr["t_exit"]: continue
            first = x[0] <= tr["t"] + d
            lo, hi, o = (x[4], x[4], p_e) if first else (x[3], x[2], x[1])
            if lo <= sl_px:
                px = o * (1 - M["sl_slip"]) if (o <= sl_px and not first) else sl_px * (1 - M["sl_slip"])
                legs.append((rem, px)); rem = 0; t_out = x[0] + 60; break
            if rem == 1.0 and hi >= tp_px:
                legs.append((S["tp_frac"], max(tp_px, o) if not first else tp_px)); rem -= S["tp_frac"]
        if rem: legs.append((rem, exit_lead))
    else:
        mode = "approx"; ref = ref or 1.0
        entry = ref * (1 + M["drift_in"]) * (1 + s); exit_lead = ref * (1 + tr["ret"]) * (1 - M["drift_out"]); r_l = exit_lead / entry - 1
        if r_l <= -0.8: legs = [(1.0, exit_lead)]
        elif r_l < S["sl"]: legs = [(1.0, entry * (1 + S["sl"]) * (1 - M["sl_slip"]))]
        elif r_l >= S["tp"]: legs = [(S["tp_frac"], entry * (1 + S["tp"])), (1 - S["tp_frac"], exit_lead)]
        else: legs = [(1.0, exit_lead)]
        t_out = tr["t_exit"]
    fx_in = M["fixed_entry"] / STAKE
    gross_in = (1 - fee) - fx_in
    n_legs = len(legs) if M["fixed_extra_leg"] else 1
    cash = sum(f * gross_in * px * (1 - s) / entry * (1 - fee) for f, px in legs) - n_legs * M["fixed_leg"] / STAKE
    return {"status": "closed", "ret": max(cash, 0) - 1, "t": tr["t"], "t_exit": t_out, "mode": mode, "mcap": mcap, "liq": liq, "slip": s}

def boot_ci(x, n=5000, seed=7):
    if len(x) < 2: return (x[0], x[0]) if x else (None, None)
    r = random.Random(seed); ms = sorted(statistics.fmean(r.choices(x, k=len(x))) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]

def evaluate(trs, M, split):
    out = {}
    for name in LEADERS:
        rs = [dict(sim(t, M), tr=t) for t in trs if t["trader"] == name]
        cl = sorted([r for r in rs if r["status"] == "closed"], key=lambda r: r["t"])
        pn = [r["ret"] * STAKE for r in cl]
        closed = [{"t": r["t"], "pnl": p, "ret": r["ret"], "is_oos": r["t"] >= split} for r, p in zip(cl, pn)]
        st = cc.stats([r["ret"] for r in cl])
        lo, hi = boot_ci(pn)
        mc = scoring.mc_drawdown(pn, BAL, 1000) if pn else None
        if st["trades"] > 1: st["ci_lo"] = lo / STAKE           # METHOD edge=5 needs bootstrap CI low > 0
        sc = scoring.score(st, None, closed, mc)
        oos = [c["pnl"] for c in closed if c["is_oos"]]; ins = [c["pnl"] for c in closed if not c["is_oos"]]
        ni = scoring.nights(closed)
        sk = {}
        for r in rs: sk[r["status"]] = sk.get(r["status"], 0) + 1
        out[name] = dict(n=len(cl), mean=statistics.fmean(pn) if pn else None, median=statistics.median(pn) if pn else None,
                         total=sum(pn), ex_best=sum(pn) - max(pn) if pn else 0, ci=(lo, hi), mc=mc, sc=sc, nights=ni,
                         oos_n=len(oos), oos_mean=statistics.fmean(oos) if oos else None, in_net=sum(ins), out_net=sum(oos),
                         win=sum(p > 0 for p in pn) / len(pn) if pn else 0, skips=sk, path=sum(r["mode"] == "path" for r in cl),
                         pn=pn, closed=closed, cl=cl)
    return out

def main():
    trs, _ = cc.load_trades()
    split = sorted(t["t"] for t in trs)[int(len(trs) * 0.6)]       # same global split as copy_candidates.py
    models = [REF] + [jup(d, p) for d in (2, 5) for p in (0.005, 0.02, 0.05)] + [jup(d, 0.05, pess=True) for d in (2, 5)]
    # like-for-like: Jupiter costs but the REF delay/drift treatment (10 s, entry drift 2%, no exit drift)
    models.append(model("JUP_feesonly_10s_refdrift", fee=0.003, fixed_entry=0.0205, fixed_leg=0.0205, fixed_extra_leg=True, liq_fn=jliq, delay=10, drift_in=0.02, drift_out=0.0))
    # upper bound: a free, instant copier (no fees, no slippage, no drift, no gas); stop still fills 2.5% below trigger
    models.append(model("ZERO_cost_bound", fee=0.0, fixed_entry=0.0, fixed_leg=0.0, liq_fn=lambda mc: 1e12, base_slip=0.0, delay=0, drift_in=0.0, drift_out=0.0))
    R = {M["name"]: evaluate(trs, M, split) for M in models}
    head = "JUP_2s_P0.020"; alt = "JUP_5s_P0.020"
    f2 = lambda v: "-" if v is None else f"{v:+.2f}"
    pc = lambda v: "-" if v is None else f"{v*100:+.1f}%"
    L = [f"# Copy fee sensitivity: copyfomo vs a self-run Jupiter copier ({iso(time.time())}, PAPER ONLY, research only)", "",
         "Question (Zero): replacing copyfomo's ~5.3% round trip with a self-run Jupiter copier, which leaders turn profitable, and by how much per $5 copy?", "",
         "## Short answer", ""]
    ans = []
    for n in LEADERS:
        a, b, p = R["REF_copyfomo"][n], R[head][n], R["JUP_5s_P0.050_pess"][n]
        flip = (a["total"] <= 0 < b["total"])
        ans.append(f"- **{n}** ({a['n']} copies): copyfomo {f2(a['mean'])}/copy (median {f2(a['median'])}, total {f2(a['total'])}) -> Jupiter 2 s {f2(b['mean'])}/copy "
                   f"(median {f2(b['median'])}, total {f2(b['total'])}); pessimistic band {f2(p['mean'])}/copy. "
                   + ("FLIPS to profitable on the mean" if flip else ("already positive under copyfomo" if a["total"] > 0 else "stays negative")) +
                   f"; without the best copy: {f2(b['ex_best'])} (Jupiter) vs {f2(a['ex_best'])} (copyfomo). Score {a['sc']['score_total']} -> {b['sc']['score_total']}/25.")
    L += ans + [""]
    L += ["## Cost assumptions", "",
          "| model | explicit fee/side | per-tx fixed | slippage | delay / drift | stop fill |", "|---|---|---|---|---|---|",
          "| REF copyfomo (unchanged from copy_candidates.py central) | 2.0% | $0.015/side (=$0.03 gas per round trip) | 0.5% + 2 x $5/$20k assumed pool | 10 s; approx mode +2% entry drift; exit at leader's sell price | 2.5% below -25% trigger |",
          "| JUP central | 0.30% (pool LP ~0.25% + route; Jupiter swap API platform fee 0) | priority fee P + $0.0005 base, per tx (buy, TP leg, final sell) | 0.5% + 2 x $5 / liq(mcap), liq = 0.41 x sqrt($70k x mcap) | 2 s or 5 s; approx mode drift 2% x delay/10 s on entry AND exit | 2.5% below trigger |",
          "| JUP pessimistic | 0.50% | $0.0505 per tx | 1.0% + 2 x $5 / (liq/2) | full 2% adverse drift on entry and exit | 2.5% below trigger |", "",
          f"Round trip at $5 (approx, no TP leg): REF ~ 4% fees + 1.0% slip + $0.03/$5 (0.6%) + 2% drift = ~7.6% incl. lag; "
          f"JUP 2 s P=$0.02 ~ 0.6% fees + ~1.0% slip + $0.041/$5 (0.8%) + 0.8% drift = ~3.2%; JUP 5 s ~ 4.4%; JUP pessimistic ~ 1.0% + 2.0% + 2.0% + 4.0% = ~9%. "
          "Impact of a $5 ticket is ~0.03% at $100k mcap, so the size term is negligible; the base slip and the delay drift dominate.", "",
          "Why liq(mcap): no point-in-time liquidity exists for these leader trades. A pump.fun coin graduates to a constant-product pool holding ~20.6% of supply "
          "at ~$70k mcap (liq ~ 0.41 x mcap); as price rises the pool's token share falls with 1/sqrt(price), giving liq ~ 0.41 x sqrt(70k x mcap): ~$34k at $100k, ~$77k at $500k, "
          "~$108k at $1M. Non-pump pools and LP pulls break this, hence the liq/2 band.", "",
          "Delay pricing: Zero asked to price entry/exit from the next swaps after the delay. That needs the pool's swaps a few slots after the leader's tx. "
          "Free sources tried: api.mainnet-beta.solana.com returned 429 (rate-limited, shared IP), solana-rpc.publicnode.com returns null for month-old transactions, "
          "GeckoTerminal /trades only keeps the last 24 h. So: trades with cached 1-min candles (8 of the copies; data/copytest/candles) use the candle interpolated at t+delay "
          "(1-min resolution cannot really separate 2 s from 5 s); the rest use the drift assumption above. This is the weakest assumption in the file: "
          "the pessimistic band (2% drift even at 2 s) is there because 686/291/52 copyfomo copiers and sniper bots race the same buy within the same slot.", ""]
    L += ["## Per leader, per model ($5 per copy, bootstrap = 5,000 resamples of the per-copy $, seed 7; MC DD on $91)", "",
          "| leader | model | copies | win | mean $/copy | median $/copy | total $ | ex-best $ | bootstrap 95% CI of mean $ | nights +/total | OOS n / mean $ | MC DD p95 | score /25 (oos,dd,n,edge,stab) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in LEADERS:
        for mn in ["REF_copyfomo", "JUP_feesonly_10s_refdrift"] + [m["name"] for m in models if m["name"].startswith("JUP_") and m["name"] != "JUP_feesonly_10s_refdrift"] + ["ZERO_cost_bound"]:
            b = R[mn][n]; s = b["sc"]
            L.append(f"| {n} | {mn} | {b['n']} | {b['win']:.0%} | {f2(b['mean'])} | {f2(b['median'])} | {f2(b['total'])} | {f2(b['ex_best'])} | "
                     f"[{f2(b['ci'][0])}, {f2(b['ci'][1])}] | {s['nights_profitable']}/{s['nights']} | {b['oos_n']} / {f2(b['oos_mean'])} | "
                     f"{b['mc'][2]*100:.0f}% | {s['score_total']} ({s['sc_oos_risk']},{s['sc_drawdown']},{s['sc_trades']},{s['sc_edge']},{s['sc_stability']}) |")
    L += ["", "## Split by night (Dublin), $ per night: REF copyfomo vs JUP 2 s P=$0.02", ""]
    for n in LEADERS:
        a, b = R["REF_copyfomo"][n]["nights"], R[head][n]["nights"]
        L.append(f"- **{n}**: " + ", ".join(f"{k[5:]} {a.get(k, 0):+.2f}/{b.get(k, 0):+.2f}" for k in sorted(set(a) | set(b))))
    L += ["", "## How much of the drag is fees? (mean $/copy uplift vs REF)", "", "| leader | REF mean | JUP fees only (REF drift) | JUP 2 s P$0.005 | JUP 2 s P$0.05 | JUP 5 s P$0.02 | JUP pess. | ZERO-cost bound | ZERO-cost median |", "|---|---|---|---|---|---|---|---|---|"]
    for n in LEADERS:
        g = lambda m: R[m][n]["mean"]
        L.append(f"| {n} | {f2(g('REF_copyfomo'))} | {f2(g('JUP_feesonly_10s_refdrift'))} | {f2(g('JUP_2s_P0.005'))} | {f2(g('JUP_2s_P0.050'))} | {f2(g('JUP_5s_P0.020'))} | {f2(g('JUP_5s_P0.050_pess'))} | {f2(g('ZERO_cost_bound'))} | {f2(R['ZERO_cost_bound'][n]['median'])} |")
    # lottery check
    L += ["", "Reading: the pessimistic band ignores the delay (2% drift at 2 s and 5 s alike), so its 2 s and 5 s rows are equal by construction. "
          "ZERO-cost = no fee, no slippage, no drift, no gas, instant copy: the most any copier could get from these leaders with these rules. "
          "If a leader loses even there, cheaper execution cannot rescue them.",
          "Bootstrap caution: bystevenr's CI excludes 0 only because one +3,300% copy dominates every resample that contains it; it is not a robust edge (median copy < 0)."]
    L += ["", "## Lottery-ticket check (Jupiter 2 s, P=$0.02)", ""]
    for n in LEADERS:
        b = R[head][n]; srt = sorted(b["pn"], reverse=True)
        L.append(f"- {n}: top 3 copies {', '.join(f'{x:+.2f}' for x in srt[:3])} of total {f2(b['total'])}; without top 3: {f2(sum(srt[3:]))}; "
                 f"share of copies losing: {sum(x < 0 for x in b['pn'])}/{b['n']}; path-mode (1-min candles) copies: {b['path']}.")
    L += ["", "## Candidate check (METHOD: >= 18/25, >= 50 trades, holds OOS with >= 20 OOS trades and OOS CI low > 0)", ""]
    for n in LEADERS:
        b = R[head][n]
        L.append(f"- {n}: {b['sc']['score_total']}/25, {b['n']} copies, OOS {b['oos_n']} -> {'CANDIDATE' if b['sc']['score_total'] >= 18 and b['n'] >= 50 and b['oos_n'] >= 20 else 'not a candidate'}"
                 f"{' (fails trade count)' if b['n'] < 50 else ''}{' (fails OOS count)' if b['oos_n'] < 20 else ''}.")
    L += ["", "## WHY THIS COULD FAIL", "",
          "- The leaders' histories are Scout's reconstruction from wallets whose mapping is LOW confidence for _benjitrades and bystevenr (medium-low pointfarmcap, medium ExactTallTakin). "
          "_benjitrades' live TRUTH buy came from a wallet we don't have, so his file is not his full trading.",
          "- Partial coverage: bystevenr from Oct 8, pointfarmcap only Oct 16-21 (8 copies). 22 of bystevenr's and 8 of pointfarmcap's first buys are still open and excluded.",
          "- Most copies are approx mode (no price path): TP/SL hits are inferred from the leader's round trip; intratrade stop-outs before a recovery are invisible, which flatters leaders who hold through dips.",
          "- The delay drift is assumed, not measured (see 'Delay pricing'). If bots front-run the leader in the same slot, a 2 s copier pays the pessimistic band, not the central one.",
          "- A self-run copier needs its own infra (RPC/websocket, signing, key management, retries) and fails differently from copyfomo: missed txs, failed swaps in congestion, stuck partial fills. None of that is modelled. Running it would be a live-trading change: proposal only, not tested here.",
          "- Means are carried by 1-3 lottery coins; medians tell the typical copy.", "",
          "Who is on the other side: the leader (sells into followers), the snipers/bundlers who bought before the leader, and the other copy bots and copyfomo's own copiers racing the same buy. "
          "Lower fees don't change who we trade against; a faster copier only moves us up that queue.", "",
          f"Multiple testing: {len(models)} cost/delay models x 4 leaders added to the variants count (rows FS_*)."]
    p = os.path.join(LAB, "out/copy_fee_sensitivity.md"); atomic_write(p, "\n".join(L) + "\n")
    # leaderboard rows
    rows = []
    for mn, short in [("REF_copyfomo", "ref"), ("JUP_2s_P0.020", "jup2s"), ("JUP_5s_P0.020", "jup5s"), ("JUP_5s_P0.050_pess", "juppess")]:
        for n in LEADERS:
            b = R[mn][n]; s = b["sc"]; cl = b["closed"]
            oos = [c["ret"] for c in cl if c["is_oos"]]
            rows.append({"variant": f"FS_{n}_{short}", "trades": b["n"], "win_rate": round(b["win"], 3), "net_profit_after_costs": round(b["total"], 2),
                         "max_drawdown": round(cc.maxdd(b["pn"]), 2), "holds_out_of_sample": f"insufficient (n_out={b['oos_n']}<20)" if b["oos_n"] < 20 else
                         ("yes" if b["in_net"] > 0 and (b["oos_mean"] or 0) > 0 and boot_ci([c['pnl'] for c in cl if c['is_oos']])[0] > 0 else "no"),
                         "n_in_sample": b["n"] - b["oos_n"], "n_out_of_sample": b["oos_n"],
                         "mean_ret": round(b["mean"] / STAKE, 3) if b["mean"] is not None else "", "median_ret": round(b["median"] / STAKE, 3) if b["median"] is not None else "",
                         "ci95_mean_ret": f"[{b['ci'][0]/STAKE:+.2f},{b['ci'][1]/STAKE:+.2f}]" if b["ci"][0] is not None else "",
                         "oos_mean_ret": round(statistics.fmean(oos), 3) if oos else "", "in_net_pnl": round(b["in_net"], 2), "out_net_pnl": round(b["out_net"], 2),
                         **{k: s[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                         "net_ex_best_trade": round(b["ex_best"], 2), "mc_dd_p5": round(b["mc"][0], 3), "mc_dd_p50": round(b["mc"][1], 3), "mc_dd_p95": round(b["mc"][2], 3),
                         "nights": s["nights"], "nights_profitable": s["nights_profitable"],
                         "candidate": "yes" if s["score_total"] >= 18 and b["n"] >= 50 and b["oos_n"] >= 20 else "no", "lucky_number": "n/a (cost sweep)",
                         "family": "copy_fee_sensitivity", "note": f"PAPER copy sim $5/copy, model {mn}; see out/copy_fee_sensitivity.md"})
    ms = [{k: v for k, v in m.items() if k != "liq_fn"} for m in models]
    json.dump({"rows": rows, "models": ms, "variant_configs": [dict(m, family="copy_fee_sensitivity", leader=l, name=f"FS_{l}_{m['name']}") for m in ms for l in LEADERS]}, open(os.path.join(LAB, "out/.fs_rows.json"), "w"), indent=0)
    print(f"wrote {p}; {len(rows)} rows staged")

if __name__ == "__main__":
    main()
