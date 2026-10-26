#!/usr/bin/env python3
"""hlscalp - Hyperliquid 15m scalper (separate from /workspace/perpbot).
  python scalper.py --dry-run   public data only, no key loaded, no orders: prints universe, votes, sizing.
  python scalper.py             LIVE (only if config live_enabled=true and base_capital_usd>0). Needs HL_ACCOUNT + HL_API_KEY
                                (trade-only API wallet key; never printed/logged).
Isolation from perpbot: never trades perpbot coins; only manages its own orders (cloid prefix 0x5ca1...) on its own coins;
sizes off its own capital = base_capital_usd + its realized PnL - fees + funding + its uPnL (written to capital.json, which
perpbot subtracts from account equity)."""
import json, os, sys, time, math, signal, traceback, secrets
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, requests

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda f: os.path.join(HERE, f)
cfg = json.load(open(P("config.json")))
DRY = "--dry-run" in sys.argv
PERP = set(cfg["perp_bot_coins"]); PREFIX = "0x" + cfg["cloid_prefix"]
KILL = P("KILL"); STATE = P("state.json"); STATUS = P("status.json"); CAPF = P("capital.json")
STRATS = ["SQZMOM", "BBKC_BRK", "EMA9_21", "VWAP_RSI", "UTBOT"]

def now(): return datetime.now(timezone.utc)
def nms(): return int(time.time() * 1000)
def iso(ms): return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def log(m):
    line = f"{now():%Y-%m-%d %H:%M:%S}Z {m}"
    if DRY: print(line)
    else:
        with open(P("bot.log"), "a") as f: f.write(line + "\n")
def jl(f, rec):
    with open(P(f), "a") as fh: fh.write(json.dumps({"ts": iso(nms()), **rec}) + "\n")
def wjson(path, obj):
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w"), indent=1, default=str); os.replace(tmp, path)

# ---------- network hardening (same approach as perpbot 2026-10-25): every HL HTTP call has (5s,10s) timeout ----------
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.utils.types import Cloid
from hyperliquid.api import API
from hyperliquid.utils.error import ClientError
HTTP_TIMEOUT = (5, 10); HEARTBEAT = P(".heartbeat"); _HB = [0.0]
def _new_session(api):
    try: api.session.close()
    except Exception: pass
    api.session = requests.Session(); api.session.headers.update({"Content-Type": "application/json"})
_raw = API.post
def _safe(self, url_path, payload=None):
    if time.time() - getattr(self, "_last_ok", time.time()) > 60: _new_session(self)
    self.timeout = HTTP_TIMEOUT; is_ex = url_path == "/exchange"
    for k in range(4):
        try:
            r = _raw(self, url_path, payload); self._last_ok = time.time()
            if time.time() - _HB[0] > 10:
                _HB[0] = time.time()
                try: open(HEARTBEAT, "w").write(str(int(_HB[0])))
                except Exception: pass
            return r
        except requests.exceptions.RequestException as e:
            # orders retry ONLY if the connection was never made -> an order can never be sent twice
            retry = isinstance(e, requests.exceptions.ConnectTimeout) if is_ex else isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError))
            _new_session(self)
            if not retry or k == 3: raise
            log(f"network {type(e).__name__} on {url_path}, retry {k+1}/3"); time.sleep(2 ** k)
API.post = _safe
_ipost = Info.post
def _iretry(self, path, payload=None):
    for k in range(5):
        try: return _ipost(self, path, payload)
        except ClientError as e:
            if e.status_code != 429 or k == 4: raise
            time.sleep(2 ** (k + 1))
Info.post = _iretry
BASE = constants.MAINNET_API_URL
info = Info(BASE, skip_ws=True)
META = {}
def load_meta():
    m, ctx = info.meta_and_asset_ctxs()
    META.clear()
    for u, c in zip(m["universe"], ctx): META[u["name"]] = {**u, **c}
    return META

# ---------- candles + indicators ----------
def candles(coin, interval, bars):
    ms = {"15m": 900_000, "1h": 3_600_000}[interval]; end = nms()
    raw = info.candles_snapshot(coin, interval, end - bars * ms, end)
    df = pd.DataFrame(raw)
    if df.empty: return df
    for k in "ohlcv": df[k] = df[k].astype(float)
    return df[df["T"] < end].reset_index(drop=True)   # closed candles only
def rma(s, n): return s.ewm(alpha=1 / n, adjust=False).mean()
def tr(df):
    pc = df.c.shift(); return pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)
def atr(df, n=14): return rma(tr(df), n)
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff(); up = rma(d.clip(lower=0), n); dn = rma(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))
def linreg_end(s, n):
    x = np.arange(n); xm = x.mean(); den = ((x - xm) ** 2).sum()
    return s.rolling(n).apply(lambda w: w.mean() + ((x - xm) * (w - w.mean())).sum() / den * (n - 1 - xm), raw=True)
def recent(cond, k): return bool(cond.iloc[-k:].any())

def votes(df):
    """+1/-1/0 per strategy on the last closed 15m bar: a fresh trigger within the last k bars whose state still holds."""
    k = cfg["fresh_bars"]; c = df.c; v = {}
    basis = c.rolling(20).mean(); dev = 2 * c.rolling(20).std(ddof=0); rng = tr(df).rolling(20).mean()
    up_bb, lo_bb = basis + dev, basis - dev; up_kc, lo_kc = basis + 1.5 * rng, basis - 1.5 * rng
    sqz_on = (lo_bb > lo_kc) & (up_bb < up_kc)
    # 1) LazyBear Squeeze Momentum: squeeze just released, momentum histogram on the right side and growing
    released = sqz_on.shift(1, fill_value=False) & ~sqz_on
    mom = linreg_end(c - ((df.h.rolling(20).max() + df.l.rolling(20).min()) / 2 + basis) / 2, 20)
    rel = recent(released, k) and not bool(sqz_on.iloc[-1])
    v["SQZMOM"] = 1 if rel and mom.iloc[-1] > 0 and mom.iloc[-1] > mom.iloc[-2] else (-1 if rel and mom.iloc[-1] < 0 and mom.iloc[-1] < mom.iloc[-2] else 0)
    # 2) Bollinger/Keltner squeeze breakout: squeeze in the last 8 bars, then a close outside the Bollinger band
    was_sqz = sqz_on.rolling(8).max().shift(1).fillna(0) > 0
    bo_up = was_sqz & (c > up_bb); bo_dn = was_sqz & (c < lo_bb)
    v["BBKC_BRK"] = 1 if recent(bo_up, k) and c.iloc[-1] > basis.iloc[-1] else (-1 if recent(bo_dn, k) and c.iloc[-1] < basis.iloc[-1] else 0)
    # 3) EMA 9/21 cross, price on the right side of both
    e9, e21 = ema(c, 9), ema(c, 21)
    xu = (e9 > e21) & (e9.shift() <= e21.shift()); xd = (e9 < e21) & (e9.shift() >= e21.shift())
    v["EMA9_21"] = 1 if recent(xu, k) and c.iloc[-1] > e9.iloc[-1] > e21.iloc[-1] else (-1 if recent(xd, k) and c.iloc[-1] < e9.iloc[-1] < e21.iloc[-1] else 0)
    # 4) VWAP reclaim (UTC session) + RSI(14) momentum band
    day = pd.to_datetime(df.t, unit="ms").dt.date; tp = (df.h + df.l + c) / 3
    vw = (tp * df.v).groupby(day).cumsum() / df.v.groupby(day).cumsum().replace(0, np.nan); r = rsi(c)
    ru = (c > vw) & (c.shift() <= vw.shift()); rd = (c < vw) & (c.shift() >= vw.shift())
    v["VWAP_RSI"] = 1 if recent(ru, k) and c.iloc[-1] > vw.iloc[-1] and 50 < r.iloc[-1] < 70 else (-1 if recent(rd, k) and c.iloc[-1] < vw.iloc[-1] and 30 < r.iloc[-1] < 50 else 0)
    # 5) UT Bot Alerts (key 1, ATR 10)
    a = atr(df, 10).values; cv = c.values; ts = np.zeros(len(cv)); ts[0] = cv[0]
    for i in range(1, len(cv)):
        p = ts[i - 1]
        if cv[i] > p and cv[i - 1] > p: ts[i] = max(p, cv[i] - a[i])
        elif cv[i] < p and cv[i - 1] < p: ts[i] = min(p, cv[i] + a[i])
        else: ts[i] = cv[i] - a[i] if cv[i] > p else cv[i] + a[i]
    tss = pd.Series(ts, index=df.index)
    bu = (c > tss) & (c.shift() <= tss.shift()); se = (c < tss) & (c.shift() >= tss.shift())
    v["UTBOT"] = 1 if recent(bu, k) and c.iloc[-1] > tss.iloc[-1] else (-1 if recent(se, k) and c.iloc[-1] < tss.iloc[-1] else 0)
    return {s: int(v[s]) for s in STRATS}

def trend_1h_old(h1):   # pre-2026-10-25 20:xx definition, kept for reference/logging comparisons only
    c = h1.c; e20, e50 = ema(c, 20), ema(c, 50)
    if c.iloc[-1] > e50.iloc[-1] and e20.iloc[-1] > e50.iloc[-1]: return 1
    if c.iloc[-1] < e50.iloc[-1] and e20.iloc[-1] < e50.iloc[-1]: return -1
    return 0
def trend_1h(h1):
    """2026-10-25 user-approved 'faster 1h trend': slope of the Hull MA(21) on closed 1h candles.
    +1 rising, -1 falling, 0 only if flat. Gate unchanged: CORE trades need trend == direction."""
    h = hma(h1.c, 21); d = h.iloc[-1] - h.iloc[-2]
    if not np.isfinite(d) or d == 0: return 0
    return 1 if d > 0 else -1

# ---------- 2026-10-25 v3: STATE confirmers (15m), TradingView-standard, none used by the perp bot ----------
ALL_CONFIRMERS = ["MACD_HIST", "HMA21_SLOPE", "RSI50", "ADX_DMI", "PSAR", "VWAP_SIDE"]   # computed + logged
CONFIRMERS = cfg.get("confirmers", ["MACD_HIST", "HMA21_SLOPE", "ADX_DMI", "PSAR", "VWAP_SIDE"])   # counted (RSI50 dropped: redundant with MACD)
def wma(s, n):
    w = np.arange(1, n + 1); return s.rolling(n).apply(lambda x: (x * w).sum() / w.sum(), raw=True)
def hma(s, n=21): return wma(2 * wma(s, n // 2) - wma(s, n), int(round(np.sqrt(n))))
def dmi(df, n=14):
    up = df.h.diff(); dn = -df.l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0); mdm = dn.where((dn > up) & (dn > 0), 0.0); a = rma(tr(df), n)
    pdi = 100 * rma(pdm, n) / a; mdi = 100 * rma(mdm, n) / a
    return rma(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan), n), pdi, mdi
def psar_side(df, step=0.02, mx=0.2):
    """Wilder Parabolic SAR (0.02/0.02/0.2): +1 if price is above the SAR on the last bar, -1 if below."""
    h, l = df.h.values, df.l.values; up = True; sar = l[0]; ep = h[0]; af = step
    for i in range(1, len(h)):
        sar = sar + af * (ep - sar)
        if up:
            sar = min(sar, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < sar: up = False; sar = ep; ep = l[i]; af = step
            elif h[i] > ep: ep = h[i]; af = min(af + step, mx)
        else:
            sar = max(sar, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > sar: up = True; sar = ep; ep = h[i]; af = step
            elif l[i] < ep: ep = l[i]; af = min(af + step, mx)
    return 1 if up else -1
def confirmers(df):
    """+1/-1/0 per confirmer = the CURRENT direction on the last closed 15m bar (state, not a fresh event)."""
    c = df.c; v = {}; sg = lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
    m = ema(c, 12) - ema(c, 26); v["MACD_HIST"] = sg(float((m - ema(m, 9)).iloc[-1]))
    hm = hma(c, 21); v["HMA21_SLOPE"] = sg(float(hm.iloc[-1] - hm.iloc[-2]))
    v["RSI50"] = sg(float(rsi(c).iloc[-1]) - 50)
    ax, pdi, mdi = dmi(df); v["ADX_DMI"] = sg(float(pdi.iloc[-1] - mdi.iloc[-1])) if float(ax.iloc[-1]) > cfg["confirm_adx_min"] else 0
    v["PSAR"] = psar_side(df)
    day = pd.to_datetime(df.t, unit="ms").dt.date; tp = (df.h + df.l + c) / 3
    vw = (tp * df.v).groupby(day).cumsum() / df.v.groupby(day).cumsum().replace(0, np.nan); v["VWAP_SIDE"] = sg(float(c.iloc[-1] - vw.iloc[-1]))
    return v

# ---------- 3 discretionary setups from posts the user shared (rule-based approximations; logged per strategy) ----------
def adx(df, n=14):
    up = df.h.diff(); dn = -df.l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0); mdm = dn.where((dn > up) & (dn > 0), 0.0); a = rma(tr(df), n)
    pdi = 100 * rma(pdm, n) / a; mdi = 100 * rma(mdm, n) / a
    return rma(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan), n)
def pivots(df, n=3, end=None):
    """Confirmed fractal swing highs/lows (n bars each side) up to index `end` (exclusive). Returns [(idx, price)] lists."""
    h, l = df.h.values, df.l.values; end = len(df) if end is None else end; ph, pl = [], []
    for i in range(n, end - n):
        if h[i] == max(h[i - n:i + n + 1]): ph.append((i, h[i]))
        if l[i] == min(l[i - n:i + n + 1]): pl.append((i, l[i]))
    return ph, pl
