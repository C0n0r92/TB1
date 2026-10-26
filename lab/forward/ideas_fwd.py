#!/usr/bin/env python3
"""PAPER ONLY combined forward tracker for Zero's 5 ideas (Lab, 2026-10-24). No keys, no wallets, no trades, no LLM/bot usage.
One shared, throttled fetch loop feeds all five strategies. Own throttle file forward/.ideas_calls.log: >= SPACING s between
ANY two calls of this poller (all hosts) -> <= 7.5 req/min total; 429 -> backoff 30/60/90 s and a global pause.
Hosts: DexScreener (pairs batch <=30, tokens), GeckoTerminal (pools lists, token info, ohlcv), pump.fun frontend-api-v3 (keyless),
Meteora DLMM datapi. NO RPC calls (consensus reads selfcopy's own leader_swap log, zero API cost). NO Helius, NO X.

Strategies -> forward/<strategy>_fwd.jsonl
 consensus : >=3 distinct ACTIVE selfcopy roster leaders buy the same mint within 30 min (from selfcopy/paper-trades.jsonl, read only)
 graduation: pump.fun coin with complete=true, GT launchpad completed_at <= 10 min ago, PumpSwap pool liq >= $20k,
             holders >= 50 and dev holding <= 10% (GT token info; one call per candidate)
 dipbuy    : watched pool with liq >= $200k (at the reference point), price drop 30-50% from the max of our own samples
             in the last 10 min; flags: liq intact (liq_now >= 0.85 x liq_ref x sqrt(p_now/p_ref), i.e. no LP pull beyond what
             the price move explains), pool still listed, txns not sell-only. Creator selling: NOT checked (no cheap history).
 revival   : pool age >= 24h, liq >= $20k, m5 volume/liq >= 5x baseline, baseline = ((h6 vol - h1 vol)/60 per 5 min)/liq,
             m5 volume >= $3k, price m5 change > 0 (buying, not dumping)
 dlmm      : 5 high-volume memecoin/SOL Meteora DLMM pairs (launchpad-origin, tvl >= $100k); every 15 min an estimate of a
             spot-uniform LP over +-10% of the start price, rolling 1h and 6h: fee income (pool-average LP fee/TVL; conservative)
             vs impermanent loss (Uniswap-v3-style range math on GT 15-min closes in token/SOL). Estimate, not a trade.
Paper trades (1,2,3,5): entry 15 s after the signal (first price poll after due), 0.04 SOL. Primary exit: sell all +15% (filled
AT the level), -10% stop (observed price, gaps through), 15 min. Shadow: +10% / -15% / 30 min. Max 3 open per strategy.
Costs per side: 2% fee + 0.5% slippage + 2 x stake/liq; plus priority 0.0001 + base 0.000005 SOL per side (= ~0.5% round trip).
Stops at 20:00Z (open positions closed at last price, exit_reason=end_of_run).
Usage: nohup python3 ideas_fwd.py &   |   python3 ideas_fwd.py --summary
"""
import json, os, sys, time, math, fcntl, urllib.request, urllib.error, datetime as dt, collections

HERE = os.path.dirname(os.path.abspath(__file__))
PID = os.path.join(HERE, "ideas.pid"); STATE = os.path.join(HERE, "ideas_state.json"); THR = os.path.join(HERE, ".ideas_calls.log")
SC_FEED = "/workspace/selfcopy/paper-trades.jsonl"; SC_ROSTER = "/workspace/selfcopy/roster.json"
STRATS = ["consensus", "graduation", "dipbuy", "dlmm", "revival"]
END_TS = dt.datetime(2026, 10, 24, 20, 0, tzinfo=dt.timezone.utc).timestamp()
SPACING = 8.0
STAKE_SOL, DELAY_S, MAX_OPEN = 0.04, 15, 3
FEE, BASE_SLIP, IMPACT, PRIO_SOL = 0.02, 0.005, 2.0, 0.0001 + 0.000005
TRACKS = {"P": (0.15, 0.10, 15), "S": (0.10, 0.15, 30)}      # name: (tp, sl, max_hold_min); P = primary (reported)
UA = {"User-Agent": "Mozilla/5.0 lab-paper-ideas/1.0", "Accept": "application/json"}
GT = "https://api.geckoterminal.com/api/v2/networks/solana"
DS = "https://api.dexscreener.com/latest/dex"
PF = "https://frontend-api-v3.pump.fun/coins?offset=0&limit=50&order=DESC&includeNsfw=true&complete=true&sort="
MET = "https://dlmm.datapi.meteora.ag"
SOL_MINT = "So11111111111111111111111111111111111111112"
NOT_MEME = {"SOL", "WSOL", "USDC", "USDT", "USD1", "PYUSD", "JUP", "JTO", "PYTH", "RAY", "ORCA", "MSOL", "JITOSOL", "BSOL", "JUPSOL",
            "INF", "CBBTC", "WBTC", "ETH", "WETH", "HYPE", "ZEC", "XMR", "MET", "PUMP", "USDS", "EURC", "BNSOL", "DSOL", "HSOL"}
