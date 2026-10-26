#!/usr/bin/env python3
"""Hyperliquid perp bot: SOL + BTC, 1h closed candles (interval from config), 4-strategy vote (>=3 agree, none opposing) + 4h trend filter.
Usage:  python bot.py --dry-run   (public mainnet data, signals only, never places orders, needs no keys)
        python bot.py             (LIVE; needs env HL_ACCOUNT + HL_API_KEY = trade-only API/agent wallet key)
Exit codes: 0 normal/clean, 3 missing/invalid credentials or config (run.sh will not restart), 4 kill switch, 5 another instance holds bot.lock (run.sh will not restart)."""
import json, os, sys, time, math, signal, traceback
from datetime import datetime, timezone
import pandas as pd
from hyperliquid.info import Info
from hyperliquid.utils import constants
import strategies
from strategies import STRATS, combine, atr, ema

HERE = os.path.dirname(os.path.abspath(__file__))
KILL = os.path.join(HERE, "KILL"); FILLS = os.path.join(HERE, "fills.jsonl")
STATUS = os.path.join(HERE, "status.json"); STATE = os.path.join(HERE, "state.json"); LOG = os.path.join(HERE, "bot.log")
# Hard caps: config values are clamped to these no matter what config.json says.
HARD = {"max_leverage": 7, "isolated_leverage": 7, "risk_per_trade": 0.05, "max_positions": 8, "max_same_direction": 8, "max_open_risk_pct": 15.0, "max_position_notional_x": 7.0, "daily_halt_pct": 10.0, "daily_defensive_pct": 10.0,
        "defensive_risk_per_trade": 0.02}  # 2026-10-25 bigpos user: open-risk 15%, per-position notional <= 7x allocated equity (margin-bound at 7x isolated)  # fix124 user: risk 5%  # 2026-10-24 user request: 2% risk, 3x, two-tier day stop (-5% defensive, -10% halt)
DRY = "--dry-run" in sys.argv

def now(): return datetime.now(timezone.utc)
def log(msg):
    line = f"{now():%Y-%m-%d %H:%M:%S}Z {msg}"; print(line, flush=True)
    if not DRY:
        with open(LOG, "a") as f: f.write(line + "\n")
def jl(rec):
    rec = {"ts": now().isoformat(), **rec}
    with open(FILLS, "a") as f: f.write(json.dumps(rec, default=str) + "\n")
def wjson(path, obj):
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w"), indent=2, default=str); os.replace(tmp, path)

cfg = json.load(open(os.path.join(HERE, "config.json")))
if cfg.get("margin_mode") != "isolated": log("config error: margin_mode must be isolated"); sys.exit(3)
for k, cap in HARD.items():
    if cfg[k] > cap: log(f"config {k}={cfg[k]} exceeds hard cap {cap}; clamping"); cfg[k] = cap
# defensive tier must be at least as strict as normal, and trigger before the halt
if cfg["defensive_risk_per_trade"] > cfg["risk_per_trade"]: cfg["defensive_risk_per_trade"] = cfg["risk_per_trade"]
if cfg["defensive_min_agree"] < cfg["min_agree"]: cfg["defensive_min_agree"] = cfg["min_agree"]
if cfg["daily_defensive_pct"] > cfg["daily_halt_pct"]: cfg["daily_defensive_pct"] = cfg["daily_halt_pct"]
strategies.BARS_PER_DAY = {"1h": 24, "4h": 6}[cfg["interval"]]
from hyperliquid.utils.error import ClientError
# ---- network hardening (2026-10-25): the SDK's requests.Session had NO timeout, so after the computer paused/woke a dead
# keep-alive socket made recv() block forever (py-spy: user_fills_by_time -> ssl.read). Every HL HTTP call (Info AND Exchange)
# now has a (connect 5s, read 10s) timeout; idle > 60s (wall clock, so it counts a pause) drops pooled sockets first.
# Info reads retry on timeout/connection errors with backoff 1/2/4 s; Exchange (order) posts retry ONLY when the connection
# was never made (ConnectTimeout), so an order can never be sent twice. No websocket is used (skip_ws=True everywhere).
import requests
from hyperliquid.api import API
HTTP_TIMEOUT = (5, 10); HEARTBEAT = os.path.join(HERE, ".heartbeat"); _HB = [0.0]
def _new_session(api):
    try: api.session.close()
    except Exception: pass
    api.session = requests.Session(); api.session.headers.update({"Content-Type": "application/json"})
_api_post_raw = API.post
def _api_post_safe(self, url_path, payload=None):
    if time.time() - getattr(self, "_last_ok", time.time()) > 60: _new_session(self)
    self.timeout = HTTP_TIMEOUT; is_ex = url_path == "/exchange"
    for k in range(4):
        try:
            r = _api_post_raw(self, url_path, payload); self._last_ok = time.time()
            if time.time() - _HB[0] > 10:
                _HB[0] = time.time()
                try: open(HEARTBEAT, "w").write(str(int(_HB[0])))
                except Exception: pass
            return r
        except requests.exceptions.RequestException as e:
            retry = isinstance(e, requests.exceptions.ConnectTimeout) if is_ex else isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError))
            _new_session(self)
            if not retry or k == 3: raise
            log(f"network {type(e).__name__} on {url_path} ({'exchange' if is_ex else 'info'}), retry {k+1}/3 in {2**k}s"); time.sleep(2**k)
API.post = _api_post_safe
_orig_post = Info.post
def _post_retry(self, path, payload=None):
    """Retry Info reads on HTTP 429 (rate limit) with backoff: 2, 4, 8, 16 s."""
    for k in range(5):
        try: return _orig_post(self, path, payload)
        except ClientError as e:
            if e.status_code != 429 or k == 4: raise
            time.sleep(2**(k+1))
Info.post = _post_retry
BASE = constants.MAINNET_API_URL if cfg["network"] == "mainnet" else constants.TESTNET_API_URL

MS = {"1h": 3600_000, "4h": 14400_000}

_CC = {}   # candle cache: (coin, interval) -> {open_ms: raw candle}
def candles(info, coin, interval=None, need=None, min_bars=1500):
    """Closed candles. First call per coin/interval: paginated backwards until `need` bars. Later calls: only the last few bars
    are fetched and merged into the cache (keeps 7 coins well under Hyperliquid's rate limit)."""
    interval = interval or cfg["interval"]; need = need or cfg["candles_lookback"]; ms = MS[interval]; end = int(time.time()*1000)
    key = (coin, interval); got = _CC.get(key)
    if got and len(got) >= need and max(got) >= end - ms*50:
        c = info.candles_snapshot(coin, interval, max(got) - 3*ms, end)
        for x in c or []: got[x["t"]] = x
        for t0 in sorted(got)[:-(need + 20)]: del got[t0]
        time.sleep(cfg.get("fetch_pace_s", 0.3))
        return _to_df(got, end, coin, interval, min_bars)
    got, hi = {}, end
    for _ in range(10):
        lo = max(hi - ms*min(need + 5, 4000), end - ms*(need + 5))
        c = info.candles_snapshot(coin, interval, lo, hi)
        if not c: break
        for x in c: got[x["t"]] = x
        first = min(x["t"] for x in c)
        if len(got) >= need + 1 or lo <= end - ms*(need + 5) or first >= hi: break
        hi = first - 1
    _CC[key] = got; time.sleep(cfg.get("fetch_pace_s", 0.3))
    return _to_df(got, end, coin, interval, min_bars)

def _to_df(got, end, coin, interval, min_bars):
    df = pd.DataFrame(sorted(got.values(), key=lambda x: x["t"])); df = df[df["T"] < end]   # closed candles only
    if len(df) < min_bars: raise RuntimeError(f"{coin} {interval}: only {len(df)} closed candles (<{min_bars})")
    return pd.DataFrame({"ts": pd.to_datetime(df.t, unit="ms", utc=True), "open": df.o.astype(float), "high": df.h.astype(float),
                         "low": df.l.astype(float), "close": df.c.astype(float)}).set_index("ts")

def htf_trend(info, coin):
    """4h filter: +1 if EMA50 > EMA200 and close > EMA50; -1 mirrored; else 0. Returns (value, detail)."""
    if not cfg.get("htf_filter", True): return 0, {}
    d = candles(info, coin, cfg["htf_interval"], 600, cfg["htf_ema_slow"] + 10)
    ef, es, c = ema(d.close, cfg["htf_ema_fast"]).iat[-1], ema(d.close, cfg["htf_ema_slow"]).iat[-1], d.close.iat[-1]
    v = 1 if (ef > es and c > ef) else (-1 if (ef < es and c < ef) else 0)
    return v, {"htf_candle": str(d.index[-1]), "htf_close": c, "htf_ema_fast": round(float(ef), 6), "htf_ema_slow": round(float(es), 6)}

