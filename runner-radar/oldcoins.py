#!/usr/bin/env python3
"""
oldcoins.py - PAPER-ONLY 'older coins' scanner + paper book (setups A/B/C, tiers core/wide).

Setup types: A = 1h breakout, B = 15m breakout, C = 15m pullback to the 15m EMA20.
Tiers: core = original approved universe rules; wide = wider universe (see CONFIG wide_*).
live_eligible is a LABEL for the separate live routine (CONFIG live_types / live_tiers /
live_allow_priority); this script itself never places any order.

NEVER trades live. Touches no wallet, key, Telegram or browser. Only reads public
GeckoTerminal market data and writes local files under live/.

Usage:
  python3 oldcoins.py [--tuned-config path.json] [--force-universe] [--no-window]

Files:
  live/oldcoins-universe.json   cached universe (refreshed at most every 60 min)
  live/oldcoins-positions.json  open paper positions + dedupe state
  live/oldcoins-paper.jsonl     every entry / partial / exit / would_short event
"""
import argparse, csv, json, math, os, sys, time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(HERE, "live")
UNIVERSE_F = os.path.join(LIVE, "oldcoins-universe.json")
SEEDS_F = os.path.join(LIVE, "oldcoins-seeds.json")
CACHE_D = os.path.join(LIVE, "oldcoins-cache")
DS = "https://api.dexscreener.com"
POS_F = os.path.join(LIVE, "oldcoins-positions.json")
LOG_F = os.path.join(LIVE, "oldcoins-paper.jsonl")
AVOID_F = "/workspace/onchain-intel/avoid.csv"
GT = "https://api.geckoterminal.com/api/v2"
DUB = ZoneInfo("Europe/Dublin")

CONFIG = {
    # universe, core tier (original approved rules)
    "min_age_days": 7,              # token age = earliest pool_created_at seen for the token
    "min_mcap_usd": 5e6, "max_mcap_usd": 200e6,   # market_cap_usd, falls back to fdv_usd
    "min_liq_usd": 500e3,           # reserve_in_usd of the token's most liquid pool
    "min_vol24_usd": 1e6,           # summed 24h volume across the token's pools seen
    # universe, wide tier (anything passing these but not the core rules is tier 'wide')
    "wide_enabled": True, "wide_min_age_days": 3, "wide_min_mcap_usd": 3e6, "wide_max_mcap_usd": 1e9,
    "wide_min_liq_usd": 300e3, "wide_min_vol24_usd": 750e3,
    "scout_intel_file": "/workspace/onchain-intel/oldcoins-intel.json",   # verdict 'avoid' -> skip; 'support'/'strong_support' -> priority input
    "pulse_midcaps_file": "/workspace/x-intel/midcaps.json",              # untrusted; parsed defensively
    "pulse_rising_trends": ["rising", "heating", "up", "surging"],
    "pulse_max_age_min": 180,       # ignore Pulse file if older (or stale flag set)
    "scout_max_age_min": 180,
    "universe_refresh_min": 60,
    "gt_pages_top": 10,             # /networks/solana/pools?sort=h24_volume_usd_desc pages
    "gt_pages_trending": 3,         # /networks/solana/trending_pools pages
    "gt_sleep_s": 3.0,              # GT throttled at 2.3s on first run (shared IP with radar)
    # signals
    "ohlcv_limit": 500,             # candles requested (need >=200 closed for EMA200)
    "min_candles": 220,
    "ema_fast": 50, "ema_slow": 200, "ema_trail": 20,
    "breakout_lookback": 24, "vol_avg_len": 20,
    # sizing / costs
    "book_sol": 0.928, "size_pct": 0.05,       # 0.0464 SOL per entry
    "fee_pct_per_side": 0.01,
    "slippage_model": "2*size_usd/liquidity_usd (constant-product impact; reserve_in_usd counts both sides)",
    # exits
    "stop_pct": 0.08,               # 1h: max stop distance below entry
    "stop_min_pct": 0.025,          # stop is breakout candle low, clamped to >=2.5% and <=max below entry
    "tp_pct": 0.15, "tp_fraction": 0.5,
    # 15m setup type (same universe; only fetched for tokens passing the 1h trend filter)
    "tf15_enabled": True, "tf15_ohlcv_limit": 200, "tf15_min_candles": 80,
    "tf15_ema_fast": 50, "tf15_ema_trail": 20, "tf15_breakout_lookback": 24, "tf15_vol_avg_len": 20,
    "tf15_stop_pct": 0.06, "tf15_tp_pct": 0.10, "tf15_tp_fraction": 0.5,
    # setup C: 15m pullback to EMA20 in a 1h uptrend
    "c_enabled": True, "c_lookback": 6, "c_touch_pct": 0.01,   # a low at or within 1% above the 15m EMA20
    "c_stop_max_pct": 0.06, "c_tp_pct": 0.10, "c_tp_fraction": 0.5,
    "c_trail_fraction": 0.3,        # 30% of original trails under 15m EMA20 after TP
    "c_moon_fraction": 0.2, "c_moon_trail_pct": 0.08,   # 20% moonbag: exit on close 8% below highest close since entry
    # volume confirmation: normal setups need vol > vol_mult x 20-bar avg; priority needs vol >= priority_vol_mult x avg
    "vol_mult": 1.0, "priority_vol_mult": 1.0,
    "priority_scout_verdicts": ["support", "strong_support"],
    # labels for the live routine (this script never trades)
    # 2026-10-23 23:58Z: all live older-coins entries stopped (Lab backtest negative for every setup) -> nothing is live_eligible.
    "live_types": [], "live_tiers": [], "live_allow_priority": False,
    # activity filters (applied before a setup counts)
    "act_n_candles": 4, "act_1h_min_usd": 150e3, "act_15m_min_usd": 40e3,
    "thin_liq_mcap_max": 0.4, "thin_vol_liq_min": 0.05,   # skip if liq/mcap > 0.4 AND vol24/liq < 0.05
    # data sources: DexScreener for discovery + metrics, GeckoTerminal only for OHLCV
    "ds_search_terms": ["solana", "SOL", "pump", "bonk", "raydium", "meteora", "orca", "pumpswap", "wif", "ai agent",
                        "cat", "dog", "trump", "meme", "moon", "fart", "useless", "pengu", "jup", "pnut"],
    "ds_batch": 30, "ds_sleep_s": 0.3, "ds_min_candidates": 15,
    "gt_fallback_discovery": True, "gt_discovery_every_min": 360,   # GT pool-list discovery at most every 6h; found addresses persist in seeds
    "candle_cache_1h_min": 10,      # (unused since v4: candles are reused exactly until the next candle closes + grace)
    "candle_close_grace_s": 75,     # wait this long after a candle closes before trusting GT has it
    "fresh_price_from_ds": True,    # latest price for entries/stops from one batched DexScreener call per run
    # timing (Europe/Dublin)
    "entry_start": "21:00", "entry_end": "07:30", "eod_close": "07:45", "night_start": "21:00",
    "max_runtime_s": 450,
}
EXCL_SYMBOLS = {s.upper() for s in """
SOL WSOL USDC USDT PYUSD USDS USDE USDH UXD USDY DAI FDUSD TUSD USD1 USDG EURC EURI EUROE FRAX
USDC.E USDT.E SUSD SUSDE USX USDB AUSD HYUSD USDO USDU USR CASH ONYC
MSOL JITOSOL BSOL JUPSOL INF HSOL STSOL LAINESOL BNSOL DSOL VSOL PICOSOL HUBSOL STRONGSOL
COMPASSSOL EDGESOL BONKSOL CGNTSOL JSOL LST SSOL FPSOL ADRASOL PATHSOL BBSOL PSOL XSOL CBSOL
WBTC CBBTC WETH ETH BTC ZBTC TBTC XBTC FBTC LBTC SOBTC WBNB BNB WAVAX WMATIC WSTETH STETH
XAUT PAXG ZEC HYPE WNEAR NEAR WHYPE WZEC""".split()}
EXCL_ADDR = {"So11111111111111111111111111111111111111112"}


