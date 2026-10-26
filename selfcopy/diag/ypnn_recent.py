"""read-only: parse ypnn-day's latest sigs with selfcopy.parse_swap; dry-run topup eligibility + LIVE filters (no state writes)."""
import json, time, sys, urllib.request
sys.path.insert(0, "/workspace/selfcopy")
import selfcopy as S, live as L
W = "YpnnUu1ZPHpAzy4xggEd5pBTbu1aDayXuARsYsavNs9"
UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 selfcopy-diag"}
def rpc(m, p):
    for u in ("https://solana-rpc.publicnode.com", "https://api.mainnet-beta.solana.com"):
        for a in range(3):
            try:
                j = json.load(urllib.request.urlopen(urllib.request.Request(u, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), headers=UA), timeout=25))
                if j.get("result") is not None: return j["result"]
            except Exception: time.sleep(1 + a)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
sigs = rpc("getSignaturesForAddress", [W, {"limit": N}]) or []
b = S.Bot.__new__(S.Bot); px = None
def solpx():
    global px
    if px is None:
        try: px = float(json.load(urllib.request.urlopen(urllib.request.Request("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", headers=UA)))["solana"]["usd"])
        except Exception: px = float(json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.dexscreener.com/tokens/v1/solana/{S.WSOL}", headers=UA)))[0]["priceUsd"])
    return px
b.sol_price = solpx
state = json.load(open("/workspace/selfcopy/state.json"))
b.state = state
sess = L.load_session(S.HERE)
print("session", sess["key"], "topup_entry", sess["topup_entry"], "ypnn rotation LIVE:", sess["manual_live"])
rows = []
for s in reversed(sigs):
    if s.get("err"): continue
    tx = rpc("getTransaction", [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]); time.sleep(0.2)
    sw = b.parse_swap(tx, W, s["signature"])
    if not sw:
        # classify non-swaps
        m = (tx or {}).get("meta") or {}
        d = {}
        for side, sg in (("preTokenBalances", -1), ("postTokenBalances", 1)):
            for x in m.get(side) or []:
                if x.get("owner") == W: d[x["mint"][:6]] = d.get(x["mint"][:6], 0) + sg * float(x["uiTokenAmount"]["uiAmountString"] or 0)
        rows.append((s.get("blockTime"), "non-swap", {k: round(v, 2) for k, v in d.items() if abs(v) > 1e-9}))
        continue
    rows.append((sw["block_time"], sw["side"], sw))
info = {}
for bt, kind, sw in rows:
    t = time.strftime("%H:%M:%S", time.gmtime(bt or 0))
    if kind != "buy":
        print(t, kind, (sw["mint"][:8], sw["usd"]) if isinstance(sw, dict) and "mint" in sw else sw); continue
    m = sw["mint"]
    if m not in info:
        try: info[m] = S.Bot.token_info(b, m)
        except Exception as e: info[m] = None
    i = info[m] or {}
    v2 = L.v2_filters(mcap=i.get("mcap"), liq=i.get("liq"), age_s=i.get("age_s"), leader_age_s=0, chase=0)
    key, why = b.topup_eligible("ypnn-day", m, t=bt)
    print(t, "BUY", m[:8], f"${sw['usd']}", "pre_bal", round(sw["pre_bal"], 1), "| mcap", i.get("mcap"), "liq", i.get("liq"),
          "age_min", round((i.get("age_s") or 0) / 60), "| v2 fails (at fresh signal):", v2 or "none", "| topup:", key or why,
          "=> WOULD EMIT ENTRY" if (key and sw["usd"] >= 50 and not v2) else "")