def signals(info, coin):
    """signal/prev_signal: >= min_agree of the 4 strategies, none opposing (used for exits and normal entries);
    def_signal/def_prev use defensive_min_agree. htf_filter is logged in votes_log but is NOT a vote; entries require htf == signal."""
    df = candles(info, coin); sg = {k: f(df) for k, f in STRATS.items()}
    votes = {k: int(x.iat[-1]) for k, x in sg.items()}; pv = {k: int(x.iat[-2]) for k, x in sg.items()}
    h, hd = htf_trend(info, coin)
    a = atr(df); ap = a/df.close; med = float(ap.iloc[-cfg["vol_filter_bars"]:].median()); ratio = float(ap.iat[-1])/med if med else 1.0
    vol_ok = (not cfg.get("vol_filter", True)) or ratio >= cfg["vol_filter_min_ratio"]
    vd = {"atr_pct": round(100*float(ap.iat[-1]), 4), "median_atr_pct_30d": round(100*med, 4), "ratio": round(ratio, 3), "ok": vol_ok}
    return dict(coin=coin, candle=str(df.index[-1]), close=df.close.iat[-1], atr=float(a.iat[-1]), votes=votes,
                votes_log={**votes, "htf_filter": h, "vol_filter": 1 if vol_ok else 0}, htf=h, htf_detail=hd, vol_ok=vol_ok, vol_detail=vd,
                signal=combine(votes, cfg["min_agree"]), prev_signal=combine(pv, cfg["min_agree"]),
                def_signal=combine(votes, cfg["defensive_min_agree"]), def_prev=combine(pv, cfg["defensive_min_agree"]))

def funding_and_mid(info, coin):
    m, ctx = info.meta_and_asset_ctxs(); i = [a["name"] for a in m["universe"]].index(coin)
    return float(ctx[i]["funding"]), float(ctx[i].get("midPx") or ctx[i]["markPx"])

_ML = {}
def iso_lev(info, coin):
    """Exchange isolated leverage for a coin: isolated_leverage capped at the coin's maxLeverage."""
    if not _ML: _ML.update({a["name"]: a["maxLeverage"] for a in info.meta()["universe"]})
    return min(cfg.get("isolated_leverage", cfg["max_leverage"]), _ML[coin]), _ML[coin]

def liq_check(info, coin, px, stop_dist):
    """Estimated isolated liquidation distance = 1/lev - maintenance (1/(2*maxLeverage)). Entry allowed only if it is
    >= liq_min_stop_mult x the stop distance. Returns (ok, liq_frac, stop_frac, lev, margin_frac_of_notional)."""
    lev, ml = iso_lev(info, coin); liq = 1/lev - 1/(2*ml); sf = stop_dist/px
    return liq >= cfg["liq_min_stop_mult"]*sf, liq, sf, lev, 1/lev

def open_risk(st, pos):
    """Sum over open positions of size x distance from entry to the current stop when that stop is still a loss
    (break-even / trailed-into-profit stops count 0). Returns ($ total, {coin: $})."""
    per = {}
    for c, p in pos.items():
        t = st["trades"].get(c) if st else None; sz = abs(float(p["szi"])); e = float(p["entryPx"]); lg = float(p["szi"]) > 0
        if not t or not t.get("stop"): per[c] = sz*e*0.05; continue          # unknown stop: assume 5% to stay conservative
        per[c] = max(0.0, (e - t["stop"]) if lg else (t["stop"] - e))*sz
    return sum(per.values()), per

# ---------------- 2026-10-25 expand: mutual lockout with the scalper (/workspace/hlscalp) ----------------
# The perp bot owns a coin's position/orders only when it opened them: its own st["trades"] record or its own fresh pending_entry.
# The original 7 coins are never traded by the scalper (its static perp_bot_coins), so they keep the old "any position is ours" rule.
# On every other coin: positions/orders the scalper claims (its state.json trades, its pending_entry, orders with its 0x5ca1 cloid)
# and positions with no perp record are FOREIGN: never adopted, managed, closed or cancelled here, and they block perp entries.
SCALP_STATE = "/workspace/hlscalp/state.json"; SCALP_PREFIX = "0x5ca1"; PENDING_MAX_S = 900
LEGACY_COINS = {"BTC", "ETH", "SOL", "HYPE", "XRP", "ZEC", "NEAR"}
_ST = {}; _SC = {"claims": None}; _ALLPOS = {}; _WARNED = {}
def scalper_claims():
    """{coin: why} for coins the scalper owns or is entering. Keeps the last good read if the file is mid-write/unreadable;
    returns (claims, ok) - ok False only if it was never readable (callers then refuse entries on non-legacy coins)."""
    try:
        s = json.load(open(SCALP_STATE)); c = {k: "scalper open trade" for k in (s.get("trades") or {})}
        pe = s.get("pending_entry") or {}
        if pe.get("coin") and time.time()*1000 - float(pe.get("ts") or 0) < PENDING_MAX_S*1000: c[pe["coin"]] = "scalper entry in flight"
        _SC["claims"] = c
    except Exception: pass
    return dict(_SC["claims"] or {}), _SC["claims"] is not None
def is_foreign_order(o): return str(o.get("cloid") or "").startswith(SCALP_PREFIX)
def my_pending(st=None):
    pe = (st if st is not None else _ST).get("pending_entry") or {}
    return pe.get("coin") if pe.get("coin") and time.time() - float(pe.get("ts") or 0) < PENDING_MAX_S else None
def perp_owns(coin, st=None):
    """Position on `coin` belongs to the perp bot? (record / own pending entry win; legacy coins always ours unless the scalper claims them)."""
    st = st if st is not None else _ST
    if coin in (st.get("trades") or {}) or coin == my_pending(st): return True
    if coin in scalper_claims()[0]: return False
    return coin in LEGACY_COINS
def warn_once(key, msg, every_s=3600):
    if time.time() - _WARNED.get(key, 0) >= every_s: _WARNED[key] = time.time(); log(msg)
def lockout_reason(st, coin):
    """FRESH exchange + scalper-state check right before a perp entry. None = coin is free; else why the entry must be skipped."""
    claims, ok_ = scalper_claims()
    if not ok_ and coin not in LEGACY_COINS: return "scalper state.json unreadable - not entering a shared coin"
    if coin in claims: return f"{claims[coin]} on {coin}"
    us = info.user_state(ACCOUNT)
    for p in us["assetPositions"]:
        q = p["position"]
        if q["coin"] == coin and float(q["szi"]) != 0 and coin not in st["trades"]: return f"exchange already has a {q['szi']} {coin} position not owned by the perp bot"
    oo = [o for o in info.frontend_open_orders(ACCOUNT) if o["coin"] == coin]
    if oo: return f"{len(oo)} resting order(s) on {coin} ({'scalper cloid' if any(map(is_foreign_order, oo)) else 'not owned by a perp position'})"
    return None
def close_windows(st, coin=None, at_ms=None):
    """Perp ownership windows (read by the scalper to keep perp fills/funding out of its P&L): close open ones for coin (or stale ones)."""
    at_ms = at_ms or int(time.time()*1000)
    for w in st.setdefault("owned", []):
        if w.get("end") is None and (w["coin"] == coin or (coin is None and w["coin"] not in st["trades"] and w["coin"] != my_pending(st))): w["end"] = at_ms
    st["owned"] = st["owned"][-200:]

def margin_budget(info, addr, eq_alloc, bot_coins):
    """2026-10-25 bigpos: isolated margin this bot may still commit = min(
         its allocated equity - margin its own positions use,
         account free collateral - the scalper's own unused capital (scalper equity - scalper margin used)).
    The second term means perp margin never takes collateral the scalper is entitled to, whatever the account totals say."""
    eq_acct, us, d = unified_equity(info, addr)
    bot_used = scalp_used = 0.0
    for p in us["assetPositions"]:
        q = p["position"]
        if float(q["szi"]) == 0: continue
        if q["coin"] in bot_coins: bot_used += float(q.get("marginUsed") or 0)
        else: scalp_used += float(q.get("marginUsed") or 0)
    acct_free = max(0.0, d["spot_usdc"] - d["spot_hold"]) if d["spot_counted"] else float(us.get("withdrawable") or 0)
    scalp_eq = max(0.0, eq_acct - eq_alloc)                     # >= scalper equity (also covers capital_cap_usd)
    scalp_reserve = max(0.0, scalp_eq - scalp_used)
    a, b = max(0.0, eq_alloc - bot_used), max(0.0, acct_free - scalp_reserve)
    return min(a, b), {"bot_used": bot_used, "scalp_used": scalp_used, "acct_free": acct_free, "scalp_reserve": scalp_reserve,
                       "free_by_allocation": a, "free_by_account": b}

def plan_size(eq, dist, ref, risk, lev, free, orisk):
    """Target size = min(risk% of allocated equity / stop distance, per-position notional cap, open-risk room / stop distance).
    fits=False when its isolated margin (notional/lev, +3% for fees/slippage) exceeds the free margin budget -> the entry is SKIPPED (not shrunk)."""
    risk_sz = risk*eq/dist; cap_sz = eq*cfg["max_position_notional_x"]/ref
    room = max(0.0, cfg["max_open_risk_pct"]/100*eq - orisk); room_sz = room/dist
    sz = min(risk_sz, cap_sz, room_sz)
    binds = [n for n, v in (("per-position-cap", cap_sz), ("open-risk", room_sz)) if v < risk_sz and v == sz]
    margin = sz*ref/lev*1.03
    return {"sz": sz, "risk_sz": risk_sz, "cap_notional": eq*cfg["max_position_notional_x"], "room": room, "binds": binds,
            "margin": margin, "free": free, "fits": margin <= free}

