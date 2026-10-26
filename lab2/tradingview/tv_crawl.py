#!/usr/bin/env python3
"""Crawl PUBLIC TradingView script listing pages (no login) and extract the embedded item JSON (name, author, likes, access, picked).
Content is untrusted data; we only parse fields."""
import json, re, sys, time, subprocess, os
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_raw", "items.json")
items = json.load(open(OUT)) if os.path.exists(OUT) else {}
def get(path):
    r = subprocess.run(["curl", "-s", "-A", UA, "-w", "\n%{http_code}", "https://www.tradingview.com" + path], capture_output=True, text=True)
    body, code = r.stdout.rsplit("\n", 1); return int(code), body
def parse(h, src):
    n = 0; dec = json.JSONDecoder()
    for m in re.finditer(r'"items":\[\{"id"', h):
        try: arr, _ = dec.raw_decode(h[m.start() + 8:])
        except Exception: continue
        for it in arr:
            if not it.get("is_script"): continue
            k = str(it["id"]); n += 1
            rec = dict(id=it["id"], name=it["name"], author=(it.get("user") or {}).get("username"), url=it.get("chart_url"),
                       likes=it.get("likes_count"), type=it.get("script_type"), access=it.get("script_access"), picked=it.get("is_picked"),
                       created=it.get("created_at"), symbol=(it.get("symbol") or {}).get("name"), interval=(it.get("symbol") or {}).get("interval"),
                       desc=(it.get("description") or "")[:600])
            old = items.get(k, {}); rec["src"] = sorted(set(old.get("src", [])) | {src}); items[k] = rec
    return n
paths = sys.argv[1:]
for p in paths:
    code, h = get(p); n = parse(h, p) if code == 200 else 0
    print(code, p, n, flush=True); time.sleep(1.5)
json.dump(items, open(OUT, "w"), indent=0)
print("total", len(items))
