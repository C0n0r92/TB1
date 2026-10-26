#!/usr/bin/env python3
"""PAPER ONLY. Extra OOS for ES picked rules: CR30 copy-replay first buys (data/cr/candles, cache only). Candles end at the leader's
full exit (H), so only entries with >= 2 h of candles are used, and end-of-data exits are flagged. Entry = candle t0 (first buy), cost 4.7%."""
import json, glob, bisect, sys, io, contextlib
from es_common import summ
with contextlib.redirect_stdout(io.StringIO()):
    import es_rules as E
out = {}
D = []
for p in glob.glob("/workspace/lab/data/cr/candles/*.json"):
    d = json.load(open(p))
    if d.get("status") != "ok" or not d.get("rows"): continue
    rows = [x for x in d["rows"] if x[4] and x[4] > 0]
    if not rows or rows[-1][0] - d["t0"] < 7200: continue
    tsl = [x[0] for x in rows]; i0 = bisect.bisect_left(tsl, d["t0"] + 10 - 59)
    if i0 >= len(rows) - 1: continue
    D.append(dict(rows=rows, tsl=tsl, i0=i0, cost=0.047, t=d["t0"]))
for nm, r in [("ES_BASE_trail15_arm20", ("TRAIL", 0.15, 0.2))] + [(v["rule"], next(x for x in E.RULES if E.name(x) == v["rule"])) for v in E.res["picked_on_b1"].values()]:
    v = [E.run(tr, r) for tr in D]
    out[nm] = dict(summ([x[0] for x in v]), eod_share=round(sum(x[2] == "eod" for x in v) / len(v), 2))
json.dump(out, open("/workspace/lab/out/es_cr30.json", "w"), indent=1); print(len(D), json.dumps(out, indent=0))
