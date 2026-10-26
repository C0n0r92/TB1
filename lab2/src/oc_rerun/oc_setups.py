#!/usr/bin/env python3
"""Per-setup live-rule check, old vs wide universe, 2% round-trip headline (PAPER research only). -> out/oldcoins_setups.md, data/midcap/oc_setups.json"""
import json, os, statistics, time, datetime as dt
import oc_backtest as ob
from labcore import LAB, iso, atomic_write
LIVEP = {"1h_breakout": dict(stop_lo=0.025, stop_hi=0.08, tp=0.15, vth=1.0, act=150e3, hours="live"),
         "15m_breakout": dict(stop_lo=0.025, stop_hi=0.06, tp=0.10, vth=1.0, act=40e3, hours="live"),
         "C_15m_pullback": dict(stop_lo=0.025, stop_hi=0.06, tp=0.10, vth=-1.0, act=40e3, hours="live")}
CO = ["c1.0", "real_P0.0005", "real_P0.0001", "chunk_1pct", "c0.5", "c0.3"]

def stats(r):
    if not r: return dict(n=0)
    lo, hi = ob.boot_mean(r)
    return dict(n=len(r), mean=statistics.fmean(r), med=statistics.median(r), win=sum(x > 0 for x in r) / len(r), lo=lo, hi=hi)

def run_trades(toks, solpx, sigs, P, cost):
    tr = ob.trades(toks, sigs, P, cost, solpx)
    return tr, ob.book(tr)

