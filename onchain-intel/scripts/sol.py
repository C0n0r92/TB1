"""Shared read-only Solana helpers (public RPC, no keys). Never signs anything."""
import json, time, os, threading, urllib.request, itertools
RPCS = ["https://solana-rpc.publicnode.com", "https://api.mainnet-beta.solana.com"]
def _helius_key():
    """HELIUS_API_KEY from env, else from /home/box/.scout-secrets/helius.env. Never printed or logged."""
    k = os.environ.get("HELIUS_API_KEY")
    fn = "/home/box/.scout-secrets/helius.env"
    if not k and os.path.exists(fn):
        for line in open(fn):
            line = line.strip().replace("export ", "", 1)
            if line.startswith("HELIUS_API_KEY="): k = line.split("=", 1)[1].strip().strip('"').strip("'")
    return k or None
if _helius_key():
    RPCS.insert(0, "https://mainnet.helius-rpc.com/?api-key=" + _helius_key())
HAVE_HELIUS = len(RPCS) == 3
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "data", "txcache")
os.makedirs(CACHE, exist_ok=True)
PUMP_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
WSOL = "So11111111111111111111111111111111111111112"
_rr = itertools.count()

# ---- optional shared Helius budget (used by refresh.sh; unset = old behaviour, e.g. for rugguard/live use)
# SCOUT_HELIUS_BUDGET_FILE=<json {"limit": N, "used": n, "denied": d}>  shared by every script in one refresh run
# SCOUT_PUBLIC_FIRST=1  try the public RPCs first, Helius only as the last resort
BUDGET_FILE = os.environ.get("SCOUT_HELIUS_BUDGET_FILE")
PUBLIC_FIRST = os.environ.get("SCOUT_PUBLIC_FIRST") == "1"
def budget_take(n=1, kind="helius"):
    """True if n Helius credits may be spent now (and books them). Always True when no budget file is set."""
    if not BUDGET_FILE: return True
    import fcntl
    with open(BUDGET_FILE + ".lock", "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try: b = json.load(open(BUDGET_FILE))
        except Exception: b = {"limit": 10000, "used": 0, "denied": 0}
        ok = b.get("used", 0) + n <= b.get("limit", 10000)
        if ok: b["used"] = b.get("used", 0) + n; b.setdefault("by_kind", {})[kind] = b.get("by_kind", {}).get(kind, 0) + n
        else: b["denied"] = b.get("denied", 0) + n; b.setdefault("denied_by_kind", {})[kind] = b.get("denied_by_kind", {}).get(kind, 0) + n
        tmp = BUDGET_FILE + ".tmp"; json.dump(b, open(tmp, "w")); os.replace(tmp, BUDGET_FILE)
        return ok

_lock = threading.Lock(); _last = [0.0]; MIN_GAP = 0.13   # <= ~7.5 req/s per process (Helius free = 10 RPS)
CREDITS_LOG = os.path.join(BASE, "data", "rpc_calls.log")
def _throttle(url):
    if "helius" not in url: return
    with _lock:
        w = _last[0] + MIN_GAP - time.time()
        if w > 0: time.sleep(w)
        _last[0] = time.time()
    try:
        with open(CREDITS_LOG, "a") as f: f.write(time.strftime("%Y-%m-%d") + " helius 1\n")   # count only, never the URL/key
    except Exception: pass

def rpc(method, params, tries=8):
    pub = [u for u in RPCS if "helius" not in u]
    for a in range(tries):
        if PUBLIC_FIRST and HAVE_HELIUS:
            url = pub[(next(_rr) + a) % len(pub)] if a < tries - 2 else RPCS[0]   # 6 public tries, then Helius
        else:
            url = RPCS[(next(_rr) + a) % len(RPCS)] if a else RPCS[0]
        if "helius" in url and not budget_take(1, "rpc"):
            if pub: url = pub[a % len(pub)]
            else: continue
        try:
            _throttle(url)
            req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "onchain-intel/1.0"})
            r = json.loads(urllib.request.urlopen(req, timeout=30).read())
            if "result" in r:
                return r["result"]
        except Exception:
            pass
        time.sleep(0.6 * (a + 1))
    return None

def sigs(addr, limit_pages=200, before=None, until=None):
    """All signatures for addr, newest first (paged)."""
    out = []
    for _ in range(limit_pages):
        p = {"limit": 1000}
        if before: p["before"] = before
        if until: p["until"] = until
        r = rpc("getSignaturesForAddress", [addr, p])
        if not r: break
        out += r
        before = r[-1]["signature"]
        if len(r) < 1000: break
    return out

def tx(sig):
    fn = os.path.join(CACHE, sig + ".json")
    if os.path.exists(fn):
        try: return json.load(open(fn))
        except Exception: pass
    r = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
    if r:
        json.dump(r, open(fn, "w"))
    return r

def deltas(t, mint):
    """Per-owner token delta for mint, and per-owner SOL delta (native + WSOL), signers."""
    m = t["meta"]; keys = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]
    signers = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"] if k.get("signer")]
    tok, wsol, acct = {}, {}, {}
    for side, sgn in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for b in m.get(side) or []:
            o = b.get("owner"); amt = float(b["uiTokenAmount"]["uiAmount"] or 0)
            if b["mint"] == mint:
                tok[o] = tok.get(o, 0) + sgn * amt; acct[o] = keys[b["accountIndex"]]
            elif b["mint"] == WSOL:
                wsol[o] = wsol.get(o, 0) + sgn * amt
    sol = {}
    for i, k in enumerate(keys):
        d = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
        if d: sol[k] = d
    return tok, sol, wsol, signers, acct
