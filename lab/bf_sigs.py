#!/usr/bin/env python3
"""Step 1: page the pump.fun migration signer's signatures back N days (public RPC). -> data/backfill/mig_sigs.jsonl (resumable)."""
import sys, time
from bf_common import *
DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 28
P = os.path.join(BF, "mig_sigs.jsonl")
rows = read_jsonl(P)
stop_t = time.time() - DAYS * 86400
before = rows[-1]["signature"] if rows else None
if rows and rows[-1]["blockTime"] < stop_t: print("done", len(rows)); sys.exit()
while True:
    opt = {"limit": 1000}
    if before: opt["before"] = before
    r = rpc("getSignaturesForAddress", [MIGRATOR, opt])
    if not r: print("rpc fail; rerun to resume"); break
    with open(P, "a") as fh:
        for x in r: fh.write(json.dumps({"signature": x["signature"], "blockTime": x["blockTime"], "slot": x["slot"], "err": bool(x["err"])}) + "\n")
    before = r[-1]["signature"]
    print(time.strftime("%m-%d %H:%M", time.gmtime(r[-1]["blockTime"])), len(r), flush=True)
    if r[-1]["blockTime"] < stop_t or len(r) < 1000: break