def funding_blocks(side, f):
    """side +1 long / -1 short. Positive funding = longs pay. Blocks if the trade would PAY more than max_adverse_funding_per_h."""
    return (side == 1 and f > cfg["max_adverse_funding_per_h"]) or (side == -1 and f < -cfg["max_adverse_funding_per_h"])

def unified_equity(info, account_addr):
    """Equity = perp accountValue (+ spot USDC total when the account is in unified mode, or perp ~0 with spot USDC > 0).
    Returns (equity, perp_user_state, detail dict)."""
    us = info.user_state(account_addr); perp = float(us["marginSummary"]["accountValue"])
    try: mode = info.post("/info", {"type": "userAbstraction", "user": account_addr})
    except Exception: mode = None
    spot, hold = 0.0, 0.0
    try:
        for b in info.spot_user_state(account_addr)["balances"]:
            if b["coin"] == "USDC": spot = float(b["total"]); hold = float(b.get("hold") or 0)
    except Exception: spot, hold = 0.0, 0.0
    use_spot = (mode in ("unifiedAccount", "portfolioMargin")) or (perp < 0.5 and spot > 0)
    # Unified (verified live 20:45Z with BTC+ETH open): spot USDC "total" already includes position margin AND uPnL
    # (hold == perp accountValue == sum marginUsed). perp + total double counts (105.45 vs true 84.52).
    # Equity = spot total; cross-check = perp + (total - hold).
    upnl = sum(float(p["position"]["unrealizedPnl"]) for p in us["assetPositions"])
    if use_spot: eq = spot
    else: eq = perp
    return eq, us, {"perp_account_value": perp, "spot_usdc": spot, "spot_hold": hold, "upnl": upnl, "abstraction": mode, "spot_counted": use_spot,
                    "cross_check_perp_plus_free_spot": perp + max(0.0, spot - hold)}

def size_for(coin_px, atr_v, eq, szd, risk=None):
    """Risk% of equity on a stop_atr_mult*ATR stop, capped at max_position_notional_x*eq notional (no margin/open-risk check)."""
    risk = cfg["risk_per_trade"] if risk is None else risk
    dist = cfg["stop_atr_mult"]*atr_v; max_notional = eq*cfg["max_position_notional_x"]
    raw = risk*eq/dist; capped = min(raw, max_notional/coin_px); sz = math.floor(capped*10**szd)/10**szd
    return dict(stop_dist=dist, risk_sz=raw, risk_notional=raw*coin_px, cap_notional=max_notional, sz=sz, notional=sz*coin_px,
                meets_min=sz*coin_px >= cfg["min_notional_usd"], cap_binding=raw > max_notional/coin_px)

def dry_run():
    global info
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    print(f"DRY RUN (no orders, no keys) - mainnet public data, {cfg['interval']} closed candles + {cfg['htf_interval']} trend filter, now {now():%Y-%m-%d %H:%M}Z")
    acct = os.getenv("HL_ACCOUNT", "").strip()
    if acct:
        eq, _, d = unified_equity(info, acct)
        print(f"equity for {acct}: ${eq:.2f}  (perp {d['perp_account_value']:.2f} + spot USDC {d['spot_usdc']:.2f} counted={d['spot_counted']}, mode={d['abstraction']})")
    szds = {a["name"]: a["szDecimals"] for a in info.meta()["universe"]}
    if acct:
        _st0 = load_state(); _ST.update(_st0)
        _us = info.user_state(acct); _pos = {p["position"]["coin"]: p["position"] for p in _us["assetPositions"] if float(p["position"]["szi"]) != 0 and p["position"]["coin"] in cfg["coins"] and perp_owns(p["position"]["coin"])}
        eq_al = allocated_equity(eq); free0, md = margin_budget(info, acct, eq_al, set(_pos))
        _cl, _ok = scalper_claims(); _oo = info.frontend_open_orders(acct)
        print(f"LOCKOUT: scalper claims {_cl} (state readable {_ok}); account positions {[p['position']['coin'] for p in _us['assetPositions'] if float(p['position']['szi']) != 0]}")
        for _c in cfg["coins"]:
            _f = [o for o in _oo if o["coin"] == _c]; _held = any(p["position"]["coin"] == _c and float(p["position"]["szi"]) != 0 for p in _us["assetPositions"])
            _w = (_cl.get(_c) or ("exchange position not perp's" if _held and _c not in _pos else None) or (f"{len(_f)} resting orders" if _f and _c not in _pos else None))
            print(f"   {_c}: {'perp holds' if _c in _pos else ('BLOCKED for perp entry: ' + _w if _w else 'free')}")
        orisk0, per0 = open_risk(load_state(), _pos)
        print(f"allocated to this bot: ${eq_al:.2f} (account ${eq:.2f} - scalper per {cfg.get('external_capital_file')}) | open bot positions {list(_pos)} risk {per0} "
              f"| margin: bot uses ${md['bot_used']:.2f}, scalper uses ${md['scalp_used']:.2f}, account free ${md['acct_free']:.2f}, scalper unused reserve ${md['scalp_reserve']:.2f} "
              f"-> free for bot ${free0:.2f} (by allocation ${md['free_by_allocation']:.2f}, by account ${md['free_by_account']:.2f})")
    for coin in cfg["coins"]:
        s = signals(info, coin); dist = cfg["stop_atr_mult"]*s["atr"]; f, mid = funding_and_mid(info, coin)
        fresh = s["signal"] and s["signal"] != s["prev_signal"]
        why = [] if not s["signal"] else ([] if fresh else ["not fresh"]) + ([] if s["htf"] == s["signal"] else ["htf_filter disagrees"]) + \
              ([] if s["vol_ok"] else ["vol_filter: dead market"]) + \
              (["funding against"] if funding_blocks(s["signal"], f) else [])
        act = "no trade" if not s["signal"] else ("ENTER " + ("LONG" if s["signal"] == 1 else "SHORT") if not why else "no entry (" + ", ".join(why) + ")")
        print(f"{coin}: 1h candle {s['candle']} close {s['close']:.6g} | votes {s['votes_log']} -> signal {s['signal']:+d} (prev {s['prev_signal']:+d}, needs >= {cfg['min_agree']} of 4) => {act}")
        print(f"   htf_filter {s['htf']:+d} {s['htf_detail']} | funding {f*100:+.5f}%/h (blocks long: {funding_blocks(1, f)}, blocks short: {funding_blocks(-1, f)}) | mid {mid}")
        print(f"   vol_filter {'OK' if s['vol_ok'] else 'BLOCKS'}: ATR% {s['vol_detail']['atr_pct']}% vs 30d median {s['vol_detail']['median_atr_pct_30d']}% = {s['vol_detail']['ratio']}x (min {cfg['vol_filter_min_ratio']}x)")
        print(f"   partial TP: at +{cfg['partial_at_r']}R close {cfg['partial_fraction']:.0%} (only if both halves >= ${cfg['partial_min_notional_usd']})")
        print(f"   stop 2xATR(14,1h) = {dist:.6g} ({dist/s['close']:.2%}) | breakeven at +{cfg['breakeven_at_r']}R, then trail {cfg['trail_atr_mult']}xATR from best | backstop TP {cfg['tp_r_multiple']}R")
        print(f"   defensive signal (>= {cfg['defensive_min_agree']} of 4): {s['def_signal']:+d} (prev {s['def_prev']:+d})")
        if acct:
            lok, lq, sf, lev, mf = liq_check(info, coin, s["close"], dist)
            pl = plan_size(eq_al, dist, s["close"], cfg["risk_per_trade"], lev, free0, orisk0); szr = math.floor(pl["sz"]*10**szds[coin])/10**szds[coin]
            print(f"   NEXT ENTRY (allocated ${eq_al:.2f}, current open risk ${orisk0:.2f}, free margin ${free0:.2f}): {cfg['risk_per_trade']:.0%} risk ${cfg['risk_per_trade']*eq_al:.2f} "
                  f"-> {szr} {coin} = ${szr*s['close']:.2f} ({szr*s['close']/eq_al:.2f}x), margin ${szr*s['close']/lev:.2f} at {lev}x | binds {pl['binds'] or 'none'} "
                  f"| EFFECTIVE RISK ${szr*dist:.2f} = {100*szr*dist/eq_al:.2f}% | {'OK' if pl['fits'] else 'SKIP: margin does not fit free margin'}"
                  f"{'' if szr*s['close'] >= cfg['min_notional_usd'] else ' | SKIP (< min notional)'}")
            print(f"   liquidation (size-independent at {lev}x isolated, coin max {_ML[coin]}x): est. {lq:.2%} away vs stop {sf:.2%} = {lq/sf:.1f}x "
                  f"-> {'OK' if lok else 'BLOCKED (liq < ' + str(cfg['liq_min_stop_mult']) + 'x stop)'}")
            d2 = size_for(s["close"], s["atr"], eq_al, szds[coin], cfg["defensive_risk_per_trade"])
            print(f"   DEFENSIVE sizing: {cfg['defensive_risk_per_trade']:.0%} risk -> {d2['sz']} {coin} = ${d2['notional']:.2f}{' [CAP BINDS]' if d2['cap_binding'] else ''}")
    print(f"MODES (UTC day, equity vs day-start): NORMAL {cfg['risk_per_trade']:.0%} risk, >= {cfg['min_agree']} of 4 | "
          f"DEFENSIVE at -{cfg['daily_defensive_pct']}%: {cfg['defensive_risk_per_trade']:.0%} risk, {cfg['defensive_min_agree']} of 4 | HALT at -{cfg['daily_halt_pct']}% | "
          f"per-position notional cap {cfg['max_position_notional_x']}x allocated equity, exchange {cfg['isolated_leverage']}x isolated, margin must fit free margin else skip, max {cfg['max_positions']} open, max {cfg['max_same_direction']} same direction, open-risk cap {cfg['max_open_risk_pct']}% of equity")
    print(f"ENTRY: post-only at best bid/ask, wait {cfg['alo_wait_s']}s, then IOC <= {cfg['ioc_max_slippage']:.1%} slippage unless price moved > {cfg['max_move_atr']} ATR | "
          f"cooldown {cfg['cooldown_after_stop_h']}h per coin after a stop-out | funding gate {cfg['max_adverse_funding_per_h']*100:.3f}%/h")
    if acct:
        print(f"   with ${eq:.2f} day-start: DEFENSIVE below ${eq*(1-cfg['daily_defensive_pct']/100):.2f}, HALT below ${eq*(1-cfg['daily_halt_pct']/100):.2f}")
    sys.exit(0)


