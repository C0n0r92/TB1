"""Build a merge_extra.py staging file for the SMC study (rows prefixed L2SMC_). Uses COPIED Lab scoring (src/oc_rerun). PAPER ONLY.
Output: results/.l2smc_rows.json (in lab2). The merge itself is run separately under flock."""
import os, sys, json, statistics
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "oc_rerun"))
import numpy as np, pandas as pd
import scoring
R = os.path.join(os.path.dirname(__file__), "..", "results")
tr = pd.concat([pd.read_csv(os.path.join(R, f)) for f in ("smc_trades_a.csv", "smc_trades_b.csv")])
tr["t"] = pd.to_datetime(tr.t_sig, utc=True).dt.as_unit("s").astype("int64")
rows, cfgs = [], []
for v, g in tr.groupby("variant"):
    cell, setup, trend = v.split("|"); name = f"L2SMC_{cell}_{setup}_{trend.replace('=', '')}"
    g = g.sort_values("t"); r = g.ret.values; pnl = 10 * r     # % of book at 10% per trade (Lab oc convention)
    isr, oos = r[~g.is_oos.values], r[g.is_oos.values]
    bs = np.random.default_rng(7).choice(r, (5000, len(r))).mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
    cum = np.cumsum(np.r_[0, pnl]); dd = float((np.maximum.accumulate(cum) - cum).max())
    closed = [dict(ret=float(a), pnl=float(b) / 100, t=int(t), is_oos=bool(o)) for a, b, t, o in zip(r, pnl, g.t, g.is_oos)]
    mc = scoring.mc_drawdown([c["pnl"] for c in closed], 1.0)
    sc = scoring.score(dict(trades=len(r), mean_ret=float(r.mean()), ci_lo=float(lo)), {}, closed, mc)
    best = pnl.max() if len(pnl) else 0
    n_out = len(oos)
    hold = "insufficient (n_out=%d<20)" % n_out if n_out < 20 else ("yes" if oos.mean() > 0 else "no")
    rows.append(dict(variant=name, trades=len(r), win_rate=round(float((r > 0).mean()), 3), net_profit_after_costs=round(float(pnl.sum()), 2),
                     max_drawdown=round(dd, 2), holds_out_of_sample=hold, n_in_sample=len(isr), n_out_of_sample=n_out,
                     mean_ret=round(float(r.mean()), 4), median_ret=round(float(np.median(r)), 4), ci95_mean_ret=f"[{lo:+.3f},{hi:+.3f}]",
                     oos_mean_ret=round(float(oos.mean()), 4) if n_out else "", in_net_pnl=round(float(10 * isr.sum()), 2), out_net_pnl=round(float(10 * oos.sum()), 2),
                     **sc, net_ex_best_trade=round(float(pnl.sum() - best), 2), mc_dd_p5=round(mc[0], 3), mc_dd_p50=round(mc[1], 3), mc_dd_p95=round(mc[2], 3),
                     candidate="no", lucky_number="n/a (R picked on train from 1.5/2/3)", family="lab2_smc",
                     note=f"OOS CI {np.percentile(np.random.default_rng(7).choice(oos, (2000, len(oos))).mean(1), 2.5)*100:+.2f}%..{np.percentile(np.random.default_rng(7).choice(oos, (2000, len(oos))).mean(1), 97.5)*100:+.2f}%/trade; Lab 2 PAPER SMC long-only, {cell}, cost {'0.3' if cell.startswith('maj') else '1'}%/side, R={g.R.iloc[0]}, train->test split; pnl %=10% of book/trade; see /workspace/lab2/results/smc_summary.md"))
    cfgs.append(dict(name=name, family="lab2_smc", cell=cell, setup=setup, trend=trend, R=float(g.R.iloc[0])))
json.dump(dict(rows=rows, variant_configs=cfgs), open(os.path.join(R, ".l2smc_rows.json"), "w"), indent=0, default=float)
print(len(rows), "rows; holds yes:", [x["variant"] for x in rows if x["holds_out_of_sample"] == "yes"])
