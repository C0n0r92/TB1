#!/usr/bin/env python3
"""Append new runner-radar signal mints to data/tokens.txt (read-only on the radar)."""
import json, os
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); fn = os.path.join(B, "data", "tokens.txt")
have = {l.split()[0] for l in open(fn) if l.strip()}
new = []
for l in open("/workspace/runner-radar/signals.jsonl"):
    try: j = json.loads(l)
    except Exception: continue
    m = j.get("mint") or j.get("token") or j.get("token_address") or j.get("address"); sym = (j.get("symbol") or j.get("sym") or "?").replace(" ", "")
    if m and m not in have: have.add(m); new.append(f"{m} {sym} radar")
if new: open(fn, "a").write("\n".join(new) + "\n")
print("new radar mints:", len(new))