# ------------------------------------------------------------------ LIVE ------------------------------------------------------------------
ACCOUNT = os.getenv("HL_ACCOUNT", "").strip()   # set properly in live_init(); importing bot.py never builds an Exchange or trades
def live_init():
    """Read creds, refuse a main-account key, build Info/Exchange clients. Only called from __main__."""
    global ACCOUNT, wallet, info, ex, SZD
    ACCOUNT, KEY = os.getenv("HL_ACCOUNT", "").strip(), os.getenv("HL_API_KEY", "").strip()
    if not ACCOUNT or not KEY: log("HL_ACCOUNT and/or HL_API_KEY not set - exiting cleanly, nothing done."); sys.exit(3)
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    try: wallet = Account.from_key(KEY)
    except Exception: log("HL_API_KEY is not a valid private key (value not shown) - exiting."); sys.exit(3)
    del KEY; os.environ.pop("HL_API_KEY", None)
    if wallet.address.lower() == ACCOUNT.lower():
        log("Refusing: HL_API_KEY is the MAIN account key (can withdraw). Create a trade-only API wallet on app.hyperliquid.xyz/API."); sys.exit(3)
    info = Info(BASE, skip_ws=True); ex = Exchange(wallet, BASE, account_address=ACCOUNT)
    SZD = {a["name"]: a["szDecimals"] for a in info.meta()["universe"]}

def rpx(coin, px): return round(float(f"{px:.5g}"), 6 - SZD[coin])          # HL: 5 sig figs, <= 6-szDecimals decimals
def rsz(coin, sz): return math.floor(round(sz * 10**SZD[coin], 6)) / 10**SZD[coin]
def ok(resp):
    try:
        st = resp["response"]["data"]["statuses"][0]; return resp["status"] == "ok" and "error" not in st, st
    except Exception: return False, resp
def tighter(is_long, a, b):
    """The more protective of two stop prices (higher for longs, lower for shorts)."""
    return max(a, b) if is_long else min(a, b)

def allocated_equity(eq):
    """Capital split (2026-10-25): the account is shared with /workspace/hlscalp. This bot sizes, day-stops and open-risk-caps off
    ITS share only = account equity - scalper equity (from external_capital_file), capped at capital_cap_usd. Missing file -> 0."""
    f = cfg.get("external_capital_file")
    if f:
        try: eq -= float(json.load(open(f)).get("scalper_equity_usd") or 0)
        except FileNotFoundError: pass
        except Exception as e: log(f"capital file unreadable ({e}); using last scalper value"); eq -= _SCALP_LAST[0]
        else:
            try: _SCALP_LAST[0] = float(json.load(open(f)).get("scalper_equity_usd") or 0)
            except Exception: pass
    if cfg.get("capital_cap_usd"): eq = min(eq, float(cfg["capital_cap_usd"]))
    return eq
_SCALP_LAST = [0.0]
def account():
    eq, us, _ = unified_equity(info, ACCOUNT)
    eq = allocated_equity(eq)
    # only this bot's coins: the scalper's positions (other coins) never count toward max_positions / margin / open risk here
    allp = {p["position"]["coin"]: p["position"] for p in us["assetPositions"] if float(p["position"]["szi"]) != 0}
    _ALLPOS.clear(); _ALLPOS.update(allp)
    pos = {}
    for c, q in allp.items():
        if c not in cfg["coins"]: continue
        if perp_owns(c):
            if c in scalper_claims()[0] and c in _ST.get("trades", {}): warn_once("conflict" + c, f"OWNERSHIP CONFLICT {c}: both bots have a record - perp keeps managing its own record, CHECK MANUALLY")
            pos[c] = q
        else: warn_once("foreign" + c, f"{c}: position {q['szi']} on the exchange is not the perp bot's (scalper/other) - not adopted, not managed, entries on {c} blocked")
    return eq, pos
def open_orders(coin=None): return [o for o in info.frontend_open_orders(ACCOUNT) if (coin is None or o["coin"] == coin) and not is_foreign_order(o)]
def is_sl(o): return o.get("isTrigger") and "Stop" in o.get("orderType", "")
def is_tp(o): return o.get("isTrigger") and "Take Profit" in o.get("orderType", "")
def cancel_all(coin):
    if not perp_owns(coin) and coin not in LEGACY_COINS and coin in scalper_claims()[0]:
        log(f"cancel_all {coin} REFUSED: coin is claimed by the scalper"); return
    for o in open_orders(coin):
        try: ex.cancel(coin, o["oid"])
        except Exception as e: log(f"cancel {coin} {o['oid']} failed: {e}")
def close(st, coin, reason):
    """Emergency/signal exit: market close. Marks the trade as bot-closed (no stop-out cooldown)."""
    if not perp_owns(coin, st): log(f"CLOSE {coin} ({reason}) REFUSED: position is not the perp bot's"); return False
    cancel_all(coin); r = ex.market_close(coin); good, res = ok(r) if r else (False, "no position")
    if coin in st["trades"]: st["trades"][coin]["closed_by_bot"] = reason
    log(f"CLOSE {coin} ({reason}) -> {res}"); jl({"event": "close", "coin": coin, "reason": reason, "result": res})
    return good

def place_trigger(coin, is_long, sz, trig, kind):
    """kind 'sl' or 'tp': reduce-only MARKET trigger order resting on the exchange. Returns (ok, trigger_px, oid)."""
    trig = rpx(coin, trig); lim = rpx(coin, trig*(0.9 if is_long else 1.1))  # aggressive limit for market trigger
    r = ex.order(coin, not is_long, sz, lim, {"trigger": {"triggerPx": trig, "isMarket": True, "tpsl": kind}}, reduce_only=True)
    good, res = ok(r); oid = res.get("resting", {}).get("oid") if isinstance(res, dict) else None
    log(f"{kind.upper()} {coin} @ {trig} sz {sz} -> {res}"); return good, trig, oid

def load_state():
    try: st = json.load(open(STATE))
    except Exception: st = {}
    for k, v in {"day": None, "day_start_equity": None, "trades": {}, "seen_tids": [], "last_candle": {}, "mode": "normal",
                 "day_trades": {}, "atr": {}, "cooldown": {}, "owned": []}.items(): st.setdefault(k, v)
    st.pop("halted", None); return st

def mode_for(day_pct):
    return "halt" if day_pct <= -cfg["daily_halt_pct"] else ("defensive" if day_pct <= -cfg["daily_defensive_pct"] else "normal")
RANK = {"normal": 0, "defensive": 1, "halt": 2}

def behind(votes, side): return [k for k, v in (votes or {}).items() if k != "htf_filter" and v == side]

def losing_breakdown(st):
    """Today's closed trades with negative PnL and the strategies that voted for each one (those whose vote matched the trade side)."""
    losers, blame = [], {}
    for tid, t in st["day_trades"].items():
        if t["pnl"] >= 0: continue
        b = behind(t.get("votes"), 1 if t.get("side") == "long" else -1)
        losers.append({"trade_id": tid, "coin": t["coin"], "side": t.get("side"), "pnl": round(t["pnl"], 4), "strategies": b})
        for k in b: blame[k] = round(blame.get(k, 0) + t["pnl"], 4)
    return {"losing_trades": losers, "loss_by_strategy": blame}

