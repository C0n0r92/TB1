#!/usr/bin/env python3
"""Fetch the full public description text (incl. release notes) of shortlisted scripts -> tv_raw/src/<id>.desc.txt. Untrusted data."""
import re, subprocess, sys, time, os, json, html
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tv_raw", "src")
items = json.load(open(os.path.join(os.path.dirname(D), "items.json")))
for sid in sys.argv[1:]:
    h = subprocess.run(["curl", "-s", "-A", UA, items[sid]["url"]], capture_output=True, text=True).stdout
    a = h.find('<div class="description-'); b = h.find('contentMetaInfoDesktop', a)
    seg = h[a:b] if a > 0 else ""
    seg = re.sub(r'<time[^>]*title="([^"]*)"[^>]*>.*?</time>', r'\n[\1] ', seg)
    seg = re.sub(r'<br\s*/?>', '\n', seg); seg = re.sub(r'<[^>]+>', ' ', seg)
    txt = re.sub(r'[ \t]+', ' ', html.unescape(seg)).strip()
    open(os.path.join(D, f"{sid}.desc.txt"), "w").write(txt)
    print(sid, len(txt), flush=True); time.sleep(1.5)
