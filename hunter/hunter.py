#!/usr/bin/env python3
"""Coin Hunter: PAPER ONLY. Hunts Solana coins >=1h old that are getting attention and
breaking out, opens simulated 0.08 SOL trades, manages exits. No wallets, no keys, no
real orders, no AI calls. One tick per run (cron every 5 min). Forward test only."""
import json, os, sys, time, statistics, datetime as dt, argparse
sys.path.insert(0, "/workspace/runner-radar")
from common import get_json, clean, valid_sol, f, dex_tokens   # reuse radar data layer

BASE = os.environ.get("HUNTER_DIR", os.path.dirname(os.path.abspath(__file__)))
P = lambda n: os.path.join(BASE, n)
STATE, TRADES, DECIS, SUMMARY, GAPS = P("state.json"), P("trades.jsonl"), P("decisions.jsonl"), P("summary.json"), P("gaps.log")

# ---- rules ----
AGE_MIN_H, LIQ_MIN, VOL24_MIN = 1.0, 50_000, 250_000
# SCALP v2 (user 10:26Z): more trades, quick in/out
STAKE_SOL, MAX_OPEN, FEE = 0.08, 6, 0.01          # 1% fee each way
HALF_SPREAD = 0.003                                # paid on top of pool impact, each way
PRIO_SOL = 0.0005                                  # priority fee + tip per tx (each way)
SL, TP1, TP1_FRAC, TRAIL, TIME_STOP_H = -0.08, 0.12, 0.5, 0.06, 0.75
COST_MULT = 3.0                                    # TP must clear round-trip cost >= 3x
FADE_MIN_HELD_MIN = 8                              # fade exit allowed after this
ACC5_MIN, BR5_MIN, BR1_MIN = 2.0, 0.58, 0.50       # 5m volume spike + buy pressure
MAX_H1_UP, MAX_M5_UP = 150.0, 25.0                 # skip vertical / spike entries
COOLDOWN_H = 1.0
GAP_MIN = 3.0                                      # minutes between ticks considered a gap
STALE_S = 45                                       # never act on prices older than this
MAX_BREAKOUT_CHECKS = 6                            # GeckoTerminal OHLCV calls per tick
DISCOVERY_TTL = 170                                # re-run full discovery every ~3 min; prices refresh every tick
WSOL = "So11111111111111111111111111111111111111112"
STABLE_MINTS = {"EPjFWN1bG3s5gjSn6Ftzz3vWwfoF2e8DMRp6A1Pz8YSd", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo", "USDSwr9ApdHk5bvJKMjzff41FfuX8bSxdKcR81vTwcA",
                "USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB", "HzwqbKZw8HxMN6bF2yFZNrht3c2iXXzpKcFu7uBEDKtr",
                "2u1tszSeqZ3qBWF3uNGPFc8TzMk2tdiwknnRMWGWjGWH", WSOL}
EXCLUDE_BASE = STABLE_MINTS | {"mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So", "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn",
                "bSo13r4TkiE4KumL71LsHTPpL2euBYLFx6h9HP3piy1", "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj"}
STABLE_SYM = ("USD", "EUR", "DAI", "FRAX")