def sync_fills(st):
    """Write exchange fills to fills.jsonl (deduped), attaching the entry votes / strategy names so we can score strategies."""
    try: fills = info.user_fills_by_time(ACCOUNT, int(time.time()*1000) - 3*86400_000)
    except Exception as e: log(f"fills sync failed: {e}"); return
    seen = set(st["seen_tids"])
    for f in sorted(fills, key=lambda x: x["time"]):
        if f["tid"] in seen or f["coin"] not in cfg["coins"]: continue
        if is_foreign_order(f) or (f["coin"] not in LEGACY_COINS and not any(w["coin"] == f["coin"] and w["start"] - 5000 <= f["time"] <= (w.get("end") or 9e15) + 5000 for w in st.get("owned", []))):
            seen.add(f["tid"]); continue   # scalper's fill on a shared coin
        seen.add(f["tid"]); t = st["trades"].get(f["coin"], {})
        pnl = float(f.get("closedPnl") or 0) - float(f.get("fee") or 0)
        fday = datetime.fromtimestamp(f["time"]/1000, timezone.utc).strftime("%Y-%m-%d")
        if t.get("id") and fday == now().strftime("%Y-%m-%d"):
            d = st["day_trades"].setdefault(f"{t['id']}@{fday}", {"coin": f["coin"], "side": t.get("side"), "votes": t.get("votes"), "pnl": 0.0, "day": fday})
            d["pnl"] += pnl
        jl({"event": "fill", "coin": f["coin"], "dir": f.get("dir"), "px": f["px"], "sz": f["sz"], "fee": f.get("fee"),
            "closedPnl": f.get("closedPnl"), "oid": f["oid"], "tid": f["tid"], "fill_time": f["time"],
            "entry_votes": t.get("votes"), "trade_id": t.get("id"), "mode": t.get("mode"),
            "strategies_behind": behind(t.get("votes"), 1 if t.get("side") == "long" else -1) if t else None})
    st["seen_tids"] = list(seen)[-2000:]

def kill_switch(st):
    log("KILL file found: closing everything and exiting.")
    try:
        _, pos = account()
        for coin in cfg["coins"]:
            if coin in pos: close(st, coin, "kill"); time.sleep(2); on_flat(st, coin)
            if perp_owns(coin, st): cancel_all(coin)
    except Exception as e: log(f"kill-switch error: {e}")
    jl({"event": "kill_switch"}); wjson(STATE, st); sys.exit(4)

def on_flat(st, coin):
    """Position gone: classify the exit, write a full trade_closed record, apply the stop-out cooldown, clear leftover orders."""
    t = st["trades"].pop(coin, None); cancel_all(coin)
    if not t: return
    is_long = t["side"] == "long"
    fl = []
    for _try in range(6):   # close fill can lag the position going flat: wait until exit size covers entry size
        try: fl = [f for f in info.user_fills_by_time(ACCOUNT, int(t.get("opened_ms", 0))) if f["coin"] == coin and not is_foreign_order(f)]
        except Exception: fl = []
        _ex = sum(float(f["sz"]) for f in fl if "Close" in (f.get("dir") or "")); _en = sum(float(f["sz"]) for f in fl if "Open" in (f.get("dir") or ""))
        if _en and _ex >= _en*0.999: break
        time.sleep(2)
    ex_f = [f for f in fl if "Close" in (f.get("dir") or "")]; en_f = [f for f in fl if "Open" in (f.get("dir") or "")]
    def vwap(xs): q = sum(float(x["sz"]) for x in xs); return (sum(float(x["sz"])*float(x["px"]) for x in xs)/q if q else None), q
    exit_px, exit_sz = vwap(ex_f); entry_px, entry_sz = vwap(en_f)
    last_px = float(ex_f[-1]["px"]) if ex_f else None
    fees = sum(float(f.get("fee") or 0) for f in fl); closed = sum(float(f.get("closedPnl") or 0) for f in ex_f)
    try:
        fh = info.user_funding_history(ACCOUNT, int(t.get("opened_ms", 0)))
        funding = sum(float(x["delta"]["usdc"]) for x in fh if x.get("delta", {}).get("coin") == coin)   # negative = paid
    except Exception: funding = None
    pnl = closed - fees + (funding or 0); r_usd = t["risk_dist"]*t.get("sz0", t["sz"]); r_mult = pnl/r_usd if r_usd else None
    if t.get("closed_by_bot"): reason = t["closed_by_bot"]
    elif last_px is not None and abs(last_px - t.get("tp", float("inf"))) < abs(last_px - t["stop"]): reason = "TP"
    elif t.get("be"):
        be_px = t["entry"]*(1 + cfg["breakeven_fee_pct"]/100) if is_long else t["entry"]*(1 - cfg["breakeven_fee_pct"]/100)
        reason = "trail" if ((t["stop"] > be_px*1.0005) if is_long else (t["stop"] < be_px*0.9995)) else "BE"
    else: reason = "stop"
    if t.get("partials") and reason != "TP": reason = f"partial+{reason}"
    rec = {"event": "trade_closed", "entry_type": t.get("entry_type", "fresh"), "trade_id": t["id"], "coin": coin, "side": t["side"], "entry_px": entry_px or t["entry"], "exit_px": exit_px,
           "size": entry_sz or t.get("sz0"), "fees": round(fees, 6), "funding": funding, "closed_pnl": round(closed, 6), "pnl_usd": round(pnl, 6),
           "risk_usd_1R": round(r_usd, 6), "pnl_r": round(r_mult, 4) if r_mult is not None else None, "exit_reason": reason,
           "partials": t.get("partials"), "final_stop": t["stop"], "breakeven_armed": t.get("be"), "best_px": t.get("best"), "mode_at_entry": t.get("mode"),
           "votes": t.get("votes"), "strategies_behind": t.get("strategies_behind"), "htf_at_entry": t.get("htf_detail"),
           "vol_at_entry": t.get("vol_detail"), "funding_at_entry": t.get("funding_at_entry"), "opened_ms": t.get("opened_ms")}
    jl(rec); close_windows(st, coin)
    log(f"CLOSED {coin} {t['side']} entry {rec['entry_px']} exit {exit_px} pnl ${pnl:.4f} ({rec['pnl_r']}R) reason {reason} strategies {t.get('strategies_behind')}")
    if not t.get("closed_by_bot") and (reason in ("stop", "BE", "partial+stop", "partial+BE") or pnl < 0):   # losing/scratch stop-outs only
        until = time.time() + 3600*cfg["cooldown_after_stop_h"]; st["cooldown"][coin] = until
        log(f"STOPPED OUT {coin}: cooldown until {datetime.fromtimestamp(until, timezone.utc):%H:%M}Z")

def resize_protection(coin, is_long, t, new_sz, oo):
    """After a partial: place new SL (and TP) for new_sz FIRST; cancel the old ones only after the exchange accepts the new ones."""
    good, trig, oid = place_trigger(coin, is_long, new_sz, t["stop"], "sl")
    if good:
        t["sl_oid"] = oid
        for o in oo:
            if is_sl(o) and o["oid"] != oid:
                try: ex.cancel(coin, o["oid"])
                except Exception: pass
    else: log(f"PARTIAL {coin}: resized stop rejected; old (larger, reduce-only) stop kept - still protected")
    if t.get("tp"):
        g2, _, toid = place_trigger(coin, is_long, new_sz, t["tp"], "tp")
        if g2:
            for o in oo:
                if is_tp(o) and o["oid"] != toid:
                    try: ex.cancel(coin, o["oid"])
                    except Exception: pass

def maybe_partial(st, coin, p, oo, mid):
    """At +partial_at_r R close partial_fraction (reduce-only market). Skip if either part would be under the $ minimum."""
    t = st["trades"].get(coin)
    if not cfg.get("partial_tp", True) or not t or t.get("partial_done") or "risk_dist" not in t: return False
    is_long = float(p["szi"]) > 0; sz = abs(float(p["szi"])); gain = (mid - t["entry"]) if is_long else (t["entry"] - mid)
    if gain < cfg["partial_at_r"]*t["risk_dist"]: return False
    half = rsz(coin, sz*cfg["partial_fraction"]); mn = cfg["partial_min_notional_usd"]
    if half*mid < mn or (sz - half)*mid < mn:
        t["partial_done"] = "skipped"; log(f"PARTIAL {coin} skipped: half {half} = ${half*mid:.2f} or rest under ${mn}; trailing only")
        jl({"event": "partial_skipped", "coin": coin, "trade_id": t["id"], "half": half, "mid": mid}); return False
    r = ex.market_close(coin, sz=half, slippage=cfg["partial_slippage"]); good, res = ok(r) if r else (False, "no response")
    if not good or "filled" not in res: log(f"PARTIAL {coin} failed: {res}"); return False
    fsz, fpx = float(res["filled"]["totalSz"]), float(res["filled"]["avgPx"])
    t["partial_done"] = True; t["partials"].append({"sz": fsz, "px": fpx, "r": round(gain/t["risk_dist"], 3), "ts": now().isoformat()})
    _, pos = account(); rem = abs(float(pos[coin]["szi"])) if coin in pos else 0.0
    log(f"PARTIAL {coin} closed {fsz} @ {fpx} (+{gain/t['risk_dist']:.2f}R); remaining {rem}, resizing stop/TP")
    jl({"event": "partial", "coin": coin, "trade_id": t["id"], "side": t["side"], "sz": fsz, "px": fpx, "r_at_partial": gain/t["risk_dist"],
        "remaining": rem, "votes": t.get("votes"), "strategies_behind": t.get("strategies_behind")})
    if rem > 0: t["sz"] = rem; resize_protection(coin, is_long, t, rem, oo)
    return True