UNIVERSE_SRC = [GT + "/pools?sort=h24_volume_usd_desc&page=1", GT + "/trending_pools?duration=5m&page=1", GT + "/pools?sort=h24_volume_usd_desc&page=2",
                GT + "/trending_pools?duration=1h&page=1", GT + "/dexes/pumpswap/pools?sort=h24_volume_usd_desc&page=1", GT + "/trending_pools?duration=6h&page=1",
                GT + "/trending_pools?duration=5m&page=1", GT + "/pools?sort=h24_volume_usd_desc&page=3", GT + "/trending_pools?duration=5m&page=2",
                GT + "/trending_pools?duration=5m&page=1", GT + "/dexes/raydium/pools?sort=h24_volume_usd_desc&page=1"]
HB_EVERY = 300
CAN = {
 "consensus": "LIVE via selfcopy's own leader_swap feed (19 active roster wallets, ~10 s detect lag), zero API calls. Kolscan top wallets NOT included "
              "(no keyless API). Feed had 160 leader buys over 16 h and 0 three-leader events, so expect few or no signals.",
 "graduation": "LIVE via pump.fun frontend-api-v3 complete=true lists (by creation and by last trade) + DexScreener liq + GT token info "
               "(completed_at, holders, dev %). Misses Raydium-LaunchLab/other launchpads; coins created long before graduating may be found late.",
 "dipbuy": "LIVE on a watchlist (<=40 pools, liq>=$200k, memecoins) sampled every ~2-2.5 min via DexScreener batch; drop measured from our own samples "
           "(10-min max), so a crash is seen at ~2-2.5 min resolution. Checked: liq intact vs 10 min ago (price-adjusted), pool listed, "
           "not sell-only. NOT checked: creator selling, LP lock/burn, mint/freeze authority.",
 "revival": "LIVE on GT trending/volume lists + watchlist: age>=24h, m5 vol/liq >= 5x the prior-5h baseline from DexScreener h6/h1 volume. "
            "Coins that are totally dead won't be on our lists until they trend.",
 "dlmm": "ESTIMATE only: Meteora datapi fees/TVL (LP share, protocol fee removed) + GT 15-min token/SOL closes; pool-average fee yield "
         "understates a tight position near the active bin, and range math approximates DLMM spot bins.",
}

