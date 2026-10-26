#!/usr/bin/env python3
"""Writes out/swing.md from sw_report.main() (+ a long-history re-run with eval from 2020-08 where data exists)."""
import os, datetime as dt
import numpy as np, pandas as pd
import sw_backtest as B
import sw_report as R
from sw_report import pct, ci

def summarize_run():
    return R.main()

def table_rows(S, lucky, cost, tf):
    out = []
    for (n, c), s in sorted(S.items()):
        if c != cost or s["cfg"]["tf"] != tf: continue
        i, o = s["is"], s["oos"]; bi, bo = s["bcurve_is"], s["bcurve_oos"]
        out.append(f"| `{n}`{' *' if s['cfg']['prereg'] else ''} | {i['n']} / {o['n']} | {pct(i['win'],0) if i['n'] else '-'} / {pct(o['win'],0) if o['n'] else '-'} | "
                   f"{pct(i['mean'],2)} / {pct(o['mean'],2)} | {pct(i['med'],2)} / {pct(o['med'],2)} | {pct(bi['total'])} / {pct(bo['total'])} | "
                   f"{bi['maxdd']*100:.1f}% / {bo['maxdd']*100:.1f}% | {pct(s['ew_tok']['is'])} / {pct(s['ew_tok']['oos'])} | "
                   f"{s['dd_tok']['is']*100:.0f}% / {s['dd_tok']['oos']*100:.0f}% | {s['exp_tok']['is']*100:.0f}% / {s['exp_tok']['oos']*100:.0f}% | {s['hold_days']:.1f} | "
                   f"{s['score']['score_total']} | {(s['mc'][2]*100 if s['mc'] else 0):.1f}% | {lucky[n]} | {s['cand']} |")
    return out

