#!/usr/bin/env python3
"""Read-only Jupiter quote sampler to calibrate copier cost vs pool liquidity (PAPER research; /quote only, never /swap,
no wallet). Pumpswap pools from data/midcap/discovered.json (GeckoTerminal reserve_in_usd = pool liquidity at discovery).
Round trip per size: SOL->token ExactIn, then token->SOL for the quoted outAmount. Gentle: one call per 6 s (shared IP
with /workspace/selfcopy). Appends data/fs_quotes/quotes.jsonl; resumable (skips mint+size already done)."""
import json, math, os, time, urllib.request, urllib.error
LAB = os.path.dirname(os.path.abspath(__file__)); Q = os.path.join(LAB, "data", "fs_quotes", "quotes.jsonl")
SOL = "So11111111111111111111111111111111111111112"; USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
GAP = 6.0; _l = [0.0]
def q(inp, out, amt):
    for a in range(3):
        w = GAP - (time.time() - _l[0]); time.sleep(max(0, w)); _l[0] = time.time()
        u = f"https://lite-api.jup.ag/swap/v1/quote?inputMint={inp}&outputMint={out}&amount={int(amt)}&slippageBps=1500&swapMode=ExactIn"
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "lab-paper-backtest/1.0"}), timeout=20) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print("HTTP", e.code, u[:160], flush=True)
            if e.code == 429: time.sleep(20 * (a + 1)); continue
            return None
        except Exception as e: print("ERR", e, flush=True); time.sleep(3)
    return None
d = json.load(open(os.path.join(LAB, "data", "midcap", "discovered.json")))
ps = [x for x in d if x["dex"] == "pumpswap" and 8e3 <= x["liq"] <= 3e6 and (x["mcap"] or x["fdv"]) >= 3e4]
ps.sort(key=lambda x: x["liq"]); ps = ps[::max(1, len(ps) // 14)][:14]
done = set()
if os.path.exists(Q):
    for l in open(Q): r = json.loads(l); done.add((r["mint"], r["size"]))
j = q(SOL, USDC, 1e9); solpx = int(j["outAmount"]) / 1e6
print("SOL", solpx, "pools", len(ps), flush=True)
for x in ps:
    for size in (5, 13):
        if (x["mint"], size) in done: continue
        b = q(SOL, x["mint"], size / solpx * 1e9)
        if not b: continue
        s = q(x["mint"], SOL, int(b["outAmount"]))
        if not s: continue
        back = int(s["outAmount"]) / 1e9 * solpx
        rec = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), mint=x["mint"], sym=x["symbol"], liq=x["liq"], mcap=x["mcap"] or x["fdv"],
                   size=size, sol_px=solpx, back_usd=back, rt_loss=1 - back / size, buy_impact=float(b.get("priceImpactPct") or 0),
                   sell_impact=float(s.get("priceImpactPct") or 0), platform_fee=[b.get("platformFee"), s.get("platformFee")],
                   route_b="+".join(r["swapInfo"].get("label", "?") for r in b.get("routePlan", [])),
                   route_s="+".join(r["swapInfo"].get("label", "?") for r in s.get("routePlan", [])),
                   fee_b=[r["swapInfo"].get("feeAmount") for r in b.get("routePlan", [])], fee_mint_b=[r["swapInfo"].get("feeMint") for r in b.get("routePlan", [])],
                   in_b=int(b["inAmount"]), fee_s=[r["swapInfo"].get("feeAmount") for r in s.get("routePlan", [])], in_s=int(s["inAmount"]))
        open(Q, "a").write(json.dumps(rec) + "\n")
        print(x["symbol"], round(x["liq"]), size, f"rt {rec['rt_loss'] * 100:.2f}%", rec["route_b"], flush=True)
print("DONE")
