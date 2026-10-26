"""Confluence/winners side track (PAPER ONLY): own throttle for GeckoTerminal + DexScreener, <= 5 req/min combined for
this job (12 s spacing, cross-process lock data/cl/calls.log). Everything cached under data/cl/. No keys."""
import json, os, time, urllib.request, urllib.error, fcntl
LAB = os.path.dirname(os.path.abspath(__file__)); CL = os.path.join(LAB, "data", "cl"); os.makedirs(CL, exist_ok=True)
LOG = os.path.join(CL, "calls.log"); SPACING = 12.0
UA = {"User-Agent": "lab-paper-research/1.0", "Accept": "application/json"}
def get(url, tries=3):
    for i in range(tries):
        with open(LOG, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX); fh.seek(0); lines = fh.read().splitlines()
            last = float(lines[-1].split()[0]) if lines else 0
            w = SPACING - (time.time() - last)
            if w > 0: time.sleep(w)
            fh.write(f"{time.time():.1f} {url.split('//')[1][:110]}\n"); fh.flush()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(45 * (i + 1)); continue
            if e.code == 404: return {"_404": True}
            if e.code >= 500: time.sleep(10); continue
            return None
        except Exception: time.sleep(5)
    return None
