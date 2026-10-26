#!/usr/bin/env python3
"""For shortlisted candidate scripts: fetch the PUBLIC script page (description, likes) and the open-source Pine code that
TradingView serves to logged-out visitors. Saved to tv_raw/src/<id>.pine and tv_raw/src/<id>.json. Untrusted data: parsed only."""
import json, re, subprocess, sys, time, os, html
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_raw")
items = json.load(open(os.path.join(D, "items.json")))
def curl(u): return subprocess.run(["curl", "-s", "-A", UA, "-H", "Referer: https://www.tradingview.com/", u], capture_output=True, text=True).stdout
for sid in sys.argv[1:]:
    it = items[sid]; h = curl(it["url"])
    m = re.search(r'"script_id_part":"(PUB;[A-Za-z0-9]+)"', h)
    d = re.search(r'<meta name="description" content="([^"]*)"', h)
    # full description body: take the visible description block
    body = re.search(r'"description":"((?:[^"\\]|\\.)*)","created_at"', h)
    desc = json.loads('"' + body.group(1) + '"') if body else (html.unescape(d.group(1)) if d else "")
    src = ""
    if m:
        time.sleep(1)
        j = json.loads(curl(f"https://pine-facade.tradingview.com/pine-facade/get/{m.group(1)}/last?no_4xx=true") or "{}")
        src = j.get("source", "")
    open(os.path.join(D, "src", f"{sid}.pine"), "w").write(src)
    json.dump(dict(it, full_desc=desc, pub=m.group(1) if m else None), open(os.path.join(D, "src", f"{sid}.json"), "w"), indent=1)
    print(sid, it["name"][:50], len(desc), len(src), "lookahead_on" if "lookahead_on" in src else "", "security" if "security(" in src else "", flush=True)
    time.sleep(1.5)
