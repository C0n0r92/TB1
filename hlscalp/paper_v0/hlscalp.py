#!/usr/bin/env python3
"""PAPER-ONLY Hyperliquid 15m scalper. Public info endpoints only. No orders, no keys, no AI.
Run every minute from cron (flock + timeout). State in state.json."""
import json, os, time, math, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import requests, numpy as np, pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
API = "https://api.hyperliquid.xyz/info"
CFG = dict(
    start_equity=84.0, risk=0.01, atr_mult_stop=1.5, max_lev=5, max_open=4,
    taker=0.00045, maker=0.00015, tp1_r=1.5, trail_atr=1.0, time_stop_h=6, day_stop=-0.06,
    exclude={"BTC", "ETH", "SOL", "HYPE", "XRP", "ZEC", "NEAR"},
    min_vol=20e6, max_spread=0.0005, universe_max=20, universe_refresh_h=3,
    funding_extreme=0.00005,  # per hour (~44%/yr) against the trade -> skip
    min_votes=2, fresh_bars=3, stale_entry_s=300, cooldown_bars=2, min_notional=10.0,
)
STRATS = ["SQZMOM", "EMA_ST", "VWAP_RSI", "UTBOT"]

def P(f): return os.path.join(D, f)
def now_ms(): return int(time.time() * 1000)
def iso(ms): return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def jlog(f, rec):
    rec = {"ts": iso(now_ms()), **rec}
    with open(P(f), "a") as fh: fh.write(json.dumps(rec) + "\n")

def post(body, tries=3):
    last = None
    for i in range(tries):
        try:
            r = requests.post(API, json=body, timeout=10)
            r.raise_for_status(); return r.json()
        except Exception as e:
            last = e; time.sleep(1 + i)
    raise RuntimeError(f"HL info failed {body.get('type')}: {last}")

def candles(coin, interval, ms_back):
    n = now_ms()
    raw = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": n - ms_back, "endTime": n}})
    df = pd.DataFrame(raw)
    if df.empty: return df
    for k in "ohlcv": df[k] = df[k].astype(float)
    df = df[df["T"] < n].reset_index(drop=True)  # closed candles only
    return df

# ---------------- indicators ----------------
def rma(s, n): return s.ewm(alpha=1 / n, adjust=False).mean()
def atr(df, n=14):
    pc = df.c.shift()
    tr = pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff(); up = rma(d.clip(lower=0), n); dn = rma(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))
def linreg_end(s, n):
    x = np.arange(n); xm = x.mean(); den = ((x - xm) ** 2).sum()
    def f(w):
        b = ((x - xm) * (w - w.mean())).sum() / den
        return w.mean() + b * (n - 1 - xm)
    return s.rolling(n).apply(f, raw=True)
