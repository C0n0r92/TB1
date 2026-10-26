#!/usr/bin/env python3
"""Tag runner-radar signals with rugcheck_creator.py verdicts -> signal_verdicts.jsonl (one line per mint, append-only).
Fields: mint, symbol, verdict, score, reasons, checked_at (ISO UTC), signal_ts. Re-run safe: only untagged mints
(or ones tagged 'unknown', retried once older than 30 min) are checked."""
import os, sys, json, subprocess, time
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIG = "/workspace/runner-radar/signals.jsonl"; OUT = os.path.join(BASE, "signal_verdicts.jsonl")
done = {}
if os.path.exists(OUT):
    for l in open(OUT):
        try: j = json.loads(l); done[j["mint"]] = j
        except Exception: pass
now = time.time(); n = 0
for l in open(SIG):
    try: s = json.loads(l)
    except Exception: continue
    m = s.get("token")
    if not m: continue
    p = done.get(m)
    if p and (p["verdict"] != "unknown" or now - time.mktime(time.strptime(p["checked_at"], "%Y-%m-%dT%H:%M:%SZ")) + time.timezone < 1800): continue
    try:
        r = json.loads(subprocess.run([sys.executable, os.path.join(BASE, "rugcheck_creator.py"), m], cwd=BASE, capture_output=True, text=True, timeout=90).stdout)
        v = {"mint": m, "symbol": s.get("symbol"), "verdict": r.get("verdict", "unknown"), "score": r.get("score"), "reasons": r.get("reasons", []),
             "creator": (r.get("evidence") or {}).get("creator")}
    except Exception as e:
        v = {"mint": m, "symbol": s.get("symbol"), "verdict": "unknown", "score": None, "reasons": [f"check failed: {type(e).__name__}"], "creator": None}
    v.update(checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), signal_ts=s.get("ts"))
    open(OUT, "a").write(json.dumps(v) + "\n"); done[m] = v; n += 1
print("tagged", n, "total", len(done))