def now(): return time.time()
def iso(t=None): return dt.datetime.fromtimestamp(now() if t is None else t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def pts(s):
    s = s.replace("Z", "")[:19]
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
def fnum(x, d=0.0):
    try: return float(x)
    except Exception: return d
def plog(*a):
    print(iso(), *a, flush=True)

FIELDS = ["ts_utc", "strategy", "event", "token_mint", "pool", "symbol", "price_usd", "liq_usd", "reason", "stake_sol", "entry_price",
          "exit_price", "gross_pct", "net_pct", "hold_s", "exit_reason"]
def emit(strategy, event, **kw):
    row = {k: None for k in FIELDS}; row.update(ts_utc=iso(), strategy=strategy, event=event); row.update(kw)
    with open(os.path.join(HERE, f"{strategy}_fwd.jsonl"), "a") as fh: fh.write(json.dumps(row) + "\n")
    return row

CALLS = collections.Counter(); PAUSE = [0.0]
def get(url, tries=3, host=None):
    host = host or url.split("/")[2]
    for i in range(tries):
        with open(THR, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX); fh.seek(0)
            try: last = float((fh.read().split() or ["0"])[-1])
            except Exception: last = 0.0
            w = max(SPACING - (now() - last), PAUSE[0] - now())
            if w > 0: time.sleep(w)
            fh.seek(0); fh.truncate(); fh.write(f"{now():.1f}\n"); fh.flush()
        CALLS[host] += 1; CALLS["_t"] += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            CALLS[f"http{e.code}"] += 1
            if e.code == 429:
                PAUSE[0] = now() + 30 * (i + 1); plog("429", host, "pause", 30 * (i + 1)); continue
            if e.code == 404: return None
            time.sleep(2)
        except Exception as e:
            CALLS["err"] += 1; time.sleep(2)
    return None

def cost_side(liq, stake_usd): return FEE + BASE_SLIP + IMPACT * stake_usd / max(liq or 0, 1000.0)
def nets(entry, eliq, exitp, xliq, sol_usd):
    su = STAKE_SOL * sol_usd; g = exitp / entry - 1
    nb = exitp * (1 - cost_side(xliq, su)) / (entry * (1 + cost_side(eliq, su))) - 1
    return round(100 * g, 2), round(100 * (nb - 2 * PRIO_SOL / STAKE_SOL), 2)

# ---------------- state
def load_state():
    try: return json.load(open(STATE))
    except Exception:
        return {"started": now(), "sol_usd": 190.0, "open": [], "pending": [], "cool": {}, "watch": {}, "hist": {}, "grad_seen": {},
                "grad_q": [], "grad_info_q": [], "grad_pf_init": False, "sc_off": 0, "sc_buys": [], "cons_q": [], "dlmm": {}, "dlmm_pairs": [],
                "uni_i": 0, "pf_i": 0, "nsig": {s: 0 for s in STRATS}, "last_hb": {}, "t": {}, "why": {}}
def save_state(S):
    json.dump(S, open(STATE + ".tmp", "w")); os.replace(STATE + ".tmp", STATE)
def due(S, k, period):
    if now() - S["t"].get(k, 0) >= period: S["t"][k] = now(); return True
    return False

def n_open(S, strat): return sum(1 for p in S["open"] if p["strategy"] == strat) + sum(1 for p in S["pending"] if p["strategy"] == strat)

def signal(S, strat, mint, pool, sym, px, liq, reason, **extra):
    key = f"{strat}:{pool}"
    if now() < S["cool"].get(key, 0): return None                 # same pool re-firing within 60 min: silent (not a new signal)
    S["nsig"][strat] = S["nsig"].get(strat, 0) + 1
    S["cool"][key] = now() + 3600
    if n_open(S, strat) >= MAX_OPEN:
        return emit(strat, "signal", token_mint=mint, pool=pool, symbol=sym, price_usd=px, liq_usd=liq, reason=reason + " | SKIP: max 3 open", **extra)
    S["pending"].append({"strategy": strat, "mint": mint, "pool": pool, "sym": sym, "t_sig": now(), "due": now() + DELAY_S, "liq_sig": liq})
    plog("SIGNAL", strat, sym, pool, reason)
    return emit(strat, "signal", token_mint=mint, pool=pool, symbol=sym, price_usd=px, liq_usd=liq, reason=reason, **extra)

# ---------------- DexScreener batch
def ds_pairs(pools):
    out = {}
    pools = [p for p in dict.fromkeys(pools) if p]
    for i in range(0, len(pools), 30):
        d = get(DS + "/pairs/solana/" + ",".join(pools[i:i + 30]))
        for p in (d or {}).get("pairs") or []:
            out[p["pairAddress"]] = p
    return out
def ds_row(p):
    v = p.get("volume") or {}; tx = p.get("txns") or {}
    return {"px": fnum(p.get("priceUsd")), "liq": fnum((p.get("liquidity") or {}).get("usd")), "m5v": fnum(v.get("m5")), "h1v": fnum(v.get("h1")),
            "h6v": fnum(v.get("h6")), "m5c": fnum((p.get("priceChange") or {}).get("m5")), "created": fnum(p.get("pairCreatedAt")) / 1000,
            "b5": (tx.get("m5") or {}).get("buys", 0) or 0, "s5": (tx.get("m5") or {}).get("sells", 0) or 0,
            "sym": (p.get("baseToken") or {}).get("symbol"), "mint": (p.get("baseToken") or {}).get("address"),
            "q": (p.get("quoteToken") or {}).get("symbol"), "pn": fnum(p.get("priceNative"))}
def upd_sol(S, r):
    if r["q"] == "SOL" and r["pn"] > 0 and r["px"] > 0:
        v = r["px"] / r["pn"]
        if 30 < v < 2000: S["sol_usd"] = v

# ---------------- positions
def monitor(S):
    T = now()
    pools = [p["pool"] for p in S["open"]] + [p["pool"] for p in S["pending"] if T >= p["due"]]
    if not pools: return False
    px = ds_pairs(pools); T = now()
    for pos in [q for q in S["pending"] if T >= q["due"]]:
        p = px.get(pos["pool"]); r = ds_row(p) if p else None
        if not r or r["px"] <= 0:
            if T - pos["due"] > 120: S["pending"].remove(pos); emit(pos["strategy"], "heartbeat", token_mint=pos["mint"], pool=pos["pool"], symbol=pos["sym"], reason="entry_fail: no price 120 s after due")
            continue
        upd_sol(S, r); S["pending"].remove(pos)
        o = {**pos, "t_entry": T, "entry": r["px"], "eliq": r["liq"] or pos["liq_sig"], "last": r["px"], "last_seen": T, "lliq": r["liq"], "tr": {"P": None, "S": None}, "mx": 0.0, "mn": 0.0}
        S["open"].append(o)
        emit(pos["strategy"], "entry", token_mint=pos["mint"], pool=pos["pool"], symbol=pos["sym"], price_usd=r["px"], liq_usd=round(o["eliq"]), stake_sol=STAKE_SOL,
             entry_price=r["px"], reason=f"delay_s={T - pos['t_sig']:.0f} entry_cost_side={cost_side(o['eliq'], STAKE_SOL * S['sol_usd']):.4f} sol_usd={S['sol_usd']:.2f}")
        plog("ENTRY", pos["strategy"], pos["sym"], r["px"])
    for o in list(S["open"]):
        p = px.get(o["pool"])
        if p:
            r = ds_row(p); upd_sol(S, r)
            if r["px"] > 0: o["last"], o["last_seen"], o["lliq"] = r["px"], T, r["liq"]
        close_check(S, o, T, live=bool(p))
    return True

def close_check(S, o, T, live=True, force=None):
    ret = o["last"] / o["entry"] - 1; o["mx"] = max(o["mx"], ret); o["mn"] = min(o["mn"], ret)
    age = (T - o["t_entry"]) / 60
    for k, (tp, sl, h) in TRACKS.items():
        if o["tr"][k]: continue
        why, xp, xl = None, o["last"], o["lliq"] or 0
        if force: why = force
        elif not live and T - o["last_seen"] > 300: why, xp, xl = "no_data_rug", o["last"] * 0.1, 1000
        elif live and (o["lliq"] or 0) < 2000: why = "rug_liq"
        elif ret <= -sl: why = "stop"
        elif ret >= tp: why, xp = "tp", o["entry"] * (1 + tp)
        elif age >= h: why = "time"
        if why:
            g, n = nets(o["entry"], o["eliq"], xp, max(xl, 1000), S["sol_usd"])
            o["tr"][k] = why
            emit(o["strategy"], "exit", token_mint=o["mint"], pool=o["pool"], symbol=o["sym"], price_usd=o["last"], liq_usd=round(o["lliq"] or 0),
                 stake_sol=STAKE_SOL, entry_price=o["entry"], exit_price=xp, gross_pct=g, net_pct=n, hold_s=round(T - o["t_entry"]),
                 exit_reason=why, track=("primary_tp15_sl10_15m" if k == "P" else "shadow_tp10_sl15_30m"),
                 reason=f"mfe={100 * o['mx']:.1f}% mae={100 * o['mn']:.1f}%")
            plog("EXIT", o["strategy"], k, o["sym"], why, n)
    if all(o["tr"].values()): S["open"].remove(o)

# ---------------- universe / watchlist (dipbuy + revival)
def is_meme(sym): return bool(sym) and sym.upper() not in NOT_MEME
def refresh_universe(S):
    url = UNIVERSE_SRC[S["uni_i"] % len(UNIVERSE_SRC)]; S["uni_i"] += 1
    d = get(url)
    added = 0
    for p in (d or {}).get("data") or []:
        a = p.get("attributes", {}); rel = p.get("relationships") or {}
        addr = a.get("address"); liq = fnum(a.get("reserve_in_usd")); name = a.get("name", "")
        base = (rel.get("base_token") or {}).get("data", {}).get("id", "").replace("solana_", "")
        quote = (rel.get("quote_token") or {}).get("data", {}).get("id", "").replace("solana_", "")
        bsym = name.split(" / ")[0].strip(); qsym = name.split(" / ")[-1].strip()
        if not is_meme(bsym) or qsym not in ("SOL", "USDC", "USDT") or base == SOL_MINT: continue
        try: age_h = (now() - pts(a["pool_created_at"])) / 3600
        except Exception: age_h = 0
        vol = a.get("volume_usd") or {}
        # revival check straight from GT attributes (cheap); DS confirms at the next watch poll
        w = S["watch"].get(addr)
        if liq >= 200000 or (liq >= 20000 and age_h >= 24):
            if not w: added += 1
            S["watch"][addr] = {"mint": base, "sym": bsym, "liq": liq, "age_h": round(age_h, 1), "v24": fnum(vol.get("h24")), "t_add": (w or {}).get("t_add", now())}
    # cap: dip-eligible first (by 24h vol), then revival-only; <= 60
    dip = sorted([kv for kv in S["watch"].items() if kv[1]["liq"] >= 200000], key=lambda kv: -kv[1]["v24"])[:40]
    rev = sorted([kv for kv in S["watch"].items() if kv[1]["liq"] < 200000], key=lambda kv: -kv[1]["v24"])[:30]
    S["watch"] = dict(dip + rev)
    return added

def watch_poll(S):
    pools = list(S["watch"].keys())
    if not pools: return
    i0 = S.get("watch_i", 0) % max(len(pools), 1); batch = (pools[i0:] + pools[:i0])[:30]; S["watch_i"] = i0 + 30
    px = ds_pairs(batch); T = now()
    for pool in batch:
        p = px.get(pool)
        if not p: continue
        r = ds_row(p); upd_sol(S, r)
        if r["px"] <= 0: continue
        h = S["hist"].setdefault(pool, []); h.append([T, r["px"], r["liq"]]); S["hist"][pool] = [x for x in h if T - x[0] <= 900]
        w = S["watch"][pool]
        age_h = (T - r["created"]) / 3600 if r["created"] else w.get("age_h", 0)
        # ---- dipbuy
        recent = [x for x in S["hist"][pool] if T - x[0] <= 600]
        if len(recent) >= 2:
            ref = max(recent[:-1], key=lambda x: x[1]); drop = 1 - r["px"] / ref[1]
            if ref[2] >= 200000 and 0.30 <= drop <= 0.50:
                f = r["px"] / ref[1]; liq_ok = r["liq"] >= 0.85 * ref[2] * math.sqrt(f); sell_only = r["b5"] == 0 and r["s5"] > 0
                flags = f"liq_intact={'Y' if liq_ok else 'N'} (now {r['liq']:.0f} vs ref {ref[2]:.0f}, price-adj min {0.85 * ref[2] * math.sqrt(f):.0f}); listed=Y; sell_only={'Y' if sell_only else 'N'}; creator_selling=NOT_CHECKED"
                rs = f"drop {100 * drop:.1f}% in {(T - ref[0]) / 60:.1f} min from {ref[1]:.6g}; {flags}"
                if liq_ok and not sell_only: signal(S, "dipbuy", r["mint"], pool, r["sym"], r["px"], round(r["liq"]), rs, drop_pct=round(100 * drop, 1))
                elif now() >= S["cool"].get("dipskip:" + pool, 0):
                    S["cool"]["dipskip:" + pool] = now() + 3600; S["nsig"]["dipbuy"] += 1; emit("dipbuy", "signal", token_mint=r["mint"], pool=pool, symbol=r["sym"], price_usd=r["px"], liq_usd=round(r["liq"]), reason=rs + " | SKIP: rug flag")
        # ---- revival
        if age_h >= 24 and r["liq"] >= 20000 and r["h6v"] > r["h1v"]:
            base5 = (r["h6v"] - r["h1v"]) / 60.0
            ratio = (r["m5v"] / r["liq"]) / max(base5 / r["liq"], 1e-9)
            if ratio >= 5 and r["m5v"] >= 3000 and r["m5c"] > 0:
                signal(S, "revival", r["mint"], pool, r["sym"], r["px"], round(r["liq"]),
                       f"m5 vol/liq {r['m5v'] / r['liq']:.3f} = {ratio:.1f}x baseline (prior-5h avg 5-min vol ${base5:.0f}); age {age_h / 24:.1f} d; m5 {r['m5c']:+.1f}%",
                       ratio=round(ratio, 2), age_d=round(age_h / 24, 2))
    S["hist"] = {k: v for k, v in S["hist"].items() if k in S["watch"] or any(o["pool"] == k for o in S["open"])}

# ---------------- graduation
def grad_poll(S):
    sort = ["created_timestamp", "last_trade_timestamp"][S["pf_i"] % 2]; S["pf_i"] += 1
    d = get(PF + sort)
    if not isinstance(d, list): return
    new = 0
    for c in d:
        m = c.get("mint"); pool = c.get("pump_swap_pool") or c.get("pool_address")
        if not m or not pool or m in S["grad_seen"]: continue
        S["grad_seen"][m] = now()
        if S["grad_pf_init"] or S["pf_i"] > 2:   # first poll of each sort only seeds
            S["grad_q"].append({"mint": m, "pool": pool, "sym": c.get("symbol"), "t": now(), "creator": c.get("creator")}); new += 1
    if S["pf_i"] >= 2: S["grad_pf_init"] = True
    return new

def grad_ds(S):
    q, S["grad_q"] = S["grad_q"][:30], S["grad_q"][30:]
    px = ds_pairs([c["pool"] for c in q])
    for c in q:
        p = px.get(c["pool"])
        if not p: continue
        r = ds_row(p)
        if r["liq"] >= 20000: S["grad_info_q"].append({**c, "liq": r["liq"], "px": r["px"]})
        else: S["why"]["grad_lowliq"] = S["why"].get("grad_lowliq", 0) + 1

def grad_info(S):
    c = S["grad_info_q"].pop(0)
    d = get(f"{GT}/tokens/{c['mint']}/info")
    a = ((d or {}).get("data") or {}).get("attributes") or {}
    lp = a.get("launchpad_details") or {}; hold = (a.get("holders") or {}).get("count"); dev = a.get("developer_holding_percentage")
    try: ago = (now() - pts(lp.get("completed_at"))) / 60
    except Exception: ago = None
    devf = fnum(dev, None) if dev is not None else None
    rs = f"graduated {ago:.1f} min ago" if ago is not None else "completed_at unknown"
    rs += f"; liq ${c['liq']:.0f}; holders {hold}; dev_holding {dev}%; top10 {((a.get('holders') or {}).get('distribution_percentage') or {}).get('top_10')}%"
    if ago is None or ago > 10:
        S["why"]["grad_stale"] = S["why"].get("grad_stale", 0) + 1; return
    if (hold is not None and hold < 50) or (devf is not None and devf > 10):
        emit("graduation", "signal", token_mint=c["mint"], pool=c["pool"], symbol=c["sym"], price_usd=c["px"], liq_usd=round(c["liq"]), reason=rs + " | SKIP: holder/dev filter")
        S["nsig"]["graduation"] += 1; return
    signal(S, "graduation", c["mint"], c["pool"], c["sym"], c["px"], round(c["liq"]), rs, holders=hold, dev_pct=devf)

# ---------------- consensus (selfcopy feed, read only, zero API calls)
def cons_scan(S):
    try:
        roster = json.load(open(SC_ROSTER)).get("leaders", [])
        act = {l["label"] for l in roster if l.get("active")}
    except Exception: act = set()
    try:
        sz = os.path.getsize(SC_FEED)
        if sz < S["sc_off"]: S["sc_off"] = 0
        with open(SC_FEED) as fh:
            fh.seek(S["sc_off"]); data = fh.read(); S["sc_off"] = fh.tell()
    except Exception: return
    first = S.get("sc_init") is None; S["sc_init"] = 1
    for ln in data.splitlines():
        if '"leader_swap"' not in ln: continue
        try: e = json.loads(ln)
        except Exception: continue
        if e.get("side") != "buy" or e.get("leader") not in act: continue
        S["sc_buys"].append([pts(e["ts"]), e["leader"], e["mint"], e.get("usd")])
    T = now(); S["sc_buys"] = [b for b in S["sc_buys"] if T - b[0] <= 1800]
    if first: return
    by = collections.defaultdict(set)
    for t, l, m, u in S["sc_buys"]: by[m].add(l)
    for m, ls in by.items():
        if len(ls) >= 3 and now() >= S["cool"].get(f"consensus_m:{m}", 0):
            S["cool"][f"consensus_m:{m}"] = now() + 3600
            S["cons_q"].append({"mint": m, "leaders": sorted(ls)})

def cons_resolve(S):
    c = S["cons_q"].pop(0)
    d = get(f"{DS}/tokens/{c['mint']}")
    ps = [p for p in (d or {}).get("pairs") or [] if p.get("chainId") == "solana"]
    if not ps:
        emit("consensus", "signal", token_mint=c["mint"], reason=f"{len(c['leaders'])} leaders {c['leaders']} | SKIP: no DEX pool found"); return
    p = max(ps, key=lambda p: fnum((p.get("liquidity") or {}).get("usd"))); r = ds_row(p)
    signal(S, "consensus", c["mint"], p["pairAddress"], r["sym"], r["px"], round(r["liq"]), f"{len(c['leaders'])} active leaders bought within 30 min: {c['leaders']}")

# ---------------- DLMM LP estimate
def v3_value(p0, p, pa, pb):
    """value (in quote) of a range position worth 1.0 at p0 vs HODL of the initial amounts. returns (lp_value, hodl_value)."""
    s0, s, sa, sb = map(math.sqrt, (p0, p, pa, pb))
    def amts(sp):
        sp = min(max(sp, sa), sb); return (1 / sp - 1 / sb), (sp - sa)
    x0, y0 = amts(s0); L = 1.0 / (x0 * p0 + y0)
    x1, y1 = amts(s)
    return L * (x1 * p + y1), L * (x0 * p + y0)

def dlmm_pick(S):
    d = get(f"{MET}/pools?page=1&page_size=100&sort_by=volume_24h:desc")
    picks, seen = [], set()
    for p in (d or {}).get("data") or []:
        x, y = p["token_x"], p["token_y"]
        if y["address"] != SOL_MINT or not p.get("launchpad") or p.get("tvl", 0) < 100000 or x["address"] in seen: continue
        if not is_meme(x["symbol"]): continue
        seen.add(x["address"]); picks.append({"addr": p["address"], "name": p["name"], "mint": x["address"], "sym": x["symbol"], "bin_step": p["pool_config"]["bin_step"],
                                              "base_fee_pct": p["pool_config"]["base_fee_pct"], "launchpad": p["launchpad"]})
        if len(picks) == 5: break
    S["dlmm_pairs"] = picks
    emit("dlmm", "heartbeat", reason="pairs picked (top 24h volume, memecoin/SOL, launchpad-origin, tvl>=$100k): " + ", ".join(f"{q['name']} bin_step={q['bin_step']}" for q in picks))

RANGE = 0.10
def dlmm_snap(S, q):
    p = get(f"{MET}/pools/{q['addr']}")
    if not p: return
    o = get(f"{GT}/pools/{q['addr']}/ohlcv/minute?aggregate=15&limit=26&currency=token&token={q['mint']}")
    ol = sorted(((o or {}).get("data") or {}).get("attributes", {}).get("ohlcv_list") or [])
    tvl = fnum(p.get("tvl")); fees = p.get("fees") or {}; prot = p.get("protocol_fees") or {}; cur = fnum(p.get("current_price"))
    lp = lambda k: fnum(fees.get(k)) - fnum(prot.get(k))
    fee6 = lp("4h") + (lp("12h") - lp("4h")) * 0.25
    out = {"pair": q["name"], "pool": q["addr"], "tvl": round(tvl), "price_sol": cur, "bin_step": q["bin_step"], "range_pct": 100 * RANGE,
           "bins_each_side": round(math.log(1 + RANGE) / math.log(1 + q["bin_step"] / 1e4)), "vol_1h": round(fnum((p.get("volume") or {}).get("1h"))),
           "dynamic_fee_pct": p.get("dynamic_fee_pct")}
    for W, nb, fee in (("1h", 4, lp("1h")), ("6h", 24, fee6)):
        if len(ol) < nb + 1 or tvl <= 0: out[W] = "insufficient_ohlcv"; continue
        p0 = ol[-(nb + 1)][4]; p1 = cur if cur > 0 else ol[-1][4]
        pa, pb = p0 / (1 + RANGE), p0 * (1 + RANGE)
        path = [c[4] for c in ol[-nb:]]
        inr = sum(1 for x in path if pa <= x <= pb) / len(path)
        v, hd = v3_value(p0, p1, pa, pb)
        il = 100 * (v / hd - 1); feep = 100 * fee / tvl * inr
        out[W] = {"price_move_pct": round(100 * (p1 / p0 - 1), 2), "in_range_frac": round(inr, 2), "fee_pct_pool_avg": round(feep, 3),
                  "il_pct_vs_hodl": round(il, 3), "net_vs_hodl_pct": round(feep + il, 3), "lp_vs_sol_only_pct": round(100 * (v * (1 + feep / 100) - 1), 3),
                  "fee_multiple_to_breakeven": (round(-il / feep, 1) if feep > 0 and il < 0 else None)}
    emit("dlmm", "signal", token_mint=q["mint"], pool=q["addr"], symbol=q["sym"], price_usd=fnum((p.get("token_x") or {}).get("price")), liq_usd=round(tvl),
         reason="LP estimate (not a trade), spot-uniform +-10% around price at window start; fees = pool-average LP fee/TVL x in-range fraction", lp=out)

# ---------------- heartbeat + summary
def heartbeat(S, strat):
    extra = {"signals_seen": S["nsig"].get(strat, 0), "open": n_open(S, strat), "calls_total": CALLS["_t"],
             "calls_per_min": round(CALLS["_t"] / max((now() - S.get("proc_start", now())) / 60, 1e-6), 2), "sol_usd": round(S["sol_usd"], 2)}
    if strat in ("dipbuy", "revival"): extra["watchlist"] = len(S["watch"]); extra["dip_eligible"] = sum(1 for w in S["watch"].values() if w["liq"] >= 200000)
    if strat == "graduation": extra.update(seen_mints=len(S["grad_seen"]), queued=len(S["grad_q"]) + len(S["grad_info_q"]), lowliq=S["why"].get("grad_lowliq", 0), stale=S["why"].get("grad_stale", 0))
    if strat == "consensus": extra.update(buys_30min=len(S["sc_buys"]), leaders_30min=len({b[1] for b in S["sc_buys"]}))
    if strat == "dlmm": extra["pairs"] = [q["name"] for q in S["dlmm_pairs"]]
    emit(strat, "heartbeat", reason=CAN[strat], **extra)

def summary():
    print(f"ideas_fwd summary @ {iso()} (primary exit +15/-10/15m; shadow +10/-15/30m; net after 2%/side fee, slippage, priority fee)")
    for s in STRATS:
        fn = os.path.join(HERE, f"{s}_fwd.jsonl")
        rows = [json.loads(l) for l in open(fn)] if os.path.exists(fn) else []
        if not rows: print(f"  {s:11s} no log yet"); continue
        t0 = pts(rows[0]["ts_utc"]); t1 = pts(rows[-1]["ts_utc"]); hrs = max((t1 - t0) / 3600, 1e-6)
        sig = [r for r in rows if r["event"] == "signal"]; ent = [r for r in rows if r["event"] == "entry"]
        if s == "dlmm":
            print(f"  {s:11s} snapshots={len(sig)} over {hrs:.2f} h")
            last = {}
            for r in sig: last[r["symbol"]] = r.get("lp", {})
            for k, v in last.items():
                f = lambda W: (f"move {v[W]['price_move_pct']:+.1f}% fee {v[W]['fee_pct_pool_avg']:.3f}% IL {v[W]['il_pct_vs_hodl']:.3f}% net {v[W]['net_vs_hodl_pct']:+.3f}%" if isinstance(v.get(W), dict) else str(v.get(W)))
                print(f"      {k:10s} tvl ${v.get('tvl')}  1h: {f('1h')}  |  6h: {f('6h')}")
            continue
        print(f"  {s:11s} signals={len(sig)} (skipped {sum(1 for r in sig if 'SKIP' in (r.get('reason') or ''))}) entries={len(ent)} over {hrs:.2f} h")
        for tr in ("primary_tp15_sl10_15m", "shadow_tp10_sl15_30m"):
            ex = [r for r in rows if r["event"] == "exit" and r.get("track") == tr]
            if not ex: print(f"      {tr}: 0 closed trades"); continue
            n = len(ex); w = sum(1 for r in ex if r["net_pct"] > 0); avg = sum(r["net_pct"] for r in ex) / n
            print(f"      {tr}: trades={n} win={100 * w / n:.0f}% avg_net={avg:+.2f}% avg_gross={sum(r['gross_pct'] for r in ex) / n:+.2f}% trades/h={n / hrs:.2f} "
                  f"exits={dict(collections.Counter(r['exit_reason'] for r in ex))}")

# ---------------- main loop
def main():
    if os.path.exists(PID):
        try:
            op = int(open(PID).read().strip())
            if op != os.getpid() and os.path.exists(f"/proc/{op}") and "ideas_fwd" in open(f"/proc/{op}/cmdline").read():
                print("already running", op); return
        except Exception: pass
    open(PID, "w").write(str(os.getpid()))
    S = load_state(); S["proc_start"] = now()
    plog("start pid", os.getpid(), "end", iso(END_TS))
    for s in STRATS: emit(s, "heartbeat", reason="START " + CAN[s], end_utc=iso(END_TS), spacing_s=SPACING)
    dlmm_pick(S); save_state(S)
    while now() < END_TS:
        try:
            T = now()
            cons_scan(S)                                                  # local file, no API
            did = False
            if any(T >= p["due"] for p in S["pending"]) or (S["open"] and due(S, "mon", 30)): did = monitor(S)
            elif S["cons_q"]: cons_resolve(S)
            elif S["grad_info_q"]: grad_info(S)
            elif S["grad_q"] and due(S, "gds", 20): grad_ds(S)
            elif due(S, "pf", 60): grad_poll(S)
            elif S.setdefault("dlmm_q", []): dlmm_snap(S, S["dlmm_q"].pop(0))      # one pair (2 calls) per loop turn
            elif S["dlmm_pairs"] and due(S, "dlmm", 900): S["dlmm_q"] = list(S["dlmm_pairs"])
            elif due(S, "uni", 120 if len(S["watch"]) >= 40 else 30): refresh_universe(S)
            elif due(S, "watch", 45): watch_poll(S)
            else: time.sleep(2)
            for s in STRATS:
                if now() - S["last_hb"].get(s, 0) >= HB_EVERY: S["last_hb"][s] = now(); heartbeat(S, s)
            save_state(S)
        except Exception as e:
            plog("ERR", repr(e)); time.sleep(5)
    for o in list(S["open"]): close_check(S, o, now(), force="end_of_run")
    for s in STRATS: emit(s, "heartbeat", reason="END of run (20:00Z)", signals_seen=S["nsig"].get(s, 0), calls_total=CALLS["_t"])
    save_state(S); plog("end", dict(CALLS))
    try: os.remove(PID)
    except Exception: pass

if __name__ == "__main__":
    if "--summary" in sys.argv: summary()
    else: main()
