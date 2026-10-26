"""Assemble results/smc_summary.md from smc_rows_*.json. PAPER ONLY."""
import json, glob, os
R = os.path.join(os.path.dirname(__file__), "..", "results")
rows, nvar = [], 0
for f in sorted(glob.glob(os.path.join(R, "smc_rows_*.json"))):
    d = json.load(open(f)); rows += d["rows"]; nvar += d["variants"]
order = ["maj_5m", "maj_15m", "maj_1h", "old_15m", "old_1h"]; rows.sort(key=lambda r: (order.index(r["cell"]), r["setup"], r["trend"]))
p = lambda x, k=2: "-" if x is None else f"{x*100:+.{k}f}%"
def s(x): return "0" if not x.get("n") else f"{x['n']}/{p(x['mean'])}/{x['pf']:.2f}"
L = ["# Track A SMC: held-out (TEST) results, Lab 2, PAPER ONLY", "",
     "Rules: results/smc_rules.md (written before testing). R picked on TRAIN from {1.5,2,3}. Costs: 0.3%/side majors, 1%/side old coins. Splits in smc_rules.md.",
     "net/trade CI = bootstrap 95% of mean net per trade. book = equal capital per token, each token compounds its own trades (exit-marked); maxDD on that curve. hold = equal-weight buy&hold of the same tokens over TEST (net of 1 round trip); SOL hold alongside.", "",
     "| cell | setup | trend | R | train n / mean | TEST n | TEST mean/trade [95% CI] | PF | win | book net | max DD | hold (eq-wt) | SOL hold | trending n/mean/PF | choppy | high_vol | crash | gate (from train) -> TEST n/mean/PF | claim? |",
     "|" + "---|" * 19]
flags = []
for r in rows:
    tr, te = r["train"], r["test"]; br = r["by_regime"]
    gate = "-" if not r["gate"] else f"{','.join(r['gate']['regimes'])} -> {s(r['gate']['test'])}"
    claim = "no (n<50)" if te.get("n", 0) < 50 else ("YES-lead" if te["lo"] > 0 and te["book"] > r["hold"] else "no")
    if r["gate"] and r["gate"]["test"].get("n", 0) >= 50 and r["gate"]["test"]["lo"] > 0: claim += " / gate YES-lead"
    if "YES" in claim: flags.append(r)
    if not te.get("n"):
        L.append(f"| {r['cell']} | {r['setup']} | {r['trend']} | {r['R']} | {tr.get('n',0)}/{p(tr.get('mean'))} | 0 | - | - | - | - | - | {p(r['hold'],1)} | {p(r['hold_sol'],1)} | - | - | - | - | {gate} | no trades |"); continue
    L.append(f"| {r['cell']} | {r['setup']} | {r['trend']} | {r['R']} | {tr.get('n',0)}/{p(tr.get('mean'))} | {te['n']} | {p(te['mean'])} [{p(te['lo'])}, {p(te['hi'])}] | {te['pf']:.2f} | {te['win']:.0%} | "
             f"{p(te['book'],1)} | {p(te['dd'],1)} | {p(r['hold'],1)} | {p(r['hold_sol'],1)} | " + " | ".join(s(br[g]['test']) for g in ("trending", "choppy", "high_vol", "crash")) + f" | {gate} | {claim} |")
L += ["", f"Variants: {len(rows)} base variants (+ gated re-tests) = {nvar} evaluated on TEST; {len(rows)*3} train configs (R grid). VI = 0 trades on GeckoTerminal old coins (opens equal the prior close, so body gaps never occur) and only a handful on Binance.",
      "Old-coin trade counts are low by rule: stops narrower than 2x round-trip cost (4% at 1%/side) are skipped.", "",
      "## Pooled TEST by regime (all base variants, trades overlap across variants, descriptive only)"]
agg = {}
for r in rows:
    for g, v in r["by_regime"].items():
        t = v["test"]
        if t.get("n"): a = agg.setdefault((r["cell"][:3], g), [0, 0.0]); a[0] += t["n"]; a[1] += t["n"] * t["mean"]
L += ["| universe | regime | trades | mean net/trade |", "|---|---|---|---|"] + [f"| {u} | {g} | {n} | {p(sm/n)} |" for (u, g), (n, sm) in sorted(agg.items())]
L += ["", "## Flags", "None: nothing clears costs held out at >=50 trades with a CI above zero and a beat of buy-and-hold." if not flags else
      "\n".join(f"- {r['cell']} {r['setup']} trend={r['trend']}: TEST {r['test']['n']} trades, {p(r['test']['mean'])} [{p(r['test']['lo'])}, {p(r['test']['hi'])}]" for r in flags)]
open(os.path.join(R, "smc_summary.md"), "w").write("\n".join(L) + "\n"); print("\n".join(L))
