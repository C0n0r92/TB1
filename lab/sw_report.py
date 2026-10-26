#!/usr/bin/env python3
"""Report + leaderboard staging for sw_backtest.py (PAPER research). -> out/swing.md, out/.sw_rows.json, out/sw_grid.csv"""
import json, os, datetime as dt
import numpy as np, pandas as pd
import scoring
from sw_backtest import run, stats, book, book_curve, window, SYMS, gen, cost_side, equity_token, bh, load, grid, OUT

def pct(x, d=1): return "n/a" if x is None else f"{x*100:+.{d}f}%"
def ci(s): return "n/a" if not s or s["n"] == 0 else f"{pct(s['mean'],2)} [{pct(s['lo'],2)}, {pct(s['hi'],2)}]"

def monthly_stability(taken):
    m = {}
    for t in taken: k = t["t_out"].strftime("%Y-%m"); m[k] = m.get(k, 0) + t["stake"] * t["ret"]
    if len(m) < 3: return 1, len(m), sum(v > 0 for v in m.values())
    f = sum(v > 0 for v in m.values()) / len(m)
    return (5 if f >= 0.8 else 4 if f >= 0.6 else 3 if f >= 0.5 else 2 if f >= 0.3 else 1), len(m), sum(v > 0 for v in m.values())

def neighbours(cfg, names):
    f = cfg["fam"]; tf = cfg["tf"]; out = []
    if f == "ema":
        ks = [2, 3, 4]; i = ks.index(cfg["k"]); out = [f"SW_ema_{tf}_k{ks[j]}" for j in (i - 1, i + 1) if 0 <= j < 3]
    elif f == "rsi":
        xs = [5, 10, 15]; i = xs.index(cfg["X"]); out = [f"SW_rsi2_{tf}_X{xs[j]}" for j in (i - 1, i + 1) if 0 <= j < 3]
    else:
        Ns, Ms = [15, 20, 30], [7, 10, 15]; a, b = Ns.index(cfg["N"]), Ms.index(cfg["M"])
        for da, db in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if 0 <= a + da < 3 and 0 <= b + db < 3: out.append(f"SW_don_{tf}_N{Ns[a+da]}_M{Ms[b+db]}")
    return out

