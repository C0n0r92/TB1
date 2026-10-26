"""Phase 1: neodot round trips -> his exact buy/sell legs (tx, slot, blockTime) + pool/venue of each leg. Read-only inputs."""
import json, os, sys, base64, struct
import pandas as pd
sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc
W = "5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG"; WSOL = "So11111111111111111111111111111111111111112"
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"; PFEE = "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"
TE = bytes.fromhex("bddb7fd34ee661ee")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "legs.json")

def keys(t):
    k = [x["pubkey"] if isinstance(x, dict) else x for x in t["transaction"]["message"]["accountKeys"]]
    la = t["meta"].get("loadedAddresses") or {}
    return k + la.get("writable", []) + la.get("readonly", [])

def pump_events(t, mint=None):
    ev = []
    for l in t["meta"].get("logMessages") or []:
        if not l.startswith("Program data: "): continue
        try: d = base64.b64decode(l[14:])
        except Exception: continue
        if d[:8] != TE or len(d) < 8 + 32 + 17 + 32 + 40: continue
        import base58  # noqa
    return ev

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58(b):
    n = int.from_bytes(b, "big"); s = ""
    while n: n, r = divmod(n, 58); s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s

def trade_events(t):
    ev = []
    for l in t["meta"].get("logMessages") or []:
        if not l.startswith("Program data: "): continue
        try: d = base64.b64decode(l[14:])
        except Exception: continue
        if d[:8] != TE or len(d) < 129: continue
        o = 8; mint = b58(d[o:o+32]); o += 32
        sol, tok = struct.unpack_from("<QQ", d, o); o += 16; isb = d[o]; o += 1; user = b58(d[o:o+32]); o += 32
        ts, vs, vt, rs, rt = struct.unpack_from("<qQQQQ", d, o)
        ev.append(dict(mint=mint, sol=sol / 1e9, tok=tok / 1e6, buy=bool(isb), user=user, ts=ts, vsol=vs / 1e9, vtok=vt / 1e6, rsol=rs / 1e9, rtok=rt / 1e6))
    return ev

def pfee_bps(t):
    out = []
    for l in t["meta"].get("logMessages") or []:
        if l.startswith(f"Program return: {PFEE} "):
            d = base64.b64decode(l.split()[-1])
            if len(d) >= 24: out.append(struct.unpack_from("<QQQ", d, 0))
    return out

def tokbal(t, which):
    k = keys(t); out = {}
    for b in t["meta"].get(which) or []:
        out[k[b["accountIndex"]]] = (b["mint"], b.get("owner"), float(b["uiTokenAmount"]["uiAmountString"] or 0), b["uiTokenAmount"]["decimals"])
    return out

def pool_of(t, mint, user=W):
    """identify the venue the mint traded against in tx t. Returns dict(kind, vault_tok, sol_side, owner, pre/post reserves)."""
    k = keys(t); pre, post = tokbal(t, "preTokenBalances"), tokbal(t, "postTokenBalances")
    cand = []
    for a in set(pre) | set(post):
        m, own, *_ = (post.get(a) or pre.get(a))
        if m != mint or own == user: continue
        d = (post.get(a, (0, 0, 0))[2]) - (pre.get(a, (0, 0, 0))[2])
        cand.append((abs(d), a, own, d))
    if not cand: return None
    _, va, own, dtok = max(cand)
    ev = [e for e in trade_events(t) if e["mint"] == mint]
    if ev and PUMP in k:
        return dict(kind="pump_curve", vault_tok=va, owner=own, vsol=ev[-1]["vsol"], vtok=ev[-1]["vtok"], events=ev, fee_bps=pfee_bps(t))
    sol = []
    for a in set(pre) | set(post):
        m, o2, *_ = (post.get(a) or pre.get(a))
        if m == WSOL and o2 == own:
            sol.append((abs(post.get(a, (0, 0, 0))[2] - pre.get(a, (0, 0, 0))[2]), a, pre.get(a, (0, 0, 0))[2], post.get(a, (0, 0, 0))[2]))
    if not sol: return dict(kind="unknown", vault_tok=va, owner=own)
    _, sa, s0, s1 = max(sol)
    progs = sorted({i["programId"] for i in t["transaction"]["message"]["instructions"]} |
                   {x["programId"] for ii in t["meta"].get("innerInstructions") or [] for x in ii["instructions"]})
    return dict(kind="amm", vault_tok=va, vault_sol=sa, owner=own, sol_pre=s0, sol_post=s1,
                tok_pre=pre.get(va, (0, 0, 0))[2], tok_post=post.get(va, (0, 0, 0))[2], progs=progs, fee_bps=pfee_bps(t))

def main():
    tr = pd.read_csv("/workspace/onchain-intel/winners/trades.csv"); tr = tr[tr.wallet == W].sort_values("entry_time").reset_index(drop=True)
    wg = json.load(open(f"/workspace/scout/data/wg/{W}.json"))["tx"]
    allts = sorted(wg, key=lambda x: x["ts"])
    trips = []
    for i, r in tr.iterrows():
        t0 = int(pd.Timestamp(r.entry_time).timestamp()); t1 = int(pd.Timestamp(r.exit_time).timestamp())
        L = sorted([x for x in wg if r.mint in x["d"] and t0 <= x["ts"] <= t1], key=lambda x: x["ts"])
        legs = []
        for x in L:
            t = rpc.tx(x["sig"])
            if t is None: legs.append(dict(sig=x["sig"], ts=x["ts"], err="tx_missing")); continue
            p = pool_of(t, r.mint)
            legs.append(dict(sig=x["sig"], ts=t["blockTime"], slot=t["slot"], dtok=x["d"][r.mint], dsol=x["d"].get(WSOL, 0.0),
                             side="buy" if x["d"][r.mint] > 0 else "sell", fee=t["meta"]["fee"] / 1e9, pool=p))
        after = [x for x in allts if x["ts"] > t1 + 120]
        trips.append(dict(i=int(i), sym=r.symbol, mint=r.mint, entry_time=r.entry_time, exit_time=r.exit_time, t0=t0, t1=t1,
                          entry_sig=r.entry_sig, exit_sig=r.exit_sig, pnl_pct_gross=r.pnl_pct_gross, hold_min=r.hold_min,
                          size_in_sol=r.size_in_sol, legs=legs, before_sig=after[0]["sig"] if after else None))
        kinds = [(l["side"], (l.get("pool") or {}).get("kind"), (l.get("pool") or {}).get("owner", "")[:6]) for l in legs]
        print(i, r.symbol, len(legs), kinds, flush=True)
    json.dump(trips, open(OUT, "w"), indent=0, default=str)

if __name__ == "__main__":
    main()