class Stale(Exception):
    pass


T0 = time.time()
_last_req = [0.0]
RL_HITS = [0]
CACHE_HITS = [0]
GT_CALLS = [0]
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json;version=20230302", "User-Agent": "oldcoins-paper/1.0"})


def gt_get(path, params=None, cfg=CONFIG, tries=4):
    for i in range(tries):
        wait = cfg["gt_sleep_s"] - (time.time() - _last_req[0])
        if wait > 0:
            time.sleep(wait)
        _last_req[0] = time.time(); GT_CALLS[0] += 1
        try:
            r = SESSION.get(GT + path, params=params, timeout=20)
        except requests.RequestException as e:
            err = str(e); time.sleep(3 * (i + 1)); continue
        if r.status_code == 200:
            return r.json()
        err = f"HTTP {r.status_code}"
        if r.status_code == 429:
            RL_HITS[0] += 1
            time.sleep(min(20, 8 * (i + 1)))
        elif r.status_code == 404:
            return None
        else:
            time.sleep(3 * (i + 1))
    raise Stale(f"GeckoTerminal {path}: {err}")


def fnum(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def hm(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)


def load_json(p, default):
    try:
        with open(p) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, p)


def log_event(ev):
    with open(LOG_F, "a") as f:
        f.write(json.dumps(ev) + "\n")


def load_avoid(notes):
    addrs = set()
    if not os.path.exists(AVOID_F):
        notes.append("avoid.csv missing - not applied")
        return addrs
    with open(AVOID_F, newline="") as f:
        for row in csv.DictReader(f):
            a = (row.get("address") or "").strip()
            if a:
                addrs.add(a)
            for m in (row.get("mints") or "").replace(";", " ").replace(",", " ").split():
                addrs.add(m.strip())
    return addrs


def is_excluded(sym, name, addr, price):
    s = (sym or "").upper().strip()
    if addr in EXCL_ADDR or s in EXCL_SYMBOLS:
        return "excluded_symbol"
    if s.endswith("SOL") and len(s) > 3 and ("staked" in (name or "").lower() or s in EXCL_SYMBOLS):
        return "lst"
    if "staked sol" in (name or "").lower() or "liquid staking" in (name or "").lower():
        return "lst"
    nl = (name or "").lower()
    # tokenized equities / bridged majors are not "coins" for this book
    if any(k in nl for k in ("xstock", "securities", "tokenized", "wrapped", "bridged", "wormhole", "(portal)")):
        return "wrapped/tokenized"
    if any(k in nl for k in ("usd coin", "tether", "stablecoin", "wrapped bitcoin", "wrapped ether", "wrapped btc")):
        return "stable/wrapped_name"
    if price is not None and 0.97 <= price <= 1.03 and ("usd" in s.lower() or "usd" in nl):
        return "stable_peg"
    return None


def ds_get(url, cfg, tries=3):
    err = "?"
    for i in range(tries):
        time.sleep(cfg["ds_sleep_s"])
        try:
            r = SESSION.get(DS + url, timeout=20)
        except requests.RequestException as e:
            err = str(e); time.sleep(2 * (i + 1)); continue
        if r.status_code == 200:
            return r.json()
        err = f"HTTP {r.status_code}"
        time.sleep(5 * (i + 1) if r.status_code == 429 else 2)
    raise Stale(f"DexScreener {url}: {err}")


def clamp_stop(entry, low, max_pct, cfg):
    """Breakout candle low, clamped to between stop_min_pct and max_pct below entry."""
    lo_bound, hi_bound = entry * (1 - max_pct), entry * (1 - cfg["stop_min_pct"])
    if low is None or low > hi_bound:
        return hi_bound, f"clamped_min_{cfg['stop_min_pct']*100:g}%"
    if low < lo_bound:
        return lo_bound, f"clamped_max_{max_pct*100:g}%"
    return low, "breakout_low"


