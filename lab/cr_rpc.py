"""Copy-replay (CR_) helpers. PAPER ONLY. Free public Solana RPC (api.mainnet-beta), read-only, sequential, >=1.2 s spacing,
hard back-off on 429 (selfcopy and bf_migrations share this IP). Everything cached under data/cr/."""
import json, os, time, urllib.request, urllib.error, fcntl
LAB = os.path.dirname(os.path.abspath(__file__)); CR = os.path.join(LAB, "data", "cr"); os.makedirs(CR, exist_ok=True)
RPC = "https://api.mainnet-beta.solana.com"
UA = {"User-Agent": "lab-paper-copyreplay/1.0", "Content-Type": "application/json"}
SPACING = 1.6; _sp = [2.5]; _last = [0.0]; STATS = {"ok": 0, "429": 0, "err": 0}
LOG = os.path.join(CR, "rpc_calls.log")
def rpc(method, params, tries=6):
    for i in range(tries):
        with open(os.path.join(CR, ".rpc_lock"), "a+") as lf:          # spacing shared by all CR processes
            fcntl.flock(lf, fcntl.LOCK_EX); lf.seek(0); t = lf.read().strip()
            last = float(t) if t else 0.0
            w = _sp[0] - (time.time() - last)
            if w > 0: time.sleep(w)
            lf.seek(0); lf.truncate(); lf.write(f"{time.time():.3f}"); lf.flush()
        try:
            req = urllib.request.Request(RPC, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers=UA)
            r = json.loads(urllib.request.urlopen(req, timeout=45).read())
            with open(LOG, "a") as fh: fh.write(f"{time.time():.1f} {method}\n")
            if "result" in r:
                STATS["ok"] += 1; _sp[0] = max(SPACING, _sp[0] - 0.02); return r["result"]
            STATS["err"] += 1; e = r.get("error", {})
            if e.get("code") in (-32009, -32007, -32004, -32020): return None     # pruned / skipped / not found
            time.sleep(4 * (i + 1))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                STATS["429"] += 1; _sp[0] = min(5.0, _sp[0] + 0.5)
                with open(LOG, "a") as fh: fh.write(f"{time.time():.1f} 429 {method}\n")
                time.sleep(10 * (i + 1)); continue
            STATS["err"] += 1; time.sleep(5 * (i + 1))
        except Exception:
            STATS["err"] += 1; time.sleep(5 * (i + 1))
    return "FAIL"

TXC = os.path.join(CR, "tx")
os.makedirs(TXC, exist_ok=True)
def get_tx(sig):
    p = os.path.join(TXC, sig[:2], sig + ".json")
    if os.path.exists(p):
        try: return json.load(open(p))
        except ValueError: pass
    r = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}])
    if r == "FAIL": return None
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(r, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
    return r

WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"; USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
def parse_swap(tx, wallet):
    """Same logic as selfcopy.parse_swap: wallet's single token delta vs its SOL+WSOL / USDC+USDT delta."""
    if not tx or tx.get("meta") is None or tx["meta"].get("err"): return None
    m = tx["meta"]; msg = tx["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    tok, pre_bal = {}, {}
    for side, sg in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for b in m.get(side) or []:
            if b.get("owner") != wallet: continue
            a = float(b["uiTokenAmount"]["uiAmountString"] or 0)
            tok[b["mint"]] = tok.get(b["mint"], 0) + sg * a
            if sg == -1: pre_bal[b["mint"]] = pre_bal.get(b["mint"], 0) + a
    sol = 0.0
    if wallet in keys:
        i = keys.index(wallet); sol = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
        if i == 0: sol += m.get("fee", 0) / 1e9
    sol += tok.pop(WSOL, 0); usd_q = tok.pop(USDC, 0) + tok.pop(USDT, 0)
    moved = {k: v for k, v in tok.items() if abs(v) > 1e-12}
    if len(moved) != 1: return None
    mint, d = next(iter(moved.items()))
    return dict(mint=mint, tokens=d, sol=sol, usdq=usd_q, pre_bal=pre_bal.get(mint, 0.0), bt=tx.get("blockTime"), slot=tx.get("slot"))
