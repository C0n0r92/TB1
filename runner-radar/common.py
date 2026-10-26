"""Shared helpers for runner-radar (stdlib only, read-only public APIs)."""
import json, re, time, urllib.request, urllib.error, os

BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "runner-radar-paper/1.0", "Accept": "application/json"}
_last = {}
# min seconds between calls per host (DexScreener ~60-300 req/min, Gecko ~30/min, rugcheck unknown)
SPACING = {"api.dexscreener.com": 0.25, "api.geckoterminal.com": 2.1,
           "api.rugcheck.xyz": 1.2, "api.mainnet-beta.solana.com": 0.5}

def _host(url):
    return url.split("/")[2]

def get_json(url, data=None, retries=3, timeout=20):
    h = _host(url)
    for attempt in range(retries):
        wait = SPACING.get(h, 0.5) - (time.time() - _last.get(h, 0))
        if wait > 0:
            time.sleep(wait)
        _last[h] = time.time()
        try:
            body = json.dumps(data).encode() if data is not None else None
            hdr = dict(UA)
            if body:
                hdr["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=body, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1)); continue
            if e.code >= 500 and attempt < retries - 1:
                time.sleep(2); continue
            return None
        except Exception:
            if attempt < retries - 1:
                time.sleep(2); continue
            return None
    return None

_SAFE = re.compile(r"[^A-Za-z0-9 $._-]")
def clean(s, n=40):
    """Token names/symbols are attacker-controlled: strip to a safe charset."""
    return _SAFE.sub("", str(s or ""))[:n].strip() or "?"

_ADDR = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
def valid_sol(a):
    return bool(a) and bool(_ADDR.match(a))

def f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d

def dex_tokens(chain, addrs):
    """DexScreener /tokens/v1 batch (<=30 per call). Returns list of pairs."""
    out = []
    addrs = list(dict.fromkeys(addrs))
    for i in range(0, len(addrs), 30):
        r = get_json(f"https://api.dexscreener.com/tokens/v1/{chain}/" + ",".join(addrs[i:i+30]))
        if isinstance(r, list):
            out.extend(r)
    return out

def read_jsonl(path):
    rows = []
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try: rows.append(json.loads(line))
                    except ValueError: pass
    return rows