def build_universe_ds(cfg, notes, avoid_thin_log):
    avoid = load_avoid(notes)
    seeds = set(load_json(SEEDS_F, []))
    prev = load_json(UNIVERSE_F, {}) or {}
    seeds.update(t["address"] for t in prev.get("tokens", []))
    disc = set()
    src_fail = 0
    for path in ("/token-boosts/top/v1", "/token-boosts/latest/v1", "/token-profiles/latest/v1",
                 "/community-takeovers/latest/v1"):
        try:
            d = ds_get(path, cfg)
            disc.update(x["tokenAddress"] for x in (d or []) if x.get("chainId") == "solana" and x.get("tokenAddress"))
        except Stale as e:
            src_fail += 1; notes.append(str(e))
    for q in cfg["ds_search_terms"]:
        try:
            d = ds_get(f"/latest/dex/search?q={requests.utils.quote(q)}", cfg)
            for pr in (d or {}).get("pairs") or []:
                if pr.get("chainId") == "solana":
                    disc.add(pr["baseToken"]["address"])
        except Stale as e:
            src_fail += 1; notes.append(str(e))

    def fetch_metrics(addrs):
        out = {}
        al = sorted(a for a in addrs if a not in EXCL_ADDR)
        for i in range(0, len(al), cfg["ds_batch"]):
            chunk = al[i:i + cfg["ds_batch"]]
            try:
                d = ds_get("/tokens/v1/solana/" + ",".join(chunk), cfg)
            except Stale as e:
                notes.append(str(e)); continue
            for pr in d or []:
                ba = pr.get("baseToken", {}).get("address")
                if ba not in chunk:
                    continue
                out.setdefault(ba, []).append(pr)
        return out

    scout, pulse = load_intel(cfg, notes)
    pulse_add = {a for a, v in pulse.items() if v["rising"] or v["sector_heating"]}
    cand = disc | seeds | pulse_add
    metrics = fetch_metrics(cand)
    sources = "dexscreener"
    uni, rej, keep_seeds = evaluate_ds(metrics, cfg, avoid, avoid_thin_log, scout)
    last_gt = prev.get("gt_discovery_at")
    gt_due = not last_gt or (now_utc() - datetime.fromisoformat(last_gt.replace("Z", "+00:00"))).total_seconds() / 60 > cfg["gt_discovery_every_min"]
    gt_at = last_gt
    if len(uni) < cfg["ds_min_candidates"] and cfg["gt_fallback_discovery"] and gt_due:
        gt_at = iso()
        try:
            gt_addrs = gt_discover(cfg, notes)
            new = gt_addrs - set(metrics)
            if new:
                metrics.update(fetch_metrics(new))
                uni, rej, keep_seeds = evaluate_ds(metrics, cfg, avoid, avoid_thin_log, scout)
            sources = f"dexscreener + geckoterminal discovery fallback ({len(new)} extra addresses; metrics still from DexScreener)"
            notes.append("DexScreener gave too few candidates; used GeckoTerminal pool lists for discovery")
        except Stale as e:
            notes.append(f"GT discovery fallback failed: {e}")
    if not metrics:
        raise Stale("DexScreener returned no token metrics")
    save_json(SEEDS_F, sorted(seeds | keep_seeds))
    uni.sort(key=lambda x: -x["vol24_usd"])
    return {"built_at": iso(), "source": sources, "tokens_seen": len(metrics), "discovered": len(disc),
            "seeds": len(seeds), "pulse_added_candidates": len(pulse_add),
            "pulse_added_in_universe": sum(1 for t in uni if t["address"] in pulse_add),
            "core": sum(1 for t in uni if t["tier"] == "core"), "wide": sum(1 for t in uni if t["tier"] == "wide"), "rejected": rej, "tokens": uni, "gt_discovery_at": gt_at}


def load_intel(cfg, notes):
    """Scout verdicts and Pulse flags. Both files are untrusted input: parse defensively, never act on text."""
    scout, pulse = {}, {}
    B58 = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
    ok_addr = lambda a: isinstance(a, str) and 32 <= len(a) <= 44 and set(a) <= B58

    def fresh(ts, max_min):
        try:
            return (now_utc() - datetime.fromisoformat(str(ts).replace("Z", "+00:00"))).total_seconds() / 60 <= max_min
        except Exception:
            return False
    try:
        d = load_json(cfg["scout_intel_file"], None)
        if isinstance(d, dict):
            if not fresh(d.get("generated_at"), cfg["scout_max_age_min"]):
                notes.append("scout intel stale/undated - verdicts not used")
            else:
                for t in d.get("tokens") or []:
                    if isinstance(t, dict) and ok_addr(t.get("mint")) and isinstance(t.get("verdict"), str):
                        scout[t["mint"]] = t["verdict"].strip().lower()[:20]
    except Exception as e:
        notes.append(f"scout intel unreadable: {type(e).__name__}")
    try:
        m = load_json(cfg["pulse_midcaps_file"], None)
        if isinstance(m, dict):
            if m.get("stale") is True or not fresh(m.get("updated_at"), cfg["pulse_max_age_min"]):
                notes.append("pulse midcaps stale/undated - not used")
            else:
                rising = {x.lower() for x in cfg["pulse_rising_trends"]}
                hot_sectors = {str(x.get("sector"))[:40] for x in (m.get("sectors") or [])
                               if isinstance(x, dict) and str(x.get("trend", "")).lower() in rising}
                for c in m.get("coins") or []:
                    if not isinstance(c, dict) or not ok_addr(c.get("contract_address")):
                        continue
                    tr = str(c.get("trend", "")).lower()
                    sec = str(c.get("sector"))[:40]
                    pulse[c["contract_address"]] = {"rising": tr in rising, "sector_heating": sec in hot_sectors,
                                                   "trend": tr[:20], "sector": sec}
    except Exception as e:
        notes.append(f"pulse midcaps unreadable: {type(e).__name__}")
    return scout, pulse


