"""Hyperliquid TESTNET runner for the 'Vote 3-of-4' 4h blend. Run once per closed 4h candle (e.g. cron at HH:00:30 for 0/4/8/12/16/20 UTC).
Modes:  --signal  : public data only, no keys, prints target positions (safe; default)
        --trade   : places orders on Hyperliquid TESTNET only (needs env vars from testnet_config.json). Mainnet is refused.
Orders: market (IOC) entry/exit with reduce-only exchange-side stop-market at entry -/+ 1.5*ATR(14)."""
import json, os, sys, ccxt, pandas as pd
from backtest import STRATS, vote_fn, atr
cfg = json.load(open(os.path.join(os.path.dirname(__file__), "testnet_config.json")))
TRADE = "--trade" in sys.argv
ex = ccxt.hyperliquid({"walletAddress": os.getenv(cfg["env_wallet_address"]) if TRADE else None,
                       "privateKey": os.getenv(cfg["env_agent_private_key"]) if TRADE else None})
ex.set_sandbox_mode(True)
assert cfg["sandbox"] and "testnet" in ex.urls["api"]["public"], "refusing: testnet only"
if TRADE and not (ex.walletAddress and ex.privateKey): sys.exit("set HL_TESTNET_WALLET_ADDRESS and HL_TESTNET_API_AGENT_KEY")
ex.load_markets(); sig_fn = vote_fn(list(STRATS), 3)

def candles(sym):
    # testnet prices are thin/odd; signals use MAINNET public candles (read-only), orders go to testnet
    pub = ccxt.hyperliquid(); o = pub.fetch_ohlcv(sym, cfg["timeframe"], limit=500)
    df = pd.DataFrame(o, columns=["ts","open","high","low","close","volume"]); df["ts"] = pd.to_datetime(df.ts, unit="ms", utc=True)
    return df.set_index("ts").iloc[:-1]  # drop still-open candle -> closed candles only

equity = None
if TRADE:
    bal = ex.fetch_balance(); equity = float(bal["total"].get("USDC", 0)); print("testnet equity", equity)
for sym in cfg["symbols"]:
    df = candles(sym); d = sig_fn(df); a = atr(df)
    target, prev = int(d.iat[-1]), int(d.iat[-2]); px = df.close.iat[-1]; dist = cfg["stop_atr_mult"]*a.iat[-1]
    print(f"{sym} close={px:.2f} target={target} prev={prev} stop_dist={dist:.2f}")
    if not TRADE: continue
    pos = [p for p in ex.fetch_positions([sym]) if float(p.get("contracts") or 0) > 0]
    side_now = 0 if not pos else (1 if pos[0]["side"] == "long" else -1)
    if side_now and target != side_now:  # exit + cancel resting stop
        ex.cancel_all_orders(sym)
        ex.create_order(sym, "market", "sell" if side_now == 1 else "buy", float(pos[0]["contracts"]), px, {"reduceOnly": True}); side_now = 0
    if side_now == 0 and target != 0 and target != prev:
        eq = equity*cfg["capital_split"][sym]
        qty = min(cfg["risk_per_trade"]*eq/dist, cfg["max_leverage"]*eq/px); qty = float(ex.amount_to_precision(sym, qty))
        if qty*px < 10: print("  below HL $10 min notional, skip"); continue
        ex.set_leverage(cfg["max_leverage"], sym, {"marginMode": "isolated"})
        ex.create_order(sym, "market", "buy" if target == 1 else "sell", qty, px)
        stop = px - target*dist
        ex.create_order(sym, "market", "sell" if target == 1 else "buy", qty, stop, {"triggerPrice": stop, "reduceOnly": True})
        print(f"  opened {target} qty={qty} stop={stop:.2f}")
