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
    liq = M["liq_fn"](mcap); stake = M.get("stake", STAKE)
    if M.get("cost_fn"): s = min(S["max_slip"], M["cost_fn"](liq, stake))       # calibrated per-side cost from Jupiter quotes
    else: s = min(S["max_slip"], M["base_slip"] + S["impact"] * stake / liq)
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
    if M.get("prio_sol") is not None:                                      # per-tx SOL cost at the SOL price of the time
        tx = (M["prio_sol"] + 5e-6) * solpx(tr["t"]); fx_e, fx_l = tx, tx
    else: fx_e, fx_l = M["fixed_entry"], M["fixed_leg"]
    fx_in = fx_e / stake
    gross_in = (1 - fee) - fx_in
    n_legs = len(legs) if M["fixed_extra_leg"] else 1
    cash = sum(f * gross_in * px * (1 - s) / entry * (1 - fee) for f, px in legs) - n_legs * fx_l / stake
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
        stake = M.get("stake", STAKE)
        pn = [r["ret"] * stake for r in cl]
        closed = [{"t": r["t"], "pnl": p, "ret": r["ret"], "is_oos": r["t"] >= split} for r, p in zip(cl, pn)]
        st = cc.stats([r["ret"] for r in cl])
        lo, hi = boot_ci(pn)
        mc = scoring.mc_drawdown(pn, BAL, 1000) if pn else None
        if st["trades"] > 1: st["ci_lo"] = lo / stake           # METHOD edge=5 needs bootstrap CI low > 0
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


# ---------- v2 (Zero correction 2026-10-23 23:22): quote-calibrated self-copier ----------
_SOL = None
def solpx(t):
    """SOL/USD at time t from the hourly Orca SOL/USDC candles fetched for the mid-cap study (data/midcap/ohlcv/rows_SOL.json)."""
    global _SOL
    if _SOL is None:
        r = json.load(open(os.path.join(LAB, "data/midcap/ohlcv/rows_SOL.json"))); _SOL = sorted((x[0], x[4]) for x in r)
    import bisect
    k = bisect.bisect_right([a for a, _ in _SOL], t) - 1
    return _SOL[max(k, 0)][1]

def load_quotes():
    Q = [json.loads(l) for l in open(os.path.join(LAB, "data/fs_quotes/quotes.jsonl")) if l.strip()]
    Q = [q for q in Q if q.get("rt_loss") is not None and q.get("liq")]
    # the one real self-copy dry-run fill (selfcopy/dryrun-paper-trades.jsonl, read-only): $5 at liq $11,930, $4.8696 back before priority fees
    Q.append({"sym": "selfcopy_dryrun", "mint": "dryrun", "liq": 11930.0, "mcap": 22031.0, "size": 5, "rt_loss": 1 - 4.8696 / 5, "route_b": "Pump.fun Amm", "route_s": "Pump.fun Amm", "platform_fee": [None, None]})
    for q in Q:
        q["imp_sum"] = (q["buy_impact"] + q["sell_impact"]) if (q.get("buy_impact") is not None and q.get("sell_impact") is not None and q["buy_impact"] + q["sell_impact"] < 0.2) else None   # drops Moustache's broken 85% priceImpactPct
    return Q

def ols(X, y):
    import numpy as np
    X = np.asarray(X, float); y = np.asarray(y, float); b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b; return b, float((r ** 2).sum())