def supertrend(df, n=10, m=3.0):
    a = atr(df, n).values; hl2 = ((df.h + df.l) / 2).values; c = df.c.values
    ub = hl2 + m * a; lb = hl2 - m * a; fu = ub.copy(); fl = lb.copy(); d = np.ones(len(c))
    for i in range(1, len(c)):
        fu[i] = ub[i] if (ub[i] < fu[i-1] or c[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = lb[i] if (lb[i] > fl[i-1] or c[i-1] < fl[i-1]) else fl[i-1]
        d[i] = 1 if c[i] > fu[i-1] else (-1 if c[i] < fl[i-1] else d[i-1])
    return pd.Series(d, index=df.index)

def recent(cond, k): return bool(cond.iloc[-k:].any())

def votes(df):
    """Each strategy votes +1 / -1 / 0 on the last closed 15m bar (fresh trigger within last k bars, state still valid)."""
    k = CFG["fresh_bars"]; c = df.c; v = {}
    # 1) LazyBear Squeeze Momentum: BB(20,2) inside KC(20,1.5) -> release, momentum sign & slope
    basis = c.rolling(20).mean(); dev = 2 * c.rolling(20).std(ddof=0)
    rng = (df.h - df.l).rolling(20).mean()  # LazyBear uses SMA of range (useTrueRange default true -> TR)
    tr = pd.concat([df.h - df.l, (df.h - c.shift()).abs(), (df.l - c.shift()).abs()], axis=1).max(axis=1)
    rng = tr.rolling(20).mean()
    sqz_on = (basis - dev > basis - 1.5 * rng) & (basis + dev < basis + 1.5 * rng)
    released = sqz_on.shift(1, fill_value=False) & ~sqz_on
    mid = ((df.h.rolling(20).max() + df.l.rolling(20).min()) / 2 + basis) / 2
    val = linreg_end(c - mid, 20)
    rel = recent(released, k) and not bool(sqz_on.iloc[-1])
    v["SQZMOM"] = 1 if (rel and val.iloc[-1] > 0 and val.iloc[-1] > val.iloc[-2]) else (-1 if (rel and val.iloc[-1] < 0 and val.iloc[-1] < val.iloc[-2]) else 0)
    # 2) EMA 9/21 cross confirmed by Supertrend(10,3)
    e9, e21 = ema(c, 9), ema(c, 21); st = supertrend(df)
    xup = (e9 > e21) & (e9.shift() <= e21.shift()); xdn = (e9 < e21) & (e9.shift() >= e21.shift())
    v["EMA_ST"] = 1 if (recent(xup, k) and e9.iloc[-1] > e21.iloc[-1] and st.iloc[-1] == 1) else (-1 if (recent(xdn, k) and e9.iloc[-1] < e21.iloc[-1] and st.iloc[-1] == -1) else 0)
    # 3) VWAP reclaim (UTC session VWAP) + RSI(14) momentum band
    day = pd.to_datetime(df.t, unit="ms").dt.date; tp = (df.h + df.l + c) / 3
    vw = (tp * df.v).groupby(day).cumsum() / df.v.groupby(day).cumsum().replace(0, np.nan)
    r = rsi(c)
    rup = (c > vw) & (c.shift() <= vw.shift()); rdn = (c < vw) & (c.shift() >= vw.shift())
    v["VWAP_RSI"] = 1 if (recent(rup, k) and c.iloc[-1] > vw.iloc[-1] and 50 < r.iloc[-1] < 70) else (-1 if (recent(rdn, k) and c.iloc[-1] < vw.iloc[-1] and 30 < r.iloc[-1] < 50) else 0)
    # 4) UT Bot Alerts (key=1, ATR 10)
    a = atr(df, 10).values * 1.0; cv = c.values; ts = np.zeros(len(cv)); ts[0] = cv[0]
    for i in range(1, len(cv)):
        p = ts[i-1]
        if cv[i] > p and cv[i-1] > p: ts[i] = max(p, cv[i] - a[i])
        elif cv[i] < p and cv[i-1] < p: ts[i] = min(p, cv[i] + a[i])
        elif cv[i] > p: ts[i] = cv[i] - a[i]
        else: ts[i] = cv[i] + a[i]
    tss = pd.Series(ts, index=df.index)
    buy = (c > tss) & (c.shift() <= tss.shift()); sell = (c < tss) & (c.shift() >= tss.shift())
    v["UTBOT"] = 1 if (recent(buy, k) and c.iloc[-1] > tss.iloc[-1]) else (-1 if (recent(sell, k) and c.iloc[-1] < tss.iloc[-1]) else 0)
    return {s: int(v[s]) for s in STRATS}, float(atr(df, 14).iloc[-1])

def trend_1h(h1):
    c = h1.c; e20, e50 = ema(c, 20), ema(c, 50)
    if c.iloc[-1] > e50.iloc[-1] and e20.iloc[-1] > e50.iloc[-1]: return 1
    if c.iloc[-1] < e50.iloc[-1] and e20.iloc[-1] < e50.iloc[-1]: return -1
    return 0

# ---------------- state ----------------
def load():
    if os.path.exists(P("state.json")): return json.load(open(P("state.json")))
    return {"cash": CFG["start_equity"], "open": {}, "universe": [], "uni_ts": 0, "last_bar": {}, "cooldown": {},
            "last_run": 0, "day": None, "day_start_eq": CFG["start_equity"], "halted_day": None, "started": now_ms()}
def save(s):
    tmp = P("state.json.tmp"); json.dump(s, open(tmp, "w"), indent=1); os.replace(tmp, P("state.json"))

def refresh_universe(s):
    meta, ctx = post({"type": "metaAndAssetCtxs"})
    cands = []
    for u, c in zip(meta["universe"], ctx):
        name = u["name"]
        if u.get("isDelisted") or name in CFG["exclude"]: continue
        vol = float(c.get("dayNtlVlm") or 0)
        if vol >= CFG["min_vol"]: cands.append((name, vol, float(c.get("funding") or 0), int(u.get("maxLeverage", 3)), int(u["szDecimals"])))
    def spread(n):
        try:
            b = post({"type": "l2Book", "coin": n}); bid = float(b["levels"][0][0]["px"]); ask = float(b["levels"][1][0]["px"])
            return (ask - bid) / ((ask + bid) / 2)
        except Exception: return None
    with ThreadPoolExecutor(6) as ex: sp = list(ex.map(spread, [c[0] for c in cands]))
    picked = sorted([dict(coin=c[0], vol=c[1], funding=c[2], maxlev=c[3], spread=x) for c, x in zip(cands, sp)
                     if x is not None and x <= CFG["max_spread"]], key=lambda d: -d["vol"])[:CFG["universe_max"]]
    s["universe"] = picked; s["uni_ts"] = now_ms()
    jlog("decisions.jsonl", {"event": "universe", "coins": [p["coin"] for p in picked], "n_candidates": len(cands),
                             "rejected_spread": [c[0] for c, x in zip(cands, sp) if x is None or x > CFG["max_spread"]]})

def equity(s, mids):
    u = 0.0
    for p in s["open"].values():
        m = float(mids.get(p["coin"], p["entry"])); u += (m - p["entry"]) * p["qty"] * p["dir"]
    return s["cash"] + u

def fill_cost(px, qty, spread, maker=False):
    fee = CFG["maker"] if maker else CFG["taker"]
    slip = 0 if maker else spread / 2
    return px * qty * (fee + slip)

def close_part(s, key, qty, px, reason, maker=False):
    p = s["open"][key]
    cost = fill_cost(px, qty, p["spread"], maker)
    pnl = (px - p["entry"]) * qty * p["dir"] - cost
    s["cash"] += pnl; p["qty"] -= qty; p["realized"] += pnl; p["fees"] += cost
    if p["qty"] <= 1e-12:
        r_mult = p["realized"] / p["risk_usd"]
        rec = {"event": "close", "coin": p["coin"], "dir": p["dir"], "entry": p["entry"], "exit": px, "reason": reason,
               "opened": iso(p["opened"]), "pnl_usd": round(p["realized"], 4), "R": round(r_mult, 3),
               "fees_funding_usd": round(p["fees"], 4), "votes": p["votes"], "tp1": p["tp1_done"]}
        jlog("trades.jsonl", rec); s["cooldown"][p["coin"]] = now_ms() + CFG["cooldown_bars"] * 900_000
        del s["open"][key]

def manage(s, mids, spreads):
    for key in list(s["open"].keys()):
        p = s["open"][key]
        try: df = candles(p["coin"], "1m", max(now_ms() - p["checked"], 120_000) + 60_000)
        except Exception as e:
            jlog("decisions.jsonl", {"event": "error", "where": "manage", "coin": p["coin"], "err": str(e)}); continue
        df = df[df.t >= p["checked"] - 60_000]
        d = p["dir"]
        for _, b in df.iterrows():
            if key not in s["open"]: break
            # funding: accrue hourly at entry-time rate (longs pay positive funding)
            hrs = (b.T - p["fund_ts"]) / 3_600_000
            if hrs >= 1:
                f = p["funding"] * math.floor(hrs) * b.c * p["qty"] * d
                s["cash"] -= f; p["realized"] -= f; p["fees"] += f; p["fund_ts"] += math.floor(hrs) * 3_600_000
            adverse = b.l if d == 1 else b.h; fav = b.h if d == 1 else b.l
            # stop first (conservative), then TP1, then trail update
            if (adverse - p["stop"]) * d <= 0:
                close_part(s, key, p["qty"], p["stop"], "trail" if p["tp1_done"] else "stop"); break
            if not p["tp1_done"] and (fav - p["tp1"]) * d >= 0:
                close_part(s, key, p["qty"] / 2, p["tp1"], "tp1", maker=True)
                p["tp1_done"] = True; p["stop"] = p["entry"]  # break-even after TP1
            if p["tp1_done"]:
                p["best"] = max(p["best"], fav) if d == 1 else min(p["best"], fav)
                trail = p["best"] - d * CFG["trail_atr"] * p["atr"]
                p["stop"] = max(p["stop"], trail) if d == 1 else min(p["stop"], trail)
            if b.T - p["opened"] >= CFG["time_stop_h"] * 3_600_000:
                close_part(s, key, p["qty"], b.c, "time"); break
            p["checked"] = int(b.T) + 1
        if key in s["open"]: s["open"][key]["checked"] = max(s["open"][key]["checked"], now_ms() - 60_000)

def main():
    s = load(); n = now_ms()
    gap = n - s["last_run"] if s["last_run"] else 0
    if gap > 180_000:
        jlog("gaps.jsonl", {"event": "gap", "from": iso(s["last_run"]), "to": iso(n), "minutes": round(gap / 60000, 1)})
    s["last_run"] = n
    today = iso(n)[:10]
    mids = post({"type": "allMids"})
    if s["day"] != today:
        s["day"] = today; s["day_start_eq"] = equity(s, mids)
    if n - s["uni_ts"] > CFG["universe_refresh_h"] * 3_600_000 or not s["universe"]:
        refresh_universe(s)
    uni = {u["coin"]: u for u in s["universe"]}
    manage(s, mids, uni)
    eq = equity(s, mids)
    if s["halted_day"] != today and eq <= s["day_start_eq"] * (1 + CFG["day_stop"]):
        s["halted_day"] = today
        for k in list(s["open"]): close_part(s, k, s["open"][k]["qty"], float(mids[s["open"][k]["coin"]]), "day_stop")
        jlog("decisions.jsonl", {"event": "day_stop", "equity": round(eq, 4), "day_start": round(s["day_start_eq"], 4)})
    # entries: only on freshly closed 15m bars
    bar_close = (n // 900_000) * 900_000  # most recent 15m boundary
    todo = [c for c in uni if s["last_bar"].get(c, 0) < bar_close]
    if todo:
        if n - bar_close > CFG["stale_entry_s"] * 1000:
            jlog("decisions.jsonl", {"event": "skip_stale", "bar_close": iso(bar_close), "late_s": (n - bar_close) // 1000, "coins": len(todo)})
            for c in todo: s["last_bar"][c] = bar_close
        else:
            def fetch(c):
                try: return c, candles(c, "15m", 250 * 900_000), candles(c, "1h", 120 * 3_600_000), None
                except Exception as e: return c, None, None, str(e)
            with ThreadPoolExecutor(5) as ex: res = list(ex.map(fetch, todo))
            # refresh live funding for filter
            try:
                meta, ctx = post({"type": "metaAndAssetCtxs"})
                fund = {u["name"]: float(x.get("funding") or 0) for u, x in zip(meta["universe"], ctx)}
            except Exception: fund = {}
            for c, m15, h1, err in res:
                s["last_bar"][c] = bar_close
                if err or m15 is None or len(m15) < 100 or h1 is None or len(h1) < 60:
                    jlog("decisions.jsonl", {"event": "error", "coin": c, "err": err or "short history"}); continue
                if int(m15["T"].iloc[-1]) + 1 != bar_close:
                    jlog("decisions.jsonl", {"event": "skip_stale", "coin": c, "last_candle_close": iso(int(m15["T"].iloc[-1]) + 1)}); continue
                vt, a = votes(m15); tr = trend_1h(h1)
                longs = sum(1 for x in vt.values() if x == 1); shorts = sum(1 for x in vt.values() if x == -1)
                sig = 1 if (longs >= CFG["min_votes"] and shorts == 0) else (-1 if (shorts >= CFG["min_votes"] and longs == 0) else 0)
                rec = {"event": "eval", "coin": c, "bar": iso(bar_close), "votes": vt, "trend1h": tr, "signal": sig}
                action = "none"
                if sig != 0:
                    f = fund.get(c, uni[c]["funding"]); u = uni[c]
                    if sig != tr: action = "skip_trend"
                    elif s["halted_day"] == today: action = "skip_day_stop"
                    elif any(p["coin"] == c for p in s["open"].values()): action = "skip_already_open"
                    elif s["cooldown"].get(c, 0) > n: action = "skip_cooldown"
                    elif len(s["open"]) >= CFG["max_open"]: action = "skip_max_open"
                    elif f * sig > CFG["funding_extreme"]: action = "skip_funding"
                    else:
                        mid = float(mids.get(c, m15.c.iloc[-1])); spr = u["spread"]
                        entry = mid * (1 + sig * spr / 2)  # taker cross
                        stop_d = CFG["atr_mult_stop"] * a
                        eq = equity(s, mids); risk_usd = eq * CFG["risk"]
                        qty = risk_usd / stop_d; notional = qty * entry
                        lev = min(CFG["max_lev"], u["maxlev"])
                        used = sum(p["qty"] * p["entry"] / p["lev"] for p in s["open"].values())
                        max_notional = max(0.0, (eq - used)) * lev
                        if notional > max_notional: qty = max_notional / entry; notional = qty * entry
                        if stop_d / entry > 0.8 / lev: action = "skip_stop_beyond_liq"
                        elif notional < CFG["min_notional"]: action = "skip_min_notional"
                        else:
                            fee = entry * qty * CFG["taker"]; s["cash"] -= fee
                            key = f"{c}-{bar_close}"
                            s["open"][key] = dict(coin=c, dir=sig, entry=entry, qty=qty, atr=a, stop=entry - sig * stop_d,
                                                  tp1=entry + sig * CFG["tp1_r"] * stop_d, tp1_done=False, best=entry,
                                                  risk_usd=qty * stop_d, opened=n, checked=n, fund_ts=n, funding=f,
                                                  spread=spr, lev=lev, realized=-fee, fees=fee, votes=vt)
                            action = "open"
                            jlog("trades.jsonl", {"event": "open", "coin": c, "dir": sig, "entry": entry, "qty": qty,
                                                  "notional": round(notional, 2), "stop": s["open"][key]["stop"],
                                                  "tp1": s["open"][key]["tp1"], "lev": lev, "votes": vt, "trend1h": tr})
                rec["action"] = action; jlog("decisions.jsonl", rec)
    summarize(s, mids); save(s)

def summarize(s, mids):
    tr = []
    if os.path.exists(P("trades.jsonl")):
        tr = [json.loads(l) for l in open(P("trades.jsonl")) if '"close"' in l]
        tr = [t for t in tr if t.get("event") == "close"]
    days = max((now_ms() - s["started"]) / 86_400_000, 1 / 24)
    per = {}
    for st in STRATS:
        sub = [t for t in tr if t["votes"].get(st, 0) == t["dir"]]
        per[st] = {"trades_voted": len(sub), "win_rate": round(sum(t["pnl_usd"] > 0 for t in sub) / len(sub), 3) if sub else None,
                   "avg_R": round(sum(t["R"] for t in sub) / len(sub), 3) if sub else None,
                   "pnl_usd": round(sum(t["pnl_usd"] for t in sub), 4)}
    evals = signals = 0
    if os.path.exists(P("decisions.jsonl")):
        for l in open(P("decisions.jsonl")):
            if '"eval"' in l:
                evals += 1; signals += ('"signal": 0' not in l)
    out = {"updated": iso(now_ms()), "paper_only": True, "started": iso(s["started"]), "days_running": round(days, 3),
           "start_equity": CFG["start_equity"], "equity": round(equity(s, mids), 4), "cash": round(s["cash"], 4),
           "open_positions": [{k: p[k] for k in ("coin", "dir", "entry", "stop", "tp1", "tp1_done", "qty")} for p in s["open"].values()],
           "closed_trades": len(tr), "trades_per_day": round(len(tr) / days, 2),
           "win_rate": round(sum(t["pnl_usd"] > 0 for t in tr) / len(tr), 3) if tr else None,
           "avg_R": round(sum(t["R"] for t in tr) / len(tr), 3) if tr else None,
           "pnl_after_fees_usd": round(sum(t["pnl_usd"] for t in tr), 4),
           "evals": evals, "signals_2plus": signals, "per_strategy": per,
           "universe": [u["coin"] for u in s["universe"]], "universe_updated": iso(s["uni_ts"]),
           "day_halted": s["halted_day"] == iso(now_ms())[:10]}
    tmp = P("summary.json.tmp"); json.dump(out, open(tmp, "w"), indent=1); os.replace(tmp, P("summary.json"))

if __name__ == "__main__":
    try: main()
    except Exception as e:
        jlog("decisions.jsonl", {"event": "fatal", "err": repr(e)}); raise
