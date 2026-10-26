#!/usr/bin/env python3
"""runner-radar grade: PAPER ONLY. For each past signal, measure what actually happened
and simulate a hypothetical $5 bet (-25% stop, sell half at 2x). Rewrites outcomes.csv."""
import argparse, csv, json, os, statistics, time, datetime as dt
from common import BASE, get_json, f, dex_tokens, read_jsonl

SIGNALS = os.path.join(BASE, "signals.jsonl")
OUT = os.path.join(BASE, "outcomes.csv")
STATE = os.path.join(BASE, "grade_state.json")   # max/min prices seen by fallback polling
CHECKS = [("1h", 3600), ("4h", 4 * 3600), ("24h", 24 * 3600)]
HORIZON = 24 * 3600

def ohlcv(pool, since_s):
    """GeckoTerminal 5-minute candles (USD, base token), oldest first, from signal time on."""
    r = get_json(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute"
                 f"?aggregate=5&limit=300&currency=usd&token=base")
    try:
        rows = r["data"]["attributes"]["ohlcv_list"]
    except Exception:
        return None
    rows = sorted((int(c[0]), f(c[1]), f(c[2]), f(c[3]), f(c[4])) for c in rows)
    # only candles that START after the signal, so pre-signal highs/lows never count
    return [c for c in rows if c[0] >= since_s and c[0] <= since_s + HORIZON] or None