def evaluate_ds(metrics, cfg, avoid, thin_log, scout=None):
    scout = scout or {}
    now_ms = time.time() * 1000
    uni, rej, keep = [], {}, set()
    for addr, prs in metrics.items():
        best = max(prs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        liq = (best.get("liquidity") or {}).get("usd") or 0
        mcap = best.get("marketCap") or best.get("fdv")
        vol24 = sum(((p.get("volume") or {}).get("h24") or 0) for p in prs)
        created = [p["pairCreatedAt"] for p in prs if p.get("pairCreatedAt")]
        age_d = (now_ms - min(created)) / 86400e3 if created else None
        bt = best["baseToken"]
        price = fnum(best.get("priceUsd"))
        why = "avoid_list" if addr in avoid else is_excluded(bt.get("symbol"), bt.get("name"), addr, price)
        if not why and scout.get(addr) == "avoid":
            why = "scout_avoid"
        W = "wide_" if cfg["wide_enabled"] else ""
        core_ok = (age_d is not None and age_d >= cfg["min_age_days"] and mcap is not None and
                   cfg["min_mcap_usd"] <= mcap <= cfg["max_mcap_usd"] and liq >= cfg["min_liq_usd"] and vol24 >= cfg["min_vol24_usd"])
        if not why:
            if age_d is None or age_d < cfg[W + "min_age_days"]: why = "too_young"
            elif mcap is None or not (cfg[W + "min_mcap_usd"] <= mcap <= cfg[W + "max_mcap_usd"]): why = "mcap"
            elif liq < cfg[W + "min_liq_usd"]: why = "liquidity"
            elif vol24 < cfg[W + "min_vol24_usd"]: why = "volume"
            elif liq / mcap > cfg["thin_liq_mcap_max"] and vol24 / liq < cfg["thin_vol_liq_min"]:
                why = "thin_activity"
                thin_log.append({"event": "filtered", "token": bt.get("symbol"), "address": addr, "pool": best.get("pairAddress"),
                                 "reason": f"liq/mcap {liq/mcap:.2f} > {cfg['thin_liq_mcap_max']} and vol24/liq {vol24/liq:.3f} < {cfg['thin_vol_liq_min']}",
                                 "liq_usd": round(liq), "mcap_usd": round(mcap), "vol24_usd": round(vol24)})
        if age_d and age_d >= cfg["wide_min_age_days"] and liq >= 0.5 * cfg["wide_min_liq_usd"] and not why in ("avoid_list",):
            keep.add(addr)   # remember plausible older tokens for future DexScreener re-checks
        if why:
            rej[why] = rej.get(why, 0) + 1; continue
        uni.append({"tier": "core" if core_ok else "wide", "address": addr, "symbol": bt.get("symbol"), "name": bt.get("name"), "pool": best.get("pairAddress"),
                    "pool_name": f"{bt.get('symbol')} / {best.get('quoteToken', {}).get('symbol')} ({best.get('dexId')})",
                    "liq_usd": round(liq), "mcap_usd": round(mcap), "mcap_is_fdv": not bool(best.get("marketCap")),
                    "vol24_usd": round(vol24), "age_days": round(age_d, 1), "price_usd": price,
                    "liq_mcap": round(liq / mcap, 3), "vol24_liq": round(vol24 / liq, 3) if liq else None})
    return uni, rej, keep


def gt_discover(cfg, notes):
    """Fallback discovery only: base-token addresses from GeckoTerminal pool lists."""
    addrs = set()
    for path, extra, n in [("/networks/solana/pools", {"sort": "h24_volume_usd_desc"}, cfg["gt_pages_top"]),
                           ("/networks/solana/trending_pools", {}, cfg["gt_pages_trending"])]:
        for page in range(1, n + 1):
            if time.time() - T0 > cfg["max_runtime_s"] * 0.4:
                notes.append("GT discovery cut short for runtime"); return addrs
            d = gt_get(path, dict(extra, page=page), cfg)
            if not d or not d.get("data"): break
            for p in d["data"]:
                addrs.add(p["relationships"]["base_token"]["data"]["id"].split("_", 1)[1])
    return addrs


def build_universe_gt_legacy(cfg, notes):
    avoid = load_avoid(notes)
    pools = []  # (pool_attr, base_token_attr, dex)
    tokens = {}
    pages = [("/networks/solana/pools", {"sort": "h24_volume_usd_desc"}, cfg["gt_pages_top"]),
             ("/networks/solana/trending_pools", {}, cfg["gt_pages_trending"])]
    fails = 0
    for path, extra, n in pages:
        for page in range(1, n + 1):
            if time.time() - T0 > cfg["max_runtime_s"] * 0.45:
                notes.append("universe page fetch cut short for runtime"); break
            try:
                d = gt_get(path, dict(extra, page=page, include="base_token,quote_token"), cfg)
            except Stale as e:
                fails += 1; notes.append(str(e)); continue
            if not d or not d.get("data"):
                break
            inc = {x["id"]: x["attributes"] for x in d.get("included", [])}
            for p in d["data"]:
                a = p["attributes"]
                bt = p["relationships"]["base_token"]["data"]["id"]
                ta = inc.get(bt, {})
                taddr = bt.split("_", 1)[1]
                pools.append((p["id"].split("_", 1)[1], a, taddr, ta))
    if not pools:
        raise Stale("no pools returned from GeckoTerminal")
    if fails:
        notes.append(f"{fails} universe page(s) failed")
    # aggregate per base token
    for paddr, a, taddr, ta in pools:
        t = tokens.setdefault(taddr, {"address": taddr, "symbol": ta.get("symbol"), "name": ta.get("name"),
                                      "pools": {}, "first_pool_created": None})
        if paddr in t["pools"]:
            continue
        created = a.get("pool_created_at")
        t["pools"][paddr] = {"liq": fnum(a.get("reserve_in_usd")) or 0.0, "vol24": fnum((a.get("volume_usd") or {}).get("h24")) or 0.0,
                             "mcap": fnum(a.get("market_cap_usd")), "fdv": fnum(a.get("fdv_usd")),
                             "price": fnum(a.get("base_token_price_usd")), "name": a.get("name"), "created": created}
        if created and (t["first_pool_created"] is None or created < t["first_pool_created"]):
            t["first_pool_created"] = created
    now = now_utc()
    uni, rej = [], {}
    for taddr, t in tokens.items():
        best_addr, best = max(t["pools"].items(), key=lambda kv: kv[1]["liq"])
        mcap = best["mcap"] if best["mcap"] else best["fdv"]
        vol24 = sum(p["vol24"] for p in t["pools"].values())
        age_d = None
        if t["first_pool_created"]:
            age_d = (now - datetime.fromisoformat(t["first_pool_created"].replace("Z", "+00:00"))).total_seconds() / 86400
        why = None
        if taddr in avoid: why = "avoid_list"
        else: why = is_excluded(t["symbol"], t["name"], taddr, best["price"])
        if not why:
            if age_d is None or age_d < cfg["min_age_days"]: why = "too_young"
            elif mcap is None or not (cfg["min_mcap_usd"] <= mcap <= cfg["max_mcap_usd"]): why = "mcap"
            elif best["liq"] < cfg["min_liq_usd"]: why = "liquidity"
            elif vol24 < cfg["min_vol24_usd"]: why = "volume"
        if why:
            rej[why] = rej.get(why, 0) + 1; continue
        uni.append({"address": taddr, "symbol": t["symbol"], "name": t["name"], "pool": best_addr,
                    "pool_name": best["name"], "liq_usd": round(best["liq"]), "mcap_usd": round(mcap),
                    "mcap_is_fdv": not bool(best["mcap"]), "vol24_usd": round(vol24), "age_days": round(age_d, 1),
                    "price_usd": best["price"]})
    uni.sort(key=lambda x: -x["vol24_usd"])
    return {"built_at": iso(), "tokens_seen": len(tokens), "pools_seen": len(pools), "rejected": rej, "tokens": uni}


def ema(vals, n):
    if len(vals) < n:
        return [None] * len(vals)
    out = [None] * (n - 1)
    e = sum(vals[:n]) / n
    out.append(e)
    k = 2 / (n + 1)
    for v in vals[n:]:
        e = v * k + e * (1 - k); out.append(e)
    return out


def get_candles(pool, cfg, tf="1h"):
    if tf == "15m":
        path, params, period = f"/networks/solana/pools/{pool}/ohlcv/minute", {"aggregate": 15, "limit": cfg["tf15_ohlcv_limit"]}, 900
    else:
        path, params, period = f"/networks/solana/pools/{pool}/ohlcv/hour", {"aggregate": 1, "limit": cfg["ohlcv_limit"]}, 3600
    cf = os.path.join(CACHE_D, f"{pool}_{tf}.json")
    rows = None
    c0 = load_json(cf, None)
    if c0:
        last_close = (time.time() - cfg["candle_close_grace_s"]) // period * period   # latest candle boundary GT should have
        # reuse only if fetched after the latest candle close (+grace): no newer closed candle can exist yet
        if c0["fetched_at"] >= last_close + cfg["candle_close_grace_s"]:
            rows = c0["rows"]; fetched_at = c0["fetched_at"]; CACHE_HITS[0] += 1
    if rows is None:
        d = gt_get(path, dict(params, currency="usd", token="base"), cfg)
        if not d:
            return None
        rows = d.get("data", {}).get("attributes", {}).get("ohlcv_list", []) or []
        fetched_at = time.time()
        os.makedirs(CACHE_D, exist_ok=True); save_json(cf, {"fetched_at": fetched_at, "rows": rows})
    now = fetched_at   # a candle counts as closed only if it had closed when the data was fetched
    c = sorted(([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows), key=lambda r: r[0])
    closed = [r for r in c if r[0] + period <= now]   # closed candles only
    last_px = c[-1][4] if c else None               # latest traded price (may be open candle; may be cached)
    return closed, last_px


def analyse(closed, cfg):
    closes = [r[4] for r in closed]
    e50, e200, e20 = ema(closes, cfg["ema_fast"]), ema(closes, cfg["ema_slow"]), ema(closes, cfg["ema_trail"])
    L, V = cfg["breakout_lookback"], cfg["vol_avg_len"]
    last = closed[-1]
    prior = closed[-1 - L:-1]
    hh = max(r[2] for r in prior); ll = min(r[3] for r in prior)
    vavg = sum(r[5] for r in closed[-1 - V:-1]) / V
    return {"ts": last[0], "o": last[1], "h": last[2], "l": last[3], "c": last[4], "v": last[5],
            "ema50": e50[-1], "ema200": e200[-1], "ema20": e20[-1], "hh24": hh, "ll24": ll, "vavg20": vavg,
            "e20_series": e20}


def cost_frac(size_usd, liq_usd, cfg):
    slip = (2 * size_usd / liq_usd) if liq_usd else 0.01
    return cfg["fee_pct_per_side"] + slip, slip


def sol_usd():
    try:
        d = ds_get("/tokens/v1/solana/So11111111111111111111111111111111111111112", CONFIG)
        prs = [p for p in d if p["baseToken"]["address"].startswith("So111")]
        return fnum(max(prs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)["priceUsd"])
    except Exception:
        return None



def ds_prices(addrs, cfg, notes):
    """Fresh USD price per token (most liquid pair) - DexScreener, 30 per call."""
    out, al = {}, sorted(set(addrs))
    for i in range(0, len(al), cfg["ds_batch"]):
        chunk = al[i:i + cfg["ds_batch"]]
        try:
            d = ds_get("/tokens/v1/solana/" + ",".join(chunk), cfg)
        except Stale as e:
            notes.append(f"fresh prices: {e}"); continue
        best = {}
        for pr in d or []:
            ba = pr.get("baseToken", {}).get("address")
            lq = (pr.get("liquidity") or {}).get("usd") or 0
            if ba in chunk and fnum(pr.get("priceUsd")) and lq >= best.get(ba, (0, None))[0]:
                best[ba] = (lq, fnum(pr["priceUsd"]))
        out.update({k: v[1] for k, v in best.items()})
    return out


def close_leg(pos, frac_of_orig, px, reason, now_s, cfg, events, leg=None):
    frac_of_orig = min(frac_of_orig, pos["remaining"])
    if frac_of_orig <= 1e-9:
        return
    size = pos["size_sol"] * frac_of_orig
    exit_eff = px * (1 - pos["cost_frac"])
    pnl_pct = exit_eff / pos["entry_eff"] - 1
    pnl_sol = size * pnl_pct
    pos["remaining"] = round(pos["remaining"] - frac_of_orig, 6)
    pos["realized_sol"] = pos.get("realized_sol", 0) + pnl_sol
    if leg:
        pos["legs"][leg] = 0.0
    else:
        pos["legs"] = {k: 0.0 for k in pos.get("legs", {})}
    ev = {"ts": now_s, "event": "partial" if pos["remaining"] > 1e-9 else "exit", "token": pos["symbol"],
          "address": pos["address"], "pool": pos["pool"], "setup_type": pos.get("setup_type"), "tier": pos.get("tier"),
          "timeframe": pos.get("timeframe"), "price": px, "size_sol": round(size, 6), "leg": leg or "all",
          "reason": reason, "pnl_sol": round(pnl_sol, 6), "pnl_pct": round(pnl_pct * 100, 3),
          "cost_frac_per_side": round(pos["cost_frac"], 5), "entry_price": pos["entry_price"]}
    log_event(ev); events.append(ev)


def plan_for(stype, cfg):
    """Legs (fractions of the original size) and their rules."""
    if stype == "C":
        return {"tp": cfg["c_tp_fraction"], "trail": cfg["c_trail_fraction"], "moon": cfg["c_moon_fraction"]}
    tpf = cfg["tf15_tp_fraction"] if stype == "B" else cfg["tp_fraction"]
    return {"tp": tpf, "trail": round(1 - tpf, 6)}


def manage(pos, closed, last_px, cfg, now_s, eod, events):
    """Walk closed candles after entry. Conservative: stop checked before TP within a candle.
    After TP: 'trail' leg exits on a close below EMA20; 'moon' leg (C only) exits on a close
    c_moon_trail_pct below the highest close since entry."""
    tf = pos.get("timeframe", "1h")
    pos.setdefault("setup_type", "B" if tf == "15m" else "A")
    pos.setdefault("legs", plan_for(pos["setup_type"], cfg))
    pos.setdefault("high_close", pos["entry_price"])
    e20 = ema([r[4] for r in closed], cfg["tf15_ema_trail"] if tf == "15m" else cfg["ema_trail"])
    for i, r in enumerate(closed):
        if r[0] <= pos["last_candle_ts"]:
            continue
        pos["last_candle_ts"] = r[0]
        if pos["remaining"] <= 1e-9: break
        if r[3] <= pos["stop"]:
            close_leg(pos, pos["remaining"], pos["stop"], "stop", now_s, cfg, events); break
        pos["high_close"] = max(pos["high_close"], r[4])
        if not pos["tp_done"] and r[2] >= pos["tp_price"]:
            close_leg(pos, pos["legs"]["tp"], pos["tp_price"], f"tp_{pos['setup_type']}", now_s, cfg, events, leg="tp")
            pos["tp_done"] = True
            continue  # trails evaluated from the next candle
        if pos["tp_done"]:
            if pos["legs"].get("trail", 0) > 0 and e20[i] is not None and r[4] < e20[i]:
                close_leg(pos, pos["legs"]["trail"], r[4], f"trail_{tf}_close_below_ema20", now_s, cfg, events, leg="trail")
            if pos["legs"].get("moon", 0) > 0 and r[4] < pos["high_close"] * (1 - cfg["c_moon_trail_pct"]):
                close_leg(pos, pos["legs"]["moon"], r[4], f"moonbag_trail_{cfg['c_moon_trail_pct']*100:g}%", now_s, cfg, events, leg="moon")
    if pos["remaining"] > 1e-9 and last_px is not None:
        if last_px <= pos["stop"]:
            close_leg(pos, pos["remaining"], last_px, "stop_live_price", now_s, cfg, events)
        elif eod:
            close_leg(pos, pos["remaining"], last_px, "eod", now_s, cfg, events)
    pos["last_px"] = last_px


def vol_ok(v, avg, priority, cfg):
    return v >= cfg["priority_vol_mult"] * avg if priority else v > cfg["vol_mult"] * avg


def find_setups(t, closed1h, a, c15, cfg, priority):
    """Return candidate setups (dicts) for one token. Pure function of candles."""
    out = []
    n = cfg["act_n_candles"]
    act1h = sum(r[5] for r in closed1h[-n:])
    trend_up = a["c"] > a["ema50"] > a["ema200"]
    if trend_up and a["c"] > a["hh24"] and vol_ok(a["v"], a["vavg20"], priority, cfg):
        out.append({"setup_type": "A", "timeframe": "1h", "candle_ts": a["ts"], "close": a["c"], "low": a["l"],
                    "act": act1h, "act_min": cfg["act_1h_min_usd"], "max_stop": cfg["stop_pct"], "tp_pct": cfg["tp_pct"],
                    "trail": f"rest on 1h close below 1h EMA{cfg['ema_trail']} (now {a['ema20']:.6g})",
                    "why": f"1h close {a['c']:.6g} > 24h high {a['hh24']:.6g}, >EMA50 {a['ema50']:.6g} > EMA200 {a['ema200']:.6g}, vol {a['v']:.0f} vs avg {a['vavg20']:.0f}"})
    if c15 and len(c15) >= cfg["tf15_min_candles"]:
        cl = [r[4] for r in c15]
        e50 = ema(cl, cfg["tf15_ema_fast"]); e20 = ema(cl, cfg["tf15_ema_trail"])
        b = c15[-1]
        V, L = cfg["tf15_vol_avg_len"], cfg["tf15_breakout_lookback"]
        vavg = sum(r[5] for r in c15[-1 - V:-1]) / V
        hh = max(r[2] for r in c15[-1 - L:-1])
        act15 = sum(r[5] for r in c15[-n:])
        if a["ema50"] > a["ema200"] and e50[-1] and b[4] > e50[-1] and b[4] > hh and vol_ok(b[5], vavg, priority, cfg):
            out.append({"setup_type": "B", "timeframe": "15m", "candle_ts": b[0], "close": b[4], "low": b[3],
                        "act": act15, "act_min": cfg["act_15m_min_usd"], "max_stop": cfg["tf15_stop_pct"], "tp_pct": cfg["tf15_tp_pct"],
                        "trail": f"rest on 15m close below 15m EMA{cfg['tf15_ema_trail']} (now {e20[-1]:.6g})",
                        "why": f"15m close {b[4]:.6g} > 6h high {hh:.6g}, >15m EMA50 {e50[-1]:.6g}, 1h EMA50>EMA200, vol {b[5]:.0f} vs avg {vavg:.0f}"})
        if cfg["c_enabled"] and trend_up and e20[-1] and e20[-2]:
            K = cfg["c_lookback"]
            win = list(range(len(c15) - 1 - K, len(c15) - 1))
            touch = [i for i in win if e20[i] and c15[i][3] <= e20[i] * (1 + cfg["c_touch_pct"])]
            prev = c15[-2]
            prev_at = prev[4] <= e20[-2] or prev[3] <= e20[-2] * (1 + cfg["c_touch_pct"])
            if touch and prev_at and b[4] > e20[-1] and vol_ok(b[5], vavg, priority, cfg):
                plow = min(c15[i][3] for i in win + [len(c15) - 1])
                out.append({"setup_type": "C", "timeframe": "15m", "candle_ts": b[0], "close": b[4], "low": plow,
                            "act": act15, "act_min": cfg["act_15m_min_usd"], "max_stop": cfg["c_stop_max_pct"], "tp_pct": cfg["c_tp_pct"],
                            "trail": (f"after TP: {cfg['c_trail_fraction']*100:g}% on 15m close below EMA{cfg['tf15_ema_trail']} (now {e20[-1]:.6g}); "
                                      f"{cfg['c_moon_fraction']*100:g}% moonbag exits on close {cfg['c_moon_trail_pct']*100:g}% below highest close"),
                            "why": f"15m pullback: {len(touch)} of last {K} lows within {cfg['c_touch_pct']*100:g}% of 15m EMA20, prev candle at/below EMA20 {e20[-2]:.6g}, "
                                   f"close {b[4]:.6g} back above EMA20 {e20[-1]:.6g}; 1h close>EMA50>EMA200; vol {b[5]:.0f} vs avg {vavg:.0f}"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tuned-config"); ap.add_argument("--force-universe", action="store_true")
    ap.add_argument("--no-window", action="store_true", help="ignore entry time window (testing)")
    ap.add_argument("--setups-json", action="store_true", help="print ONLY this scan's fresh long setups as JSON")
    args = ap.parse_args()
    cfg = dict(CONFIG)
    if args.tuned_config:
        with open(args.tuned_config) as f:
            tuned = json.load(f)
        unknown = set(tuned) - set(cfg)
        cfg.update({k: v for k, v in tuned.items() if k in cfg})
        if unknown:
            print(f"oldcoins: warning, unknown tuned keys ignored: {sorted(unknown)}", file=sys.stderr)
    os.makedirs(LIVE, exist_ok=True)
    notes = []
    nowd = now_utc().astimezone(DUB); now_s = iso()
    mins = nowd.hour * 60 + nowd.minute
    in_window = args.no_window or (mins >= hm(cfg["entry_start"]) or mins < hm(cfg["entry_end"]))
    eod = hm(cfg["eod_close"]) <= mins < hm(cfg["night_start"])
    ns = nowd.replace(hour=int(cfg["night_start"][:2]), minute=int(cfg["night_start"][3:]), second=0, microsecond=0)
    if nowd < ns: ns -= timedelta(days=1)
    night_start_utc = ns.astimezone(timezone.utc)

    thin_log = []
    uni = load_json(UNIVERSE_F, None)
    age_min = None
    if uni:
        age_min = (now_utc() - datetime.fromisoformat(uni["built_at"].replace("Z", "+00:00"))).total_seconds() / 60
    rebuilt = False
    if args.force_universe or not uni or age_min > cfg["universe_refresh_min"] or "core" not in uni:
        try:
            uni = build_universe_ds(cfg, notes, thin_log); save_json(UNIVERSE_F, uni); rebuilt = True
        except Stale as e:
            if uni and age_min is not None and age_min < 180:
                notes.append(f"universe refresh failed, using cache {age_min:.0f}m old: {e}")
            else:
                print(f"oldcoins: STALE/ERROR universe: {e}"); sys.exit(2)
    t_universe = time.time() - T0
    scout, pulse = load_intel(cfg, notes)
    avoid = load_avoid(notes)

    state = load_json(POS_F, {"positions": [], "seen_long": {}, "seen_short": {}})
    for k in ("seen_long", "seen_short", "seen_filtered"):
        state.setdefault(k, {})
    positions = state["positions"]
    filtered, events, setups_all, fresh_setups, shorts = [], [], [], [], []
    fetch_fail, short_hist = 0, 0
    for ev in thin_log:
        k = f"{ev['address']}:thin:{iso(night_start_utc)}"
        if k not in state["seen_filtered"]:
            state["seen_filtered"][k] = now_s; log_event(dict(ev, ts=now_s)); filtered.append(ev)
    size_sol = round(cfg["book_sol"] * cfg["size_pct"], 6)
    solpx = sol_usd() or 150.0
    if solpx == 150.0: notes.append("SOL price unavailable, assumed $150 for slippage")
    size_usd = size_sol * solpx
    held = {p["address"] for p in positions if p["remaining"] > 1e-9}
    prices = ds_prices([t["address"] for t in uni["tokens"]] + list(held), cfg, notes) if cfg["fresh_price_from_ds"] else {}
    c1h = {}

    # 1) manage open positions (also those no longer in the universe)
    for pos in positions:
        if pos["remaining"] <= 1e-9: continue
        ptf = pos.get("timeframe", "1h")
        try:
            res = get_candles(pos["pool"], cfg, ptf)
        except Stale as e:
            fetch_fail += 1; notes.append(f"manage {pos['symbol']}: {e}"); continue
        if not res: fetch_fail += 1; continue
        if ptf == "1h": c1h[pos["pool"]] = res
        manage(pos, res[0], prices.get(pos["address"]) or res[1], cfg, now_s, eod, events)

    # 2) scan
    scanned = trend_pass = 0
    for t in uni["tokens"]:
        if time.time() - T0 > cfg["max_runtime_s"]:
            notes.append(f"scan cut short at {scanned}/{len(uni['tokens'])} for runtime"); break
        if t["address"] in avoid or scout.get(t["address"]) == "avoid":
            k = f"{t['address']}:avoid:{iso(night_start_utc)}"
            fe = {"ts": now_s, "event": "filtered", "token": t["symbol"], "address": t["address"], "tier": t.get("tier"),
                  "reason": "scout_avoid" if scout.get(t["address"]) == "avoid" else "avoid_list"}
            filtered.append(fe)
            if k not in state["seen_filtered"]:
                state["seen_filtered"][k] = now_s; log_event(fe)
            continue
        try:
            res = c1h.get(t["pool"]) or get_candles(t["pool"], cfg, "1h")
        except Stale as e:
            fetch_fail += 1; notes.append(f"{t['symbol']}: {e}"); continue
        scanned += 1
        if not res or len(res[0]) < cfg["min_candles"]:
            short_hist += 1; continue
        closed, last_px = res
        if time.time() - (closed[-1][0] + 3600) > 3 * 3600:
            notes.append(f"{t['symbol']}: last closed 1h candle stale"); continue
        a = analyse(closed, cfg)
        px = prices.get(t["address"]) or last_px
        base = {"token": t["symbol"], "address": t["address"], "pool": t["pool"], "tier": t.get("tier", "core")}
        # would-short (1h, log only)
        if a["c"] < a["ema50"] < a["ema200"] and a["c"] < a["ll24"] and a["v"] > a["vavg20"]:
            shorts.append(base)
            key = f"{t['address']}:{a['ts']}"
            if key not in state["seen_short"]:
                state["seen_short"][key] = now_s
                ev = dict(base, ts=now_s, event="would_short", timeframe="1h", price=a["c"], size_sol=0, pnl_sol=0, pnl_pct=0,
                          reason=f"LOG ONLY: 1h close {a['c']:.6g} < 24h low {a['ll24']:.6g}, <EMA50<EMA200, vol {a['v']:.0f}>{a['vavg20']:.0f}")
                log_event(ev); events.append(ev)
        if not a["ema50"] > a["ema200"]:
            continue   # no long setup type possible; no 15m fetch
        trend_pass += 1
        c15 = None
        try:
            r15 = get_candles(t["pool"], cfg, "15m")
            if r15 and r15[0] and time.time() - (r15[0][-1][0] + 900) <= 3600:
                c15 = r15[0]
        except Stale as e:
            fetch_fail += 1; notes.append(f"{t['symbol']} 15m: {e}")
        sv = scout.get(t["address"])
        pv = pulse.get(t["address"]) or {}
        priority = sv in cfg["priority_scout_verdicts"] and bool(pv.get("rising"))
        for su in find_setups(t, closed, a, c15, cfg, priority):
            key = f"{t['address']}:{su['setup_type']}:{su['candle_ts']}"
            fresh = key not in state["seen_long"]
            ent = px or su["close"]
            stop, sbasis = clamp_stop(ent, su["low"], su["max_stop"], cfg)
            tier = t.get("tier", "core")
            live_ok = (tier in cfg["live_tiers"] and su["setup_type"] in cfg["live_types"]
                       and (cfg["live_allow_priority"] or not priority))
            rec = {"ts": now_s, "event": "setup", "side": "long", "setup_type": su["setup_type"],
                   "setup_name": {"A": "1h_breakout", "B": "15m_breakout", "C": "15m_pullback"}[su["setup_type"]],
                   "timeframe": su["timeframe"], "tier": tier, "priority": priority, "live_eligible": live_ok,
                   "token": t["symbol"], "address": t["address"], "pool": t["pool"], "pool_name": t.get("pool_name"),
                   "signal_candle": iso(datetime.fromtimestamp(su["candle_ts"], timezone.utc)),
                   "signal_close": su["close"], "breakout_low": su["low"], "entry_price": ent,
                   "stop_price": stop, "stop_basis": sbasis, "stop_distance_pct": round((1 - stop / ent) * 100, 3),
                   "target_price": ent * (1 + su["tp_pct"]), "target_pct": su["tp_pct"] * 100,
                   "legs": plan_for(su["setup_type"], cfg), "trail": su["trail"],
                   "liquidity_usd": t["liq_usd"], "mcap_usd": t["mcap_usd"], "vol24_usd": t["vol24_usd"], "age_days": t.get("age_days"),
                   "activity_4c_usd": round(su["act"]), "scout_verdict": sv, "pulse": pv or None,
                   "fresh": fresh, "reason": su["why"], "taken": False, "skip_reason": None,
                   "note": "PAPER scanner output; this script never trades"}
            if su["act"] < su["act_min"]:
                rec.update(event="filtered", skip_reason=f"activity: last {cfg['act_n_candles']} {su['timeframe']} candles ${su['act']:,.0f} < ${su['act_min']:,.0f}")
                filtered.append(rec)
                if fresh:
                    state["seen_long"][key] = now_s; log_event(rec)
                continue
            setups_all.append(rec)
            if not fresh:
                continue
            state["seen_long"][key] = now_s
            if t["address"] in held: rec["skip_reason"] = "already holding this token (1 per token)"
            elif not in_window: rec["skip_reason"] = "outside entry window 21:00-07:30 Dublin"
            elif eod: rec["skip_reason"] = "eod"
            else:
                cf, slip = cost_frac(size_usd, t["liq_usd"], cfg)
                pos = {"timeframe": su["timeframe"], "setup_type": su["setup_type"], "tier": tier, "priority": priority,
                       "symbol": t["symbol"], "address": t["address"], "pool": t["pool"], "opened": now_s,
                       "entry_price": ent, "entry_eff": ent * (1 + cf), "cost_frac": cf, "slippage_frac": slip,
                       "size_sol": size_sol, "remaining": 1.0, "stop": stop, "stop_basis": sbasis, "stop_rule_v2": True,
                       "breakout_low": su["low"], "tp_price": rec["target_price"], "tp_done": False,
                       "legs": plan_for(su["setup_type"], cfg), "high_close": ent,
                       "last_candle_ts": su["candle_ts"] if su["timeframe"] == "15m" else a["ts"],
                       "signal_candle": rec["signal_candle"], "realized_sol": 0.0, "last_px": ent}
                if su["timeframe"] == "1h" and c15 is None:
                    pass
                positions.append(pos); held.add(t["address"])
                rec["taken"] = True
                ev = {"ts": now_s, "event": "entry", "setup_type": su["setup_type"], "tier": tier, "priority": priority,
                      "live_eligible": live_ok, "timeframe": su["timeframe"], "token": t["symbol"], "address": t["address"],
                      "pool": t["pool"], "price": ent, "size_sol": size_sol, "reason": su["why"], "stop": stop,
                      "stop_basis": sbasis, "tp_price": rec["target_price"], "liq_usd": t["liq_usd"],
                      "cost_frac_per_side": round(cf, 5), "slippage_assumed": round(slip, 6),
                      "pnl_sol": round(-size_sol * (1 - 1 / (1 + cf)), 6), "pnl_pct": round(-cf * 100, 3)}
            if priority:
                rec["priority_note"] = f"PRIORITY: scout {sv} + pulse rising; volume rule relaxed to >= {cfg['priority_vol_mult']}x avg"
            fresh_setups.append(rec); log_event(rec)
            if rec["taken"]:
                log_event(ev); events.append(ev)

    # prune dedupe keys older than 3 days
    cutoff = iso(now_utc() - timedelta(days=3))
    for k in ("seen_long", "seen_short", "seen_filtered"):
        state[k] = {kk: v for kk, v in state[k].items() if v >= cutoff}
    open_pos = [p for p in positions if p["remaining"] > 1e-9]
    state["positions"] = open_pos
    state["updated_at"] = now_s
    save_json(POS_F, state)

    closed_today, pnl_today = 0, 0.0
    if os.path.exists(LOG_F):
        ns_s = iso(night_start_utc)
        for line in open(LOG_F):
            try: ev = json.loads(line)
            except ValueError: continue
            if ev.get("ts", "") < ns_s: continue
            if ev.get("event") == "exit": closed_today += 1
            if ev.get("event") in ("partial", "exit"): pnl_today += ev.get("pnl_sol", 0)
    unreal = sum(p["size_sol"] * p["remaining"] * ((p["last_px"] or p["entry_price"]) * (1 - p["cost_frac"]) / p["entry_eff"] - 1) for p in open_pos)
    toks = uni["tokens"]
    total = len(toks)
    if total and fetch_fail >= max(3, total // 2):
        print(f"oldcoins: STALE/ERROR candles failed for {fetch_fail}/{total} tokens"); sys.exit(3)
    ncore = sum(1 for x in toks if x.get("tier") == "core")
    by = lambda typ: sum(1 for s_ in setups_all if s_["setup_type"] == typ)
    line = (f"oldcoins: universe {total} (core {ncore}, wide {total - ncore}), 1h-trend pass {trend_pass}, "
            f"setups A {by('A')} / B {by('B')} / C {by('C')} (fresh {len(fresh_setups)}, taken {sum(1 for x in fresh_setups if x['taken'])}), "
            f"would-short {len(shorts)}, open {len(open_pos)}, closed today {closed_today}, "
            f"paper pnl {pnl_today:+.4f} SOL realized ({unreal:+.4f} unrealized), runtime {time.time()-T0:.0f}s"
            f"{' (universe rebuild %.0fs)' % t_universe if rebuilt else ''}")
    if short_hist: line += f", {short_hist} skipped <{cfg['min_candles']} candles"
    if not in_window: line += ", entries off (outside 21:00-07:30)"
    if fetch_fail: line += f", {fetch_fail} fetch fails"
    if filtered: line += f", filtered {len(filtered)}"
    line += f", GT calls {GT_CALLS[0]} (throttle waits {RL_HITS[0]}, cache hits {CACHE_HITS[0]})"
    for su in fresh_setups:
        line += (f"\n  SETUP {su['setup_type']} {su['timeframe']} {su['tier']}{' PRIORITY' if su['priority'] else ''} {su['token']} "
                 f"addr {su['address']} pool {su['pool']} low {su['breakout_low']:.6g} entry {su['entry_price']:.6g} "
                 f"stop {su['stop_price']:.6g} ({su['stop_basis']}, -{su['stop_distance_pct']}%) target {su['target_price']:.6g} "
                 f"liq ${su['liquidity_usd']:,} live_eligible={su['live_eligible']} "
                 f"{'TAKEN (paper)' if su['taken'] else 'skipped: ' + str(su['skip_reason'])}")
    if args.setups_json:
        print(json.dumps(fresh_setups, indent=1))
    else:
        print(line)
    detail = {"line": line, "fresh_setups": fresh_setups, "setups_all": setups_all, "filtered": filtered, "notes": notes,
              "shorts": shorts, "events": events, "universe_source": uni.get("source"),
              "universe": [f"{x.get('tier')} {x['symbol']} ({x['address']})" for x in toks],
              "universe_rejected": uni.get("rejected"), "universe_built_at": uni["built_at"],
              "gt_calls": GT_CALLS[0], "gt_throttle_waits": RL_HITS[0], "cache_hits": CACHE_HITS[0],
              "runtime_s": round(time.time() - T0, 1)}
    save_json(os.path.join(LIVE, "oldcoins-last-run.json"), detail)


if __name__ == "__main__":
    try:
        main()
    except Stale as e:
        print(f"oldcoins: STALE/ERROR {e}"); sys.exit(2)
    except Exception as e:
        print(f"oldcoins: STALE/ERROR {type(e).__name__}: {e}"); sys.exit(4)