def main():
    toks, solpx = ob.load()
    tmax = max(k["T"][-1] for k in toks.values())
    R = {}
    for un in ("old", "wide"):
        ob.set_univ(un)
        for su, P in LIVEP.items():
            if su == "1h_breakout": t_lo = tmax - 60 * ob.DAY; sigs = ob.signals_1h(toks, t_lo)
            else:
                t_lo = max(tmax - 60 * ob.DAY, min(k["m15"]["T"][80] for k in toks.values() if k.get("m15")))
                sigs = (ob.signals_15m if su == "15m_breakout" else ob.signals_15c)(toks, t_lo)
            if not sigs: R[(un, su)] = None; continue
            d0 = dt.date.fromisoformat(ob.bookday(min(s["t"] for s in sigs))); d1 = dt.date.fromisoformat(ob.bookday(tmax - 9 * 3600))
            days = [(d0 + dt.timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]
            dO = set(days[int(len(days) * 0.7):])
            row = dict(nsig=len(sigs), days=len(days), oos_from=min(dO), tokens=len({s["mint"] for s in sigs}), costs={})
            for c in CO:
                allt, bk = run_trades(toks, solpx, sigs, P, c)
                rec = {}
                for lab, tr in (("all_signals", allt), ("book_max3", bk)):
                    r = [t["ret"] for t in tr]; ri = [t["ret"] for t in tr if ob.bookday(t["t"]) not in dO]; ro = [t["ret"] for t in tr if ob.bookday(t["t"]) in dO]
                    rec[lab] = dict(all=stats(r), IS=stats(ri), OOS=stats(ro), book_pnl=sum(t["pnl"] for t in tr),
                                    exits={w: sum(t["why"] == w for t in tr) for w in ("stop", "eod", "eod_gap", "trail")},
                                    tokens=len({t["mint"] for t in tr}))
                rec["med_cost_side"] = statistics.median([t["cost"] for t in allt]) if allt else None
                row["costs"][c] = rec
            R[(un, su)] = row
            print(un, su, "sig", len(sigs), "trades", row["costs"]["c1.0"]["all_signals"]["all"].get("n"), flush=True)
    json.dump({f"{a}|{b}": v for (a, b), v in R.items()}, open("/workspace/lab2/results/oc_rerun/oc_setups.json", "w"), indent=1, default=str)
    return R, toks

def flag(rec):
    a, i, o = rec["all"], rec["IS"], rec["OOS"]
    if a.get("n", 0) < 30: return "sample too small"
    if a["mean"] < 0 and a["hi"] < 0.002 and i.get("n", 0) and i["mean"] < 0 and o.get("n", 0) >= 5 and o["mean"] < 0: return "CLEARLY NEGATIVE"
    if a["mean"] < 0: return "negative, not conclusive"
    return "not negative"

def pc(v, k=2): return "-" if v is None else f"{v*100:+.{k}f}%"

if __name__ == "__main__":
    R, toks = main()
    L = [f"# Older-coins live setups, per setup, old vs wide universe ({iso(time.time())}, PAPER research only)", "",
         "Headline cost = 1% per side (= 2% round trip). Also: real_P0.0005 / real_P0.0001 = liquidity-scaled pool fee + 2 x size/liq + priority fee at a 10% x 0.928 SOL ticket; chunk_1pct = 1%/side + 2 x size/liq; flat 0.5% and 0.3%/side.",
         "Universes: old = age >= 7 d, mcap $5-200M, liq >= $500k, vol24 >= $1M; wide = age >= 3 d, mcap $3M-1B, liq >= $300k, vol24 >= $750k (point-in-time approximations; 220 closed 1h bars still needed for EMA200, as in oldcoins.py). Both: thin-activity skip, avoid list, stables/LST/wrapped/tokenized excluded.",
         "Live params: 1h breakout stop = breakout low clamped 2.5-8%, TP +15% half, trail 1h EMA20, act $150k/4 bars; 15m breakout clamp 2.5-6%, TP +10% half, trail 15m EMA20, act $40k/4 bars; "
         "C = 15m pullback (Lab spec, not yet in oldcoins.py or trades-log.md): last closed 1h C > EMA50 > EMA200, 15m low <= EMA20 < close, close > 15m EMA50, >= 3 of the prior 4 closes above EMA20; stop = pullback low clamped 2.5-6%, TP +10% half, trail 15m EMA20, act $40k, no volume test. "
         "All: entries 21:00-07:30 Dublin at next bar open, flat 07:45. 'all signals' = every qualifying signal (per-trade test); 'book' = max 3 open, one per token, 10% each. IS = first 70% of nights, OOS = last 30%.", "",
         "| universe | setup | cost | sample | trades (IS/OOS) | tokens | mean/trade [95% CI] | median | win | IS mean | OOS mean [CI] | book P&L (10%/trade) | exits stop/eod/trail | verdict |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for (un, su), row in R.items():
        if not row: L.append(f"| {un} | {su} | - | no signals | | | | | | | | | | |"); continue
        for c in ("c1.0", "real_P0.0005", "c0.5", "c0.3"):
            for lab in ("all_signals", "book_max3"):
                x = row["costs"][c][lab]; a, i, o = x["all"], x["IS"], x["OOS"]
                if not a.get("n"): continue
                L.append(f"| {un} | {su} | {c} | {lab} | {a['n']} ({i.get('n',0)}/{o.get('n',0)}) | {x['tokens']} | {pc(a['mean'])} [{pc(a['lo'])}, {pc(a['hi'])}] | {pc(a['med'])} | {a['win']:.0%} | "
                         f"{pc(i.get('mean'))} | {pc(o.get('mean'))} [{pc(o.get('lo'))}, {pc(o.get('hi'))}] | {pc(x['book_pnl'])} | {x['exits']['stop']}/{x['exits']['eod']+x['exits']['eod_gap']}/{x['exits']['trail']} | {flag(x) if c == 'c1.0' else ''} |")
        L.append(f"| {un} | {su} | | window {row['days']} nights, OOS from {row['oos_from']}, raw signals {row['nsig']}, median real cost/side {pc(row['costs']['real_P0.0005']['med_cost_side'])} | | | | | | | | | | |")
    atomic_write(os.path.join("/workspace/lab2/results/oc_rerun", "oldcoins_setups_copy.md"), "\n".join(L) + "\n")
    print("\n".join(L[-40:]))