HDR = ("| variant (* = pre-registered) | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% ret IS / OOS | book max DD IS / OOS | "
       "per-token 100% avg ret IS / OOS | median token max DD IS / OOS | exposure IS / OOS | median hold (d) | score /25 | MC p95 DD | lucky | cand |\n"
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

def main():
    S, bhs, lucky, n_tried, now, data = R.main()
    st4, sp4, en4 = B.window("4h"); st1, sp1, en1 = B.window("1d")
    L, solbh, ewbh, fams = R.write(S, bhs, lucky, n_tried, now, data)
    head = L[:]; L = []; A = L.append
    A(head[0]); A(head[1])
    A("## Plain reading\n")
    A("PLACEHOLDER_PLAIN\n")
    A("## Per-rule headline (hi cost = 0.6% round trip + 0.1% on stop fills; selection never uses OOS)\n")
    L += head[3:]
    A("")
    # ---------- setup
    A("## Setup\n")
    A(f"- Universe: SOL, JUP, BONK, WIF, JTO, PYTH, RAY, Binance spot USDT klines (proxy for Jupiter fills), full history from data-api.binance.vision: "
      + ", ".join(f"{s} {data['1d'][s].index[0].date()}" for s in B.SYMS) + ". All 7 have data, so nothing was dropped.")
    A(f"- Common evaluation window (all tokens listed): {st4.date()} .. {en4.date()} ({(en4-st4).days} days). Indicators warm up on each token's full history (RSI's 200-day SMA needs 200 days, so WIF/JUP/PYTH/JTO/BONK only become eligible for (c) from late 2024).")
    A(f"- Holdout (untouched for selection): last 30% of that window, from **{sp4.date()}** (4h) / **{sp1.date()}** (1d) to the end. In-sample {st4.date()}..{sp4.date()}.")
    A("- Fills: signal on a bar's close, fill at the NEXT bar's open. ATR trailing stop is intrabar and fills at min(open, stop) (gap-through). Donchian/RSI exits fill at the next open. Positions still open at the end are closed at the last close (exit 'eod').")
    A("- Costs: **lo** = 0.15%/side + 2 x $50 / pool liquidity ($30M SOL, $2M others) = ~0.31% round trip; **hi** = 0.30%/side + the same slippage + 0.10% extra on stop fills = ~0.6-0.7% round trip. At $10-50 tickets size impact is < 0.01%, fees dominate.")
    A("- Book: one equal-weight portfolio across the 7 tokens, max 3 open, 10% of realised equity per position (max 30% deployed), one position per token, simultaneous signals taken in list order SOL, JUP, BONK, WIF, JTO, PYTH, RAY. Book max DD is on realised equity. "
      "Per-token 'fully invested' = 100% of that token's sleeve in every trade, compounding, mark-to-market DD on bar closes; 'avg ret' is the equal-weight average over the 7 sleeves.")
    A("- Rules exactly as pre-registered (textbook): (a) enter on the EMA20 cross above EMA50, exit only on the trailing stop = highest close since entry - k x ATR14 (k = 3; neighbours 2, 4); a fresh cross is needed to re-enter. "
      "(b) enter when the close is above the prior 20-bar high, exit when the close is below the prior 10-bar low (N 15/20/30 x M 7/10/15). "
      "(c) when close > 200-day SMA (1200 bars on 4h) and RSI(2) < 10 buy; exit when RSI(2) > 70 or close > SMA5 (X 5/10/15). No stops on (b)/(c) beyond the rule exit, as in the textbook versions.")
    A("- Scoring per METHOD on the 10% book at hi cost, with one adaptation: sc_stability uses calendar MONTHS (by exit month) instead of Dublin nights, since these trades last days. MC = 1,000 reshuffles of trade order on $100.\n")
    # ---------- buy and hold
    A("## Buy-and-hold over the same windows (hi cost round trip, daily closes)\n")
    A("| token | IS ret | IS max DD | IS ret/DD | OOS ret | OOS max DD | OOS ret/DD | full ret | full CAGR | full max DD |\n|---|---|---|---|---|---|---|---|---|---|")
    for s in B.SYMS:
        b = bhs[("1d", s)]
        A(f"| {s} | {pct(b['is']['total'])} | {b['is']['maxdd']*100:.0f}% | {b['is']['total']/b['is']['maxdd']:+.2f} | {pct(b['oos']['total'])} | {b['oos']['maxdd']*100:.0f}% | {b['oos']['total']/b['oos']['maxdd']:+.2f} | "
          f"{pct(b['full']['total'])} | {pct(b['full']['cagr'])} | {b['full']['maxdd']*100:.0f}% |")
    A(f"| equal-weight 7 | {pct(ewbh['1d']['is'])} | | | {pct(ewbh['1d']['oos'])} | | | {pct(ewbh['1d']['full'])} | | |")
    A("\nThe held-out window is a falling market for SOL, BONK and WIF (SOL about -27%, max DD ~58%), and up for JUP and RAY. 'Beating SOL hold' held out mostly means 'being in cash'; the fair yardstick is return per unit of drawdown and the result at the 10% book vs a 30%-deployed hold.\n")
    # ---------- full tables
    for cost in ("hi", "lo"):
        for tf in ("4h", "1d"):
            A(f"### All settings, {tf}, cost {cost}\n"); A(HDR); L += table_rows(S, lucky, cost, tf); A("")
    # ---------- return per unit DD comparison (pre-reg, hi)
    A("## Return per unit of drawdown, pre-registered rules, held out (hi cost)\n")
    A("| rule | tf | book 10% OOS ret | book DD | ret/DD | per-token 100%: avg ret | median DD | SOL sleeve ret | SOL sleeve DD | SOL hold ret | SOL hold DD | SOL hold ret/DD |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (n, c), s in sorted(S.items()):
        if c != "hi" or not s["cfg"]["prereg"]: continue
        tf = s["cfg"]["tf"]; bo = s["bcurve_oos"]; sb = solbh[tf]["oos"]; so = s["per"]["SOL"]["oos"]
        A(f"| `{n}` | {tf} | {pct(bo['total'])} | {bo['maxdd']*100:.1f}% | {bo['total']/max(bo['maxdd'],1e-9):+.2f} | {pct(s['ew_tok']['oos'])} | {s['dd_tok']['oos']*100:.0f}% | {pct(so['total'])} | {so['maxdd']*100:.0f}% | {pct(sb['total'])} | {sb['maxdd']*100:.0f}% | {sb['total']/sb['maxdd']:+.2f} |")
    # ---------- per token pre-reg
    A("\n## Per token, pre-registered rules, hi cost (fully invested sleeve: return / max DD / trades, IS | OOS)\n")
    A("| rule | " + " | ".join(B.SYMS) + " |\n|---|" + "---|" * len(B.SYMS))
    for (n, c), s in sorted(S.items()):
        if c != "hi" or not s["cfg"]["prereg"]: continue
        A(f"| `{n}` | " + " | ".join(f"{pct(s['per'][t]['is']['total'],0)}/{s['per'][t]['is']['maxdd']*100:.0f}%/{s['per'][t]['n']['is']} \\| {pct(s['per'][t]['oos']['total'],0)}/{s['per'][t]['oos']['maxdd']*100:.0f}%/{s['per'][t]['n']['oos']}" for t in B.SYMS) + " |")
    A("| hold (1d) | " + " | ".join(f"{pct(bhs[('1d',t)]['is']['total'],0)}/{bhs[('1d',t)]['is']['maxdd']*100:.0f}% \\| {pct(bhs[('1d',t)]['oos']['total'],0)}/{bhs[('1d',t)]['oos']['maxdd']*100:.0f}%" for t in B.SYMS) + " |")
    # ---------- 33% book
    A("\n## Same book at 1/3 per position (fully invested when 3 are open), pre-registered, hi cost\n")
    A("| rule | IS ret | IS DD | OOS ret | OOS DD |\n|---|---|---|---|---|")
    for (n, c), s in sorted(S.items()):
        if c == "hi" and s["cfg"]["prereg"]:
            A(f"| `{n}` | {pct(s['b33_is']['total'])} | {s['b33_is']['maxdd']*100:.1f}% | {pct(s['b33_oos']['total'])} | {s['b33_oos']['maxdd']*100:.1f}% |")
    # ---------- best/worst trade dependency
    A("\n## Lottery check (hi cost book): P&L on $100 with and without the single best trade\n")
    A("| variant | trades | net $ | net ex best $ | exits |\n|---|---|---|---|---|")
    for (n, c), s in sorted(S.items()):
        if c == "hi" and (s["cfg"]["prereg"] or lucky[n] != "n/a (not profitable)"):
            A(f"| `{n}` | {len(s['bk'])} | {sum(100*t['stake']*t['ret'] for t in s['bk']):+.2f} | {s['net_ex_best']:+.2f} | {s['exits']} |")
    return L, S, bhs, lucky

def long_history():
    """Second view: eval from SOL's listing (2020-08-11), split at 70% of THAT range; only SOL and RAY have pre-2023 data."""
    B.EVAL_START = pd.Timestamp("2020-08-11", tz="UTC")
    data = {tf: {s: B.load(s, tf) for s in B.SYMS} for tf in ("4h", "1d")}
    out = []
    for cfg in [c for c in B.grid() if c["prereg"]] + [c for c in B.grid() if c["name"] in ("SW_rsi2_1d_X5", "SW_ema_1d_k2")]:
        tf = cfg["tf"]; start, split, end = B.window(tf); allt = []
        per = {}
        for s in B.SYMS:
            tr = B.gen(data[tf][s], s, cfg, "hi", start, end)
            for t in tr: t["is_oos"] = t["t_in"] >= split
            allt += tr
            if s in ("SOL", "RAY"):
                cs = B.cost_side(s, "hi")
                per[s] = {w: B.equity_token(data[tf][s], [t for t in tr if (t["t_in"] >= split) == (w == "oos")], *((start, split) if w == "is" else (split, end)), cs) for w in ("is", "oos")}
                per[s]["bh"] = {w: B.bh(data[tf][s], *((max(start, data[tf][s].index[0]), split) if w == "is" else (split, end)), cs) for w in ("is", "oos")}
        i = B.stats([t["ret"] for t in allt if not t["is_oos"]]); o = B.stats([t["ret"] for t in allt if t["is_oos"]])
        bi = B.book_curve(B.book([t for t in allt if not t["is_oos"]]), start, split); bo = B.book_curve(B.book([t for t in allt if t["is_oos"]]), split, end)
        out.append((cfg["name"], start, split, end, i, o, bi, bo, per))
    B.EVAL_START = pd.Timestamp("2024-03-05", tz="UTC")
    return out

if __name__ == "__main__":
    L, S, bhs, lucky = main()
    lh = long_history()
    A = L.append
    A("\n## Long-history view (eval from 2020-08-11, holdout = last 30% from " + str(lh[0][2].date()) + "; SOL from 2020, RAY from 2021, others join as listed) — hi cost\n")
    A("| variant | trades IS / OOS | win IS / OOS | mean IS / OOS | median IS / OOS | book 10% IS / OOS (DD) | SOL sleeve IS / OOS (DD) | SOL hold IS / OOS (DD) | RAY sleeve IS / OOS | RAY hold IS / OOS |\n|---|---|---|---|---|---|---|---|---|---|")
    for n, st, sp, en, i, o, bi, bo, per in lh:
        sv, sh, rv, rh = per["SOL"], per["SOL"]["bh"], per["RAY"], per["RAY"]["bh"]
        A(f"| `{n}` | {i['n']} / {o['n']} | {pct(i['win'],0)} / {pct(o['win'],0) if o['n'] else '-'} | {pct(i['mean'],2)} / {pct(o['mean'],2)} | {pct(i['med'],2)} / {pct(o['med'],2)} | "
          f"{pct(bi['total'])} ({bi['maxdd']*100:.0f}%) / {pct(bo['total'])} ({bo['maxdd']*100:.0f}%) | {pct(sv['is']['total'],0)} ({sv['is']['maxdd']*100:.0f}%) / {pct(sv['oos']['total'],0)} ({sv['oos']['maxdd']*100:.0f}%) | "
          f"{pct(sh['is']['total'],0)} ({sh['is']['maxdd']*100:.0f}%) / {pct(sh['oos']['total'],0)} ({sh['oos']['maxdd']*100:.0f}%) | {pct(rv['is']['total'],0)} / {pct(rv['oos']['total'],0)} | {pct(rh['is']['total'],0)} / {pct(rh['oos']['total'],0)} |")
    open("/tmp/sw_body.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))
