#!/usr/bin/env python3
"""Merge staged side-track rows (out/.fs_rows.json, out/.mc_rows.json) into out/leaderboard_extra_<P>.json + leaderboard.csv
and data/variants_tried.json. Run ONLY under the pipeline lock (flock out/.pipeline.lock). Backups: *.bak-fsmc."""
import csv, json, os, shutil, sys
import scoring
from labcore import LAB
OUT = os.path.join(LAB, "out")
pref = sys.argv[1]                       # FS or MC
st = json.load(open(sys.argv[2] if len(sys.argv) > 2 else os.path.join(OUT, f".{pref.lower()}_rows.json")))   # optional explicit staging file
cfgs = [dict(c, name=c.get("name")) for c in st["variant_configs"]]
n = scoring.variants_tried(cfgs)
rows = st["rows"]
for r in rows: r["variants_tried"] = n
json.dump(rows, open(os.path.join(OUT, f"leaderboard_extra_{pref}.json"), "w"), indent=0)
lb = os.path.join(LAB, "leaderboard.csv"); shutil.copy2(lb, lb + f".bak-{pref.lower()}")
old = list(csv.DictReader(open(lb))); cols = list(old[0].keys())
keep = [r for r in old if not r["variant"].startswith(pref + "_")]
with open(lb + ".tmp", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(keep); w.writerows(rows)
os.replace(lb + ".tmp", lb)
print(f"{pref}: {len(rows)} rows merged; variants_tried={n}")
