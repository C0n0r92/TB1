#!/usr/bin/env python3
"""Run all CL_ tests from cache (PAPER ONLY). python3 cl_run.py  -> out/cl_results.json, out/cl_trades.csv, out/.cl_rows.json"""
import json, os, csv, statistics as S
import scoring
from cl_sim import *
E = json.load(open(os.path.join(CL, "events.json"))); C = load_series()
res = dict(tests={}, sweeps={}, controls={}, coverage={}); rows = []; cfgs = []; trades_out = []
def T(name, evs, cfg, fam, la, key="t", hold_t=None, note=""):
    tr = run(evs, C, cfg, key); st = stats(tr, hold_t)
    res["tests"][name] = dict(cfg=cfg, lookahead=la, n_events=len(evs), **{k: v for k, v in st.items()})
    cfgs.append(dict(cfg, name=name, sig=name.split("__")[0]))
    r = row(name + ("_LOOKAHEAD" if la else ""), tr, st, fam, note, la) if tr else None
    if r: rows.append(r)
    for t in tr: trades_out.append(dict(test=name, **{k: t[k] for k in ("mint", "t", "entry", "mcap", "cost", "ret", "why", "rug", "is_oos")}))
    return st, tr
pit_ev = E["events"]["EB_PIT_n2_w30"]["events"]; ts = sorted(e["t"] for e in pit_ev); HO = ts[int(0.6 * (len(ts) - 1))]
res["holdout_after_pit"] = HO
for k, v in E["events"].items():
    if not v["events"]: res["tests"][k] = dict(n_events=0, lookahead=v["lookahead"]); continue
    la = v["lookahead"] != "PIT"
    cov = sum(1 for e in v["events"] if C.get(e["mint"], {}).get("rows")); res["coverage"][k] = dict(events=len(v["events"]), with_candles=cov)
    T(f"CL_{k}", v["events"], DEFAULT, f"cl_{v['set']}", la, hold_t=HO if not la else None,
      note=f"PAPER confluence {v['set']} N>={v['N']} within {v['W']}m; default exit SL25/TP50/2h; {v['lookahead']}")
# first-buyer (single-wallet) entry on the same cluster tokens, and single-wallet copies of every PIT buy with candles
for k in ("EB_PIT_n2_w30", "EB_PIT_n3_w30", "EB_ALL_n2_w30"):
    v = E["events"][k]; la = v["lookahead"] != "PIT"
    T(f"CL_{k}_firstbuyer", v["events"], DEFAULT, f"cl_{v['set']}_ctl", la, key="t_first", hold_t=HO if not la else None, note="control: enter on 1st wallet's buy")
cl_m = {e["mint"] for e in E["events"]["EB_ALL_n2_w60"]["events"]}
sing = [s for s in E["singles"]["EB_PIT"] if s["mint"] not in cl_m]; first = {}
for s in sing: first.setdefault(s["mint"], s)
T("CL_EB_PIT_single_noncluster", list(first.values()), DEFAULT, "cl_EB_PIT_ctl", False, hold_t=HO, note="control: single-wallet copies, tokens with no 2-wallet cluster (random 60-token sample)")
# controls
for k in ("EB_PIT_n2_w30", "EB_PIT_n3_w30", "EB_ALL_n2_w30"):
    res["controls"][k] = controls(E["events"][k]["events"], C, DEFAULT)
# neighbour sweeps (one parameter at a time around DEFAULT) on PIT n2/n3
fams = {}
for k in ("EB_PIT_n2_w30", "EB_PIT_n3_w30"):
    evs = E["events"][k]["events"]
    grid = dict(sl=[0.15, 0.25, 0.40], tp=[0.25, 0.5, 1.0, 2.0, 0], hold_m=[15, 30, 120, 360], delay_s=[10, 60, 120],
                cost_pump=[0.033, 0.047, 0.07], ladder=[False, 0.15, 0.30])
    for p, vals in grid.items():
        fam = f"{k}@{p}"; fams[fam] = []
        for x in vals:
            cfg = dict(DEFAULT, **{p: x}); nm = f"CL_{k}__{p}{x}"
            if cfg == DEFAULT: nm = f"CL_{k}"
            else: T(nm, evs, cfg, f"cl_sweep_{k}", False, hold_t=HO, note=f"sweep {p}={x}")
            fams[fam].append((x if x is not False else 0, nm))
flags = scoring.lucky_flags(rows, fams)
for r in rows: r["lucky_number"] = flags.get(r["variant"], "n/a")
json.dump(res, open(os.path.join(OUT, "cl_results.json"), "w"), indent=1, default=str)
json.dump(dict(rows=rows, variant_configs=cfgs), open(os.path.join(OUT, ".cl_rows.json"), "w"), default=str)
with open(os.path.join(OUT, "cl_trades.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(trades_out[0].keys())); w.writeheader(); w.writerows(trades_out)
for k, v in res["tests"].items():
    if v.get("trades"): print(f"{k:45s} n={v['trades']:4d} mean={v['mean_ret']:+.3f} ci=[{v['ci_lo'] or 0:+.3f},{v['ci_hi'] or 0:+.3f}] oos n={v['n_out']} m={v['oos_mean'] if v['oos_mean'] is None else round(v['oos_mean'],3)} rug={v['rug_rate']:.2f} LA={v['lookahead']}")
print(json.dumps(res["controls"], default=str)[:1500]); print(res["coverage"])
