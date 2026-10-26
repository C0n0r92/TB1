"""Active-hours profile per wallet from swap timestamps already on disk (0 credits).
Sources (deduped by signature): leader_activity_cache.json (free-RPC classify), onchain-intel data/raw/<w>.json,
data/enh_*.json + tmp/enh_*.json (Helius SWAP pages already fetched), scout data/raw/<w>.json and data/w/<w>.json.
day = 07:00-19:59 UTC, night = 20:00-06:59 UTC. tag day/night if >=60% of swaps in that window, else both.
Window = last 14 days (falls back to reporting what exists inside it). <10 swaps -> tag 'insufficient'."""
import json, os, glob, time, collections
BASE = "/workspace/onchain-intel"; SCOUT = "/workspace/scout"
WIN_DAYS = 14; MIN_N = 10

def _load(fn):
    try: return json.load(open(fn))
    except Exception: return None

_enh_index = None
def _enh_files():
    """map wallet -> list of (sig, ts) from Helius SWAP dumps (lists of raw enhanced tx) whose feePayer/accounts include wallet"""
    global _enh_index
    if _enh_index is not None: return _enh_index
    idx = collections.defaultdict(dict)
    files = glob.glob(f"{BASE}/data/enh_*.json") + glob.glob(f"{BASE}/tmp/enh_*.json") + glob.glob(f"{BASE}/data/raw/*.json") + glob.glob(f"{SCOUT}/data/raw/*.json")
    for fn in files:
        d = _load(fn)
        if isinstance(d, dict): d = d.get("txs") or d.get("tx") or []
        if not isinstance(d, list): continue
        for x in d:
            if not isinstance(x, dict) or "timestamp" not in x or x.get("type") not in (None, "SWAP"): continue
            ws = set()
            for t in x.get("tokenTransfers") or []: ws.add(t.get("fromUserAccount")); ws.add(t.get("toUserAccount"))
            for a in x.get("accountData") or []:
                if a.get("nativeBalanceChange"): ws.add(a.get("account"))
            for w in ws:
                if w: idx[w][x["signature"]] = x["timestamp"]
    _enh_index = idx; return idx

def swap_times(w, cache=None):
    s = {}
    for sig, v in (cache or {}).items():
        if v.get("w") == w and v.get("swap"): s[sig] = v["t"]
    s.update(_enh_files().get(w, {}))
    d = _load(f"{SCOUT}/data/w/{w}.json")
    if isinstance(d, dict):
        for x in d.get("tx") or []: s[x["sig"]] = x["ts"]
    return s

def profile(wallets, cache=None, now=None):
    now = now or time.time(); cut = now - WIN_DAYS * 86400
    allts = {}
    for w in wallets: allts.update(swap_times(w, cache))
    ts = sorted(t for t in allts.values() if t >= cut)
    hist = collections.Counter(time.gmtime(t).tm_hour for t in ts)
    n = len(ts); day = sum(c for h, c in hist.items() if 7 <= h < 20); night = n - day
    p = {"window_utc": (time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(ts[0])) + " .. " + time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(ts[-1]))) if ts else None,
         "window_days_requested": WIN_DAYS, "window_days_covered": round((ts[-1] - ts[0]) / 86400, 1) if ts else 0,
         "n_swaps": n, "day_share_07_20": round(day / n, 3) if n else None, "night_share_20_07": round(night / n, 3) if n else None,
         "peak_hours_utc": [h for h, _ in hist.most_common(3)] if n else [],
         "hour_hist_utc": {str(h): hist[h] for h in sorted(hist)},
         "tag": None}
    if n < MIN_N: p["tag"] = "insufficient"
    elif day / n >= 0.6: p["tag"] = "day"
    elif night / n >= 0.6: p["tag"] = "night"
    else: p["tag"] = "both"
    p["computed_utc"] = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(now))
    p["note"] = "Solana swaps only (EVM activity not included); timestamps from on-disk Helius SWAP pages + free-RPC cache; coverage per wallet varies, see window/n_swaps."
    return p