def manage_stop(st, coin, p, oo, mid):
    """Breakeven at +breakeven_at_r R, then trail trail_atr_mult x ATR(14,1h) from the best price. Stop only ever tightens.
    Safe update order: place the NEW reduce-only stop first; only if the exchange accepts it, cancel the older stop(s)."""
    t = st["trades"].get(coin)
    if not t or "risk_dist" not in t: return
    is_long = float(p["szi"]) > 0; sz = abs(float(p["szi"])); e = t["entry"]; R = t["risk_dist"]; a = st["atr"].get(coin)
    t["best"] = max(t.get("best", e), mid) if is_long else min(t.get("best", e), mid)
    gain = (t["best"] - e) if is_long else (e - t["best"])
    cand = t["stop"]
    if gain >= cfg["breakeven_at_r"]*R:
        be_px = e*(1 + cfg["breakeven_fee_pct"]/100) if is_long else e*(1 - cfg["breakeven_fee_pct"]/100)
        cand = tighter(is_long, cand, be_px)
        if a: cand = tighter(is_long, cand, t["best"] - cfg["trail_atr_mult"]*a if is_long else t["best"] + cfg["trail_atr_mult"]*a)
    cand = rpx(coin, cand)
    step_min = cfg["trail_min_step_atr"]*(a or R/cfg["stop_atr_mult"])
    improve = (cand - t["stop"]) if is_long else (t["stop"] - cand)
    if improve < step_min: return
    if (is_long and cand >= mid*0.999) or (not is_long and cand <= mid*1.001):
        return  # would be at/through market: keep the existing stop, retry next loop
    good, trig, oid = place_trigger(coin, is_long, sz, cand, "sl")
    if not good: log(f"TRAIL {coin}: new stop {cand} rejected; existing stop {t['stop']} kept"); return
    old = [o for o in oo if is_sl(o) and o["oid"] != oid]
    prev = t["stop"]; t.update(stop=trig, sl_oid=oid); t["be"] = t.get("be") or ((trig >= e) if is_long else (trig <= e))
    for o in old:
        try: ex.cancel(coin, o["oid"])
        except Exception as ex_: log(f"TRAIL {coin}: cancel old stop {o['oid']} failed ({ex_}); reconcile will retry")
    log(f"TRAIL {coin} stop {prev} -> {trig} (best {t['best']}, +{gain/R:.2f}R, breakeven {'on' if t['be'] else 'off'})")
    jl({"event": "trail", "coin": coin, "trade_id": t["id"], "old_stop": prev, "new_stop": trig, "best": t["best"], "gain_r": gain/R})

def enter(st, coin, s, eq, risk, f_rate):
    is_long = s["signal"] == 1; dist = cfg["stop_atr_mult"]*s["atr"]; opened_ms = int(time.time()*1000) - 5000
    _, ref = funding_and_mid(info, coin)
    lok, lq, sf, lev, _ = liq_check(info, coin, ref, dist)
    if not lok: log(f"{coin} skip: est. liquidation {lq:.2%} away < {cfg['liq_min_stop_mult']}x stop {sf:.2%} at {lev}x"); return
    _, pos_now = account(); orisk, _ = open_risk(st, pos_now)
    free, md = margin_budget(info, ACCOUNT, eq, set(pos_now))          # bigpos: never into the scalper's capital / free margin
    pl = plan_size(eq, dist, ref, risk, lev, free, orisk); sz = rsz(coin, pl["sz"])
    log(f"{coin} sizing: {risk:.0%} of ${eq:.2f} on stop {dist/ref:.2%} -> {sz} (${sz*ref:.2f}, risk ${sz*dist:.2f} = {100*sz*dist/eq:.2f}%) "
        f"binds {pl['binds'] or 'none'} | margin ${pl['margin']:.2f} vs free ${free:.2f} (bot uses ${md['bot_used']:.2f}, scalper reserve ${md['scalp_reserve']:.2f}) | open risk ${orisk:.2f}")
    if not pl["fits"]:
        log(f"{coin} skip: isolated margin ${pl['margin']:.2f} at {lev}x does not fit free margin ${free:.2f}")
        jl({"event": "entry_skipped", "coin": coin, "reason": "margin_does_not_fit", "margin": pl["margin"], "free": free, "detail": md}); return
    if sz*ref < cfg["min_notional_usd"]: log(f"{coin} skip: size {sz} below min notional"); return
    # expand lockout: publish the claim first (scalper reads it), then re-check exchange + scalper state; both bots write-then-check
    st["pending_entry"] = {"coin": coin, "ts": time.time()}; st.setdefault("owned", []).append({"coin": coin, "start": int(time.time()*1000) - 5000, "end": None})
    wjson(STATE, st)
    why = lockout_reason(st, coin)
    if why:
        st.pop("pending_entry", None); st["owned"] = [w for w in st["owned"] if not (w["coin"] == coin and w.get("end") is None)]; wjson(STATE, st)
        log(f"{coin} skip: LOCKOUT at order time - {why}"); jl({"event": "entry_skipped", "coin": coin, "reason": "lockout", "detail": why}); return
    try: _enter_orders(st, coin, s, eq, risk, f_rate, is_long, dist, opened_ms, ref, sz, lev)
    finally:
        st.pop("pending_entry", None)
        if coin not in st["trades"]: close_windows(st, coin)
        wjson(STATE, st)

def _enter_orders(st, coin, s, eq, risk, f_rate, is_long, dist, opened_ms, ref, sz, lev):
    r = ex.update_leverage(lev, coin, is_cross=False)
    if r.get("status") != "ok": log(f"{coin} leverage set failed {r}; no entry"); return
    filled, how = 0.0, []
    if cfg.get("entry_post_only", True):
        lv = info.l2_snapshot(coin)["levels"]; px = float(lv[0][0]["px"] if is_long else lv[1][0]["px"])
        good, res = ok(ex.order(coin, is_long, sz, rpx(coin, px), {"limit": {"tif": "Alo"}}))
        oid = res.get("resting", {}).get("oid") if good and isinstance(res, dict) else None
        log(f"ENTRY ALO {coin} {'BUY' if is_long else 'SELL'} {sz} @ {rpx(coin, px)} -> {res}")
        if oid:
            t0 = time.time()
            while time.time() - t0 < cfg["alo_wait_s"]:
                time.sleep(3)
                try:
                    q = info.query_order_by_oid(ACCOUNT, oid)
                    if q.get("order", {}).get("status") == "filled": break
                except Exception: pass
            try: ex.cancel(coin, oid)
            except Exception: pass
            time.sleep(1)
        if oid:
            fl = [x for x in info.user_fills_by_time(ACCOUNT, opened_ms) if x["oid"] == oid]
            filled = sum(float(x["sz"]) for x in fl)
            if filled: how.append(f"ALO {filled}")
    rem = rsz(coin, sz - filled)
    if rem > 0 and rem*ref >= cfg["min_notional_usd"]:
        _, mid = funding_and_mid(info, coin)
        if abs(mid - ref) > cfg["max_move_atr"]*s["atr"]:
            log(f"{coin} IOC fallback skipped: price moved {abs(mid-ref):.6g} > {cfg['max_move_atr']} ATR ({cfg['max_move_atr']*s['atr']:.6g})")
        else:
            lim = rpx(coin, mid*(1 + cfg["ioc_max_slippage"]) if is_long else mid*(1 - cfg["ioc_max_slippage"]))
            good, res = ok(ex.order(coin, is_long, rem, lim, {"limit": {"tif": "Ioc"}}))
            log(f"ENTRY IOC {coin} {'BUY' if is_long else 'SELL'} {rem} limit {lim} -> {res}")
            if good and "filled" in res: how.append(f"IOC {res['filled']['totalSz']}")
    _, pos = account()
    if coin not in pos: log(f"{coin} entry not filled ({how or 'nothing'}); no position"); return
    p = pos[coin]; fsz = abs(float(p["szi"])); fpx = float(p["entryPx"])
    if (float(p["szi"]) > 0) != is_long: log(f"{coin} position side mismatch - closing"); close(st, coin, "side mismatch"); return
    stop = fpx - dist if is_long else fpx + dist; tp = fpx + cfg["tp_r_multiple"]*dist if is_long else fpx - cfg["tp_r_multiple"]*dist
    tid = f"{coin}-{int(time.time())}"
    sl_ok, stop, sl_oid = place_trigger(coin, is_long, fsz, stop, "sl")
    if not sl_ok: sl_ok, stop, sl_oid = place_trigger(coin, is_long, fsz, stop, "sl")  # one retry
    if not sl_ok:
        close(st, coin, "stop-loss placement failed"); jl({"event": "entry_aborted", "trade_id": tid, "coin": coin, "votes": s["votes_log"]}); return
    tp_ok, tp, _ = place_trigger(coin, is_long, fsz, tp, "tp")
    try:
        lp = float(p.get("liquidationPx") or 0)
        if lp: log(f"{coin} liquidation {lp} is {abs(fpx - lp)/fpx:.2%} away vs stop {dist/fpx:.2%} ({abs(fpx - lp)/dist:.1f}x)"
                   + ("" if abs(fpx - lp) >= cfg["liq_min_stop_mult"]*dist else " WARNING: closer than guard"))
    except Exception: pass
    sb = behind(s["votes"], s["signal"])
    st["trades"][coin] = {"id": tid, "mode": st["mode"], "side": "long" if is_long else "short", "entry": fpx, "sz": fsz, "stop": stop, "sl_oid": sl_oid,
                          "tp": tp, "risk_dist": dist, "best": fpx, "be": False, "votes": s["votes_log"], "strategies_behind": sb,
                          "funding_at_entry": f_rate, "opened_ms": opened_ms, "fill_how": how, "sz0": fsz, "htf_detail": s["htf_detail"], "entry_type": s.get("entry_type", "fresh"),
                          "vol_detail": s["vol_detail"], "partial_done": False, "partials": []}
    jl({"event": "entry", "entry_type": s.get("entry_type", "fresh"), "trade_id": tid, "coin": coin, "side": "long" if is_long else "short", "sz": fsz, "entry_px": fpx, "stop": stop, "tp": tp,
        "tp_placed": tp_ok, "strategies_behind": sb, "risk_usd": fsz*dist, "risk_pct": risk, "mode": st["mode"], "equity": eq,
        "candle": s["candle"], "votes": s["votes_log"], "htf": s["htf_detail"], "vol": s["vol_detail"], "funding_per_h": f_rate, "fill_how": how})
    log(f"ENTER {coin} {'LONG' if is_long else 'SHORT'} {fsz} @ {fpx} ({', '.join(how)}) stop {stop} backstop-TP {tp} risk {risk:.0%} mode {st['mode']} "
        f"funding {f_rate*100:+.5f}%/h votes {s['votes_log']}")
    try:   # fix124: liquidation must sit beyond the stop; if the exchange says otherwise, get out immediately
        _, pz = account(); lp2 = float((pz.get(coin) or {}).get("liquidationPx") or 0)
        if lp2 and ((is_long and lp2 >= stop) or (not is_long and lp2 <= stop)):
            log(f"{coin} liquidation {lp2} is not beyond stop {stop} - closing the new position"); close(st, coin, "liq_inside_stop")
            time.sleep(2); sync_fills(st); on_flat(st, coin)
    except Exception as e: log(f"{coin} post-fill liquidation check failed: {e}")

JOIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "JOIN_ONCE")
def latest_closed_open():
    ms = MS[cfg["interval"]]; return str(pd.Timestamp((int(time.time()*1000)//ms)*ms - ms, unit="ms", tz="UTC"))

def step(st):
    eq, pos = account(); today = now().strftime("%Y-%m-%d")
    if st["day"] != today:
        st.update(day=today, day_start_equity=eq, mode="normal", mode_reason=None,
                  day_trades={k: v for k, v in st["day_trades"].items() if v.get("day") == today}); log(f"new UTC day, start equity {eq:.2f}, mode NORMAL")
    day_pnl = eq - st["day_start_equity"]; day_pct = 100*day_pnl/st["day_start_equity"] if st["day_start_equity"] else 0
    new_mode = mode_for(day_pct)
    if RANK[new_mode] > RANK[st["mode"]]:   # only escalates; stays until the next UTC day even if equity recovers
        st["mode"] = new_mode; lb = losing_breakdown(st); st["mode_reason"] = {"at": now().isoformat(), "day_pct": round(day_pct, 3), "equity": eq, **lb}
        if new_mode == "defensive":
            log(f"DEFENSIVE day P&L {day_pct:.2f}% (<= -{cfg['daily_defensive_pct']}%): rest of UTC day risk {cfg['defensive_risk_per_trade']:.0%}, "
                f"entries need {cfg['defensive_min_agree']} of 4 agreeing | losing trades {lb['losing_trades']} | loss by strategy {lb['loss_by_strategy']}")
        else:
            log(f"HALT day P&L {day_pct:.2f}% (<= -{cfg['daily_halt_pct']}%): no new entries until 00:00 UTC; open positions keep their exchange stops "
                f"| losing trades {lb['losing_trades']} | loss by strategy {lb['loss_by_strategy']}")
        jl({"event": new_mode, "equity": eq, "day_pct": day_pct, **lb})
    # safety reconcile + trailing: every open position must have a resting stop; flat coins must have no stray orders
    mids = info.all_mids(); all_oo = open_orders()
    for coin in cfg["coins"]:
        oo = [o for o in all_oo if o["coin"] == coin]
        if coin in pos:
            p = pos[coin]; is_long = float(p["szi"]) > 0; sz = abs(float(p["szi"])); t = st["trades"].get(coin, {})
            sls = [o for o in oo if is_sl(o)]
            if not sls:
                good = False
                if t.get("stop"):
                    good, trig, oid = place_trigger(coin, is_long, sz, t["stop"], "sl")
                    if good: t["sl_oid"] = oid
                if not good: close(st, coin, "emergency_no_stop"); continue
            else:
                if t.get("sl_oid") and any(o["oid"] == t["sl_oid"] for o in sls):   # leftover older stops after a trail: cancel them
                    for o in sls:
                        if o["oid"] != t["sl_oid"]:
                            try: ex.cancel(coin, o["oid"])
                            except Exception: pass
                if not any(is_tp(o) for o in oo) and t.get("tp"): place_trigger(coin, is_long, sz, t["tp"], "tp")
                if maybe_partial(st, coin, p, open_orders(coin), float(mids[coin])):
                    _, pos2 = account()
                    if coin not in pos2: continue
                    p = pos2[coin]
                manage_stop(st, coin, p, open_orders(coin), float(mids[coin]))
        elif coin in st["trades"]: on_flat(st, coin)   # exchange stop / TP filled
        elif oo and coin not in scalper_claims()[0] and (coin in LEGACY_COINS or (coin not in _ALLPOS and any(
                w["coin"] == coin and (w.get("end") or 9e15) > time.time()*1000 - 86400_000 for w in st.get("owned", [])))):
            cancel_all(coin)   # stray perp orders (no 0x5ca1 cloid) left from a perp position closed in the last 24h
    # new closed candle -> evaluate signals (only fetch when a new candle should exist)
    eq, pos = account()
    join = False   # 2026-10-25 fix124 (user): join-existing-trends pass removed permanently; only fresh signals enter
    if os.path.exists(JOIN_FILE):
        os.remove(JOIN_FILE); log("JOIN_ONCE file ignored and deleted: join pass is disabled (fresh signals only)")
    for coin in cfg["coins"]:
        if not join and st["last_candle"].get(coin) == latest_closed_open(): continue
        s = signals(info, coin)
        if not join and st["last_candle"].get(coin) == str(s["candle"]): continue
        st["last_candle"][coin] = str(s["candle"]); st["atr"][coin] = s["atr"]
        log(f"{'JOIN ' if join else ''}{coin} {s['candle']} close {s['close']} votes {s['votes_log']} signal {s['signal']:+d} prev {s['prev_signal']:+d}")
        held = (1 if float(pos[coin]["szi"]) > 0 else -1) if coin in pos else 0
        if held and s["signal"] == -held:   # signal-flip exit (>= min_agree of 4 now opposing)
            close(st, coin, "flip"); time.sleep(2); sync_fills(st); on_flat(st, coin)
            eq, pos = account(); held = 0
        elif held and s["signal"] == 0 and s["prev_signal"] != held:   # fix124: neutral on 2 consecutive closed candles
            log(f"SIGNAL_FADED {coin}: {'long' if held == 1 else 'short'} signal neutral on candles {s['candle']} and the one before -> market close")
            jl({"event": "signal_faded", "coin": coin, "candle": s["candle"], "votes": s["votes_log"], "prev_signal": s["prev_signal"]})
            close(st, coin, "signal_faded"); time.sleep(2); sync_fills(st); on_flat(st, coin)
            eq, pos = account(); held = 0
        elif held and s["signal"] == 0:
            log(f"FADE WATCH {coin}: signal neutral on {s['candle']} (1 of 2); closes if the next closed candle is neutral too")
        defensive = st["mode"] == "defensive"
        sig, prev = (s["def_signal"], s["def_prev"]) if defensive else (s["signal"], s["prev_signal"])
        if join and (held or not sig):
            log(f"JOIN {coin} skipped: {'already holding' if held else 'no signal (needs >= ' + str(cfg['defensive_min_agree'] if defensive else cfg['min_agree']) + ' of 4, none opposing)'}")
        if held or not sig or (sig == prev and not join): continue   # only fresh signals (join pass: current state is enough)
        tag = f"{coin} {'LONG' if sig == 1 else 'SHORT'} signal skipped:"
        if st["mode"] == "halt": log(f"{tag} HALT (day loss <= -{cfg['daily_halt_pct']}%)"); continue
        if cfg.get("htf_filter", True) and s["htf"] != sig: log(f"{tag} htf_filter {s['htf']:+d} {s['htf_detail']}"); continue
        if not s["vol_ok"]: log(f"{tag} vol_filter dead market {s['vol_detail']}"); continue
        if time.time() < st["cooldown"].get(coin, 0):
            log(f"{tag} cooldown after stop-out until {datetime.fromtimestamp(st['cooldown'][coin], timezone.utc):%H:%M}Z"); continue
        f_rate, _ = funding_and_mid(info, coin)
        if funding_blocks(sig, f_rate): log(f"{tag} funding {f_rate*100:+.5f}%/h against the trade (> {cfg['max_adverse_funding_per_h']*100:.3f}%/h)"); continue
        if len(pos) >= cfg["max_positions"]: log(f"{tag} max positions ({len(pos)})"); continue
        why = lockout_reason(st, coin)
        if why:
            log(f"{tag} LOCKOUT - {why}")
            jl({"event": "entry_skipped", "coin": coin, "reason": "lockout", "detail": why, "side": "long" if sig == 1 else "short", "candle": s["candle"]}); continue
        same = sum(1 for p in pos.values() if (float(p["szi"]) > 0) == (sig == 1))
        if same >= cfg["max_same_direction"]:
            log(f"{tag} same-direction limit ({same} {'long' if sig == 1 else 'short'} open, max {cfg['max_same_direction']})")
            jl({"event": "entry_skipped", "coin": coin, "reason": "max_same_direction", "side": "long" if sig == 1 else "short", "open_same": same, "candle": s["candle"]}); continue
        enter(st, coin, {**s, "signal": sig, "entry_type": "join" if join else "fresh"}, eq, cfg["defensive_risk_per_trade"] if defensive else cfg["risk_per_trade"], f_rate)
        wjson(STATE, st); eq, pos = account()
    close_windows(st)   # windows of coins the perp no longer holds (e.g. after a crash) are closed so the scalper may use them

def write_status(st, err=None):
    try:
        eq, pos = account(); sd = st["day_start_equity"] or eq
        try: _, _, eqd = unified_equity(info, ACCOUNT)
        except Exception: eqd = None
        wjson(STATUS, {"updated": now().isoformat(), "network": cfg["network"], "account": ACCOUNT, "equity": eq, "equity_detail": eqd, "interval": cfg["interval"],
                       "day": st["day"], "day_start_equity": st["day_start_equity"], "day_pnl": eq - sd, "day_pnl_pct": 100*(eq - sd)/sd if sd else 0,
                       "mode": st["mode"], "mode_reason": st.get("mode_reason"),
                       "tiers": {"defensive_at_pct": -cfg["daily_defensive_pct"], "halt_at_pct": -cfg["daily_halt_pct"]},
                       "vote_rule": {"normal": cfg["min_agree"], "defensive": cfg["defensive_min_agree"], "htf_filter": cfg.get("htf_filter", True)},
                       "today": losing_breakdown(st),
                       "cooldown_until": {c: datetime.fromtimestamp(u, timezone.utc).isoformat() for c, u in st["cooldown"].items() if u > time.time()},
                       "positions": {c: {"size": p["szi"], "entry": p["entryPx"], "unrealized_pnl": p["unrealizedPnl"], "leverage": p.get("leverage"),
                                         "liq_px": p.get("liquidationPx"), **{k: st["trades"].get(c, {}).get(k) for k in
                                         ("stop", "sl_oid", "tp", "best", "be", "risk_dist", "sz0", "partial_done", "partials", "votes", "strategies_behind", "funding_at_entry", "vol_detail")}}
                                     for c, p in pos.items()},
                       "OPEN_RISK": (lambda o: {"usd": round(o[0], 4), "pct_of_equity": round(100*o[0]/eq, 3) if eq else None,
                                     "cap_pct": cfg["max_open_risk_pct"], "per_coin": {k: round(v, 4) for k, v in o[1].items()}})(open_risk(st, pos)),
                       "coins": cfg["coins"], "max_positions": cfg["max_positions"], "max_same_direction": cfg["max_same_direction"], "atr": st["atr"], "last_candle": st["last_candle"], "last_error": err})
    except Exception as e: log(f"status write failed: {e}")

def main_loop():
    signal.signal(signal.SIGTERM, lambda *a: (log("SIGTERM - stopping (positions keep their exchange stops)"), sys.exit(0)))
    log(f"START live bot on {cfg['network']} account {ACCOUNT} (api wallet {wallet.address}) {cfg['interval']} + {cfg['htf_interval']} filter, coins {cfg['coins']} "
        f"lev {cfg['max_leverage']}x total ({cfg['isolated_leverage']}x isolated) risk {cfg['risk_per_trade']:.0%} maxpos {cfg['max_positions']} vote >= {cfg['min_agree']}/4 | DEFENSIVE at -{cfg['daily_defensive_pct']}% "
        f"({cfg['defensive_risk_per_trade']:.0%}, {cfg['defensive_min_agree']}/4) | HALT at -{cfg['daily_halt_pct']}% | BE +{cfg['breakeven_at_r']}R, partial {cfg['partial_fraction']:.0%} at +{cfg['partial_at_r']}R, trail {cfg['trail_atr_mult']}xATR, TP {cfg['tp_r_multiple']}R "
        f"| max same direction {cfg['max_same_direction']} | per-position notional cap {cfg['max_position_notional_x']}x | open-risk cap {cfg['max_open_risk_pct']}% | signal_faded exit after 2 neutral closed candles | join pass disabled")
    st = load_state(); _base = {}; _ST.clear(); _ST.update(st); st = _ST   # same dict object used by ownership checks
    # Startup (2026-10-25): st["last_candle"] = last candle the step() actually PROCESSED (persisted in state.json). It is no longer
    # overwritten here, so if the latest closed candle (which by definition closed < 1h ago) was never processed - e.g. a restart
    # right after a close - the first step() processes it now. Older candles are never replayed (step only looks at the latest).
    # Duplicates are impossible: held coins are skipped and an entry also needs a fresh signal flip on that candle.
    for _c in cfg["coins"]:
        for _try in range(3):
            try:
                _s = signals(info, _c); st["atr"][_c] = _s["atr"]
                _done = st["last_candle"].get(_c) == str(_s["candle"])
                log(f"BASELINE {_c} {_s['candle']} votes {_s['votes_log']} signal {_s['signal']:+d} ATR {_s['atr']:.6g} "
                    + ("(already processed; waiting for next close)" if _done else f"(CATCH-UP: last processed {st['last_candle'].get(_c)}, will process this closed candle now)")); break
            except Exception as e:
                log(f"baseline {_c} failed ({type(e).__name__}: {e}); retrying"); time.sleep(5)
        else:
            log(f"baseline {_c} unavailable - exiting so the loop restarts"); sys.exit(1)
        _base[_c] = _s
    # fix124: a held position whose already-processed latest closed candle AND the one before are neutral exits now (signal_faded);
    # candles not yet processed are handled by step() as usual.
    try:
        _, _pos0 = account()
        for _c, _s in _base.items():
            if _c not in _pos0 or st["last_candle"].get(_c) != str(_s["candle"]): continue
            _held = 1 if float(_pos0[_c]["szi"]) > 0 else -1
            if _s["signal"] == 0 and _s["prev_signal"] != _held:
                log(f"SIGNAL_FADED {_c} (startup): signal neutral on {_s['candle']} and the candle before -> market close")
                jl({"event": "signal_faded", "coin": _c, "candle": _s["candle"], "votes": _s["votes_log"], "prev_signal": _s["prev_signal"], "at": "startup"})
                close(st, _c, "signal_faded"); time.sleep(2); sync_fills(st); on_flat(st, _c)
    except Exception as e: log(f"startup fade check failed ({type(e).__name__}: {e}); step() will handle the next candle")
    wjson(STATE, st)
    while True:
        if os.path.exists(KILL): kill_switch(st)
        err = None
        try:
            if now().minute != 0 or now().second >= cfg["candle_close_delay_s"]:   # give the exchange a moment after the candle closes
                sync_fills(st); step(st)
        except SystemExit: raise
        except Exception as e: err = f"{type(e).__name__}: {e}"; log("ERROR " + err + "\n" + traceback.format_exc(limit=3))
        wjson(STATE, st); write_status(st, err)
        for _ in range(cfg["loop_seconds"]):
            if os.path.exists(KILL): kill_switch(st)
            time.sleep(1)

LOCKFILE = os.path.join(HERE, "bot.lock"); _LOCK_FD = None
def acquire_lock():
    """Single-instance guard: exclusive non-blocking flock on bot.lock, held (fd kept open) for the process lifetime.
    The kernel releases it automatically when the process dies, so a crash never leaves a stale lock."""
    global _LOCK_FD
    import fcntl
    fd = os.open(LOCKFILE, os.O_RDWR | os.O_CREAT, 0o644)
    try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        try: other = os.pread(fd, 32, 0).decode().strip() or "?"
        except Exception: other = "?"
        os.close(fd)
        log(f"LOCK REFUSED: another bot instance (pid {other}) holds {LOCKFILE} - exiting immediately, no orders placed, nothing touched.")
        sys.exit(5)
    os.ftruncate(fd, 0); os.pwrite(fd, str(os.getpid()).encode(), 0); _LOCK_FD = fd

if __name__ == "__main__":
    if DRY: dry_run()
    acquire_lock()          # before credentials / clients / any order path
    live_init()
    main_loop()