def simulate(entry, candles, bet, stop, tp, fee, matured=True):
    """Walk candles. Same-candle stop & 2x: assume the STOP hit first (conservative)."""
    size, cash, half_sold, exit_note = bet * (1 - fee), 0.0, False, "open"
    units = size / entry
    for _, o, h, l, c in candles:
        if l <= entry * (1 + stop):
            cash += units * entry * (1 + stop) * (1 - fee); units = 0
            exit_note = "stopped after 2x" if half_sold else "stopped"
            break
        if not half_sold and h >= entry * tp:
            sell = units / 2
            cash += sell * entry * tp * (1 - fee); units -= sell; half_sold = True
    if units:
        last = candles[-1][4]
        cash += units * last * (1 - fee)
        exit_note = ("2x half sold, rest " if half_sold else "") + (("marked @24h" if matured else "open, marked now") if exit_note == "open" else exit_note)
    return cash - bet, half_sold, exit_note

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bet", type=float, default=5.0)
    ap.add_argument("--stop", type=float, default=-0.25)
    ap.add_argument("--tp", type=float, default=2.0)
    ap.add_argument("--fee", type=float, default=0.02, help="per buy and per sell (copyfomo charges 2%%)")
    a = ap.parse_args()
    sigs = read_jsonl(SIGNALS)
    if not sigs:
        print("no signals yet; run scan.py first"); return
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    now = time.time()
    cur = {}
    for p in dex_tokens("solana", [s["token"] for s in sigs]):
        t = (p.get("baseToken") or {}).get("address")
        if t and (t not in cur or f((p.get("liquidity") or {}).get("usd")) > cur[t][1]):
            cur[t] = (f(p.get("priceUsd")), f((p.get("liquidity") or {}).get("usd")))
    rows = []
    for s in sigs:
        t0 = dt.datetime.fromisoformat(s["ts"]).timestamp()
        age = now - t0
        entry = s["price"]
        price_now, liq_now = cur.get(s["token"], (0.0, 0.0))
        st = state.setdefault(s["token"], {"max": entry, "min": entry})
        if price_now:
            st["max"], st["min"] = max(st["max"], price_now), min(st["min"], price_now)
        candles = ohlcv(s["pair"], t0) if entry else None
        r = {"token": s["token"], "symbol": s["symbol"], "signal_ts": s["ts"], "score": s["score"],
             "entry_price": entry, "entry_mcap": round(s["mcap"]), "hours_since": round(age / 3600, 2),
             "current_ret": round(price_now / entry - 1, 3) if price_now and entry else "",
             "liq_now": round(liq_now), "url": s["url"]}
        if candles is None and entry and age < 600:
            pass  # too fresh for a full 5m candle; falls back to polled price
        if candles:
            r["method"] = "ohlcv5m"
            for name, secs in CHECKS:
                cs = [c for c in candles if c[0] <= t0 + secs]
                r[f"ret_{name}"] = round(cs[-1][4] / entry - 1, 3) if age >= secs and cs else ""
                r[f"max_{name}"] = round(max(c[2] for c in cs) / entry - 1, 3) if cs else ""
            r["max_ret"] = round(max(c[2] for c in candles) / entry - 1, 3)
            r["min_ret"] = round(min(c[3] for c in candles) / entry - 1, 3)
            pnl, half, note = simulate(entry, candles, a.bet, a.stop, a.tp, a.fee, age >= HORIZON)
        else:
            # fallback: only prices we've seen when grade.py ran (coarse!)
            r["method"] = "polled"
            for name, secs in CHECKS:
                r[f"ret_{name}"] = ""; r[f"max_{name}"] = ""
            r["max_ret"] = round(st["max"] / entry - 1, 3) if entry else ""
            r["min_ret"] = round(st["min"] / entry - 1, 3) if entry else ""
            mx, mn = f(r["max_ret"]), f(r["min_ret"])
            if mn <= a.stop:
                pnl, half, note = a.bet * ((1 + a.stop) * (1 - a.fee) ** 2 - 1), False, "stopped (polled)"
            elif mx >= a.tp - 1:
                rest = 1 + f(r["current_ret"])
                pnl = a.bet * (1 - a.fee) * (0.5 * a.tp + 0.5 * rest) * (1 - a.fee) - a.bet; half, note = True, "2x (polled)"
            else:
                pnl, half, note = a.bet * ((1 + f(r["current_ret"])) * (1 - a.fee) ** 2 - 1), False, "marked (polled)"
        r["hit_2x"] = int(f(r["max_ret"]) >= a.tp - 1)
        r["bet_pnl"], r["bet_exit"] = round(pnl, 2), note
        rows.append(r)
    json.dump(state, open(STATE, "w"))
    cols = ["signal_ts", "symbol", "score", "entry_mcap", "hours_since", "ret_1h", "ret_4h", "ret_24h",
            "max_1h", "max_4h", "max_24h", "max_ret", "min_ret", "current_ret", "hit_2x", "bet_pnl", "bet_exit",
            "liq_now", "method", "entry_price", "token", "url"]
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)

    for r in rows:
        print(f"{r['symbol']:<12} score {r['score']:5.1f} {r['hours_since']:5.1f}h  max {f(r['max_ret']):+7.0%}  "
              f"min {f(r['min_ret']):+6.0%}  now {f(r['current_ret']):+6.0%}  bet {r['bet_pnl']:+6.2f}  {r['bet_exit']}")
    n = len(rows)
    matured = [r for r in rows if r["hours_since"] >= 24]
    def med(key, rs):
        v = [f(r[key]) for r in rs if r[key] != ""]
        return f"{statistics.median(v):+.0%} (n={len(v)})" if v else "n/a"
    tot = sum(r["bet_pnl"] for r in rows)
    print(f"\nSignals: {n} ({len(matured)} fully matured >=24h)")
    print(f"Hit 2x (max price >= 2x entry so far): {sum(r['hit_2x'] for r in rows)}/{n} = {sum(r['hit_2x'] for r in rows)/n:.0%}")
    print(f"Median return  now: {med('current_ret', rows)}   @1h: {med('ret_1h', rows)}   @4h: {med('ret_4h', rows)}   @24h: {med('ret_24h', rows)}")
    print(f"Median max run-up: {med('max_ret', rows)}   median max drawdown: {med('min_ret', rows)}")
    print(f"Hypothetical ${a.bet:.0f}/signal, stop {a.stop:.0%}, sell half at {a.tp:.0f}x, {a.fee:.0%} fee each side: "
          f"total {tot:+.2f} on ${a.bet*n:.0f} staked ({tot/(a.bet*n):+.0%}); "
          f"wins {sum(r['bet_pnl']>0 for r in rows)}, losses {sum(r['bet_pnl']<=0 for r in rows)}")
    print("Approximation: entry = DexScreener price at signal time (real fills would be worse);"
          " path from GeckoTerminal 5-min candles, stop filled exactly at -25% (memecoins gap, so real stops"
          " fill worse), if a candle touches both stop and 2x the stop is assumed first; unsold remainder is"
          " marked at the last candle (<=24h). 'polled' rows have no candles and only know prices seen when grade.py ran.")

if __name__ == "__main__":
    main()