def now(): return time.time()
def iso(t=None): return dt.datetime.fromtimestamp(t or now(), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def jload(p, d):
    try:
        with open(p) as fh: return json.load(fh)
    except Exception: return d
def jsave(p, o):
    tmp = p + ".tmp"
    with open(tmp, "w") as fh: json.dump(o, fh, indent=1)
    os.replace(tmp, p)
def append(p, o):
    with open(p, "a") as fh: fh.write(json.dumps(o) + "\n")
def log(*a): print(iso(), *a, flush=True)

# ---------- data ----------
def sol_usd():
    r = get_json("https://api.dexscreener.com/tokens/v1/solana/" + WSOL) or []
    ps = [p for p in r if (p.get("quoteToken") or {}).get("symbol") in ("USDC", "USDT") and (p.get("baseToken") or {}).get("address") == WSOL]
    ps.sort(key=lambda p: -f((p.get("liquidity") or {}).get("usd")))
    return f(ps[0].get("priceUsd")) if ps else 0.0

def discover():
    """Candidate mints + 'hype' tags (trending/boost are a minor input only)."""
    found, hype = set(), {}
    def add(a, tag=None):
        if valid_sol(a) and a not in EXCLUDE_BASE:
            found.add(a)
            if tag: hype.setdefault(a, set()).add(tag)
    for path, tag in (("token-boosts/latest/v1", "ds_boost"), ("token-boosts/top/v1", "ds_boost_top")):
        for t in get_json("https://api.dexscreener.com/" + path) or []:
            if isinstance(t, dict) and t.get("chainId") == "solana": add(t.get("tokenAddress"), tag)
    for q in ("SOL", "pumpswap", "raydium", "meteora"):
        for p in (get_json("https://api.dexscreener.com/latest/dex/search?q=" + q) or {}).get("pairs") or []:
            if p.get("chainId") == "solana": add((p.get("baseToken") or {}).get("address"))
    gk = {}
    for url, tag in (("trending_pools?duration=5m", "gt_trend_5m"), ("trending_pools?duration=1h", "gt_trend_1h"),
                     ("pools?sort=h24_volume_usd_desc&page=1", None), ("pools?sort=h24_volume_usd_desc&page=2", None),
                     ("pools?sort=h24_tx_count_desc&page=1", None)):
        r = get_json("https://api.geckoterminal.com/api/v2/networks/solana/" + url)
        for p in (r or {}).get("data") or []:
            base = (((p.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", "")
            a = base.split("solana_", 1)[-1]
            add(a, tag)
            at = p.get("attributes") or {}
            if at.get("address"): gk[at["address"]] = at
    return found, hype, gk

def best_pairs(mints):
    best = {}
    for p in dex_tokens("solana", list(mints)):
        if p.get("chainId") != "solana": continue
        a = (p.get("baseToken") or {}).get("address")
        if a not in mints: continue
        if (p.get("quoteToken") or {}).get("address") not in (WSOL, "EPjFWN1bG3s5gjSn6Ftzz3vWwfoF2e8DMRp6A1Pz8YSd", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"):
            continue
        if f((p.get("liquidity") or {}).get("usd")) > f(((best.get(a) or {}).get("liquidity") or {}).get("usd")): best[a] = p
    return best

def authorities(mint, cache):
    """mint/freeze authority via rugcheck, RPC fallback. Revoked is permanent, so cache 'ok' forever."""
    c = cache.get(mint)
    if c and (c["ok"] or now() - c["t"] < 6 * 3600): return c
    out = {"t": now(), "ok": False, "why": "unknown"}
    rep = get_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", retries=2)
    if isinstance(rep, dict) and rep.get("mint"):
        ma, fa = rep.get("mintAuthority"), rep.get("freezeAuthority")
        out.update(ok=not ma and not fa and not rep.get("rugged"),
                   why="ok" if not ma and not fa else ("mint auth" if ma else "freeze auth"))
        if rep.get("rugged"): out["why"] = "rugged"
    else:
        r = get_json("https://api.mainnet-beta.solana.com", {"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                     "params": [mint, {"encoding": "jsonParsed"}]}, retries=2)
        try:
            info = r["result"]["value"]["data"]["parsed"]["info"]
            ma, fa = info.get("mintAuthority"), info.get("freezeAuthority")
            out.update(ok=not ma and not fa, why="ok" if not ma and not fa else ("mint auth" if ma else "freeze auth"))
        except Exception:
            out["why"] = "authority check failed"
    cache[mint] = out
    return out

def candles_5m(pool):
    r = get_json(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=5&limit=24&currency=usd", retries=2)
    try: return sorted(r["data"]["attributes"]["ohlcv_list"])   # [ts, o, h, l, c, v]
    except Exception: return None

# ---------- costs ----------
def impact(usd, liq):  # constant-product, liq = both sides in USD
    return usd / max(liq / 2, 1.0)
def round_trip_cost(usd, liq, solp):
    """fraction of stake lost to fees+spread+impact+priority on a full in/out."""
    return 2 * FEE + 2 * (HALF_SPREAD + impact(usd, liq)) + 2 * PRIO_SOL * solp / usd
def buy_fill(px, usd, liq): return px * (1 + HALF_SPREAD + impact(usd, liq))
def sell_fill(px, usd, liq): return px * max(0.0, 1 - HALF_SPREAD - impact(usd, liq))

# ---------- signal ----------
def evaluate(mint, p, gkat, hype, hist):
    pc, vol, tx = p.get("priceChange") or {}, p.get("volume") or {}, p.get("txns") or {}
    liq, age_h = f((p.get("liquidity") or {}).get("usd")), (now() * 1000 - f(p.get("pairCreatedAt"), now() * 1000)) / 3.6e6
    sym = clean((p.get("baseToken") or {}).get("symbol"), 16)
    m5, h1 = f(pc.get("m5")), f(pc.get("h1"))
    v5, vh1, vh6, v24 = f(vol.get("m5")), f(vol.get("h1")), f(vol.get("h6")), f(vol.get("h24"))
    b5, s5 = f((tx.get("m5") or {}).get("buys")), f((tx.get("m5") or {}).get("sells"))
    b1, s1 = f((tx.get("h1") or {}).get("buys")), f((tx.get("h1") or {}).get("sells"))
    b6, s6 = f((tx.get("h6") or {}).get("buys")), f((tx.get("h6") or {}).get("sells"))
    m = {"sym": sym, "liq": round(liq), "vol24": round(v24), "age_h": round(age_h, 1), "m5": m5, "h1": h1}
    # universe
    rej = []
    if age_h < AGE_MIN_H: rej.append("age<1h")
    if liq < LIQ_MIN: rej.append("liq<50k")
    if v24 < VOL24_MIN: rej.append("vol24<250k")
    if any(sym.upper().startswith(s) or sym.upper().endswith(s) for s in STABLE_SYM) or \
       (0.97 < f(p.get("priceUsd")) < 1.03 and abs(f(pc.get("h24"))) < 1.5): rej.append("stablecoin")
    if rej: return "universe_fail", m, rej
    # attention
    acc5 = v5 / (vh1 / 12) if vh1 else 0            # last 5m vs avg 5m of last hour
    acc1 = vh1 / (vh6 / 6) if vh6 else 0            # last 1h vs avg hour of last 6h
    br5 = b5 / (b5 + s5) if b5 + s5 else 0
    br1 = b1 / (b1 + s1) if b1 + s1 else 0
    tx_up = (b1 + s1) / ((b6 + s6) / 6) if b6 + s6 else 0   # txns last hour vs 6h hourly avg
    tr = (gkat or {}).get("transactions") or {}
    by5, by1 = f((tr.get("m5") or {}).get("buyers")), f((tr.get("h1") or {}).get("buyers"))
    buyer_up = by5 / (by1 / 12) if by1 else None
    # own history: tx count in the last hour vs what we saw ~30-90 min ago
    past = [h for h in hist if 1800 <= now() - h["t"] <= 5400]
    hist_tx = (b1 + s1) / past[0]["tx1"] if past and past[0]["tx1"] else None
    m.update(acc5=round(acc5, 2), acc1=round(acc1, 2), br5=round(br5, 2), br1=round(br1, 2), tx_up=round(tx_up, 2),
             buyer_up=round(buyer_up, 2) if buyer_up else None, hist_tx=round(hist_tx, 2) if hist_tx else None,
             hype=sorted(hype))
    att = []
    if acc5 < ACC5_MIN: att.append(f"no 5m volume spike ({acc5:.1f}x < {ACC5_MIN}x)")
    if br5 < BR5_MIN or br1 < BR1_MIN: att.append(f"weak buy pressure (5m {br5:.0%}, 1h {br1:.0%})")
    if att: return "attention_fail", m, att
    # pre-breakout momentum gates (cheap, before the OHLCV call)
    mom = []
    if h1 <= 0 or m5 <= 0: mom.append(f"no momentum (1h {h1:+.0f}%, 5m {m5:+.0f}%)")
    if h1 > MAX_H1_UP: mom.append(f"already vertical 1h +{h1:.0f}%")
    if m5 > MAX_M5_UP: mom.append(f"5m spike +{m5:.0f}% (chase)")
    if mom: return "momentum_fail", m, mom
    m["score"] = round(min(acc5, 5) + 5 * (br5 - 0.5) + min(tx_up, 3) + min(buyer_up or 0, 3) + 0.5 * len(hype), 2)
    return "breakout_check", m, []

def breakout(pool, px):
    c = candles_5m(pool)
    if not c or len(c) < 14: return False, "no candle data", {}
    last_ts = c[-1][0]
    if now() - last_ts > 900: return False, "candles stale", {}
    prior = [x for x in c if last_ts - 3600 <= x[0] < last_ts - 300]   # 1h window, excl. current+last 5m bar
    if not prior: return False, "no candle data", {}
    hi1 = max(x[2] for x in prior)
    info = {"hi1": hi1, "px": px, "over_hi1_pct": round(100 * (px / hi1 - 1), 2)}
    if px <= hi1 * 1.003: return False, f"below 1h high ({info['over_hi1_pct']:+.1f}%)", info
    if px <= c[-2][4]: return False, "no 5m momentum", info
    return True, f"broke 1h high by {info['over_hi1_pct']:.1f}%", info

# ---------- trades ----------
def trade_value(t, px):
    """Mark-to-market SOL of a position at mid px, net of exit costs."""
    rem = t["tokens_left"] * sell_fill(px, t["tokens_left"] * px, t["liq"]) * (1 - FEE) / t["sol_usd_entry"] - PRIO_SOL
    return t["realised_sol"] + rem

def close_part(t, px, frac, reason, events):
    tok = t["tokens_total"] * frac if frac < 1 else t["tokens_left"]
    fill = sell_fill(px, tok * px, t["liq"])
    sol = tok * fill * (1 - FEE) / t["sol_usd_entry"] - PRIO_SOL   # SOL at entry SOL price: isolates coin P&L
    t["costs_sol"] = t.get("costs_sol", 0) + PRIO_SOL + tok * px * (FEE + HALF_SPREAD + impact(tok * px, t["liq"])) / t["sol_usd_entry"]
    t["tokens_left"] -= tok; t["realised_sol"] += sol
    ev = {"t": iso(), "id": t["id"], "sym": t["sym"], "event": "sell", "frac": round(frac, 2), "reason": reason,
          "mid": px, "fill": fill, "sol": round(sol, 5), "move_pct": round(100 * (px / t["entry_mid"] - 1), 2)}
    events.append(ev); append(TRADES, ev)

def manage(st, prices, tick_gap, events):
    for t in [t for t in st["open"]]:
        q = prices.get(t["mint"])
        if not q or now() - q["fetched"] > STALE_S:
            log(f"  {t['sym']}: no fresh price, hold (will retry next tick)"); continue
        px, t["liq"] = q["px"], max(q["liq"], 1.0)
        pr = q.get("pair") or {}; tx5 = (pr.get("txns") or {}).get("m5") or {}
        b5, s5 = f(tx5.get("buys")), f(tx5.get("sells")); br5 = b5 / (b5 + s5) if b5 + s5 else 0.5
        m5 = f((pr.get("priceChange") or {}).get("m5"))
        t["peak"] = max(t["peak"], px)
        mv = px / t["entry_mid"] - 1
        tag = " [after gap]" if tick_gap else ""
        age_h = (now() - t["opened"]) / 3600
        if not t["tp1_done"] and mv <= SL:
            close_part(t, px, 1.0, f"stop-loss {mv:+.1%}{tag}", events)
        elif not t["tp1_done"] and mv >= TP1:
            close_part(t, px, TP1_FRAC, f"TP1 +12% (at {mv:+.1%}){tag}", events); t["tp1_done"] = True
        if t["tokens_left"] > 1e-12 and t["tp1_done"] and px <= t["peak"] * (1 - TRAIL):
            close_part(t, px, 1.0, f"trail 6% off peak {t['peak']/t['entry_mid']-1:+.1%}{tag}", events)
        held_min = age_h * 60
        if t["tokens_left"] > 1e-12 and held_min >= FADE_MIN_HELD_MIN and br5 < 0.45 and m5 < 0:
            close_part(t, px, 1.0, f"momentum faded (5m buys {br5:.0%}, 5m {m5:+.1f}%, pos {mv:+.1%}){tag}", events)
        if t["tokens_left"] > 1e-12 and age_h >= TIME_STOP_H:
            close_part(t, px, 1.0, f"time stop {held_min:.0f}min ({mv:+.1%}){tag}", events)
        if t["tokens_left"] <= 1e-12:
            t["closed"] = iso(); t["closed_ts"] = now(); t["pnl_sol"] = round(t["realised_sol"] - STAKE_SOL, 5)
            t["pnl_pct"] = round(100 * t["pnl_sol"] / STAKE_SOL, 2)
            st["open"].remove(t); st["closed"].append(t); st["cooldown"][t["mint"]] = now()
            append(TRADES, {"t": iso(), "id": t["id"], "sym": t["sym"], "event": "closed", "pnl_sol": t["pnl_sol"],
                            "pnl_pct": t["pnl_pct"], "held_h": round(age_h, 2), "entry_reason": t["reason"]})
            log(f"  CLOSED {t['sym']} {t['pnl_pct']:+.1f}% ({t['pnl_sol']:+.4f} SOL)")
        else:
            t["mtm_sol"] = round(trade_value(t, px), 5)

def open_trade(st, mint, p, m, why, solp, fetched, events):
    if now() - fetched > STALE_S: log(f"  skip {m['sym']}: price {now()-fetched:.0f}s old"); return False
    px, liq = f(p.get("priceUsd")), f((p.get("liquidity") or {}).get("usd"))
    usd = STAKE_SOL * solp
    rt = round_trip_cost(usd, liq, solp)
    if TP1 < COST_MULT * rt:
        log(f"  skip {m['sym']}: round-trip cost {rt:.1%} too high for +{TP1:.0%} TP")
        append(DECIS, {"t": iso(), "mint": mint, "stage": "cost_fail", "why": [f"round-trip {rt:.2%} > TP/{COST_MULT:g}"], "m": m})
        return False
    fill = buy_fill(px, usd, liq)
    tokens = (usd - PRIO_SOL * solp) * (1 - FEE) / fill
    st["seq"] += 1
    t = {"id": st["seq"], "mint": mint, "sym": m["sym"], "pair": p.get("pairAddress"), "opened": now(), "opened_iso": iso(),
         "entry_mid": px, "entry_fill": fill, "slip_pct": round(100 * (fill / px - 1), 2), "liq": liq, "round_trip_cost_pct": round(100 * rt, 2),
         "costs_sol": PRIO_SOL + usd * (FEE + HALF_SPREAD + impact(usd, liq)) / solp,
         "sol_usd_entry": solp, "tokens_total": tokens, "tokens_left": tokens, "realised_sol": 0.0,
         "peak": px, "tp1_done": False, "reason": why, "metrics": m,
         "url": "https://dexscreener.com/solana/" + (p.get("pairAddress") or mint)}
    st["open"].append(t)
    ev = {"t": iso(), "id": t["id"], "sym": t["sym"], "event": "buy", "mint": mint, "mid": px, "fill": fill,
          "slip_pct": t["slip_pct"], "round_trip_cost_pct": t["round_trip_cost_pct"], "stake_sol": STAKE_SOL, "reason": why, "metrics": m, "url": t["url"]}
    events.append(ev); append(TRADES, ev)
    log(f"  OPEN #{t['id']} {t['sym']} @ {px:.6g} (fill {fill:.6g}, slip {t['slip_pct']}%) :: {why}")
    return True

def tpd(c):
    d = {}
    for t in c: d[t["closed"][:10]] = d.get(t["closed"][:10], 0) + 1
    return d
def pnl_day(c):
    d = {}
    for t in c: d[t["closed"][:10]] = round(d.get(t["closed"][:10], 0) + t["pnl_sol"], 5)
    return d

def summarize(st):
    c = st["closed"]; pn = [t["pnl_pct"] for t in c]
    s = {"updated": iso(), "mode": "PAPER", "stake_sol": STAKE_SOL, "trades_closed": len(c), "open": len(st["open"]),
         "wins": sum(1 for x in pn if x > 0), "win_rate": round(sum(1 for x in pn if x > 0) / len(pn), 3) if pn else None,
         "median_pct": round(statistics.median(pn), 2) if pn else None,
         "total_pnl_sol": round(sum(t["pnl_sol"] for t in c), 5),
         "open_mtm_pnl_sol": round(sum(t.get("mtm_sol", STAKE_SOL) - STAKE_SOL for t in st["open"]), 5),
         "total_costs_sol_closed": round(sum(t.get("costs_sol", 0) for t in c), 5),
         "trades_per_day": tpd(c), "pnl_after_costs_by_day": pnl_day(c),
         "avg_hold_min": round(statistics.mean((t["closed_ts"] - t["opened"]) / 60 for t in c), 1) if c else None,
         "rules": {"sl": SL, "tp1": TP1, "tp1_frac": TP1_FRAC, "trail": TRAIL, "time_stop_min": TIME_STOP_H * 60,
                   "max_open": MAX_OPEN, "fee_each_way": FEE, "prio_sol_each_way": PRIO_SOL, "cost_mult": COST_MULT},
         "best": max(c, key=lambda t: t["pnl_pct"])["sym"] if c else None,
         "open_positions": [{"id": t["id"], "sym": t["sym"], "opened": t["opened_iso"], "mtm_sol": t.get("mtm_sol"),
                             "tp1_done": t["tp1_done"], "url": t["url"]} for t in st["open"]],
         "ticks": st["ticks"], "gaps": st["gaps"], "last_scan": st.get("last_scan_stats")}
    jsave(SUMMARY, s)
    return s

# ---------- tick ----------
def tick(args):
    st = jload(STATE, {"disc": {}, "seq": 0, "open": [], "closed": [], "cooldown": {}, "auth": {}, "hist": {}, "ticks": 0, "gaps": 0, "last": None})
    t0 = now()
    gap = st["last"] and (t0 - st["last"]) / 60 > GAP_MIN
    if gap:
        mins = (t0 - st["last"]) / 60; st["gaps"] += 1
        with open(GAPS, "a") as fh: fh.write(f"{iso()} gap {mins:.1f} min since {iso(st['last'])} (open trades: {len(st['open'])})\n")
        log(f"GAP {mins:.1f} min since last tick; managing open trades at live prices only")
    st["ticks"] += 1
    events = []
    solp = sol_usd()
    if not solp: log("no SOL price; abort tick"); st["last"] = t0; jsave(STATE, st); return
    # 1) refresh + manage open trades first (fresh prices)
    if st["open"]:
        fetched = now(); prices = {}
        for p in dex_tokens("solana", [t["mint"] for t in st["open"]]):
            a = (p.get("baseToken") or {}).get("address")
            for t in st["open"]:
                if a == t["mint"] and p.get("pairAddress") == t["pair"]:
                    prices[a] = {"px": f(p.get("priceUsd")), "liq": f((p.get("liquidity") or {}).get("usd")), "fetched": fetched, "pair": p}
        if args.fake_move:   # selftest only
            for a in prices: prices[a]["px"] *= args.fake_move
        manage(st, prices, gap, events)
    # 2) scan
    dc = st.get("disc") or {}
    if args.fresh or now() - dc.get("t", 0) > DISCOVERY_TTL:
        mints, hype, gk = discover()
        st["disc"] = {"t": now(), "mints": sorted(mints), "hype": {k: sorted(v) for k, v in hype.items()}}
        gk_cache = gk
    else:
        mints, hype, gk = set(dc["mints"]), {k: set(v) for k, v in dc["hype"].items()}, {}
        log(f"discovery cached ({now()-dc['t']:.0f}s old), refreshing prices for {len(mints)} mints")
    fetched = now()
    pairs = best_pairs(mints)
    counts = {"discovered": len(mints), "priced": len(pairs)}
    stage = {}; cands = []
    for mint, p in pairs.items():
        hist = st["hist"].setdefault(mint, [])
        tx = p.get("txns") or {}
        tx1 = f((tx.get("h1") or {}).get("buys")) + f((tx.get("h1") or {}).get("sells"))
        res, m, why = evaluate(mint, p, gk.get(p.get("pairAddress")), hype.get(mint, set()), hist)
        hist.append({"t": t0, "tx1": tx1, "px": f(p.get("priceUsd"))})
        st["hist"][mint] = [h for h in hist if t0 - h["t"] < 3 * 3600][-40:]
        stage[res] = stage.get(res, 0) + 1
        if res != "universe_fail":
            append(DECIS, {"t": iso(), "mint": mint, "stage": res, "why": why, "m": m})
        if res == "breakout_check": cands.append((m["score"], mint, p, m))
        if args.force_open and res != "universe_fail" and len(st["open"]) < 2 and mint not in {t["mint"] for t in st["open"]}:
            open_trade(st, mint, p, m, "SELFTEST forced entry", solp, fetched, events)   # selftest only
    st["hist"] = {k: v for k, v in st["hist"].items() if v and t0 - v[-1]["t"] < 3 * 3600}
    counts["universe_pass"] = len(pairs) - stage.get("universe_fail", 0)
    counts.update(stage)
    # 3) authority + breakout on the best candidates
    cands.sort(reverse=True); entered = 0; checks = 0; sigs = []
    held = {t["mint"] for t in st["open"]}
    for sc, mint, p, m in cands:
        if checks >= MAX_BREAKOUT_CHECKS: break
        if mint in held or now() - st["cooldown"].get(mint, 0) < COOLDOWN_H * 3600: continue
        a = authorities(mint, st["auth"])
        if not a["ok"]:
            append(DECIS, {"t": iso(), "mint": mint, "stage": "safety_fail", "why": [a["why"]], "m": m}); continue
        checks += 1
        ok, why, info = breakout(p.get("pairAddress"), f(p.get("priceUsd")))
        m.update(info)
        append(DECIS, {"t": iso(), "mint": mint, "stage": "SIGNAL" if ok else "breakout_fail", "why": [why], "m": m})
        if not ok: continue
        reason = (f"{why}; vol 5m {m['acc5']}x / 1h {m['acc1']}x, buys 5m {m['br5']:.0%}, tx {m['tx_up']}x"
                  + (f", buyers {m['buyer_up']}x" if m.get("buyer_up") else "") + (f", hype {','.join(m['hype'])}" if m["hype"] else ""))
        sigs.append(f"{m['sym']}: {reason}")
        if len(st["open"]) >= MAX_OPEN:
            log(f"  signal {m['sym']} skipped: max {MAX_OPEN} open"); continue
        if open_trade(st, mint, p, m, reason, solp, fetched, events): entered += 1; held.add(mint)
    counts.update(auth_breakout_checks=checks, signals=len(sigs), entered=entered)
    st["last_scan_stats"] = dict(counts, t=iso(), secs=round(now() - t0, 1), gap=bool(gap))
    st["last"] = t0
    jsave(STATE, st); s = summarize(st)
    log(f"tick: {json.dumps(counts)} | open {len(st['open'])} closed {s['trades_closed']} pnl {s['total_pnl_sol']:+.4f} SOL | {now()-t0:.0f}s")
    for x in sigs: log("  SIGNAL", x)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-open", action="store_true", help="SELFTEST ONLY")
    ap.add_argument("--fresh", action="store_true", help="force full discovery")
    ap.add_argument("--fake-move", type=float, default=0, help="SELFTEST ONLY: multiply open-trade prices")
    args = ap.parse_args()
    if (args.fake_move or args.force_open) and "HUNTER_DIR" not in os.environ: sys.exit("fake-move only allowed with HUNTER_DIR (selftest)")
    tick(args)