def bull_rev(df, i):
    o, h, l, c = df.o.iloc[i], df.h.iloc[i], df.l.iloc[i], df.c.iloc[i]; po, pc = df.o.iloc[i - 1], df.c.iloc[i - 1]; rg = h - l
    if rg <= 0: return False
    engulf = c > o and pc < po and c >= po and o <= pc
    hammer = (min(o, c) - l) >= 2 * abs(c - o) and (c - l) >= 0.66 * rg
    return bool(engulf or hammer)
def bear_rev(df, i):
    o, h, l, c = df.o.iloc[i], df.h.iloc[i], df.l.iloc[i], df.c.iloc[i]; po, pc = df.o.iloc[i - 1], df.c.iloc[i - 1]; rg = h - l
    if rg <= 0: return False
    engulf = c < o and pc > po and c <= po and o >= pc
    star = (h - max(o, c)) >= 2 * abs(c - o) and (h - c) >= 0.66 * rg
    return bool(engulf or star)
def setup_pullback(m15, h1, A):
    """Steve Burns trend pullback: 1h price above a RISING 50 EMA (mirror for shorts); 15m pulls back to the 15m 50 EMA or the prior
    swing and the last closed bar is a reversal candle. Stop beyond the pullback swing; target prior swing (else 1.5R)."""
    e1 = ema(h1.c, 50); e15 = ema(m15.c, 50); i = len(m15) - 1; c = m15.c.iloc[i]
    up = h1.c.iloc[-1] > e1.iloc[-1] and e1.iloc[-1] > e1.iloc[-4]; dn = h1.c.iloc[-1] < e1.iloc[-1] and e1.iloc[-1] < e1.iloc[-4]
    ph, pl = pivots(m15, 3, i - 1); lo3, hi3 = m15.l.iloc[i - 2:i + 1].min(), m15.h.iloc[i - 2:i + 1].max()
    if m15.h.iloc[i] - m15.l.iloc[i] < 0.5 * A: return None          # reversal candle must be a real bar, not noise
    dcl = m15.c.diff().iloc[i - 4:i]                                    # a real pullback: >= 2 of the 4 prior bars against the trend
    if up and (dcl < 0).sum() >= 2 and bull_rev(m15, i):
        lv = [e15.iloc[i]] + [p for _, p in ph[-3:] if p < c] + [p for _, p in pl[-2:] if p < c]
        hit = [x for x in lv if lo3 <= x + 0.25 * A and c > x]
        if hit:
            tgt = next((p for _, p in reversed(ph) if p > c), None)
            return {"side": 1, "stop": lo3 - 0.1 * A, "target": tgt, "why": f"pullback to {min(hit, key=lambda x: abs(x-lo3)):.6g}"}
    if dn and (dcl > 0).sum() >= 2 and bear_rev(m15, i):
        lv = [e15.iloc[i]] + [p for _, p in pl[-3:] if p > c] + [p for _, p in ph[-2:] if p > c]
        hit = [x for x in lv if hi3 >= x - 0.25 * A and c < x]
        if hit:
            tgt = next((p for _, p in reversed(pl) if p < c), None)
            return {"side": -1, "stop": hi3 + 0.1 * A, "target": tgt, "why": f"pullback to {min(hit, key=lambda x: abs(x-hi3)):.6g}"}
    return None
def sr_levels(m15, A, upto):
    """Clear S/R: swing pivots of the last ~200 bars that were hit >= 2 times (within 0.3 ATR), plus the prior UTC day high/low."""
    ph, pl = pivots(m15.iloc[max(0, upto - 200):upto].reset_index(drop=True), 3)
    pts = [p for _, p in ph + pl]; lv = []
    for p in pts:
        if sum(abs(q - p) <= 0.3 * A for q in pts) >= 2 and not any(abs(p - x) <= 0.3 * A for x in lv): lv.append(p)
    d = pd.to_datetime(m15.t, unit="ms").dt.date; days = sorted(set(d.iloc[:upto]))
    if len(days) >= 2:
        pdm = m15[d == days[-2]]; lv += [pdm.h.max(), pdm.l.min()]
    return lv
def setup_absorb(m15, A, adx1h, coin=None, l2=False):
    """Koroush AK order-flow reversal, candle proxy: at a clear S/R level, bar A has volume >= 2x its 20-bar avg, a small body and a long
    wick INTO the level, then bar E (last closed) trades on lower volume without breaking A's wick (exhaustion). Fade it, stop beyond
    the wick. Only when 1h ADX < 25. Optional HL L2 wall check (logged; not required)."""
    if not (adx1h < cfg["absorb_adx_max"]): return None
    i = len(m15) - 1; a = i - 1; va = m15.v.iloc[a]; vavg = m15.v.iloc[a - 20:a].mean()
    o, h, l, c = m15.o.iloc[a], m15.h.iloc[a], m15.l.iloc[a], m15.c.iloc[a]; rg = h - l
    if rg <= 0 or va < 2 * vavg or abs(c - o) > 0.35 * rg or m15.v.iloc[i] >= va: return None
    lv = sr_levels(m15, A, a)
    for side in (1, -1):
        wick = (min(o, c) - l) if side == 1 else (h - max(o, c))
        if wick < 0.5 * rg: continue
        ext = l if side == 1 else h
        if side == 1 and m15.l.iloc[i] < l or side == -1 and m15.h.iloc[i] > h: continue
        near = [x for x in lv if abs(ext - x) <= 0.3 * A and ((side == 1 and c > x) or (side == -1 and c < x))]
        if not near: continue
        out = {"side": side, "stop": ext - 0.1 * A if side == 1 else ext + 0.1 * A, "target": None,
               "why": f"absorb vol {va/vavg:.1f}x at {near[0]:.6g}, ADX1h {adx1h:.0f}", "l2_wall": None}
        if l2 and coin:
            try:
                bk = info.l2_snapshot(coin)["levels"][0 if side == 1 else 1][:20]; szs = [float(x["sz"]) for x in bk]
                med = float(np.median(szs)); out["l2_wall"] = any(abs(float(x["px"]) - near[0]) <= 0.3 * A and float(x["sz"]) >= 3 * med for x in bk)
            except Exception: pass
        return out
    return None