def fit_cost(Q, nboot=2000, seed=11, ykey="rt_loss"):
    """Round-trip quote loss rt = A + C*log10(liq/1e5) + B*(size/liq). Per side = rt/2. Pool-level bootstrap for uncertainty."""
    import numpy as np
    def design(qs, form):
        if form == "flat": return [[1.0] for q in qs]
        if form == "size": return [[1.0, q["size"] / q["liq"]] for q in qs]
        if form == "logliq": return [[1.0, math.log10(q["liq"] / 1e5)] for q in qs]
        return [[1.0, math.log10(q["liq"] / 1e5), q["size"] / q["liq"]] for q in qs]
    Q = [q for q in Q if q.get(ykey) is not None]
    y = [q[ykey] for q in Q]; n = len(Q); res = {}
    for form in ("flat", "size", "logliq", "logliq+size"):
        b, sse = ols(design(Q, form), y); k = len(b)
        res[form] = dict(coef=[float(v) for v in b], sse=sse, aic=n * math.log(max(sse, 1e-12) / n) + 2 * k, rmse=math.sqrt(sse / n))
    ok = [f for f in res if not (f.endswith("size") and res[f]["coef"][-1] < 0)]   # a negative size slope is unphysical (noise): excluded
    best = min(ok, key=lambda f: res[f]["aic"])
    mints = sorted(set(q["mint"] for q in Q)); rnd = random.Random(seed); boots = []
    for _ in range(nboot):
        pick = [rnd.choice(mints) for _ in mints]; qs = [q for m in pick for q in Q if q["mint"] == m]
        if len(set(q["mint"] for q in qs)) < 3: continue
        b, _ = ols(design(qs, best), [q[ykey] for q in qs]); boots.append([float(v) for v in b])
    return dict(forms=res, best=best, boots=boots, n=n, n_pools=len(mints), resid_sd=res[best]["rmse"])

def rt_pred(fit, liq, size, coef=None):
    c = coef or fit["forms"][fit["best"]]["coef"]; f = fit["best"]
    if f == "flat": v = c[0]
    elif f == "size": v = c[0] + c[1] * size / liq
    elif f == "logliq": v = c[0] + c[1] * math.log10(liq / 1e5)
    else: v = c[0] + c[1] * math.log10(liq / 1e5) + c[2] * size / liq
    return v

def rt_band(fit, liq, size):
    v = sorted(rt_pred(fit, liq, size, b) for b in fit["boots"]); n = len(v)
    return v[int(0.025 * n)], v[int(0.975 * n) - 1]

def cost_fn(fit, which="mid", floor=0.0025):
    """per-side cost (fraction): half the predicted round trip, floored at 0.25%/side (pool LP fee), capped at 15% by cc.S['max_slip']."""
    def f(liq, size):
        if which == "mid": v = rt_pred(fit, liq, size)
        else: v = rt_band(fit, liq, size)[1] + 1.0 * fit["resid_sd"]   # pessimistic: upper 95% of the fit plus one residual SD
        return max(floor, v / 2)
    return f

def impact_only_fn(fit):
    """size-dependent part of the fit only (for copyfomo, whose ~5.3% already includes its pool costs)."""
    c = fit["forms"][fit["best"]]["coef"]; b = c[-1] if fit["best"].endswith("size") else 0.0
    return lambda liq, size: max(0.0, b * size / liq) / 2

SIZES = (5.0, 10.0, 13.0); PRIOS = (0.0001, 0.0005); DELAYS = (2, 5)

def build_models(fit):
    ms = []
    for z in SIZES:
        imp = impact_only_fn(fit)
        ms.append(model(f"REF_copyfomo_${z:.0f}", stake=z, cost_fn=lambda liq, size, imp=imp: 0.0035 + imp(liq, size), kind="REF"))
        for pr in PRIOS:
            for d in DELAYS:
                ms.append(model(f"SELF_${z:.0f}_P{pr:.4f}_{d}s", stake=z, fee=0.0, prio_sol=pr, fixed_extra_leg=True, liq_fn=jliq,
                                cost_fn=cost_fn(fit), delay=d, drift_in=0.02 * d / 10, drift_out=0.02 * d / 10, kind="SELF"))
        ms.append(model(f"SELF_${z:.0f}_P0.0005_pess", stake=z, fee=0.0, prio_sol=0.0005, fixed_extra_leg=True, liq_fn=lambda mc: jliq(mc, 0.5),
                        cost_fn=cost_fn(fit, "hi"), delay=5, drift_in=0.02, drift_out=0.02, kind="PESS"))
    # old v1 0.3% scenario: kept ONLY as an unrealistic lower bound ($5)
    ms.append(model("LOWERBOUND_0.3pct_UNREALISTIC_$5", stake=5.0, fee=0.003, fixed_entry=0.0205, fixed_leg=0.0205, fixed_extra_leg=True, liq_fn=jliq,
                    base_slip=0.005, delay=2, drift_in=0.004, drift_out=0.004, kind="LB"))
    ms.append(model("ZERO_cost_bound_$5", stake=5.0, fee=0.0, fixed_entry=0.0, fixed_leg=0.0, liq_fn=lambda mc: 1e12, base_slip=0.0, delay=0, drift_in=0.0, drift_out=0.0, kind="ZERO"))
    return ms

