"""Backfill helpers (PAPER ONLY, read-only public APIs, no keys). Rate-limited, cached, resumable."""
import json, os, time, urllib.request, urllib.error, fcntl
LAB = os.path.dirname(os.path.abspath(__file__))
BF = os.path.join(LAB, "data", "backfill")
os.makedirs(BF, exist_ok=True)
RPC_URLS = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]
MIGRATOR = "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"   # pump.fun migration signer (MigrateV2 -> PumpSwap)
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMPSWAP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"
UA = {"User-Agent": "lab-paper-backfill/1.0", "Accept": "application/json"}
_last = {}
GECKO_SPACING = 16.0         # 2026-10-23 23:33Z Zero: backfill is #3 tonight -> COMBINED Gecko+DexScreener <= 4 req/min (shared lock)
def _wait(host, spacing):
    w = spacing - (time.time() - _last.get(host, 0))
    if w > 0: time.sleep(w)
    _last[host] = time.time()

def rpc(method, params, spacing=0.6, tries=4):
    for i in range(tries):
        url = RPC_URLS[i % len(RPC_URLS)]
        _wait(url, spacing if i % 2 == 0 else 1.5)
        try:
            req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         headers={**UA, "Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=40).read())
            if "result" in r: return r["result"]
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(3 * (i + 1))
    return None

GLOCK = os.path.join(BF, ".gecko_calls.log")
def throttle(tag):
    """Shared spacing for ALL Lab-backfill HTTP calls to Gecko + DexScreener (cross-process lock) -> combined <= 3.75/min."""
    with open(GLOCK, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0); lines = fh.read().splitlines()
        last = float(lines[-1].split()[0]) if lines else 0
        w = GECKO_SPACING - (time.time() - last)
        if w > 0: time.sleep(w)
        fh.write(f"{time.time():.1f} {tag[:90]}\n"); fh.flush()

def gecko(url, tries=3):
    """GeckoTerminal GET, >= 6.5 s spacing (also across processes via a lock file), 429 back-off. Counts calls."""
    for i in range(tries):
        with open(GLOCK, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            fh.seek(0); lines = fh.read().splitlines()
            last = float(lines[-1].split()[0]) if lines else 0
            w = GECKO_SPACING - (time.time() - last)
            if w > 0: time.sleep(w)
            fh.write(f"{time.time():.1f} {url.split('/v2/')[-1][:90]}\n"); fh.flush()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(30 * (i + 1)); continue
            if e.code == 404: return {"_404": True}
            if e.code >= 500: time.sleep(10); continue
            return None
        except Exception:
            time.sleep(5); continue
    return None

def read_jsonl(p):
    out = []
    if os.path.exists(p):
        for l in open(p):
            l = l.strip()
            if l:
                try: out.append(json.loads(l))
                except ValueError: pass
    return out
def append_jsonl(p, row):
    with open(p, "a") as fh: fh.write(json.dumps(row) + "\n")
