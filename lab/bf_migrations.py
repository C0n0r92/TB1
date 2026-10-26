#!/usr/bin/env python3
"""Step 2: random sample of REAL pump.fun -> PumpSwap migrations per UTC day (public RPC getTransaction).
Unbiased w.r.t. survival: drawn from the on-chain migration signer's full signature list, not from any listing.
-> data/backfill/migrations.jsonl {mint, pool, t_mig, sig, day}; data/backfill/mig_seen.jsonl (every tx inspected). Resumable.
Usage: bf_migrations.py [per_day=60] [days=28]"""
import sys, random, time, collections
from bf_common import *
PER_DAY = int(sys.argv[1]) if len(sys.argv) > 1 else 60
DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 28
P_OUT, P_SEEN = os.path.join(BF, "migrations.jsonl"), os.path.join(BF, "mig_seen.jsonl")
sigs = [r for r in read_jsonl(os.path.join(BF, "mig_sigs.jsonl")) if not r["err"]]
now = time.time()
byday = collections.defaultdict(list)
for r in sigs:
    if r["blockTime"] >= now - DAYS * 86400 and r["blockTime"] < now - 20 * 3600:   # need >= 20 h of history after migration
        byday[time.strftime("%Y-%m-%d", time.gmtime(r["blockTime"]))].append(r)
rnd = random.Random(20261023)
for d in byday: rnd.shuffle(byday[d])                       # fixed random order per day (seeded) -> resumable
seen = {r["sig"] for r in read_jsonl(P_SEEN)}
got = collections.Counter(r["day"] for r in read_jsonl(P_OUT)); mints = {r["mint"] for r in read_jsonl(P_OUT)}
ptr = {d: 0 for d in byday}
print({d: len(v) for d, v in sorted(byday.items())}, flush=True)
while True:
    active = [d for d in sorted(byday) if got[d] < PER_DAY and ptr[d] < len(byday[d])]
    if not active: break
    for d in active:
        while ptr[d] < len(byday[d]) and byday[d][ptr[d]]["signature"] in seen and got[d] < PER_DAY:
            ptr[d] += 1
        if ptr[d] >= len(byday[d]) or got[d] >= PER_DAY: continue
        x = byday[d][ptr[d]]; ptr[d] += 1
        t = rpc("getTransaction", [x["signature"], {"maxSupportedTransactionVersion": 0, "encoding": "jsonParsed"}])
        rec = {"sig": x["signature"], "day": d, "ok": False}
        if t:
            logs = t["meta"].get("logMessages") or []
            real = any("Instruction: Migrate" in l for l in logs) and not any("already migrated" in l for l in logs) and not t["meta"].get("err")
            pb = t["meta"].get("postTokenBalances") or []
            big = [b for b in pb if b["mint"] != WSOL and (b["uiTokenAmount"].get("uiAmount") or 0) > 1e8]
            rec.update(real=real, fetched=True)
            if real and big:
                b = big[0]; m = b["mint"]
                rec.update(ok=True, mint=m)
                if m not in mints:
                    mints.add(m); got[d] += 1
                    append_jsonl(P_OUT, {"mint": m, "pool": b["owner"], "pool_tokens": b["uiTokenAmount"]["uiAmount"],
                                         "decimals": b["uiTokenAmount"].get("decimals"), "t_mig": t["blockTime"], "sig": x["signature"], "day": d})
        else:
            rec["fetched"] = False
        append_jsonl(P_SEEN, rec); seen.add(x["signature"])
    print(time.strftime("%H:%M:%S"), dict(sorted(got.items())), flush=True)
print("done", sum(got.values()))
