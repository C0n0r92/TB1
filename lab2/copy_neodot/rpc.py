"""Free public Solana RPC (api.mainnet-beta.solana.com, no key) with disk cache + throttle. Read-only."""
import json, os, time, urllib.request, urllib.error, hashlib
U = "https://api.mainnet-beta.solana.com"
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
_last = [0.0]; GAP = float(os.environ.get("RPC_GAP", "0.12"))
def rpc(m, p, tries=8):
    for k in range(tries):
        dt = time.time() - _last[0]
        if dt < GAP: time.sleep(GAP - dt)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(U, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                         headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=40))
            if "error" in r and r["error"].get("code") in (429, -32429, -32005, -32004, -32014): raise RuntimeError(str(r["error"]))
            return r
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, TimeoutError, ConnectionError, OSError) as e:
            time.sleep(min(30, 1.5 * 2 ** k))
    raise RuntimeError(f"rpc failed {m}")
def tx(sig):
    f = os.path.join(D, "tx", sig + ".json")
    if os.path.exists(f): return json.load(open(f))
    r = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
    res = r.get("result")
    if res is not None: json.dump(res, open(f, "w"))
    return res
def sigs(addr, before, until, maxpages=40):
    """all signatures of addr strictly between until (older) and before (newer); cached."""
    key = hashlib.sha1(f"{addr}|{before}|{until}|{maxpages}".encode()).hexdigest()[:20]
    f = os.path.join(D, "sigs", key + ".json")
    if os.path.exists(f): return json.load(open(f))
    out = []; b = before; complete = False
    for _ in range(maxpages):
        p = {"limit": 1000}
        if b: p["before"] = b
        if until: p["until"] = until
        r = rpc("getSignaturesForAddress", [addr, p]).get("result") or []
        out += r
        if len(r) < 1000: complete = True; break
        b = r[-1]["signature"]
    o = dict(addr=addr, complete=complete, sigs=[dict(s=x["signature"], slot=x["slot"], t=x["blockTime"], err=x["err"] is not None) for x in out])
    json.dump(o, open(f, "w")); return o
