"""Regime-split rerun of Lab's older-coins setups on COPIED code (src/oc_rerun/*, read-only on Lab's data). PAPER ONLY.
-> results/oc_rerun/oc_regime.md, oc_regime_trades.csv"""
import os, sys, datetime as dt, json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "oc_rerun")); sys.path.insert(1, HERE)
import numpy as np, pandas as pd
import oc_backtest as ob, oc_setups as os_
import regime
REG = ["trending", "choppy", "high_vol", "crash"]
OUTD = "/workspace/lab2/results/oc_rerun"

def st(r):
    if not r: return dict(n=0)
    r = np.array(r); w, l = r[r > 0].sum(), -r[r < 0].sum()
    bs = np.random.default_rng(7).choice(r, (5000, len(r))).mean(1)
    return dict(n=len(r), mean=r.mean(), lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), pf=w / l if l else np.inf, win=(r > 0).mean())

def f(s):
    if not s.get("n"): return "0 | - | - "
    return f"{s['n']} | {s['mean']*100:+.2f}% [{s['lo']*100:+.2f}, {s['hi']*100:+.2f}] | {s['pf']:.2f}"

def main():
    toks, solpx = ob.load(); tmax = max(k["T"][-1] for k in toks.values()); rtab = regime.build()
    L = ["# Regime-split rerun of Lab's older-coins setups (copied code in src/oc_rerun, Lab 2, PAPER ONLY)", "",
         "Same rules, universes, costs and IS/OOS split (first 70% / last 30% of nights) as /workspace/lab/out/oldcoins_setups.md; every trade tagged with src/regime.py at the entry decision time (signal bar close).",
         "hours=live is Lab's 21:00-07:30 Dublin window; hours=all is a Lab 2 extension (same rules, any hour, no forced 07:45 flat beyond Lab's walk) to get more trades. Gate = regimes with IS mean > 0 and >= 10 IS trades, re-tested OOS.", "",
         "| universe | setup | hours | cost | IS all n / mean [CI] / PF | OOS all n / mean [CI] / PF | " + " | ".join(f"{g} IS n/mean/PF | {g} OOS n/mean/PF" for g in REG) + " | gate (from IS) | gated OOS n/mean/PF |",
         "|" + "---|" * (6 + 2 * len(REG) + 2)]
    allrows = []; nvar = 0; summary = []
    for un in ("old", "wide"):
        ob.set_univ(un)
        for su, P0 in os_.LIVEP.items():
            if su == "1h_breakout": t_lo = tmax - 60 * ob.DAY; sigs = ob.signals_1h(toks, t_lo)
            else:
                t_lo = max(tmax - 60 * ob.DAY, min(k["m15"]["T"][80] for k in toks.values() if k.get("m15")))
                sigs = (ob.signals_15m if su == "15m_breakout" else ob.signals_15c)(toks, t_lo)
            if not sigs: continue
            d0 = dt.date.fromisoformat(ob.bookday(min(s["t"] for s in sigs))); d1 = dt.date.fromisoformat(ob.bookday(tmax - 9 * 3600))
            days = [(d0 + dt.timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]; dO = set(days[int(len(days) * 0.7):])
            for hours in ("live", "all"):
                P = dict(P0, hours=hours)
                for cost in ("c1.0", "real_P0.0005"):
                    nvar += 1
                    tr = ob.trades(toks, sigs, P, cost, solpx)
                    if not tr: continue
                    g = regime.regime_at(pd.to_datetime([t["t"] for t in tr], unit="s", utc=True), rtab)
                    lab = dict(zip(g.index, g["regime"]))
                    for t in tr:
                        t["regime"] = lab.get(pd.Timestamp(t["t"], unit="s", tz="UTC"), "na"); t["oos"] = ob.bookday(t["t"]) in dO
                        allrows.append(dict(universe=un, setup=su, hours=hours, cost_model=cost, sym=t["sym"], t=dt.datetime.fromtimestamp(t["t"], dt.timezone.utc).isoformat(),
                                            ret=t["ret"], why=t["why"], cost=t["cost"], regime=t["regime"], oos=t["oos"]))
                    IS = [t for t in tr if not t["oos"]]; OOS = [t for t in tr if t["oos"]]
                    cells = []
                    gate = []
                    for rg in REG:
                        a = [t["ret"] for t in IS if t["regime"] == rg]; b = [t["ret"] for t in OOS if t["regime"] == rg]
                        cells += [f(st(a)).replace(" | ", "/"), f(st(b)).replace(" | ", "/")]
                        if len(a) >= 10 and np.mean(a) > 0: gate.append(rg)
                    gs = st([t["ret"] for t in OOS if t["regime"] in gate]) if gate else {}
                    if gate: nvar += 1
                    L.append(f"| {un} | {su} | {hours} | {cost} | {f(st([t['ret'] for t in IS]))} | {f(st([t['ret'] for t in OOS]))} | " + " | ".join(cells) +
                             f" | {','.join(gate) or 'none'} | {f(gs).replace(' | ', '/') if gate else '-'} |")
                    summary.append(dict(un=un, su=su, hours=hours, cost=cost, IS=st([t['ret'] for t in IS]), OOS=st([t['ret'] for t in OOS]), gate=gate, gated=gs))
                    print(L[-1], flush=True)
    L += ["", f"Variants evaluated: {nvar} (2 universes x 3 setups x 2 hour windows x 2 cost models, + gated re-tests).",
          "Note: the old and wide universes overlap heavily, and c1.0 vs real_P0.0005 is the same trades at two costs, so the variants are far from independent."]
    pd.DataFrame(allrows).to_csv(os.path.join(OUTD, "oc_regime_trades.csv"), index=False)
    open(os.path.join(OUTD, "oc_regime.md"), "w").write("\n".join(L) + "\n")
    json.dump(summary, open(os.path.join(OUTD, "oc_regime_summary.json"), "w"), default=float, indent=1)

if __name__ == "__main__":
    main()
