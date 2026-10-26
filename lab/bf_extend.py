#!/usr/bin/env python3
"""Extend 1-min candles forward for replayed SIGNAL pools whose first 1000 traded minutes end before the trade deadline
(data/backfill/need_more.json from bf_replay.py). Shares the Gecko cross-process spacing lock. Resumable/idempotent."""
import json, os, time
from bf_common import *
C1 = os.path.join(BF, "candles1m"); G = "https://api.geckoterminal.com/api/v2/networks/solana"
need = json.load(open(os.path.join(BF, "need_more.json"))) if os.path.exists(os.path.join(BF, "need_more.json")) else []
calls = 0
for n in need:
    p = os.path.join(C1, n["pool"] + ".json"); d = json.load(open(p))
    for _ in range(3):
        last = d["rows"][-1][0]
        if last + 60 >= n["deadline"] or d.get("ext_done"): break
        before = int(min(n["deadline"] + 600, last + 60 * 1000))
        r = gecko(f"{G}/pools/{n['pool']}/ohlcv/minute?aggregate=1&limit=1000&currency=usd&token=base&before_timestamp={before}"); calls += 1
        try: rows = [[int(x[0])] + [float(v) for v in x[1:6]] for x in r["data"]["attributes"]["ohlcv_list"]]
        except Exception: break
        have = {x[0] for x in d["rows"]}; new = [x for x in rows if x[0] not in have]
        d["rows"] = sorted(d["rows"] + new); d["ext"] = d.get("ext", 0) + 1
        if not [x for x in new if x[0] > last]: d["ext_done"] = True     # nothing after the old end -> coin stopped trading
        json.dump(d, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
    print(n["pool"][:8], len(d["rows"]), "calls", calls, flush=True)
print("done", calls)