def main():
    data, res, bhs = run()
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    S = {}   # summaries
    for (name, cost), r in res.items():
        cfg = r["cfg"]; tf = cfg["tf"]; start, split, end = window(tf); tr = r["trades"]
        tk = book(tr, 0.10, 3); tk_is = [t for t in tk if not t["is_oos"]]; tk_oos = [t for t in tk if t["is_oos"]]
        # book curves per window: rerun the book inside each window so equity starts at 1
        b_is = book_curve(book([t for t in tr if not t["is_oos"]]), start, split); b_oos = book_curve(book([t for t in tr if t["is_oos"]]), split, end)
        b33_oos = book_curve(book([t for t in tr if t["is_oos"]], 1 / 3), split, end); b33_is = book_curve(book([t for t in tr if not t["is_oos"]], 1 / 3), start, split)
        S[(name, cost)] = {"cfg": cfg, "all": stats([t["ret"] for t in tr]), "is": stats([t["ret"] for t in tr if not t["is_oos"]]),
                           "oos": stats([t["ret"] for t in tr if t["is_oos"]]), "bk": tk, "bk_is": stats([t["ret"] for t in tk_is]),
                           "bk_oos": stats([t["ret"] for t in tk_oos]), "bcurve_is": b_is, "bcurve_oos": b_oos, "b33_is": b33_is, "b33_oos": b33_oos,
                           "per": r["per"], "trades": tr,
                           "exp_tok": {w: float(np.mean([r["per"][s][w]["exposure"] for s in SYMS])) for w in ("is", "oos", "full")},
                           "ew_tok": {w: float(np.mean([r["per"][s][w]["total"] for s in SYMS])) for w in ("is", "oos", "full")},
                           "dd_tok": {w: float(np.median([r["per"][s][w]["maxdd"] for s in SYMS])) for w in ("is", "oos", "full")},
                           "exits": pd.Series([t["exit"] for t in tr]).value_counts().to_dict(),
                           "hold_days": float(np.median([(t["t_out"] - t["t_in"]).total_seconds() / 86400 for t in tr])) if tr else 0}
    names = sorted({k[0] for k in S})
    # lucky flags on full-sample book P&L at hi cost
    prof = {n: len(S[(n, "hi")]["bk"]) >= 5 and sum(t["stake"] * t["ret"] for t in S[(n, "hi")]["bk"]) > 0 for n in names}
    lucky = {}
    for n in names:
        nb = neighbours(S[(n, "hi")]["cfg"], names)
        lucky[n] = ("yes" if not all(prof[x] for x in nb) else "no") if prof[n] else "n/a (not profitable)"
    # staging rows
    cfgs = [dict({k: v for k, v in c.items() if k != "prereg"}, name=c["name"], study="swing_v1", cost=cost) for c in grid() for cost in ("lo", "hi")]
    rows = []
    n_tried = scoring.variants_tried(cfgs)
    for (name, cost), s in S.items():
        bk = s["bk"]; closed = [{"ret": t["ret"], "is_oos": t["is_oos"], "t": t["t_in"].timestamp(), "pnl": 100 * t["stake"] * t["ret"]} for t in bk]
        st = stats([t["ret"] for t in bk]); mc = scoring.mc_drawdown([c["pnl"] for c in closed], 100.0) if closed else None
        sc = scoring.score({"trades": len(bk), "mean_ret": st["mean"], "ci_lo": st["lo"] if st["n"] else -1}, None, closed, mc)
        stab, nm, npos = monthly_stability(bk); sc["score_total"] += stab - sc["sc_stability"]; sc["sc_stability"] = stab; sc["nights"] = nm; sc["nights_profitable"] = npos
        so = s["bk_oos"]; ins = [c for c in closed if not c["is_oos"]]; oos = [c for c in closed if c["is_oos"]]
        in_pnl = sum(c["pnl"] for c in ins); out_pnl = sum(c["pnl"] for c in oos)
        hold = f"insufficient (n_out={len(oos)}<20)" if len(oos) < 20 else ("yes" if in_pnl > 0 and so["mean"] > 0 and so["lo"] > 0 else "no")
        eq = np.cumsum([c["pnl"] for c in sorted(closed, key=lambda c: c["t"])]); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq])) if len(eq) else 0
        pn = sorted(c["pnl"] for c in closed)
        cand = "yes" if sc["score_total"] >= 18 and len(bk) >= 50 and hold == "yes" and lucky[name] != "yes" else "no"
        s["score"] = sc; s["mc"] = mc; s["hold"] = hold; s["cand"] = cand; s["net_ex_best"] = sum(pn[:-1]) if pn else 0
        rows.append({"variant": f"{name}_{cost}", "trades": len(bk), "win_rate": round(st["win"] or 0, 3), "net_profit_after_costs": round(sum(pn), 2),
                     "max_drawdown": round(dd, 2), "holds_out_of_sample": hold, "n_in_sample": len(ins), "n_out_of_sample": len(oos),
                     "mean_ret": round(st["mean"], 5) if st["n"] else None, "median_ret": round(st["med"], 5) if st["n"] else None,
                     "ci95_mean_ret": f"[{st['lo']:+.4f},{st['hi']:+.4f}]" if st["n"] else "", "oos_mean_ret": round(so["mean"], 5) if so["n"] else None,
                     "in_net_pnl": round(in_pnl, 2), "out_net_pnl": round(out_pnl, 2),
                     **{k: sc[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
                     "net_ex_best_trade": round(s["net_ex_best"], 2), "mc_dd_p5": round(mc[0], 4) if mc else None, "mc_dd_p50": round(mc[1], 4) if mc else None,
                     "mc_dd_p95": round(mc[2], 4) if mc else None, "candidate": cand, "lucky_number": lucky[name], "family": f"sw_{s['cfg']['fam']}_{s['cfg']['tf']}",
                     "variants_tried": n_tried,
                     "note": f"PAPER swing long-only spot, 7 tokens Binance USDT proxy, book 10%/pos max 3, cost {cost} ({'0.3%' if cost=='lo' else '0.6%+0.1% stop slip'} rt); stability=calendar months; {'PRE-REG' if s['cfg']['prereg'] else 'neighbour'}; see out/swing.md"})
    json.dump({"rows": rows, "variant_configs": cfgs}, open(os.path.join(OUT, ".sw_rows.json"), "w"), default=str, indent=0)
    # grid csv
    g = []
    for (name, cost), s in S.items():
        g.append({"variant": name, "cost": cost, "prereg": s["cfg"]["prereg"], "n_is": s["is"]["n"], "n_oos": s["oos"]["n"], "is_mean": s["is"]["mean"], "oos_mean": s["oos"]["mean"],
                  "is_med": s["is"]["med"], "oos_med": s["oos"]["med"], "bk_is_ret": s["bcurve_is"]["total"], "bk_oos_ret": s["bcurve_oos"]["total"],
                  "ewtok_is": s["ew_tok"]["is"], "ewtok_oos": s["ew_tok"]["oos"], "score": s["score"]["score_total"], "lucky": lucky[name]})
    pd.DataFrame(g).to_csv(os.path.join(OUT, "sw_grid.csv"), index=False)
    return S, bhs, lucky, n_tried, now, data

def write(S, bhs, lucky, n_tried, now, data):
    L = []; A = L.append
    st4, sp4, en4 = window("4h"); st1, sp1, en1 = window("1d")
    A(f"# Swing trading on liquid Solana large caps, 4h + daily, long-only spot ({now}, PAPER research only)\n")
    A(f"Scripts: sw_fetch.py (data/sw_candles/, Binance spot USDT full history), sw_backtest.py, sw_report.py. Grid: out/sw_grid.csv. Variants in this study: 30 rule settings x 2 cost levels; Lab variants_tried now {n_tried}.\n")
    def bhrow(tf, s, w): return bhs[(tf, s)][w]
    solbh = {tf: bhs[(tf, "SOL")] for tf in ("4h", "1d")}
    ewbh = {tf: {w: float(np.mean([bhs[(tf, s)][w]["total"] for s in SYMS])) for w in ("is", "oos", "full")} for tf in ("4h", "1d")}
    fams = [("ema", "(a) EMA20/50 + ATR trail"), ("don", "(b) Donchian breakout"), ("rsi", "(c) RSI(2) pullback > 200d SMA")]
    # ---------- headline
    A("## Headline\n")
    hl = []
    for f, lab in fams:
        for tf in ("4h", "1d"):
            pre = [n for (n, c), s in S.items() if c == "hi" and s["cfg"]["fam"] == f and s["cfg"]["tf"] == tf and s["cfg"]["prereg"]][0]
            cands = [n for (n, c), s in S.items() if c == "hi" and s["cfg"]["fam"] == f and s["cfg"]["tf"] == tf and S[(n, c)]["is"]["n"] >= 10]
            best = max(cands, key=lambda n: S[(n, "hi")]["bcurve_is"]["total"])
            for tag, n in (("pre-registered", pre), ("best in-sample", best)):
                if tag == "best in-sample" and n == pre: continue
                s = S[(n, "hi")]; o = s["oos"]; sb = s["bcurve_oos"]
                hl.append(f"- **{lab}, {tf}, {tag} `{n}`**: held out {o['n']} trades (all tokens), win {pct(o['win'],0) if o['n'] else 'n/a'}, mean {pct(o['mean'],2)}, median {pct(o['med'],2)}; "
                          f"book (10%/pos, max 3) OOS {pct(sb['total'])} (max DD {sb['maxdd']*100:.1f}%), per-token fully invested OOS avg {pct(s['ew_tok']['oos'])} (median token DD {s['dd_tok']['oos']*100:.0f}%, exposure {s['exp_tok']['oos']*100:.0f}%) "
                          f"vs SOL hold {pct(solbh[tf]['oos']['total'])} (DD {solbh[tf]['oos']['maxdd']*100:.0f}%) and equal-weight hold {pct(ewbh[tf]['oos'])}. "
                          f"IS: {s['is']['n']} trades, mean {pct(s['is']['mean'],2)}, book {pct(s['bcurve_is']['total'])}. Score {s['score']['score_total']}/25, holds OOS {s['hold']}, lucky {lucky[n]}, candidate {s['cand']}.")
    L += hl
    return L, solbh, ewbh, fams

if __name__ == "__main__":
    S, bhs, lucky, n_tried, now, data = main()
    L, *_ = write(S, bhs, lucky, n_tried, now, data)
    print("\n".join(L))
    import pickle; pickle.dump((S, bhs, lucky, n_tried, now), open("/tmp/sw_state.pkl", "wb"))
