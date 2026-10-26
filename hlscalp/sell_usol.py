#!/usr/bin/env python3
"""One-shot: sell ALL USOL in the account's spot wallet to USDC on HL spot (@156), IOC limit 0.5% under best bid.
Uses the trade-only API wallet from perpbot/.env (never printed). Prints USDC received."""
import os, sys, math, time, json
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from eth_account import Account
B = "https://api.hyperliquid.xyz"; ACC = os.environ["HL_ACCOUNT"].strip()
w = Account.from_key(os.environ.pop("HL_API_KEY").strip())
if w.address.lower() == ACC.lower(): sys.exit("refusing main key")
info = Info(B, skip_ws=True); ex = Exchange(w, B, account_address=ACC)
bal = {b["coin"]: b for b in info.spot_user_state(ACC)["balances"]}
usol = float(bal.get("USOL", {}).get("total", 0)) - float(bal.get("USOL", {}).get("hold", 0))
usdc0 = float(bal["USDC"]["total"])
sz = math.floor(usol * 1000) / 1000
if sz < 0.01: sys.exit(f"no USOL to sell ({usol})")
bid = float(info.l2_snapshot("@156")["levels"][0][0]["px"]); lim = float(f"{bid*0.995:.5g}")
t0 = int(time.time() * 1000)
r = ex.order("@156", False, sz, lim, {"limit": {"tif": "Ioc"}})
print("order:", json.dumps(r.get("response", r))[:400])
time.sleep(3)
fills = [f for f in info.user_fills_by_time(ACC, t0 - 1000) if f["coin"] == "@156"]
got = sum(float(f["px"]) * float(f["sz"]) for f in fills) - sum(float(f["fee"]) for f in fills if f.get("feeToken") == "USDC")
bal2 = {b["coin"]: b for b in info.spot_user_state(ACC)["balances"]}
usdc1 = float(bal2["USDC"]["total"])
print(json.dumps({"usol_sold": sum(float(f["sz"]) for f in fills), "avg_px": (sum(float(f["px"]) * float(f["sz"]) for f in fills) / max(1e-9, sum(float(f["sz"]) for f in fills))),
                  "usdc_from_fills_net": round(got, 4), "usdc_delta": round(usdc1 - usdc0, 4), "usol_left": bal2.get("USOL", {}).get("total", "0")}))