def vol_profile(df, bins=48):
    lo, hi = df.l.min(), df.h.max()
    if hi <= lo: return None
    edges = np.linspace(lo, hi, bins + 1); vol = np.zeros(bins); w = edges[1] - edges[0]
    for l, h, v in zip(df.l.values, df.h.values, df.v.values):
        a, b = int((l - lo) // w), min(bins - 1, int((h - lo) // w)); vol[a:b + 1] += v / (b - a + 1)
    mid = (edges[:-1] + edges[1:]) / 2; poc = int(vol.argmax()); lo_i = hi_i = poc; tot = vol.sum(); acc = vol[poc]
    while acc < 0.7 * tot and (lo_i > 0 or hi_i < bins - 1):
        dn_v = vol[lo_i - 1] if lo_i > 0 else -1; up_v = vol[hi_i + 1] if hi_i < bins - 1 else -1
        if up_v >= dn_v: hi_i += 1; acc += up_v
        else: lo_i -= 1; acc += dn_v
    mean = vol.mean()
    lvn = [mid[k] for k in range(bins) if vol[k] < 0.35 * mean]
    hvn = [mid[k] for k in range(1, bins - 1) if vol[k] >= 1.2 * mean and vol[k] >= vol[k - 1] and vol[k] >= vol[k + 1]]
    return {"poc": mid[poc], "vah": edges[hi_i + 1], "val": edges[lo_i], "lvn": lvn, "hvn": hvn}
def setup_vprofile(m15, A, adx1h):
    """Tradewriter volume profile (~48h of 15m bars, excluding the signal bar): ADX1h < 20 -> fade VAH/VAL rejections toward POC;
    breakout -> fresh 15m close outside value with an LVN in the path, target the next HVN (else 1.5R)."""
    i = len(m15) - 1; vp = vol_profile(m15.iloc[i - 192:i])
    if not vp: return None
    o, h, l, c, pc = m15.o.iloc[i], m15.h.iloc[i], m15.l.iloc[i], m15.c.iloc[i], m15.c.iloc[i - 1]
    lvl = {k: round(vp[k], 8) for k in ("poc", "vah", "val")}
    if adx1h < cfg["vp_range_adx_max"]:
        if h >= vp["vah"] and vp["poc"] < c < vp["vah"] and c < o:
            return {"side": -1, "stop": h + 0.1 * A, "target": vp["poc"], "why": f"range VAH rejection -> POC, ADX1h {adx1h:.0f}", "mode": "range", **lvl}
        if l <= vp["val"] and vp["val"] < c < vp["poc"] and c > o:
            return {"side": 1, "stop": l - 0.1 * A, "target": vp["poc"], "why": f"range VAL rejection -> POC, ADX1h {adx1h:.0f}", "mode": "range", **lvl}
        return None
    if c > vp["vah"] >= pc and any(vp["vah"] <= x <= c + A for x in vp["lvn"]):
        tgt = next((x for x in sorted(vp["hvn"]) if x > c), None)
        return {"side": 1, "stop": min(l, vp["vah"]) - 0.1 * A, "target": tgt, "why": "breakout above VAH through LVN", "mode": "breakout", **lvl}
    if c < vp["val"] <= pc and any(c - A <= x <= vp["val"] for x in vp["lvn"]):
        tgt = next((x for x in sorted(vp["hvn"], reverse=True) if x < c), None)
        return {"side": -1, "stop": max(h, vp["val"]) + 0.1 * A, "target": tgt, "why": "breakout below VAL through LVN", "mode": "breakout", **lvl}
    return None
def setup_swingbrk(m15, A):
    """2026-10-25 exec3 (replaces VPROFILE as a trigger): the closed 15m bar closes beyond the most recent confirmed 5-bar fractal swing
    (2 bars each side, confirmed before the signal bar) and the previous close was at/inside that level. Stop: just beyond the most recent
    confirmed opposite swing, +0.1% buffer (the usual widest-of floor - 1 ATR / 0.8% - is applied in _decide). Target: none (tp1_r)."""
    i = len(m15) - 1; c, pc = float(m15.c.iloc[i]), float(m15.c.iloc[i - 1])
    ph, pl = pivots(m15.iloc[max(0, i - 120):i].reset_index(drop=True), 2)
    if ph and pl:
        H, L = float(ph[-1][1]), float(pl[-1][1])
        if c > H >= pc and L < c:
            return {"side": 1, "stop": L * (1 - 0.001), "target": None, "why": f"close {c:.6g} > swing high {H:.6g}; swing low {L:.6g}"}
        if c < L <= pc and H > c:
            return {"side": -1, "stop": H * (1 + 0.001), "target": None, "why": f"close {c:.6g} < swing low {L:.6g}; swing high {H:.6g}"}
    return None
def setup_failbrk(m15, A):
    """2026-10-26 FAIL_BRK (failed-breakout fade): the previous closed bar wicked/closed beyond the last confirmed 5-bar fractal swing
    high (low) - confirmed before that bar - and the just-closed bar closes back inside the level -> short (long). Stop beyond the
    extreme of the failed poke (both bars) +0.1%; the usual widest-of floor (1 ATR / 0.8%) and 3-ATR cap are applied in _decide."""
    i = len(m15) - 1; j = i - 1; c = float(m15.c.iloc[i])
    ph, pl = pivots(m15.iloc[max(0, j - 120):j].reset_index(drop=True), 2)
    hj, lj = float(m15.h.iloc[j]), float(m15.l.iloc[j]); ext_h = max(hj, float(m15.h.iloc[i])); ext_l = min(lj, float(m15.l.iloc[i]))
    up = bool(ph) and hj > float(ph[-1][1]) and c < float(ph[-1][1])
    dn = bool(pl) and lj < float(pl[-1][1]) and c > float(pl[-1][1])
    if up and not dn:
        H = float(ph[-1][1]); return {"side": -1, "stop": ext_h * (1 + 0.001), "target": None, "why": f"poke {hj:.6g} > swing high {H:.6g}, close {c:.6g} back inside"}
    if dn and not up:
        L = float(pl[-1][1]); return {"side": 1, "stop": ext_l * (1 - 0.001), "target": None, "why": f"poke {lj:.6g} < swing low {L:.6g}, close {c:.6g} back inside"}
    return None
def session_vwap(m15):
    """UTC-day anchored VWAP and volume-weighted std dev of typical price, per bar (cumulative within each UTC day)."""
    day = (m15.t.astype("int64") // 86_400_000); tp = (m15.h + m15.l + m15.c) / 3; v = m15.v.clip(lower=0)
    cv = v.groupby(day).cumsum(); vw = (tp * v).groupby(day).cumsum() / cv.replace(0, np.nan)
    var = (tp * tp * v).groupby(day).cumsum() / cv.replace(0, np.nan) - vw * vw
    return vw, np.sqrt(var.clip(lower=0)), day
def setup_vwapband(m15, A):
    """2026-10-26 VWAP_BAND (band reclaim): session (UTC-day) VWAP +-2 sd. The previous bar closed outside a band and the just-closed bar
    closes back inside it -> long from the lower band, short from the upper band. Stop beyond the outside bar's extreme (and the signal
    bar's, if further) +0.1%; usual widest-of floor and 3-ATR cap in _decide. Needs >= 4 bars of the session before the previous bar."""
    k = cfg.get("vwap_band_sd", 2.0); i = len(m15) - 1; j = i - 1
    vw, sd, day = session_vwap(m15)
    if day.iloc[j] != day.iloc[i] or (day.iloc[:j + 1] == day.iloc[j]).sum() < 5: return None
    if not (sd.iloc[j] > 0 and sd.iloc[i] > 0): return None
    cj, ci = float(m15.c.iloc[j]), float(m15.c.iloc[i])
    lo_j, lo_i = vw.iloc[j] - k * sd.iloc[j], vw.iloc[i] - k * sd.iloc[i]; hi_j, hi_i = vw.iloc[j] + k * sd.iloc[j], vw.iloc[i] + k * sd.iloc[i]
    if cj < lo_j and ci > lo_i:
        ext = min(float(m15.l.iloc[j]), float(m15.l.iloc[i]))
        return {"side": 1, "stop": ext * (1 - 0.001), "target": None, "why": f"close {cj:.6g} < lower band {lo_j:.6g}, reclaimed {ci:.6g} > {lo_i:.6g} (vwap {vw.iloc[i]:.6g})"}
    if cj > hi_j and ci < hi_i:
        ext = max(float(m15.h.iloc[j]), float(m15.h.iloc[i]))
        return {"side": -1, "stop": ext * (1 + 0.001), "target": None, "why": f"close {cj:.6g} > upper band {hi_j:.6g}, back {ci:.6g} < {hi_i:.6g} (vwap {vw.iloc[i]:.6g})"}
    return None
SETUPS = ["PULLBACK", "ABSORB", "VPROFILE", "SWING_BRK", "FAIL_BRK", "VWAP_BAND"]; ALL = STRATS + SETUPS
def stop_floor(dist_struct, A, c):
    """v3 stops: max(structural, 1.0 ATR15, 0.8% of price). The 3-ATR cap is checked on max(structural, 1 ATR) so the % floor alone never blocks."""
    d0 = max(dist_struct, cfg["min_stop_atr"] * A)
    return max(d0, cfg["min_stop_pct"] / 100 * c), d0 > cfg["setup_max_stop_atr"] * A
def _decide(m15, h1, coin=None, l2=False, pullback_solo=False):
    """v3 (2026-10-25): one fresh TRIGGER (5 core event signals or a qualified PULLBACK/ABSORB/VPROFILE setup) on the closed bar,
    then count STATE confirmers in the same direction. >= confirm_full agreeing -> full risk, == confirm_half -> half risk, fewer -> skip.
    Vetoes: any trigger in the opposite direction; ADX_DMI opposing (ADX>20 with DMI the other way). Core triggers need the 1h trend;
    setups keep their own regime filters. PULLBACK still needs >= 1 other trigger (no solo PULLBACK)."""
    A = float(atr(m15).iloc[-1]); c = float(m15.c.iloc[-1]); a1 = float(adx(h1).iloc[-1]); vt = votes(m15); tr1 = trend_1h(h1)
    det = {"PULLBACK": setup_pullback(m15, h1, A), "ABSORB": setup_absorb(m15, A, a1, coin, l2), "VPROFILE": setup_vprofile(m15, A, a1), "SWING_BRK": setup_swingbrk(m15, A),
           "FAIL_BRK": setup_failbrk(m15, A), "VWAP_BAND": setup_vwapband(m15, A)}
    for s in SETUPS: vt[s] = det[s]["side"] if det[s] else 0
    cf = confirmers(m15)
    out = dict(votes=vt, confirm=cf, setups={k: v for k, v in det.items() if v}, adx1h=round(a1, 1), trend=tr1, signal=0, risk_mult=0.0,
               stop_dist=cfg["stop_atr_mult"] * A, tp_r=cfg["tp1_r"], primary=None, strategies=[], confirmers=[], block=None)
    for d in (1, -1):
        TRG = cfg.get("trigger_strats", ALL)   # UTBOT is computed/logged but no longer a trigger (flips constantly; PSAR covers it)
        trg = [s for s in TRG if vt[s] == d]; opp = [s for s in TRG if vt[s] == -d]
        if not trg: continue
        def blk(why, p): out.update(block=why, blocked_signal=d, blocked_primary=p)
        st_ = [s for s in SETUPS if vt[s] == d and s in TRG]  # 2026-10-25 user: PULLBACK off
        p = st_[0] if st_ else "CORE"
        if opp: blk("trigger_opposed:" + ",".join(opp), p); continue
        if p == "PULLBACK" and len(trg) < 2 and not pullback_solo: blk("pullback_solo", p); continue
        if p == "CORE" and tr1 != d: out["block"] = "core_against_1h_trend"; continue      # same as before: not logged as a blocked signal
        if p == "SWING_BRK" and tr1 != d: blk("swing_against_1h_trend", p); continue      # SWING_BRK uses the same Hull 1h gate as CORE
        if p in ("FAIL_BRK", "VWAP_BAND") and tr1 != d: blk(f"{p.lower()}_against_1h_trend", p); continue   # 2026-10-26: same 1h gate
        agree = [k for k in CONFIRMERS if cf[k] == d]; n = len(agree); against = [k for k in CONFIRMERS if cf[k] == -d]
        if len(against) > cfg["confirm_max_opp"]: blk(f"confirm_opposed:{','.join(against)} (agree {n})", p); continue
        if n >= cfg["confirm_full"]: rm = 1.0
        elif n >= cfg["confirm_half"]: rm = cfg["confirm_half_risk_mult"]
        else: blk(f"weak_confirm {n}<{cfg['confirm_half']}", p); continue
        tr_ = cfg["tp1_r"]
        if p == "CORE": dist, wide = stop_floor(cfg["stop_atr_mult"] * A, A, c)
        else:
            s0 = det[p]; dist, wide = stop_floor(abs(c - s0["stop"]), A, c)
            if s0.get("target") is not None:
                r = abs(s0["target"] - c) / dist
                if (s0["target"] - c) * d > 0 and r >= cfg["setup_min_target_r"]: tr_ = min(r, cfg["setup_max_target_r"])
                elif p == "VPROFILE" and s0.get("mode") == "range": blk("vp_poc_too_close", p); continue
        if wide: blk(f"{p}_stop_too_wide", p); continue
        out.update(signal=d, risk_mult=rm, stop_dist=dist, tp_r=round(tr_, 2), primary=p, strategies=trg, confirmers=agree, n_confirm=n, block=None)
        out.pop("blocked_signal", None); out.pop("blocked_primary", None); return out
    return out
# ---------- rule 4 (2026-10-25): no chasing exhausted moves (market = BTC, plus per-coin) ----------
def btc_state(b15, b1h):
    """BTC context from closed bars: 1h RSI14, % move from the UTC-day open (first 15m bar of the day), distance from 1h EMA20 in 1h ATRs."""
    if b15 is None or b1h is None or len(b15) < 2 or len(b1h) < 30: return None
    px = float(b15.c.iloc[-1]); day = pd.to_datetime(b15.t, unit="ms").dt.date
    dopen = float(b15[day == day.iloc[-1]].o.iloc[0])
    return {"rsi1h": round(float(rsi(b1h.c).iloc[-1]), 1), "day_move_pct": round((px / dopen - 1) * 100, 2),
            "ema20_atr": round((px - float(ema(b1h.c, 20).iloc[-1])) / float(atr(b1h).iloc[-1]), 2)}
def exhaustion(side, m15, h1, btc):
    """All reasons a NEW trade in `side` would be chasing an exhausted move ([] = ok)."""
    why = []; X = cfg
    if btc:
        if side == -1:
            if btc["rsi1h"] < X["exh_btc_rsi1h_lo"]: why.append(f"btc_rsi1h {btc['rsi1h']}<{X['exh_btc_rsi1h_lo']}")
            if btc["day_move_pct"] < -X["exh_btc_day_move_pct"]: why.append(f"btc_day {btc['day_move_pct']}%<-{X['exh_btc_day_move_pct']}%")
            if btc["ema20_atr"] < -X["exh_btc_ema20_atr"]: why.append(f"btc_ema20 {btc['ema20_atr']}ATR<-{X['exh_btc_ema20_atr']}")
        else:
            if btc["rsi1h"] > X["exh_btc_rsi1h_hi"]: why.append(f"btc_rsi1h {btc['rsi1h']}>{X['exh_btc_rsi1h_hi']}")
            if btc["day_move_pct"] > X["exh_btc_day_move_pct"]: why.append(f"btc_day {btc['day_move_pct']}%>{X['exh_btc_day_move_pct']}%")
            if btc["ema20_atr"] > X["exh_btc_ema20_atr"]: why.append(f"btc_ema20 {btc['ema20_atr']}ATR>{X['exh_btc_ema20_atr']}")
    r1 = float(rsi(h1.c).iloc[-1]); r15 = float(rsi(m15.c).iloc[-1])
    if side == -1:
        if r1 < X["exh_coin_rsi1h_lo"]: why.append(f"coin_rsi1h {r1:.1f}<{X['exh_coin_rsi1h_lo']}")
        if r15 < X["exh_coin_rsi15_lo"]: why.append(f"coin_rsi15 {r15:.1f}<{X['exh_coin_rsi15_lo']}")
    else:
        if r1 > X["exh_coin_rsi1h_hi"]: why.append(f"coin_rsi1h {r1:.1f}>{X['exh_coin_rsi1h_hi']}")
        if r15 > X["exh_coin_rsi15_hi"]: why.append(f"coin_rsi15 {r15:.1f}>{X['exh_coin_rsi15_hi']}")
    return why
def decide(m15, h1, coin=None, l2=False, btc=None):
    out = _decide(m15, h1, coin, l2, pullback_solo=cfg.get("pullback_solo_allowed", False))
    if out["signal"]:
        why = exhaustion(out["signal"], m15, h1, btc)
        if why: out.update(block="exhausted: " + "; ".join(why), blocked_signal=out["signal"], blocked_primary=out["primary"], signal=0, risk_mult=0.0)
    out["btc"] = btc
    return out
BTC_CTX = [None]
def refresh_btc():
    try: BTC_CTX[0] = btc_state(candles("BTC", "15m", 100), candles("BTC", "1h", 120))
    except Exception as x: BTC_CTX[0] = None; log(f"BTC context failed ({x}) - market exhaustion check skipped this bar")
    return BTC_CTX[0]
def evaluate(coin, l2=False):
    m15 = candles(coin, "15m", 250); h1 = candles(coin, "1h", 120)
    if len(m15) < 210 or len(h1) < 60: raise RuntimeError("short history")
    d = decide(m15, h1, coin, l2, BTC_CTX[0])
    return dict(coin=coin, bar_close=int(m15["T"].iloc[-1]) + 1, close=float(m15.c.iloc[-1]), bar_high=float(m15.h.iloc[-1]), bar_low=float(m15.l.iloc[-1]),
                atr=float(atr(m15).iloc[-1]), **d)
# ---------- universe ----------
def pick_universe():
    load_meta(); cands = []
    for n, a in META.items():
        if a.get("isDelisted") or n in PERP or n.startswith("@"): continue
        if float(a.get("dayNtlVlm") or 0) >= cfg["min_day_ntl_vol_usd"]: cands.append(n)
    def spread(n):
        try:
            lv = info.l2_snapshot(n)["levels"]; b, a = float(lv[0][0]["px"]), float(lv[1][0]["px"]); return (a - b) / ((a + b) / 2)
        except Exception: return None
    with ThreadPoolExecutor(5) as ex: sp = dict(zip(cands, ex.map(spread, cands)))
    ok = [n for n in cands if sp[n] is not None and sp[n] <= cfg["max_spread"]]
    ok.sort(key=lambda n: -float(META[n]["dayNtlVlm"]))
    uni = [{"coin": n, "vol": float(META[n]["dayNtlVlm"]), "spread": sp[n], "maxlev": int(META[n]["maxLeverage"])} for n in ok[:cfg["universe_max"]]]
    rej = [n for n in cands if n not in ok]
    return uni, rej

# ---------- sizing (shared by dry-run and live) ----------
def choose_lev(maxlev, stop_frac):
    """Highest leverage <= min(cfg max, coin max) whose est. isolated liq distance (1/L - 1/(2*maxlev)) >= liq_min_stop_mult x stop."""
    for L in range(min(cfg["max_leverage"], maxlev), 0, -1):
        if 1 / L - 1 / (2 * maxlev) >= cfg["liq_min_stop_mult"] * stop_frac: return L, 1 / L - 1 / (2 * maxlev)
    return None, None
def size_trade(cap, px, atr_v, maxlev, open_risk_usd, free_margin, stop_dist=None, risk_mult=1.0, side_room_usd=None):
    dist = max(stop_dist or cfg["stop_atr_mult"] * atr_v, cfg["min_stop_pct"] / 100 * px, cfg["min_stop_atr"] * atr_v)   # belt-and-braces floor
    rdist = dist + cfg["stop_slip_buffer_pct"] / 100 * px   # size off stop + expected fees/slippage so a stop-out is ~1R, not 1.3R
    sf = rdist / px
    L, liq = choose_lev(maxlev, sf)
    if not L: return {"ok": False, "why": f"stop {sf:.2%} too wide for liq guard", "stop_frac": sf}
    room = max(0.0, cfg["max_open_risk_pct"] / 100 * cap - open_risk_usd)
    risk_usd = min(cfg["risk_per_trade"] * risk_mult * cap, room)
    if side_room_usd is not None: risk_usd = min(risk_usd, max(0.0, side_room_usd))   # 2026-10-26 focus: same-direction cap (3R)
    qty = risk_usd / rdist; notional = qty * px
    max_by_margin = max(0.0, free_margin * 0.95) * L
    if notional > max_by_margin: notional = max_by_margin; qty = notional / px
    out = {"ok": notional >= cfg["min_entry_notional_usd"], "lev": L, "est_liq_frac": round(liq, 4), "stop_frac": round(sf, 4),
           "stop_dist": dist, "risk_dist": rdist, "risk_usd": round(qty * rdist, 3), "qty": qty, "notional": round(notional, 2), "margin": round(notional / L, 2)}
    if not out["ok"]: out["why"] = f"notional ${notional:.2f} < min ${cfg['min_entry_notional_usd']} (open-risk / same-direction / margin room)"
    return out

def funding_blocks(side, f): return (side == 1 and f > cfg["max_adverse_funding_per_h"]) or (side == -1 and f < -cfg["max_adverse_funding_per_h"])

def gate_of(e, f, z):
    if not e["signal"]: return "none" + (f" ({e['block']})" if e.get("block") else "")
    if e["primary"] == "CORE" and e["signal"] != e["trend"]: return "skip_trend"
    if funding_blocks(e["signal"], f): return "skip_funding"
    return "WOULD ENTER" if z["ok"] else "skip_size"
def dry_run():
    print(f"DRY RUN {now():%Y-%m-%d %H:%M}Z - public data only, no key, no orders. Capital ${cfg['dry_run_capital_usd']} (assumed)")
    uni, rej = pick_universe()
    print(f"Universe ({len(uni)}): " + ", ".join(f"{u['coin']}(vol ${u['vol']/1e6:.0f}M, spr {u['spread']*100:.3f}%, max {u['maxlev']}x)" for u in uni))
    if rej: print(f"Rejected on spread: {rej}")
    cap = cfg["dry_run_capital_usd"]; orisk = 0.0; free = cap; nsig = 0
    for u in uni:
        if BTC_CTX[0] is None: print("BTC ctx", refresh_btc())
        e = evaluate(u["coin"], l2=True); f = float(META[u["coin"]]["funding"])
        z = size_trade(cap, e["close"], e["atr"], u["maxlev"], orisk, free, e["stop_dist"], e["risk_mult"] or 1.0)
        gate = gate_of(e, f, z); nsig += gate == "WOULD ENTER"
        nz = {k: v for k, v in e["votes"].items() if v}
        print(f"{u['coin']:>9} {iso(e['bar_close'])} close {e['close']:.6g} ADX1h {e['adx1h']} 1h {e['trend']:+d} votes {nz or '{}'} signal {e['signal']:+d} "
              f"[{e['primary']} risk x{e['risk_mult']} tp {e['tp_r']}R] -> {gate} | if entered: {z.get('lev')}x, stop {z.get('stop_frac',0):.2%}, "
              f"risk ${z.get('risk_usd')}, notional ${z.get('notional')}, margin ${z.get('margin')} {z.get('why','')}")
        for k, v in e["setups"].items(): print(f"           setup {k}: {v}")
        if gate == "WOULD ENTER": orisk += z["risk_usd"]; free -= z["margin"]
    print(f"would-enter now: {nsig}")
    # signal COUNT (no P&L) over the last 96 closed bars, by primary strategy
    print("Signal count, last 96 bars (fresh entries that would pass trend/regime rules; primary strategy, solo setups marked):")
    tot = {}; allc = 0; EX = []; B15 = candles("BTC", "15m", 400); B1H = candles("BTC", "1h", 220)
    for u in uni:
        m15 = candles(u["coin"], "15m", 400); h1 = candles(u["coin"], "1h", 220); prev = 0; cc = {}
        for i in range(len(m15) - 96, len(m15)):
            sub = m15.iloc[:i + 1].reset_index(drop=True); hh = h1[h1["T"] < sub["T"].iloc[-1]].reset_index(drop=True)
            if len(sub) < 210 or len(hh) < 60: continue
            d = decide(sub, hh, btc=btc_state(B15[B15["T"] <= sub["T"].iloc[-1]].reset_index(drop=True), B1H[B1H["T"] < sub["T"].iloc[-1]].reset_index(drop=True))); sg = d["signal"]
            if sg and sg != prev:
                key = d["primary"] + ("(solo)" if d["risk_mult"] < 1 else "")
                if d["primary"] != "CORE": EX.append((u["coin"], iso(int(sub["T"].iloc[-1]) + 1), sg, d["risk_mult"], d["tp_r"], round(d["stop_dist"] / float(sub.c.iloc[-1]) * 100, 2), d["strategies"], d["setups"][d["primary"]]["why"]))
                cc[key] = cc.get(key, 0) + 1; tot[key] = tot.get(key, 0) + 1; allc += 1
            prev = sg
        print(f"  {u['coin']}: {sum(cc.values())} {cc}")
    print(f"  total/24h: {allc} {tot}")
    print("Latest setup signals (coin, bar, side, risk mult, TP1 R, stop %, agreeing, why):")
    for x in sorted(EX, key=lambda x: x[1])[-8:]: print("  ", x)
    sys.exit(0)

# =================== LIVE ===================
ACCOUNT = ""; ex = None; SZD = {}
def live_init():
    global ACCOUNT, ex, SZD
    if not cfg.get("live_enabled") or not cfg.get("base_capital_usd"):
        log("live_enabled=false or base_capital_usd=0 - not trading (waiting for funds). Exiting."); sys.exit(3)
    ACCOUNT, KEY = os.getenv("HL_ACCOUNT", "").strip(), os.getenv("HL_API_KEY", "").strip()
    if not ACCOUNT or not KEY: log("HL_ACCOUNT/HL_API_KEY not set - exiting."); sys.exit(3)
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    try: wallet = Account.from_key(KEY)
    except Exception: log("HL_API_KEY is not a valid private key (value not shown) - exiting."); sys.exit(3)
    del KEY; os.environ.pop("HL_API_KEY", None)
    if wallet.address.lower() == ACCOUNT.lower(): log("Refusing: key is the MAIN account key. Use a trade-only API wallet."); sys.exit(3)
    ex = Exchange(wallet, BASE, account_address=ACCOUNT)
    SZD = {a["name"]: a["szDecimals"] for a in info.meta()["universe"]}
    log(f"live init ok: account {ACCOUNT}, api wallet {wallet.address}")

def rpx(coin, px): return round(float(f"{px:.5g}"), 6 - SZD[coin])
def rsz(coin, sz): return math.floor(round(sz * 10 ** SZD[coin], 6)) / 10 ** SZD[coin]
def new_cloid(kind):   # 0x 5ca1 | kind(2) | 26 random hex
    return Cloid.from_str(PREFIX + {"entry": "e0", "lentry": "e1", "sl": "51", "tp": "7a", "close": "c1"}[kind] + secrets.token_hex(13))
# ---------- 2026-10-25 expand: dynamic lockout with the perp bot (/workspace/perpbot), whose universe now overlaps ours ----------
# perp-owned coins = perpbot state.json open trades + its fresh pending_entry + coins in an open (or <3 min closed) perp ownership
# window. On those coins the scalper never enters, adopts, manages, closes or cancels, and perp fills/funding stay out of our P&L.
# Our own open trade record always wins (we keep managing what we opened). PERP (static legacy coins) is still fully excluded.
PERP_STATE = "/workspace/perpbot/state.json"; PERP_CFG = "/workspace/perpbot/config.json"; PERP_PENDING_S = 900; PERP_RELEASE_MS = 180_000
_ST = {}; _PC = {"claims": None, "windows": [], "coins": set()}; _WARN = {}
def perp_claims():
    """({coin: why}, windows). Last good read is kept; if perpbot state was never readable every perp-universe coin is claimed."""
    try:
        try: _PC["coins"] = set(json.load(open(PERP_CFG)).get("coins") or [])
        except Exception: pass
        ps = json.load(open(PERP_STATE)); c = {k: "perp open trade" for k in (ps.get("trades") or {})}
        pe = ps.get("pending_entry") or {}
        if pe.get("coin") and time.time() - float(pe.get("ts") or 0) < PERP_PENDING_S: c.setdefault(pe["coin"], "perp entry in flight")
        w = ps.get("owned") or []
        for x in w:
            if x.get("end") is None or nms() - int(x["end"]) < PERP_RELEASE_MS: c.setdefault(x["coin"], "perp ownership window")
        _PC["claims"], _PC["windows"] = c, w
    except Exception: pass
    if _PC["claims"] is None: return {k: "perpbot state unreadable (fail-safe)" for k in _PC["coins"]}, []
    return dict(_PC["claims"]), list(_PC["windows"])
def perp_owned(coin):
    """True if the perp bot owns/claims `coin` and we have no own trade record on it."""
    return coin in PERP or (coin in perp_claims()[0] and coin not in (_ST.get("trades") or {}))
def in_perp_window(coin, ms, windows=None):
    w = perp_claims()[1] if windows is None else windows
    return any(x["coin"] == coin and int(x["start"]) - 5000 <= ms <= (int(x["end"]) if x.get("end") is not None else 9e15) + 5000 for x in w)
def warn_once(k, msg, every=3600):
    if time.time() - _WARN.get(k, 0) >= every: _WARN[k] = time.time(); log(msg)
def guard(coin):
    if coin in PERP: raise RuntimeError(f"REFUSED: {coin} belongs to perpbot")
    if perp_owned(coin): raise RuntimeError(f"REFUSED: {coin} is currently owned by perpbot ({perp_claims()[0].get(coin)})")
def okr(resp):
    try:
        s = resp["response"]["data"]["statuses"][0]; return resp["status"] == "ok" and "error" not in s, s
    except Exception: return False, resp
def own_orders():
    return [o for o in info.frontend_open_orders(ACCOUNT) if not perp_owned(o["coin"]) and str(o.get("cloid") or "").startswith(PREFIX)]
def own_positions(us):
    out = {}
    for p in us["assetPositions"]:
        q = p["position"]; c = q["coin"]
        if c in PERP or float(q["szi"]) == 0: continue
        if perp_owned(c): continue                      # perp bot's position on a shared coin: invisible to the scalper
        if c in perp_claims()[0]: warn_once("conflict" + c, f"OWNERSHIP CONFLICT {c}: perpbot also claims it - scalper keeps managing its own record, CHECK MANUALLY")
        out[c] = q
    return out
def any_position(us, coin):
    return any(p["position"]["coin"] == coin and float(p["position"]["szi"]) != 0 for p in us["assetPositions"])
def cancel(coin, oid):
    guard(coin)
    try: ex.cancel(coin, oid)
    except Exception as e: log(f"cancel {coin} {oid} failed: {e}")
def place_trigger(coin, is_long, sz, trig, kind):
    guard(coin); trig = rpx(coin, trig); lim = rpx(coin, trig * (0.9 if is_long else 1.1))
    r = ex.order(coin, not is_long, sz, lim, {"trigger": {"triggerPx": trig, "isMarket": True, "tpsl": kind}}, reduce_only=True, cloid=new_cloid(kind))
    good, res = okr(r); oid = res.get("resting", {}).get("oid") if isinstance(res, dict) else None
    log(f"{kind.upper()} {coin} @ {trig} sz {sz} -> {res}"); return good, trig, oid
def market_close(coin, reason):
    guard(coin)
    for o in own_orders():
        if o["coin"] == coin: cancel(coin, o["oid"])
    r = ex.market_close(coin, slippage=0.01, cloid=new_cloid("close")); good, res = okr(r) if r else (False, "no position")
    log(f"CLOSE {coin} ({reason}) -> {res}"); jl("trades.jsonl", {"event": "close_order", "coin": coin, "reason": reason, "result": str(res)}); return good

def load_state():
    try: st = json.load(open(STATE))
    except Exception: st = {}
    for k, v in {"start_ms": nms(), "realized": 0.0, "fees": 0.0, "funding": 0.0, "seen_tids": [], "fund_ms": None, "trades": {},
                 "cooldown": {}, "last_bar": 0, "universe": [], "uni_ts": 0, "day": None, "day_start_cap": None, "halted_day": None}.items():
        st.setdefault(k, v)
    if st["fund_ms"] is None: st["fund_ms"] = st["start_ms"]
    return st

def sync_pnl(st):
    """Realized PnL / fees / funding on non-perpbot coins since the scalper started (coin sets are disjoint, so attribution is exact)."""
    seen = set(st["seen_tids"])
    for f in info.user_fills_by_time(ACCOUNT, st["start_ms"]):
        if f["coin"] in PERP or f["coin"].startswith("@") or "/" in f["coin"] or f["tid"] in seen: continue   # perps of our own coins only
        if not str(f.get("cloid") or "").startswith(PREFIX) and in_perp_window(f["coin"], int(f["time"])): seen.add(f["tid"]); continue   # perpbot fill on a shared coin
        seen.add(f["tid"]); st["realized"] += float(f.get("closedPnl") or 0) - float(f.get("fee") or 0); st["fees"] += float(f.get("fee") or 0)
        jl("fills.jsonl", {k: f.get(k) for k in ("coin", "dir", "px", "sz", "fee", "closedPnl", "oid", "tid", "time", "cloid")})
        t = st["trades"].get(f["coin"])
        if t: t["realized"] = t.get("realized", 0.0) + float(f.get("closedPnl") or 0) - float(f.get("fee") or 0)
        else: st.setdefault("untracked_fill_coins", []).append(f["coin"])
    st["seen_tids"] = list(seen)[-3000:]
    try:
        for h in info.user_funding_history(ACCOUNT, st["fund_ms"] + 1):
            d = h.get("delta", {})
            if d.get("coin") in PERP or in_perp_window(d.get("coin"), int(h["time"])): continue
            st["funding"] += float(d.get("usdc") or 0); st["fund_ms"] = max(st["fund_ms"], int(h["time"]))
            t = st["trades"].get(d.get("coin"))
            if t: t["realized"] = t.get("realized", 0.0) + float(d.get("usdc") or 0)
    except Exception as e: log(f"funding sync failed: {e}")

# ---------- bookkeeping / reconcile (exchange is the source of truth) ----------
_SIGN = {"Open Long": 1, "Close Long": -1, "Open Short": -1, "Close Short": 1}
def round_trips(fills, coin):
    """Walk this coin's fills in time order -> list of round trips {side, opened_ms, closed_ms|None, entry, sz0, realized, exit, close_cloid}."""
    out = []; cur = None; net = 0.0
    for f in sorted((f for f in fills if f["coin"] == coin), key=lambda f: (f["time"], f["tid"])):
        d = f.get("dir", ""); sz = float(f["sz"]); px = float(f["px"]); sg = _SIGN.get(d)
        if sg is None: continue
        if cur is None:
            if not d.startswith("Open"): continue      # tail of a trip that started before the window
            cur = dict(side="long" if sg > 0 else "short", opened_ms=int(f["time"]), closed_ms=None, _ntl=0.0, _osz=0.0, sz0=0.0,
                       realized=0.0, _xntl=0.0, _xsz=0.0, close_cloid=None, entry_cloids=[])
        net += sg * sz; cur["realized"] += float(f.get("closedPnl") or 0) - float(f.get("fee") or 0)
        if d.startswith("Open"):
            cur["_ntl"] += px * sz; cur["_osz"] += sz; cur["entry_cloids"].append(f.get("cloid"))
        else:
            cur["_xntl"] += px * sz; cur["_xsz"] += sz; cur["close_cloid"] = f.get("cloid")
        cur["sz0"] = max(cur["sz0"], abs(net))
        if abs(net) < 1e-9:
            cur["closed_ms"] = int(f["time"]); out.append(cur); cur = None; net = 0.0
    if cur: out.append(cur)
    for t in out:
        t["entry"] = t["_ntl"] / t["_osz"] if t["_osz"] else None; t["exit"] = t["_xntl"] / t["_xsz"] if t["_xsz"] else None
        t["entry_cloids"] = sorted(set(c for c in t["entry_cloids"] if c))
    return out

def decision_for(coin, side, opened_ms):
    """Best-effort: the eval record that produced this entry (same coin/side, bar within ~35 min before the fill)."""
    best = None; want = 1 if side == "long" else -1
    try:
        for l in open(P("decisions.jsonl")):
            if f'"{coin}"' not in l or '"eval"' not in l: continue
            d = json.loads(l)
            if d.get("coin") != coin or d.get("signal") != want or not d.get("bar"): continue
            bms = int(datetime.strptime(d["bar"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
            if -60_000 <= opened_ms - bms <= 35 * 60_000: best = d
    except Exception: pass
    return best

def recent_fills(hours=26):
    return [f for f in info.user_fills_by_time(ACCOUNT, max(nms() - int(hours * 3_600_000), 0))
            if f["coin"] not in PERP and not f["coin"].startswith("@") and "/" not in f["coin"]
            and (str(f.get("cloid") or "").startswith(PREFIX) or not in_perp_window(f["coin"], int(f["time"])))]

def adopt(st, coin, p, oo, fills):
    """Build a managed trade record for an exchange position the state does not know about. Touches NO exchange orders."""
    guard(coin)
    if coin in _PC["coins"] or coin in perp_claims()[0]:
        tr = [t for t in round_trips(fills, coin) if t["closed_ms"] is None]
        if not (tr and any(str(c).startswith(PREFIX) for c in tr[-1]["entry_cloids"])):
            warn_once("noadopt" + coin, f"NOT adopting {coin}: perp-universe coin and the open position has no scalper (0x5ca1) entry fill - left to its owner")
            return
    is_long = float(p["szi"]) > 0; side = "long" if is_long else "short"; sz = abs(float(p["szi"])); e = float(p["entryPx"])
    trips = [t for t in round_trips(fills, coin) if t["closed_ms"] is None and t["side"] == side]
    trip = trips[-1] if trips else None
    mine = [o for o in oo if o["coin"] == coin and o.get("isTrigger")]
    sls = [o for o in mine if "Stop" in o.get("orderType", "")]; tps = [o for o in mine if "Take Profit" in o.get("orderType", "")]
    try: a = float(atr(candles(coin, "15m", 120)).iloc[-1])
    except Exception as x: a = e * 0.004; log(f"adopt {coin}: ATR fetch failed ({x}), using 0.4% of price")
    fb = max(cfg["min_stop_atr"] * a, cfg["min_stop_pct"] / 100 * e)
    if sls:
        trig = [float(o["triggerPx"]) for o in sls]; stop = max(trig) if is_long else min(trig)
    else: stop = rpx(coin, e - fb if is_long else e + fb)   # no stop resting: manage() will place this one next
    tp1 = float(tps[0]["triggerPx"]) if tps else None
    sz0 = max(sz, trip["sz0"] if trip else 0.0)
    rdist = abs(e - stop) + cfg["stop_slip_buffer_pct"] / 100 * e
    d = decision_for(coin, side, trip["opened_ms"] if trip else nms())
    lev = (p.get("leverage") or {}).get("value")
    t = dict(side=side, entry=e, sz0=sz0, stop=stop, tp1=tp1, tp1_ok=bool(tps), tp1_done=sz <= sz0 * (1 - cfg["tp1_fraction"] / 2),
             atr=a, best=float(p["entryPx"]), risk_usd=sz0 * rdist, lev=lev, opened_ms=trip["opened_ms"] if trip else nms(),
             votes=(d or {}).get("votes", {}), realized=trip["realized"] if trip else 0.0,
             primary=(d or {}).get("primary") or "ADOPTED", strategies=[k for k, v in ((d or {}).get("votes") or {}).items() if v] ,
             risk_mult=(d or {}).get("risk_mult"), adopted=True)
    st["trades"][coin] = t
    rec = {"event": "adopted", "coin": coin, "side": side, "entry": e, "sz": sz, "sz0": sz0, "notional": round(sz * e, 2), "lev": lev,
           "stop": stop, "stop_resting": bool(sls), "tp1": tp1, "tp1_resting": bool(tps), "risk_usd": round(sz0 * rdist, 3), "atr": a,
           "opened": iso(t["opened_ms"]), "entry_cloids": trip["entry_cloids"] if trip else [], "primary": t["primary"],
           "strategies": t["strategies"], "risk_mult": t["risk_mult"], "realized_so_far": round(t["realized"], 4)}
    jl("trades.jsonl", rec)
    log(f"ADOPTED untracked {side} {coin} {sz} @ {e} (stop {stop} {'resting' if sls else 'NOT resting - manage will place'}, tp1 {tp1}, opened {rec['opened']})")

def log_untracked_closes(st, fills, pos):
    """Round trips on our coins that opened AND closed while no trade record existed -> 'closed' records so stats are complete."""
    known = set(st.setdefault("logged_trips", []))
    opens = []
    try:
        for l in open(P("trades.jsonl")):
            if '"open"' in l or '"adopted"' in l:
                r = json.loads(l)
                if r.get("event") == "open": opens.append((r["coin"], r.get("ts")))
                elif r.get("event") == "adopted": opens.append((r["coin"], r.get("opened")))
    except Exception: pass
    def tracked(coin, oms):
        for c, ts in opens:
            if c != coin or not ts: continue
            try: tms = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp() * 1000
            except Exception: continue
            if -120_000 <= tms - oms <= 15 * 60_000: return True
        return False
    for coin in sorted(set(f["coin"] for f in fills)):
        for t in round_trips(fills, coin):
            if t["closed_ms"] is None or t["opened_ms"] < st["start_ms"]: continue
            key = f"{coin}:{t['opened_ms']}"
            if key in known: continue
            known.add(key)
            if tracked(coin, t["opened_ms"]): continue
            if not any(str(c).startswith(PREFIX) for c in t["entry_cloids"]): continue   # not a scalper entry
            d = decision_for(coin, t["side"], t["opened_ms"])
            # risk estimate: a stop-out exit ~= -1R (+ buffer); otherwise unknown
            rdist = abs(t["entry"] - t["exit"]) + cfg["stop_slip_buffer_pct"] / 100 * t["entry"] if t["exit"] and str(t["close_cloid"] or "").startswith(PREFIX + "51") else None
            risk = t["sz0"] * rdist if rdist else None
            jl("trades.jsonl", {"event": "closed", "coin": coin, "side": t["side"], "entry": round(t["entry"], 8), "opened": iso(t["opened_ms"]),
                                "closed_at": iso(t["closed_ms"]), "exit": t["exit"], "sz": t["sz0"], "pnl_usd": round(t["realized"], 4),
                                "R": round(t["realized"] / risk, 3) if risk else None, "R_estimated": True, "tp1_done": False, "last_stop": t["exit"],
                                "votes": (d or {}).get("votes", {}), "lev": None, "primary": (d or {}).get("primary") or "UNTRACKED",
                                "strategies": [k for k, v in ((d or {}).get("votes") or {}).items() if v], "risk_mult": (d or {}).get("risk_mult"),
                                "untracked": True, "entry_cloids": t["entry_cloids"]})
            log(f"backfilled untracked round trip {coin} {t['side']} {iso(t['opened_ms'])}->{iso(t['closed_ms'])} pnl ${t['realized']:.3f}")
    st["logged_trips"] = sorted(known)[-500:]

def reconcile(st, pos, oo, fills=None):
    """Every loop, before manage(): every scalper-coin position on the exchange must have a trade record; record size follows the exchange."""
    need = [c for c in pos if c not in st["trades"]]
    grew = [c for c in pos if c in st["trades"] and abs(float(pos[c]["szi"])) > st["trades"][c]["sz0"] * 1.001]
    if fills is None and (need or grew): fills = recent_fills()
    for c in need:
        try: adopt(st, c, pos[c], oo, fills)
        except Exception as x: log(f"adopt {c} failed: {x}\n{traceback.format_exc(limit=2)}")
    for c in grew:   # extra untracked fill on a tracked coin (e.g. duplicate entry): record follows the real size, orders untouched
        t = st["trades"][c]; p = pos[c]; sz = abs(float(p["szi"])); e = float(p["entryPx"]); old = t["sz0"]
        t["sz0"] = sz; t["entry"] = e; t["risk_usd"] = sz * (abs(e - t["stop"]) + cfg["stop_slip_buffer_pct"] / 100 * e)
        jl("trades.jsonl", {"event": "resized_record", "coin": c, "old_sz0": old, "sz0": sz, "entry": e, "risk_usd": round(t["risk_usd"], 3)})
        log(f"RECORD RESIZED {c}: sz0 {old} -> {sz} (exchange position), entry {e}")
    return fills

def scalper_capital(st, pos):
    upnl = sum(float(p["unrealizedPnl"]) for p in pos.values())
    return cfg["base_capital_usd"] + st["realized"] + st["funding"] + upnl, upnl

def open_risk(st, pos, side=None):
    """Open $ risk to the current stops (+ unfilled planned risk of resting limits). side='long'/'short' -> that side only."""
    tot = 0.0
    for c, p in pos.items():
        t = st["trades"].get(c); sz = abs(float(p["szi"])); e = float(p["entryPx"]); lg = float(p["szi"]) > 0
        if side and ("long" if lg else "short") != side: continue
        tot += sz * e * 0.05 if not t else max(0.0, (e - t["stop"]) if lg else (t["stop"] - e)) * sz
    for c, t in st["trades"].items():   # 2026-10-25 exec3: resting limit entries count their unfilled planned risk
        if t.get("pending") and (not side or t.get("side") == side):
            f = abs(float(pos[c]["szi"])) if c in pos else 0.0
            tot += max(0.0, t["sz0"] - f) * abs(t["lim"] - t["stop"])
    return tot

def account_free(us):
    """Unified mode: spot USDC total - hold is the free collateral shared by both bots."""
    try:
        for b in info.spot_user_state(ACCOUNT)["balances"]:
            if b["coin"] == "USDC": return float(b["total"]) - float(b.get("hold") or 0)
    except Exception: pass
    return float(us.get("withdrawable") or 0)

def hilo_since(coin, start_ms):
    """(high, low) of 1m candles from start_ms (max 6h back) to now, incl. the forming minute; (None, None) if no data."""
    start = max(int(start_ms), nms() - 6 * 3_600_000)
    raw = info.candles_snapshot(coin, "1m", start, nms())
    if not raw: return None, None
    return max(float(c["h"]) for c in raw), min(float(c["l"]) for c in raw)

def samedir_count(st, side):
    """Scalper's own open trades + resting limit entries in `side` (perp-bot positions never count)."""
    return sum(1 for t in st["trades"].values() if t.get("side") == side)

# ---------- 2026-10-25 exec3: midpoint GTC limit entry with market fallback ----------
# Exchange-side protection from the instant of ANY fill, even if this computer is asleep:
#  (1) a standalone reduce-only Stop Market ("backup SL", full planned size) is placed BEFORE the limit. HL keeps reduce-only triggers
#      resting while flat (verified live 20:45 UTC) and a reduce-only order can never open/flip a position, so it covers partial fills;
#  (2) the limit itself goes in with grouping "normalTpsl" (entry + SL child + TP1 child at 50%): HL activates the children once the
#      parent is fully filled (or partially filled then margin-cancelled). Partial fills are covered by (1) until we resolve them.
# The record lives in st["trades"][coin] with pending=True, so the perp bot sees the coin as taken, and the orphan sweep / adopt skip it.
def _order_status(cloid_raw):
    q = info.query_order_by_cloid(ACCOUNT, Cloid.from_str(cloid_raw))
    if not isinstance(q, dict): return None, {}
    if q.get("status") == "order": o = q.get("order") or {}; return o.get("status"), o.get("order") or {}
    return q.get("status"), {}

def _first_fill_ms(coin, since_ms, cloids):
    try:
        ts = [int(f["time"]) for f in info.user_fills_by_time(ACCOUNT, since_ms - 60_000) if f["coin"] == coin and f.get("cloid") in cloids]
        return min(ts) if ts else None
    except Exception: return None

def _pending_finalize(st, coin, t, p, kind):
    """Pending limit -> normal managed trade. Position p is on the exchange; resting stop: child SL and/or backup SL."""
    is_long = t["side"] == "long"; fsz = abs(float(p["szi"])); fpx = float(p["entryPx"])
    mine = [o for o in own_orders() if o["coin"] == coin]
    child_sl = [o for o in mine if o.get("cloid") == t["sl_cloid"]]; child_tp = [o for o in mine if o.get("cloid") == t.get("tp_cloid")]
    bk = [o for o in mine if o.get("cloid") == t["bk_cloid"]]
    # 2026-10-26 focus: a limit that filled at a better price than the limit (midpoint already past the market) got a stop/TP measured
    # from the limit -> stop far tighter than planned, TP1 far beyond 1.5R (AERO 0.29% stop vs 1.98% planned). Re-base both on the fill.
    lim = t["lim"]; better = (fpx < lim * (1 - 2e-4)) if is_long else (fpx > lim * (1 + 2e-4))
    if better and kind in ("limit", "limit_partial"):
        dpl = max(abs(lim - t["stop"]), cfg["min_stop_pct"] / 100 * fpx, cfg["min_stop_atr"] * t["atr"])
        nstop = rpx(coin, fpx - dpl if is_long else fpx + dpl); ntp = rpx(coin, fpx + t.get("tp_r", cfg["tp1_r"]) * dpl if is_long else fpx - t.get("tp_r", cfg["tp1_r"]) * dpl)
        good, trig, noid = place_trigger(coin, is_long, fsz, nstop, "sl")
        if good:
            log(f"LIMIT {coin}: filled at {fpx}, better than the limit {lim} (marketable) - stop {t['stop']} -> {trig}, tp1 {t['tp1']} -> {ntp} (planned distance {dpl:.6g})")
            jl("trades.jsonl", {"event": "instant_fill_rebase", "coin": coin, "fill": fpx, "limit_px": lim, "old_stop": t["stop"], "stop": trig,
                                "old_tp1": t["tp1"], "tp1": ntp, "dist": dpl})
            for o in child_sl + bk:
                if o["oid"] != noid: cancel(coin, o["oid"])
            for o in child_tp: cancel(coin, o["oid"])
            t["stop"] = trig; t["tp1"] = ntp; child_sl = [{"sz": str(fsz)}]; child_tp = []; bk = []
        else: log(f"LIMIT {coin}: instant-fill stop re-base FAILED - keeping the limit-based stop {t['stop']}")
    if child_sl and abs(float(child_sl[0]["sz"]) - fsz) < 1e-9:
        for o in bk: cancel(coin, o["oid"])   # child SL is live and exact: drop the backup
    tp_ok = bool(child_tp); tp1 = t["tp1"]
    if not tp_ok:
        half = rsz(coin, fsz * cfg["tp1_fraction"])
        if half * fpx >= 10.5: tp_ok, tp1, _ = place_trigger(coin, is_long, half, tp1, "tp")
    f0 = _first_fill_ms(coin, t["placed_ms"], [t["cloid"]] + ([t["fb_cloid"]] if t.get("fb_cloid") else [])) or t["placed_ms"]
    rdist = abs(fpx - t["stop"]) + cfg["stop_slip_buffer_pct"] / 100 * fpx
    for k in ("pending", "deadline_ms", "lim_oid", "instant"): t.pop(k, None)
    t.update(entry=fpx, sz0=fsz, best=fpx, tp1=tp1, tp1_ok=tp_ok, opened_ms=f0, risk_usd=fsz * rdist, dist0=abs(fpx - t["stop"]),
             hl_ms=f0 - 60_000, entry_type=kind)
    log(f"LIMIT {kind.upper()} {coin}: {t['side']} {fsz} @ {fpx} (limit {t['lim']}), stop {t['stop']} ({'child' if child_sl else 'backup'} SL resting), tp1 {tp1} {'resting' if tp_ok else 'not placed'}")
    jl("trades.jsonl", {"ts": iso(f0), "event": "open", "coin": coin, "side": t["side"], "entry": fpx, "sz": fsz, "notional": round(fsz * fpx, 2),
                        "lev": t["lev"], "stop": t["stop"], "tp1": tp1, "tp1_placed": tp_ok, "risk_usd": round(fsz * rdist, 3), "votes": t["votes"],
                        "confirm": t.get("confirm"), "confirmers": t.get("confirmers"), "trend1h": t.get("trend1h"), "primary": t["primary"],
                        "strategies": t["strategies"], "risk_mult": t["risk_mult"], "samedir_mult": t.get("samedir_mult"), "tp_r": t.get("tp_r"),
                        "setups": t.get("setups"), "est_liq_frac": t.get("est_liq_frac"), "liq_px": p.get("liquidationPx"),
                        "entry_type": kind, "limit_px": t["lim"], "planned_sz": t["planned_sz"]})

def _fresh_pos(coin, tries=3, wait=1.5):
    """2026-10-25 chipfix: ask the exchange NOW (the step-start snapshot can predate a fill by many seconds)."""
    for k in range(tries):
        try:
            p = own_positions(info.user_state(ACCOUNT)).get(coin)
            if p: return p
        except Exception as x: log(f"{coin} position re-check failed: {x}")
        if k < tries - 1: time.sleep(wait)
    return None

def _closing_fills(coin, t):
    try: return [f for f in info.user_fills_by_time(ACCOUNT, t["placed_ms"] - 60_000) if f["coin"] == coin and "Close" in str(f.get("dir", ""))
                 and int(f["time"]) >= t["placed_ms"] - 5_000]
    except Exception: return None

def _pending_drop(st, coin, t, why):
    p = _fresh_pos(coin, tries=2)
    if p:   # 2026-10-25 chipfix: never cancel the stop/TP of a live position - it is our fill, track it normally
        log(f"LIMIT {coin}: was about to drop ({why}) but the exchange holds the position - tracking it as a normal trade")
        return _pending_finalize(st, coin, t, p, "limit")
    for o in [o for o in own_orders() if o["coin"] == coin]: cancel(coin, o["oid"])
    rec = {"event": "limit_expired", "coin": coin, "side": t["side"], "limit_px": t["lim"], "planned_sz": t["planned_sz"], "reason": why,
           "realized": round(t.get("realized", 0.0), 4), "primary": t.get("primary")}
    if abs(t.get("realized", 0.0)) > 1e-9:   # a partial fill that was already closed on the exchange: keep the stats complete
        rec.update(event="closed", opened=iso(t["placed_ms"]), entry=t["lim"], pnl_usd=round(t["realized"], 4), R=None, tp1_done=False,
                   last_stop=t["stop"], votes=t["votes"], lev=t["lev"], strategies=t.get("strategies", []), risk_mult=t.get("risk_mult"), entry_type="limit_partial")
        st["cooldown"][coin] = time.time() + cfg["cooldown_bars"] * 900
    jl("trades.jsonl", rec); log(f"LIMIT {coin} done without a position ({why}) - orders cancelled, record removed")
    del st["trades"][coin]

def _pending_one(st, coin, t, pos, mids):
    is_long = t["side"] == "long"; p = pos.get(coin); mid = float(mids.get(coin, t["lim"]))
    ost, _ = _order_status(t["cloid"])
    if ost == "filled":
        p = p or _fresh_pos(coin)   # 2026-10-25 chipfix: pos snapshot was taken before the fill (CHIP 23:34) -> re-check the exchange
        if p: return _pending_finalize(st, coin, t, p, "limit")
        cf = _closing_fills(coin, t); t.setdefault("filled_seen_ms", nms())
        if cf: return _pending_drop(st, coin, t, f"filled then already closed (stop/TP on exchange, {len(cf)} closing fills)")
        if nms() - t["filled_seen_ms"] < 180_000:
            log(f"LIMIT {coin}: entry shows filled but no position and no closing fill yet - waiting (stops stay resting)"); return
        return _pending_drop(st, coin, t, "filled, but no position or closing fill found for 3 min")
    hit_stop = (mid <= t["stop"]) if is_long else (mid >= t["stop"]); hit_tp = (mid >= t["tp1"]) if is_long else (mid <= t["tp1"])
    late = nms() >= t["deadline_ms"]
    if ost == "open" and not (late or hit_stop or hit_tp): return
    if ost in (None, "unknownOid") and nms() - t["placed_ms"] < 60_000: return   # just placed: give the API a moment
    # ---- resolve: cancel the remainder, then market the unfilled size if the trade is still valid ----
    _CRIT[0] = True
    try:
        if ost == "open" and t.get("lim_oid"): cancel(coin, t["lim_oid"])
        elif ost == "open": ex.cancel_by_cloid(coin, Cloid.from_str(t["cloid"]))
        time.sleep(1)
        ost2, o2 = _order_status(t["cloid"])
        p = own_positions(info.user_state(ACCOUNT)).get(coin) if not perp_owned(coin) else None
        fsz = abs(float(p["szi"])) if p else 0.0
        if ost2 == "filled" and p: return _pending_finalize(st, coin, t, p, "limit")
        why = None
        if hit_stop or hit_tp: why = "price hit " + ("stop" if hit_stop else "TP1") + " before fill"
        elif not late: why = f"limit order ended on the exchange ({ost2})"
        elif nms() > t["deadline_ms"] + cfg["entry_stale_s"] * 1000: why = "fallback too late (computer paused)"
        elif not cfg.get("limit_fallback_market", True): why = "fallback disabled"
        elif coin in perp_claims()[0]: why = f"perp bot claims {coin}"
        elif os.path.exists(KILL) or st.get("halted_day") == now().strftime("%Y-%m-%d"): why = "kill/day stop"
        else:
            try:
                hi, lo = hilo_since(coin, t["placed_ms"])
                if hi is not None:
                    if (lo <= t["stop"]) if is_long else (hi >= t["stop"]): why = "stop level traded while the limit rested"
                    elif (hi >= t["tp1"]) if is_long else (lo <= t["tp1"]): why = "TP1 level traded while the limit rested"
            except Exception as x: why = f"validity check failed ({x})"
        try: mid = float(info.all_mids().get(coin, mid))   # fresh price (step snapshot can be old)
        except Exception: pass
        if why is None and ((mid <= t["stop"] * 1.001) if is_long else (mid >= t["stop"] * 0.999)): why = f"price {mid} at/through the stop"
        # 2026-10-26 focus: size the market part off the ACTUAL price -> total $ risk = plan (was planned_sz -> ~1.3x risk when chased)
        buf = cfg["stop_slip_buffer_pct"] / 100; d_lim = abs(t["lim"] - t["stop"]) + buf * t["lim"]
        plan_risk = t["planned_sz"] * d_lim; left = max(0.0, plan_risk - fsz * d_lim); d_now = abs(mid - t["stop"]) + buf * mid
        rem = rsz(coin, min(t["planned_sz"] - fsz, left / d_now)) if d_now > 0 else 0.0
        if why is None and rem * mid < 10.5: why = f"unfilled remainder {rem} below min notional"
        if why is None:
            lim = rpx(coin, mid * (1 + cfg["ioc_max_slippage"]) if is_long else mid * (1 - cfg["ioc_max_slippage"]))
            cid = new_cloid("entry"); t["fb_cloid"] = cid.to_raw(); wjson(STATE, st)
            try: good, res = okr(ex.order(coin, is_long, rem, lim, {"limit": {"tif": "Ioc"}}, cloid=cid))
            except Exception as x: good, res = False, f"raised {type(x).__name__}: {x}"
            log(f"LIMIT FALLBACK {coin}: market {'BUY' if is_long else 'SELL'} {rem} @~{mid} (filled {fsz}/{t['planned_sz']} at limit, sized for ${left:.3f} risk to stop {t['stop']}) lim {lim} -> {res}")
            jl("trades.jsonl", {"event": "limit_fallback", "coin": coin, "remaining": rem, "filled_at_limit": fsz, "mid": mid, "risk_left_usd": round(left, 4), "planned_sz": t["planned_sz"], "result": str(res)})
            for k in range(3):
                time.sleep(1.5)
                p = own_positions(info.user_state(ACCOUNT)).get(coin)
                if p and abs(float(p["szi"])) > fsz + 1e-12: break
            if p: return _pending_finalize(st, coin, t, p, "market_fallback" if fsz == 0 else "limit+market")
            return _pending_drop(st, coin, t, f"fallback did not fill ({res})")
        log(f"LIMIT {coin}: no fallback - {why}")
        if p: return _pending_finalize(st, coin, t, p, "limit_partial")
        return _pending_drop(st, coin, t, why)
    finally: _CRIT[0] = False

_SNAP = [0]   # 2026-10-26 focus: ms time of the last positions/orders/prices snapshot
def snapshot():
    us = info.user_state(ACCOUNT); pos = own_positions(us); oo = own_orders(); mids = info.all_mids(); _SNAP[0] = nms()
    return us, pos, oo, mids

def _snap_stale():
    return nms() - _SNAP[0] > cfg.get("snapshot_max_age_s", 45) * 1000

def manage_pending(st, pos, mids):
    for coin in [c for c, t in st["trades"].items() if t.get("pending")]:
        if coin not in st["trades"]: continue
        if _snap_stale():
            log(f"snapshot {(nms() - _SNAP[0]) // 1000}s old (computer paused?) - refreshing before the pending check"); _, pos, _, mids = snapshot()
        try: _pending_one(st, coin, st["trades"][coin], pos, mids)
        except Exception as x: log(f"pending limit {coin} error {x}\n{traceback.format_exc(limit=3)}")
        wjson(STATE, st)
        if _CRIT[1]: log("deferred SIGTERM - stopping now"); sys.exit(0)

def manage(st, pos, oo, mids):
    for coin in list(st["trades"]):
        if coin not in st["trades"]: continue
        if _snap_stale():   # 2026-10-26 focus: stale prices after a pause closed SUI/FARTCOIN/CASHCAT at 01:39 as 'breakeven' in profit
            log(f"snapshot {(nms() - _SNAP[0]) // 1000}s old (computer paused?) - refreshing positions/orders/prices before managing"); _, pos, oo, mids = snapshot()
        t = st["trades"][coin]; mine = [o for o in oo if o["coin"] == coin]
        if t.get("pending"): continue   # resting limit entry: handled by manage_pending (backup stop already on the exchange)
        if coin not in pos:   # flat: exchange stop / TP / close did it
            for o in mine: cancel(coin, o["oid"])
            pnl = t.get("realized", 0.0)
            jl("trades.jsonl", {"event": "closed", "coin": coin, "side": t["side"], "entry": t["entry"], "opened": iso(t["opened_ms"]),
                                "pnl_usd": round(pnl, 4), "R": round(pnl / t["risk_usd"], 3) if t["risk_usd"] else None,
                                "tp1_done": t["tp1_done"], "last_stop": t["stop"], "votes": t["votes"], "lev": t["lev"],
                                "primary": t.get("primary"), "strategies": t.get("strategies", []), "risk_mult": t.get("risk_mult")})
            log(f"FLAT {coin}: pnl ${pnl:.3f}"); st["cooldown"][coin] = time.time() + cfg["cooldown_bars"] * 900
            del st["trades"][coin]; continue
        p = pos[coin]; is_long = float(p["szi"]) > 0; sz = abs(float(p["szi"])); mid = float(mids.get(coin, p["entryPx"])); e = t["entry"]
        if (time.time() * 1000 - t["opened_ms"]) >= cfg["time_stop_h"] * 3_600_000:
            market_close(coin, "time_stop"); continue
        if not t["tp1_done"] and sz <= t["sz0"] * (1 - cfg["tp1_fraction"] / 2):
            t["tp1_done"] = True; log(f"TP1 filled on {coin}: remaining {sz}")
            jl("trades.jsonl", {"event": "tp1", "coin": coin, "remaining": sz})
        t["best"] = max(t["best"], mid) if is_long else min(t["best"], mid)
        cand = t["stop"]; be_bind = False
        # 2026-10-25 exec3: break-even at +be_arm_r R (bar wick or live mid). The peak is tracked from the mid every loop plus 1m candle
        # highs/lows since the last check (so a touch while the computer slept is not missed). Not a resting exchange trigger (HL has no
        # "move my stop when price X" order): checked on every wake/loop. The stop is only ever tightened.
        if cfg.get("be_arm_r") and not t.get("be_armed") and not t["tp1_done"]:
            d0 = t.setdefault("dist0", abs(e - t["stop"]))
            pk = t.get("peak", t["best"]); pk = max(pk, mid) if is_long else min(pk, mid)
            h0 = t.get("hl_ms", t["opened_ms"] - 60_000)
            if nms() - h0 >= cfg.get("be_hilo_refresh_s", 120) * 1000:
                try:
                    hi, lo = hilo_since(coin, h0)
                    if hi is not None: pk = max(pk, hi) if is_long else min(pk, lo)
                    t["hl_ms"] = nms() - 60_000
                except Exception as x: log(f"{coin} BE high/low fetch failed: {x}")
            t["peak"] = pk
            if d0 > 0 and ((pk - e) if is_long else (e - pk)) >= cfg["be_arm_r"] * d0:
                t["be_armed"] = True; log(f"BE ARMED {coin}: peak {pk} reached +{cfg['be_arm_r']}R (entry {e}, R {d0:.6g})")
                jl("trades.jsonl", {"event": "be_armed", "coin": coin, "peak": pk, "entry": e, "dist0": d0})
        if t.get("be_armed"):
            bep = e * (1 + cfg["be_fee_pct"] / 100) if is_long else e * (1 - cfg["be_fee_pct"] / 100)
            if (bep > cand) if is_long else (bep < cand): cand = bep; be_bind = True
        if t["tp1_done"]:
            be = e * (1 + cfg["breakeven_fee_pct"] / 100) if is_long else e * (1 - cfg["breakeven_fee_pct"] / 100)
            tr_ = t["best"] - cfg["trail_atr_mult"] * t["atr"] if is_long else t["best"] + cfg["trail_atr_mult"] * t["atr"]
            cand = max(cand, be, tr_) if is_long else min(cand, be, tr_)
        cand = rpx(coin, cand)
        # 2026-10-25 chipfix: self-heal a missing TP1 (tracked tp1, still full size, no take-profit resting) - at most every 5 min
        tps = [o for o in mine if o.get("isTrigger") and "Take Profit" in o.get("orderType", "")]
        if t.get("tp1") and t.get("tp1_ok") and not t["tp1_done"] and not tps and sz >= t["sz0"] - 1e-9 and time.time() - t.get("tp_retry", 0) > 300:
            t["tp_retry"] = time.time(); half = rsz(coin, sz * cfg["tp1_fraction"])
            if half * mid >= 10.5:
                good, trig, _ = place_trigger(coin, is_long, half, t["tp1"], "tp")
                log(f"TP1 RESTORED {coin} @ {trig} sz {half} -> {'ok' if good else 'FAILED'}")
                if good: t["tp1"] = trig
        sls = [o for o in mine if o.get("isTrigger") and "Stop" in o.get("orderType", "")]
        need_new = not sls or abs(sum(float(o["sz"]) for o in sls) - sz) > 1e-9 or \
                   ((cand - t["stop"]) if is_long else (t["stop"] - cand)) >= 0.1 * t["atr"]
        if need_new:
            thru = lambda m: (is_long and cand >= m * 0.999) or (not is_long and cand <= m * 1.001)
            if thru(mid):   # 2026-10-26 focus: never market-close on a cached price - confirm with a fresh one first
                try: m2 = float(info.all_mids().get(coin, mid))
                except Exception: m2 = mid
                if not thru(m2): log(f"{coin}: stop {cand} looked through the market on cached price {mid}, fresh price {m2} is not - placing the stop"); mid = m2
            if thru(mid):
                if not sls: market_close(coin, "stop through market, no stop resting")
                elif be_bind and not t["tp1_done"]: market_close(coin, "breakeven: armed but price already back at the BE level")
                continue
            good, trig, oid = place_trigger(coin, is_long, sz, cand, "sl")
            if good:
                log(f"STOP {coin} {t['stop']} -> {trig} (sz {sz})"); t["stop"] = trig
                for o in sls:
                    if o["oid"] != oid: cancel(coin, o["oid"])
            elif not sls: market_close(coin, "could not place any stop")

def enter(st, e, cap, pos, oo, us, mids, uni_row):
    coin = e["coin"]; guard(coin); is_long = e["signal"] == 1
    used = sum(float(p.get("marginUsed") or 0) for p in pos.values())
    used += sum(max(0.0, t["sz0"] - (abs(float(pos[c]["szi"])) if c in pos else 0.0)) * t["lim"] / (t.get("lev") or 1)
                for c, t in st["trades"].items() if t.get("pending"))   # margin a resting limit will take
    free = min(cap - used, account_free(us))
    side = "long" if is_long else "short"; nsame = samedir_count(st, side)   # 3rd+ same direction -> x samedir_risk_mult (0.25 since 2026-10-26)
    sdm = cfg["samedir_risk_mult"] if nsame >= cfg["samedir_half_from"] else 1.0; rm = e["risk_mult"] * sdm
    mid = float(mids[coin]); use_lim = bool(cfg.get("limit_entry"))
    lpx = rpx(coin, (e["bar_high"] + e["bar_low"]) / 2) if use_lim else mid
    sd_cap = cfg.get("samedir_max_risk_r", 3.0) * cfg["risk_per_trade"] * cap; sd_used = open_risk(st, pos, side)
    z = size_trade(cap, lpx, e["atr"], uni_row["maxlev"], open_risk(st, pos), free, e["stop_dist"], rm, side_room_usd=sd_cap - sd_used)
    if sdm < 1: log(f"{coin}: {nsame} scalper {side}s already open/pending - size x{sdm}")
    if sd_used > 0: log(f"{coin}: {side} open risk ${sd_used:.2f} of ${sd_cap:.2f} same-direction cap ({cfg.get('samedir_max_risk_r', 3.0)}R) -> risk ${z.get('risk_usd')}")
    if not z["ok"]: log(f"{coin} skip: {z.get('why')}"); return "skip_size"
    sz = rsz(coin, z["qty"])
    r = ex.update_leverage(z["lev"], coin, is_cross=False)
    if r.get("status") != "ok": log(f"{coin} leverage set failed {r}"); return "skip_lev"
    # the step-start position snapshot can be minutes old (slow bar / paused box): re-check the exchange right before ordering
    if any_position(info.user_state(ACCOUNT), coin): log(f"{coin}: exchange already holds a position - no entry"); return "skip_held_exchange"
    if any(o["coin"] == coin for o in info.frontend_open_orders(ACCOUNT)): log(f"{coin}: resting orders on exchange - no entry"); return "skip_held_exchange"
    if use_lim: return enter_limit(st, e, z, coin, is_long, sz, lpx, mid, rm, sdm)
    lim = rpx(coin, mid * (1 + cfg["ioc_max_slippage"]) if is_long else mid * (1 - cfg["ioc_max_slippage"]))
    opened_ms = nms() - 2000; cid = new_cloid("entry")
    st["pending_entry"] = {"coin": coin, "cloid": cid.to_raw(), "ts": nms()}; wjson(STATE, st)
    if perp_owned(coin):   # write-then-check (perpbot does the same): one of two simultaneous entries always sees the other
        st.pop("pending_entry", None); wjson(STATE, st); log(f"{coin}: perpbot claims it ({perp_claims()[0].get(coin)}) - no entry"); return "skip_perp_owned"
    try:
        good, res = okr(ex.order(coin, is_long, sz, lim, {"limit": {"tif": "Ioc"}}, cloid=cid))
    except Exception as x:
        good, res = False, f"order post raised {type(x).__name__}: {x}"
    log(f"ENTRY IOC {coin} {'BUY' if is_long else 'SELL'} {sz} lim {lim} {z['lev']}x cloid {cid.to_raw()} -> {res}")
    p = None
    for k in range(4):   # never conclude 'failed' from an error/timeout: ask the exchange (order status by cloid + position)
        try:
            p = own_positions(info.user_state(ACCOUNT)).get(coin)
            if p: break
            if good: break   # clean IOC answer and no position -> genuinely not filled
            os_ = info.query_order_by_cloid(ACCOUNT, cid)
            stt = (os_.get("order") or {}).get("status") if isinstance(os_, dict) else None
            log(f"{coin} entry verify {k+1}: order status {stt or os_.get('status') if isinstance(os_, dict) else os_}")
            if stt in ("canceled", "rejected", "marginCanceled") or (isinstance(os_, dict) and os_.get("status") == "unknownOid" and k >= 1): break
        except Exception as x: log(f"{coin} entry verify {k+1} failed: {x}")
        time.sleep(2)
    st.pop("pending_entry", None)
    if not p: return "not_filled"
    fsz = abs(float(p["szi"])); fpx = float(p["entryPx"]); dist = z["stop_dist"]; rdist = z["risk_dist"]
    stop = fpx - dist if is_long else fpx + dist; tp1 = fpx + e["tp_r"] * dist if is_long else fpx - e["tp_r"] * dist
    sl_ok, stop, _ = place_trigger(coin, is_long, fsz, stop, "sl")
    if not sl_ok: sl_ok, stop, _ = place_trigger(coin, is_long, fsz, stop, "sl")
    if not sl_ok: market_close(coin, "stop placement failed"); return "aborted_no_stop"
    half = rsz(coin, fsz * cfg["tp1_fraction"]); tp_ok = False
    if half * fpx >= 10.5: tp_ok, tp1, _ = place_trigger(coin, is_long, half, tp1, "tp")
    st["trades"][coin] = dict(side="long" if is_long else "short", entry=fpx, sz0=fsz, stop=stop, tp1=tp1, tp1_ok=tp_ok, tp1_done=False,
                              atr=e["atr"], best=fpx, risk_usd=fsz * rdist, lev=z["lev"], opened_ms=opened_ms, votes=e["votes"], realized=0.0,
                              primary=e["primary"], strategies=e["strategies"], risk_mult=rm, samedir_mult=sdm, dist0=z["stop_dist"])
    jl("trades.jsonl", {"event": "open", "coin": coin, "side": st["trades"][coin]["side"], "entry": fpx, "sz": fsz, "notional": round(fsz * fpx, 2),
                        "lev": z["lev"], "stop": stop, "tp1": tp1, "tp1_placed": tp_ok, "risk_usd": round(fsz * rdist, 3), "votes": e["votes"], "confirm": e.get("confirm"), "confirmers": e.get("confirmers"), "trend1h": e["trend"],
                        "primary": e["primary"], "strategies": e["strategies"], "risk_mult": rm, "samedir_mult": sdm, "tp_r": e["tp_r"], "setups": e["setups"], "est_liq_frac": z["est_liq_frac"], "liq_px": p.get("liquidationPx"), "entry_type": "market"})
    return "open"

def enter_limit(st, e, z, coin, is_long, sz, lpx, mid, rm, sdm):
    """GTC limit at the signal bar's midpoint: backup reduce-only SL first, then entry+SL+TP1 as one normalTpsl group."""
    dist = z["stop_dist"]; stop = rpx(coin, lpx - dist if is_long else lpx + dist); tp1 = rpx(coin, lpx + e["tp_r"] * dist if is_long else lpx - e["tp_r"] * dist)
    if (mid <= stop * 1.001) if is_long else (mid >= stop * 0.999): log(f"{coin}: price {mid} already at/through the stop {stop} - no entry"); return "skip_through_stop"
    side = "long" if is_long else "short"; now_ms = nms()
    cid, scid, tcid, bcid = new_cloid("lentry"), new_cloid("sl"), new_cloid("tp"), new_cloid("sl")
    half = rsz(coin, sz * cfg["tp1_fraction"]); with_tp = half * lpx >= 10.5
    st["pending_entry"] = {"coin": coin, "cloid": cid.to_raw(), "ts": now_ms}; wjson(STATE, st)
    if perp_owned(coin):
        st.pop("pending_entry", None); wjson(STATE, st); log(f"{coin}: perpbot claims it ({perp_claims()[0].get(coin)}) - no entry"); return "skip_perp_owned"
    st["trades"][coin] = dict(side=side, pending=True, lim=lpx, entry=lpx, sz0=sz, planned_sz=sz, stop=stop, tp1=tp1, tp1_ok=False, tp1_done=False,
                              atr=e["atr"], best=lpx, risk_usd=z["risk_usd"], lev=z["lev"], opened_ms=now_ms, placed_ms=now_ms,
                              deadline_ms=now_ms + int(cfg.get("limit_fallback_s", 300)) * 1000, cloid=cid.to_raw(), sl_cloid=scid.to_raw(), tp_cloid=tcid.to_raw() if with_tp else None,
                              bk_cloid=bcid.to_raw(), votes=e["votes"], realized=0.0, primary=e["primary"], strategies=e["strategies"], risk_mult=rm,
                              samedir_mult=sdm, tp_r=e["tp_r"], confirm=e.get("confirm"), confirmers=e.get("confirmers"), trend1h=e["trend"],
                              setups=e["setups"], est_liq_frac=z["est_liq_frac"], bar_high=e["bar_high"], bar_low=e["bar_low"])
    st.pop("pending_entry", None); wjson(STATE, st)   # the trades record now holds the claim (perp bot reads it)
    t = st["trades"][coin]; slx = lambda trig: rpx(coin, trig * (0.9 if is_long else 1.1))
    # (1) backup SL, before any fill is possible
    bk_ok = False
    for _ in range(2):
        try:
            good, res = okr(ex.order(coin, not is_long, sz, slx(stop), {"trigger": {"triggerPx": stop, "isMarket": True, "tpsl": "sl"}}, reduce_only=True, cloid=bcid))
        except Exception as x: good, res = False, f"raised {type(x).__name__}: {x}"
        log(f"BACKUP SL {coin} @ {stop} sz {sz} -> {res}")
        if good: bk_ok = True; break
        if _order_status(bcid.to_raw())[0] == "open": bk_ok = True; break
    if not bk_ok:
        for o in [o for o in own_orders() if o["coin"] == coin]: cancel(coin, o["oid"])
        del st["trades"][coin]; log(f"{coin}: backup stop could not be placed - limit entry NOT placed"); return "aborted_no_stop"
    # (2) grouped entry + children
    reqs = [{"coin": coin, "is_buy": is_long, "sz": sz, "limit_px": lpx, "order_type": {"limit": {"tif": "Gtc"}}, "reduce_only": False, "cloid": cid},
            {"coin": coin, "is_buy": not is_long, "sz": sz, "limit_px": slx(stop), "order_type": {"trigger": {"triggerPx": stop, "isMarket": True, "tpsl": "sl"}}, "reduce_only": True, "cloid": scid}]
    if with_tp:
        reqs.append({"coin": coin, "is_buy": not is_long, "sz": half, "limit_px": rpx(coin, tp1 * (0.9 if is_long else 1.1)),
                     "order_type": {"trigger": {"triggerPx": tp1, "isMarket": True, "tpsl": "tp"}}, "reduce_only": True, "cloid": tcid})
    try: r = ex.bulk_orders(reqs, grouping="normalTpsl"); sts = r["response"]["data"]["statuses"] if r.get("status") == "ok" else [r]
    except Exception as x: r, sts = None, [f"raised {type(x).__name__}: {x}"]
    s0 = sts[0] if sts else None
    log(f"ENTRY LIMIT {coin} {'BUY' if is_long else 'SELL'} {sz} @ {lpx} (bar mid, mkt {mid}) {z['lev']}x stop {stop} tp1 {tp1 if with_tp else '-'} cloid {cid.to_raw()} -> {sts}")
    if isinstance(s0, dict) and "resting" in s0: t["lim_oid"] = s0["resting"]["oid"]
    elif isinstance(s0, dict) and "filled" in s0: t["instant"] = True   # marketable at placement: re-base stop/TP on the fill
    else:
        ost, _ = _order_status(cid.to_raw())
        if ost not in ("open", "filled"):
            for o in [o for o in own_orders() if o["coin"] == coin]: cancel(coin, o["oid"])
            if not own_positions(info.user_state(ACCOUNT)).get(coin):
                del st["trades"][coin]; jl("trades.jsonl", {"event": "limit_rejected", "coin": coin, "result": str(sts)}); return "limit_rejected"
    jl("trades.jsonl", {"event": "limit_placed", "coin": coin, "side": side, "limit_px": lpx, "sz": sz, "stop": stop, "tp1": tp1 if with_tp else None,
                        "risk_usd": z["risk_usd"], "lev": z["lev"], "deadline": iso(t["deadline_ms"]), "mkt": mid, "primary": e["primary"],
                        "risk_mult": rm, "samedir_mult": sdm, "result": str(sts)})
    return "limit_placed"

def step(st):
    us, pos, oo, mids = snapshot()
    sync_pnl(st)
    cap, upnl = scalper_capital(st, pos)
    wjson(CAPF, {"updated": now().isoformat(), "scalper_equity_usd": round(cap, 4), "base": cfg["base_capital_usd"], "realized": st["realized"],
                 "funding": st["funding"], "upnl": upnl})
    today = now().strftime("%Y-%m-%d")
    if st["day"] != today: st.update(day=today, day_start_cap=cap); log(f"new UTC day, scalper capital {cap:.2f}")
    if st["halted_day"] != today and cap <= st["day_start_cap"] * (1 - cfg["day_stop_pct"] / 100):
        st["halted_day"] = today; log(f"DAY STOP: capital {cap:.2f} vs day start {st['day_start_cap']:.2f} - no new entries today")
        jl("decisions.jsonl", {"event": "day_stop", "cap": cap, "day_start": st["day_start_cap"]})
    fills = reconcile(st, pos, oo)
    if st.pop("untracked_fill_coins", None) or not st.get("trips_checked"):
        try: log_untracked_closes(st, fills or recent_fills(), pos); st["trips_checked"] = True
        except Exception as x: log(f"untracked-close backfill failed: {x}")
    if any(t.get("pending") for t in st["trades"].values()):
        manage_pending(st, pos, mids); us, pos, oo, mids = snapshot()
    manage(st, pos, oo, mids)
    for o in oo:   # orphan own orders on coins we hold no position/trade in
        if o["coin"] not in pos and o["coin"] not in st["trades"]: cancel(o["coin"], o["oid"])
    if time.time() * 1000 - st["uni_ts"] > cfg["universe_refresh_h"] * 3_600_000 or not st["universe"]:
        st["universe"], rej = pick_universe(); st["uni_ts"] = nms()
        jl("decisions.jsonl", {"event": "universe", "coins": [u["coin"] for u in st["universe"]], "rejected_spread": rej}); log(f"universe {[u['coin'] for u in st['universe']]}")
    bar = (nms() // 900_000) * 900_000
    if st["last_bar"] >= bar or time.time() * 1000 - bar < cfg["candle_close_delay_s"] * 1000: return cap
    st["last_bar"] = bar
    if time.time() * 1000 - bar > cfg["entry_stale_s"] * 1000:
        log(f"bar {iso(bar)} closed {int((nms()-bar)/1000)}s ago (computer was paused) - stale, no entries"); jl("gaps.jsonl", {"event": "stale_bar", "bar": iso(bar), "late_s": (nms() - bar) // 1000}); return cap
    load_meta(); b = refresh_btc(); log(f"bar {iso(bar)} BTC ctx {b}")
    for u in st["universe"]:
        coin = u["coin"]
        try: e = evaluate(coin, l2=True)
        except Exception as x: log(f"{coin} eval failed: {x}"); continue
        rec = {"event": "eval", "coin": coin, "bar": iso(bar), "votes": e["votes"], "trend1h": e["trend"], "adx1h": e["adx1h"], "signal": e["signal"],
               "primary": e["primary"], "risk_mult": e["risk_mult"], "setups": e["setups"], "block": e["block"], "confirm": e.get("confirm"), "n_confirm": e.get("n_confirm"),
               "blocked_signal": e.get("blocked_signal"), "blocked_primary": e.get("blocked_primary"), "btc": e.get("btc")}
        if e["bar_close"] != bar: rec["action"] = "stale_candle"; jl("decisions.jsonl", rec); continue
        s = e["signal"]; f = float(META.get(coin, {}).get("funding") or 0); act = "none"
        if s:
            if e["primary"] == "CORE" and s != e["trend"]: act = "skip_trend"
            elif st["halted_day"] == today: act = "skip_day_stop"
            elif coin in pos or coin in st["trades"]: act = "skip_held"
            elif perp_owned(coin): act = "skip_perp_owned"
            elif time.time() < st["cooldown"].get(coin, 0): act = "skip_cooldown"
            elif time.time() - st.setdefault("last_entry", {}).get(coin, 0) < cfg["entry_refractory_bars"] * 900: act = "skip_refractory"
            elif len(set(pos) | set(st["trades"])) >= cfg["max_open"]: act = "skip_max_open"   # resting limits count
            elif funding_blocks(s, f): act = "skip_funding"
            elif os.path.exists(KILL): act = "skip_kill"
            else:
                try:
                    _CRIT[0] = True
                    act = enter(st, e, cap, pos, oo, us, mids, u)
                    if act in ("open", "limit_placed"): st.setdefault("last_entry", {})[coin] = time.time()
                except Exception as x: act = f"entry_error {type(x).__name__}"; log(f"{coin} entry error {x}\n{traceback.format_exc(limit=3)}")
                finally: _CRIT[0] = False
                wjson(STATE, st)
                if _CRIT[1]: jl("decisions.jsonl", dict(rec, action=act)); log("deferred SIGTERM - stopping now"); sys.exit(0)
                us = info.user_state(ACCOUNT); pos = own_positions(us); cap, _ = scalper_capital(st, pos)
        rec["action"] = "blocked" if act == "none" and e.get("blocked_signal") else act; jl("decisions.jsonl", rec)
        if rec["action"] == "blocked": log(f"{coin} BLOCKED {'long' if e['blocked_signal'] == 1 else 'short'} ({e['blocked_primary']}): {e['block']}")
    return cap

def write_status(st, cap, err):
    try:
        cl = [json.loads(l) for l in open(P("trades.jsonl")) if '"closed"' in l] if os.path.exists(P("trades.jsonl")) else []
        per = {}
        for s in ALL + ["CORE"]:
            sub = [t for t in cl if s in t.get("strategies", []) or t.get("primary") == s]
            prim = [t for t in sub if t.get("primary") == s]
            per[s] = {"trades": len(sub), "wins": sum(t["pnl_usd"] > 0 for t in sub), "pnl": round(sum(t["pnl_usd"] for t in sub), 4),
                      "as_primary": len(prim), "primary_pnl": round(sum(t["pnl_usd"] for t in prim), 4), "R_sum": round(sum(t["R"] or 0 for t in sub), 3),
                      "solo": sum(1 for t in prim if (t.get("risk_mult") or 1) < 1)}
        days = max((nms() - st["start_ms"]) / 86_400_000, 1 / 24)
        wjson(STATUS, {"updated": now().isoformat(), "capital": cap, "base": cfg["base_capital_usd"], "day_start": st["day_start_cap"],
                       "halted_today": st["halted_day"] == now().strftime("%Y-%m-%d"), "open": st["trades"], "universe": [u["coin"] for u in st["universe"]],
                       "closed_trades": len(cl), "trades_per_day": round(len(cl) / days, 2),
                       "win_rate": round(sum(t["pnl_usd"] > 0 for t in cl) / len(cl), 3) if cl else None,
                       "avg_R": round(sum(t["R"] or 0 for t in cl) / len(cl), 3) if cl else None,
                       "pnl_usd": round(sum(t["pnl_usd"] for t in cl), 4), "per_strategy": per, "last_error": err})
        wjson(P("summary.json"), json.load(open(STATUS)))
    except Exception as e: log(f"status write failed {e}")

def kill_switch(st):
    log("KILL file: closing scalper positions + cancelling scalper orders (perpbot untouched)")
    try:
        us = info.user_state(ACCOUNT)
        for c in own_positions(us): market_close(c, "kill")
        for o in own_orders(): cancel(o["coin"], o["oid"])
    except Exception as e: log(f"kill error {e}")
    wjson(STATE, st); sys.exit(4)

_CRIT = [False, False]   # [entry in flight, SIGTERM pending]
_LOCK = None
def acquire_lock():
    global _LOCK
    import fcntl
    fd = os.open(P("bot.lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: os.close(fd); log("LOCK REFUSED: another scalper instance is running - exiting."); sys.exit(5)
    os.ftruncate(fd, 0); os.pwrite(fd, str(os.getpid()).encode(), 0); _LOCK = fd

def main_loop():
    def _term(*a):
        if _CRIT[0]: _CRIT[1] = True; log("SIGTERM during an entry - finishing the entry (stop placement) first"); return
        log("SIGTERM - stopping (positions keep their exchange stops)"); sys.exit(0)
    signal.signal(signal.SIGTERM, _term)
    st = load_state(); _ST.update(st); st = _ST; last = time.time()
    log(f"START scalper: base ${cfg['base_capital_usd']}, max {cfg['max_open']} open, <= {cfg['max_leverage']}x isolated, risk {cfg['risk_per_trade']:.2%}, open-risk cap {cfg['max_open_risk_pct']}%, day stop -{cfg['day_stop_pct']}%")
    while True:
        if os.path.exists(KILL): kill_switch(st)
        if time.time() - last > 120: jl("gaps.jsonl", {"event": "gap", "seconds": int(time.time() - last)}); log(f"gap {int(time.time()-last)}s (computer paused)")
        last = time.time(); err = None; cap = None
        try: cap = step(st)
        except SystemExit: raise
        except Exception as e: err = f"{type(e).__name__}: {e}"; log("ERROR " + err + "\n" + traceback.format_exc(limit=3))
        wjson(STATE, st); write_status(st, cap, err)
        for _ in range(cfg["loop_seconds"]):
            if os.path.exists(KILL): kill_switch(st)
            time.sleep(1)

if __name__ == "__main__":
    if DRY: dry_run()
    acquire_lock(); live_init(); main_loop()