def main():
    trs, _ = cc.load_trades()
    split = sorted(t["t"] for t in trs)[int(len(trs) * 0.6)]
    Q = load_quotes(); fit = fit_cost(Q); fit_imp = fit_cost(Q, ykey="imp_sum")
    models = build_models(fit)
    R = {M["name"]: evaluate(trs, M, split) for M in models}
    f2 = lambda v: "-" if v is None else f"{v:+.2f}"
    pc = lambda v: "-" if v is None else f"{v*100:+.1f}%"
    co = fit["forms"][fit["best"]]["coef"]
    # copy-time liquidity distribution (from the mcap formula) for context
    liqs = sorted(r["liq"] for r in R["SELF_$5_P0.0001_2s"]["bystevenr"]["cl"] + R["SELF_$5_P0.0001_2s"]["_benjitrades"]["cl"] +
                  R["SELF_$5_P0.0001_2s"]["pointfarmcap"]["cl"] + R["SELF_$5_P0.0001_2s"]["ExactTallTakin"]["cl"])
    medliq = liqs[len(liqs) // 2] if liqs else 50_000
    sp = [solpx(t["t"]) for t in trs]
    L = [f"# Copy fee sensitivity v2: copyfomo vs a self-run Jupiter copier, quote-calibrated ({iso(time.time())}, PAPER ONLY, research only)", "",
         "v2 replaces v1 (kept at out/copy_fee_sensitivity_v1.md). Zero's correction: a live Jupiter $5 quote on a Pump.fun AMM pool cost ~4.7% round trip, not 0.3%. "
         "The v1 0.3%/side self-copier is now shown only as a labelled UNREALISTIC lower bound.", "",
         "Copy rules unchanged: first buys only, leader buy >= $50, mcap >= $100k, TP +100% sells half, SL -25% (fills 2.5% below trigger), max chase 15%, rest exits with the leader.", ""]
    # ---- calibration section
    L += ["## Cost calibration from Jupiter quotes", "",
          f"Data: {fit['n'] - 1} read-only Jupiter lite-api /swap/v1/quote round trips (buy SOL->token at $5/$10/$13, then quote selling the tokens received back to SOL) on "
          f"{fit['n_pools'] - 1} pools (Pump.fun AMM; one routed via Meteora DLMM) spanning the liquidity range, sampled tonight at <= 1 call per 6 s (shared with selfcopy's limiter), plus the one selfcopy dry-run fill "
          "($5 at liq $11.9k: $4.87 back = 2.6% before priority fees). /workspace/selfcopy/quotes.jsonl named in the brief does not exist; the selfcopy dry-run has only that one trade, "
          "so the quotes are my own sample. No /swap call was made.", "",
          "| pool | liq $ | mcap $ | size $ | round-trip loss | Jupiter buy priceImpact | sell priceImpact | route | platform fee |", "|---|---|---|---|---|---|---|---|---|"]
    for q in sorted(Q, key=lambda q: (q["liq"], q["size"])):
        L.append(f"| {q['sym']} | {q['liq']:,.0f} | {q.get('mcap') or 0:,.0f} | {q['size']:.0f} | {q['rt_loss']*100:.2f}% | "
                 f"{'-' if q.get('buy_impact') is None else f'{q[chr(98)+chr(117)+chr(121)+chr(95)+chr(105)+chr(109)+chr(112)+chr(97)+chr(99)+chr(116)]*100:.2f}%'} | "
                 f"{'-' if q.get('sell_impact') is None else f'{q[chr(115)+chr(101)+chr(108)+chr(108)+chr(95)+chr(105)+chr(109)+chr(112)+chr(97)+chr(99)+chr(116)]*100:.2f}%'} | "
                 f"{q.get('route_b')}/{q.get('route_s')} | {q.get('platform_fee')} |")
    L += ["", "Fits (OLS on round-trip loss; per side = half):", "", "| form | coefficients | RMSE | AIC |", "|---|---|---|---|"]
    for k, v in fit["forms"].items():
        L.append(f"| {k}{' (chosen)' if k == fit['best'] else ''} | {', '.join(f'{c:+.4f}' for c in v['coef'])} | {v['rmse']*100:.2f} pt | {v['aic']:.1f} |")
    L += ["", f"Forms: flat rt = A; size rt = A + B*size/liq; logliq rt = A + C*log10(liq/$100k); logliq+size rt = A + C*log10(liq/$100k) + B*size/liq. Chosen by AIC among forms with a non-negative size slope: **{fit['best']}** (the free size slope came out negative = noise: at $5-$13 the size effect is not measurable, it is fee-dominated). "
          f"Uncertainty: pool-level bootstrap ({len(fit['boots'])} resamples). Residual SD {fit['resid_sd']*100:.2f} pt.", "",
          "Noise: the sell-back quote is taken 6-60 s after the buy quote (rate limit and 429 back-off), so the round-trip loss also contains the coin's price move in that gap "
          "(zero-mean but large on memecoins; the same pool gave 0.9% and 4.0% minutes apart). Cross-check that has no time gap: Jupiter's own buy + sell priceImpactPct, "
          f"fit the same way ({fit_imp['best']}): coefficients {', '.join(f'{c:+.4f}' for c in fit_imp['forms'][fit_imp['best']]['coef'])}, RMSE {fit_imp['resid_sd']*100:.2f} pt, "
          f"n = {fit_imp['n']}. Mean round-trip loss {statistics.fmean(q['rt_loss'] for q in Q)*100:.2f}% vs mean impact sum "
          f"{statistics.fmean(q['imp_sum'] for q in Q if q.get('imp_sum') is not None)*100:.2f}%. The model uses the round-trip loss (money actually returned).", "",
          "| liq $ | size $ | predicted round trip | 95% band (fit) |", "|---|---|---|---|"]
    for lq in (15_000, 34_000, 77_000, 108_000, 250_000, 1_000_000):
        for z in SIZES:
            lo, hi = rt_band(fit, lq, z)
            L.append(f"| {lq:,} | {z:.0f} | {rt_pred(fit, lq, z)*100:.2f}% | [{lo*100:.2f}%, {hi*100:.2f}%] |")
    L += ["", "Reading the quotes: on Pump.fun AMM the round-trip loss is mostly the pool's fee schedule (LP + protocol + coin-creator fee; pump.fun's dynamic fee is largest at small mcap), "
          "not depth: at $5-$13 the size term is small and noisy, and Jupiter's priceImpactPct is mostly on the buy leg (fee charged on the quote side). "
          "No Jupiter platform fee appeared on any quote (platformFee null; the lite API adds none without a referral account); any route fee is inside the round-trip loss, which is used as-is.", "",
          f"Applied at copy time: liq = 0.41*sqrt($70k*mcap) (no point-in-time pool liquidity exists for these trades); median copy-time liq ~${medliq:,.0f}. "
          "Per side cost = predicted round trip / 2, floored at 0.25%. Per tx: priority 0.0001 or 0.0005 SOL + 0.000005 SOL base fee, converted at the hourly SOL/USD of the copy "
          f"(Orca SOL/USDC; ${min(sp):.0f}-${max(sp):.0f} over the sample); one tx per buy, per TP leg, per final sell. Delay 2 s or 5 s: entry and exit drift 2% x delay/10 s "
          "(path mode, 8 copies, uses 1-min candles at t+delay). Pessimistic: upper 95% of the fit + 1 residual SD, liq/2, full 2% drift on both legs, 0.0005 SOL.", "",
          f"Check against Zero's live quote: at the median copy-time liq the fit gives {rt_pred(fit, medliq, 5)*100:.1f}% round trip + 2 x 0.0005 SOL priority on $5 "
          f"({2*(0.0005+5e-6)*statistics.median(sp)/5*100:.1f}%) = {(rt_pred(fit, medliq, 5) + 2*(0.0005+5e-6)*statistics.median(sp)/5)*100:.1f}%, consistent with the ~4.7% measured. "
          "At P 0.0005 SOL a $5 self-copy costs about as much as copyfomo before delay; the saving comes from the 0.0001 SOL priority fee and larger tickets.", "",
          "copyfomo at the same sizes: 2%/side fee + $0.015/side gas + 0.35%/side (=~5.3% round trip at $5 incl. gas) + the fitted size-impact term; 10 s lag, +2% entry drift as in copy_candidates.py.", ""]
    # ---- per tx cost table
    L += ["Priority fee as % of the ticket per side (SOL ~$" + f"{statistics.median(sp):.0f}):", ""]
    for z in SIZES:
        L.append(f"- ${z:.0f}: P 0.0001 -> {(0.0001+5e-6)*statistics.median(sp)/z*100:.2f}%/side; P 0.0005 -> {(0.0005+5e-6)*statistics.median(sp)/z*100:.2f}%/side")
    # ---- main comparison
    L += ["", "## Net P&L per copy by leader, size and priority fee (mean $/copy; % of ticket in brackets)", "",
          "| leader | size | copies | copyfomo | self P0.0001 2s | self P0.0001 5s | self P0.0005 2s | self P0.0005 5s | self pessimistic | flips? |", "|---|---|---|---|---|---|---|---|---|---|"]
    flips = {}
    for n in LEADERS:
        for z in SIZES:
            ref = R[f"REF_copyfomo_${z:.0f}"][n]
            cells = []
            for pr in PRIOS:
                for d in DELAYS:
                    b = R[f"SELF_${z:.0f}_P{pr:.4f}_{d}s"][n]; cells.append(b)
            pe = R[f"SELF_${z:.0f}_P0.0005_pess"][n]
            fl = [c for c, (pr, d) in zip(cells, [(p, d) for p in PRIOS for d in DELAYS]) if ref["total"] <= 0 < c["total"]]
            fl_names = [f"P{pr:.4f}/{d}s" for c, (pr, d) in zip(cells, [(p, d) for p in PRIOS for d in DELAYS]) if ref["total"] <= 0 < c["total"]]
            flips[(n, z)] = fl_names
            fm = lambda b: f"{f2(b['mean'])} ({pc(b['mean']/z if b['mean'] is not None else None)})"
            L.append(f"| {n} | ${z:.0f} | {ref['n']} | {fm(ref)} | " + " | ".join(fm(c) for c in cells) + f" | {fm(pe)} | "
                     + ("already >0 under copyfomo" if ref["total"] > 0 else ("FLIPS: " + ", ".join(fl_names) if fl_names else "no")) + " |")
    L += ["", "Medians ($/copy), same layout:", "", "| leader | size | copyfomo | self P0.0001 2s | self P0.0001 5s | self P0.0005 2s | self P0.0005 5s | pessimistic |", "|---|---|---|---|---|---|---|---|"]
    for n in LEADERS:
        for z in SIZES:
            ks = [f"REF_copyfomo_${z:.0f}"] + [f"SELF_${z:.0f}_P{pr:.4f}_{d}s" for pr in PRIOS for d in DELAYS] + [f"SELF_${z:.0f}_P0.0005_pess"]
            L.append(f"| {n} | ${z:.0f} | " + " | ".join(f2(R[k][n]["median"]) for k in ks) + " |")
    L += ["", "Bounds at $5 (not tradeable models): ", ""]
    for n in LEADERS:
        a, b = R["LOWERBOUND_0.3pct_UNREALISTIC_$5"][n], R["ZERO_cost_bound_$5"][n]
        L.append(f"- {n}: v1 0.3%/side scenario (UNREALISTIC lower bound on cost) {f2(a['mean'])}/copy, median {f2(a['median'])}; zero-cost instant copier {f2(b['mean'])}/copy, median {f2(b['median'])}.")
    # ---- full stats
    L += ["", "## Full stats per model (bootstrap 5,000 resamples of per-copy $, seed 7; MC drawdown 1,000 shuffles on $91)", "",
          "| leader | model | copies | win | mean $ | median $ | total $ | ex-best $ | bootstrap 95% CI mean $ | nights +/total | OOS n / mean $ | MC DD p95 | score /25 (oos,dd,n,edge,stab) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in LEADERS:
        for M in models:
            b = R[M["name"]][n]; s = b["sc"]
            L.append(f"| {n} | {M['name']} | {b['n']} | {b['win']:.0%} | {f2(b['mean'])} | {f2(b['median'])} | {f2(b['total'])} | {f2(b['ex_best'])} | "
                     f"[{f2(b['ci'][0])}, {f2(b['ci'][1])}] | {s['nights_profitable']}/{s['nights']} | {b['oos_n']} / {f2(b['oos_mean'])} | "
                     f"{b['mc'][2]*100:.0f}% | {s['score_total']} ({s['sc_oos_risk']},{s['sc_drawdown']},{s['sc_trades']},{s['sc_edge']},{s['sc_stability']}) |")
    hd = "SELF_$5_P0.0005_2s"
    L += ["", f"## Split by night (Dublin), $ per night: copyfomo $5 vs self $5 P0.0005 2 s", ""]
    for n in LEADERS:
        a, b = R["REF_copyfomo_$5"][n]["nights"], R[hd][n]["nights"]
        L.append(f"- **{n}**: " + ", ".join(f"{k[5:]} {a.get(k, 0):+.2f}/{b.get(k, 0):+.2f}" for k in sorted(set(a) | set(b))))
    L += ["", f"## Lottery-ticket check ({hd})", ""]
    for n in LEADERS:
        b = R[hd][n]; srt = sorted(b["pn"], reverse=True)
        L.append(f"- {n}: top 3 copies {', '.join(f'{x:+.2f}' for x in srt[:3])} of total {f2(b['total'])}; without top 3: {f2(sum(srt[3:]))}; "
                 f"losing copies {sum(x < 0 for x in b['pn'])}/{b['n']}; path-mode copies {b['path']}.")
    L += ["", "Bootstrap caution: bystevenr's mean (and any CI excluding 0) rests on one ~+3,300% copy; his median copy is negative in every cost model. That is not a robust edge.", ""]
    L += ["## Candidate check (METHOD: >= 18/25, >= 50 trades, >= 20 OOS trades with OOS CI low > 0)", ""]
    for n in LEADERS:
        for z in SIZES:
            b = R[f"SELF_${z:.0f}_P0.0005_2s"][n]
            L.append(f"- {n} ${z:.0f} (P0.0005 2 s): {b['sc']['score_total']}/25, {b['n']} copies, OOS {b['oos_n']} -> "
                     f"{'CANDIDATE' if b['sc']['score_total'] >= 18 and b['n'] >= 50 and b['oos_n'] >= 20 else 'not a candidate'}"
                     f"{' (fails trade count)' if b['n'] < 50 else ''}{' (fails OOS count)' if b['oos_n'] < 20 else ''}.")
    L += ["", "## WHY THIS COULD FAIL", "",
          f"- The cost fit rests on {fit['n_pools']} pools / {fit['n']} quotes taken in one hour tonight; pump.fun's fee schedule and pool depth at the time of each historical copy are not observed. "
          "Copy-time liquidity comes from the mcap formula, not the pool; a pulled or thin pool costs more (pessimistic column).",
          "- Quotes are not fills: a landed tx adds slippage between quote and slot, failed/expired txs still pay base + priority, and 2-5 s delay drift is assumed, not measured.",
          "- Leader mappings are LOW confidence for _benjitrades and bystevenr (medium-low pointfarmcap, medium ExactTallTakin); pointfarmcap has only 8 copies (Oct 16-21).",
          "- Most copies are approx mode (no price path), which hides intratrade stop-outs and flatters holders through dips.",
          "- Means are carried by 1-3 lottery coins; medians tell the typical copy.",
          "- A self-run copier is a live-infra change (RPC, signing, keys, retries): proposal only, not tested here.", "",
          "Who is on the other side: the leader (selling into followers), the snipers/bundlers ahead of him, and other copy bots including copyfomo's own users racing the same buy. "
          "Cheaper execution doesn't change who we trade against.", "",
          f"Multiple testing: {len(models)} cost models x 4 leaders added to the variants count (rows FS_*)."]
    p = os.path.join(LAB, "out/copy_fee_sensitivity.md"); atomic_write(p, "\n".join(L) + "\n")
    rows = []
    pick = [(f"REF_copyfomo_${z:.0f}", f"ref{z:.0f}") for z in SIZES] + [(f"SELF_${z:.0f}_P0.0001_2s", f"self{z:.0f}_p1_2s") for z in SIZES] + \
           [(f"SELF_${z:.0f}_P0.0005_5s", f"self{z:.0f}_p5_5s") for z in SIZES] + [("SELF_$5_P0.0005_pess", "self5_pess")]
    for mn, short in pick:
        z = next(M["stake"] for M in models if M["name"] == mn)
        for n in LEADERS:
            b = R[mn][n]; s = b["sc"]; cl = b["closed"]
            oos = [c["ret"] for c in cl if c["is_oos"]]
            rows.append({"variant": f"FS_{n}_{short}", "trades": b["n"], "win_rate": round(b["win"], 3), "net_profit_after_costs": round(b["total"], 2),
                         "max_drawdown": round(cc.maxdd(b["pn"]), 2), "holds_out_of_sample": f"insufficient (n_out={b['oos_n']}<20)" if b["oos_n"] < 20 else
                         ("yes" if b["in_net"] > 0 and (b["oos_mean"] or 0) > 0 and boot_ci([c['pnl'] for c in cl if c['is_oos']])[0] > 0 else "no"),
                         "n_in_sample": b["n"] - b["oos_n"], "n_out_of_sample": b["oos_n"],
                         "mean_ret": round(b["mean"] / z, 3) if b["mean"] is not None else "", "median_ret": round(b["median"] / z, 3) if b["median"] is not None else "",
                         "ci95_mean_ret": f"[{b['ci'][0]/z:+.2f},{b['ci'][1]/z:+.2f}]" if b["ci"][0] is not None else "",
                         "oos_mean_ret": round(statistics.fmean(oos), 3) if oos else "", "in_net_pnl": round(b["in_net"], 2), "out_net_pnl": round(b["out_net"], 2),
                         **{k: s[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                         "net_ex_best_trade": round(b["ex_best"], 2), "mc_dd_p5": round(b["mc"][0], 3), "mc_dd_p50": round(b["mc"][1], 3), "mc_dd_p95": round(b["mc"][2], 3),
                         "nights": s["nights"], "nights_profitable": s["nights_profitable"],
                         "candidate": "yes" if s["score_total"] >= 18 and b["n"] >= 50 and b["oos_n"] >= 20 else "no", "lucky_number": "n/a (cost sweep)",
                         "family": "copy_fee_sensitivity", "note": f"PAPER copy sim v2 (quote-calibrated) ${z:.0f}/copy, model {mn}; see out/copy_fee_sensitivity.md"})
    ms = [{k: v for k, v in m.items() if not callable(v)} for m in models]
    json.dump({"rows": rows, "models": ms, "fit": {k: v for k, v in fit.items() if k != "boots"},
               "variant_configs": [dict(m, family="copy_fee_sensitivity", leader=l, name=f"FS_{l}_{m['name']}") for m in ms for l in LEADERS]},
              open(os.path.join(LAB, "out/.fs_rows.json"), "w"), indent=0)
    print(f"wrote {p}; {len(rows)} rows staged; fit {fit['best']} {co}")

if __name__ == "__main__":
    main()
