#!/usr/bin/env python3
"""Lab fetch: PAPER ONLY, read-only public APIs, cache everything, stay far below shared rate limits.
1) seed data/candles from runner-radar/candles_cache (read-only copy)  2) snapshot Pulse/Scout files (point-in-time)
3) fetch missing GeckoTerminal 5m candles (<= max_gecko_calls, ~9/min)  4) poll DexScreener liquidity for coins
in their 24 h window (1 call / 30 coins) -> data/liq_polls.jsonl  5) rugcheck LP-lock/holder snapshot for coins
scanned <= 15 min ago (point-in-time; later reports would be lookahead)."""
import argparse, glob, json, os, subprocess, sys, time
from guards import classify, SCOUT_DIR
from labcore import *
from sources import all_entries

def seed_from_radar(cfg):
    n = 0
    for fp in glob.glob(os.path.join(cfg["paths"]["radar_candles"], "*.json")):
        pair = os.path.basename(fp)[:-5]; c = load_json(fp)
        if not c or not c.get("rows"): continue
        mine = load_candles(pair)
        if mine and mine.get("fetched_at", 0) >= c.get("fetched_at", 0) and len(mine["rows"]) >= len(c["rows"]): continue
        merge_candles(pair, c["rows"], c.get("fetched_at", 0), min(c.get("fetched_at", 0), c.get("last_ts", 0))); n += 1
    return n

def gecko_page(pair, before, spacing):
    url = (f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pair}/ohlcv/minute"
           f"?aggregate=5&limit=300&currency=usd&token=base" + (f"&before_timestamp={int(before)}" if before else ""))
    r = get_json(url, spacing)
    try: return [[int(x[0])] + [float(v) for v in x[1:6]] for x in r["data"]["attributes"]["ohlcv_list"]]
    except Exception: return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config"); ap.add_argument("--no-network", action="store_true")
    a = ap.parse_args(); cfg = load_config(a.config); F = cfg["fetch"]; H = cfg["sim"]["horizon_h"] * 3600
    os.makedirs(CANDLES, exist_ok=True); os.makedirs(RUGC, exist_ok=True)
    print(f"seeded {seed_from_radar(cfg)} candle files from radar cache"); snapshot_intel(cfg)
    if a.no_network: return
    now = time.time(); ents = all_entries(cfg)
    # windows per pair: [first entry t, last entry t + horizon]
    win = {}; backfill = set()      # retro (non point-in-time) cluster pairs: fetched last, at most 6 calls/run
    for src, rows in ents.items():
        for r in rows:
            if not r.get("pair"): continue
            if src == "radar" and (classify(r["rejects"])[0] or r["score"] < F["min_score_fetch"]): continue   # guard-rejected rows kept (guard sweeps)
            lo, hi = win.get(r["pair"], (1e18, 0)); win[r["pair"]] = (min(lo, r["t"]), max(hi, r["t"] + H))
            if src == "cluster" and not r.get("pit", True): backfill.add(r["pair"])
    # pairs for chunk/copyfomo tokens never scanned by the radar
    pairs = load_json(PAIRS, {}); need_pair = sorted({r["token"] for s in ("chunk_live", "copyfomo_skips", "copyfomo_trades", "cluster", "chunk_paper") if s in ents
                                                       for r in ents[s] if not r.get("pair") and r["token"] not in pairs})
    for i in range(0, len(need_pair), 30):
        res = get_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(need_pair[i:i+30]), F["dex_spacing_s"]) or []
        for p in res:
            t = (p.get("baseToken") or {}).get("address")
            if t and fnum((p.get("liquidity") or {}).get("usd")) >= fnum(pairs.get(t + ":liq")):
                pairs[t] = p.get("pairAddress"); pairs[t + ":liq"] = fnum((p.get("liquidity") or {}).get("usd"))
    if need_pair: atomic_write(PAIRS, json.dumps(pairs))
    calls = 0
    todo = []
    for pair, (lo, hi) in win.items():
        c = load_candles(pair) or {}
        done_hi = c.get("covered_until", 0) >= min(hi, now) - 600 or (c.get("covered_until", 0) >= hi)
        stale = now - c.get("fetched_at", 0) > F["refresh_min"] * 60
        has_lo = c.get("first") is not None and c["first"] <= lo + 300
        if (not has_lo or (not done_hi and stale)) and lo < now - 300:
            todo.append((lo, pair, hi))
    backfill -= {p for src, rows in ents.items() if src != "cluster" for r in rows for p in [r.get("pair")]}
    todo.sort(key=lambda x: (x[1] in backfill, x[0])); bf_calls = 0
    for lo, pair, hi in todo:
        if pair in backfill:
            if bf_calls >= 6: continue
            bf_calls += 1
        before = None if hi >= now - 600 else hi + 600
        for _ in range(3):                       # walk back if the window is longer than one 25 h page
            if calls >= F["max_gecko_calls"]: break
            rows = gecko_page(pair, before, F["gecko_spacing_s"]); calls += 1
            if rows is None: break
            c = merge_candles(pair, rows, now, before or now)
            if not rows or c["first"] <= lo + 300 or min(r[0] for r in rows) <= lo: break
            before = min(r[0] for r in rows)
        if calls >= F["max_gecko_calls"]: break
    print(f"candles: {len(win)} pairs in scope, {len(todo)} needed refresh, {calls} GeckoTerminal calls")
    # liquidity polls for coins still inside their window (point-in-time liq series going forward)
    live = sorted({r["token"] for rows in ents.values() for r in rows if now - r["t"] <= H and (r["src"] != "radar" or not classify(r["rejects"])[0])})
    polled = 0
    with open(LIQ_POLLS, "a") as fh:
        for i in range(0, len(live), 30):
            res = get_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(live[i:i+30]), F["dex_spacing_s"]) or []
            best = {}
            for p in res:
                t = (p.get("baseToken") or {}).get("address"); l = fnum((p.get("liquidity") or {}).get("usd"))
                if t in live and (t not in best or l > best[t][1]): best[t] = (p, l)
            for t, (p, l) in best.items():
                fh.write(json.dumps({"ts": now, "token": t, "pair": p.get("pairAddress"), "price": fnum(p.get("priceUsd")), "liq": l,
                                     "mcap": fnum(p.get("marketCap") or p.get("fdv"))}) + "\n"); polled += 1
    print(f"liquidity polled for {polled}/{len(live)} live coins")
    # rugcheck LP-lock + holders, only for scans <= 15 min old (else it would be lookahead)
    rc = 0
    fresh = {}
    for r in ents["radar"]:
        if not classify(r["rejects"])[0] and r["score"] >= 45 and 0 <= now - r["t"] <= 900: fresh.setdefault(r["token"], r)
    for tok, r in fresh.items():
        if rc >= F["max_rugcheck_calls"] or os.path.exists(os.path.join(RUGC, tok + ".json")): continue
        rep = get_json(f"https://api.rugcheck.xyz/v1/tokens/{tok}/report", F["rugcheck_spacing_s"]); rc += 1
        if not isinstance(rep, dict) or not rep.get("mint"): continue
        lp = None
        for m in rep.get("markets") or []:
            if m.get("pubkey") == r["pair"]: lp = (m.get("lp") or {}).get("lpLockedPct")
        atomic_write(os.path.join(RUGC, tok + ".json"), json.dumps({"token": tok, "fetched_at": time.time(), "signal_t": r["t"],
            "lp_locked": lp, "creator": rep.get("creator"), "rugged": bool(rep.get("rugged")),
            "holders": [h.get("owner") for h in rep.get("topHolders") or [] if h.get("owner")][:20]}))
        os.makedirs(os.path.join(DATA, "rugcheck_full"), exist_ok=True)       # full report -> point-in-time guard replays
        atomic_write(os.path.join(DATA, "rugcheck_full", tok + ".json"), json.dumps({"fetched_at": time.time(), "signal_t": r["t"], "report": rep}))
    print(f"rugcheck snapshots: {rc} calls")
    print(f"scout creator checks: {scout_capture(cfg, fresh, now)}")

def scout_capture(cfg, fresh, now):
    """Point-in-time Scout verdict (block/caution/ok/unknown) for radar rows scanned <= 15 min ago.
    Re-uses Scout's own 10-min cache when it is fresh enough; otherwise runs Scout's script (sequential, max N/run)."""
    F = cfg["fetch"]; os.makedirs(SCOUT_DIR, exist_ok=True); n_run = n_copy = 0
    for tok, r in sorted(fresh.items(), key=lambda kv: -kv[1]["score"]):
        dst = os.path.join(SCOUT_DIR, tok + ".json")
        if os.path.exists(dst): continue
        src = os.path.join(cfg["paths"]["onchain"], "data", "rugcheck", tok + ".json"); j = load_json(src)
        if isinstance(j, dict) and j.get("verdict") and j.get("checked_utc") and -7200 <= ts_of(j["checked_utc"]) - r["t"] <= 900:
            atomic_write(dst, json.dumps({"captured_at": ts_of(j["checked_utc"]), "signal_t": r["t"], "how": "scout_cache", "verdict": j["verdict"], "raw": j})); n_copy += 1; continue
        if n_run >= F.get("max_scout_calls", 3): continue
        try:
            p = subprocess.run([sys.executable, "-B", cfg["paths"].get("scout_script", "/workspace/onchain-intel/rugcheck_creator.py"), tok],
                               capture_output=True, text=True, timeout=60); n_run += 1
            j = json.loads(p.stdout[p.stdout.index("{"):])
        except Exception as ex:
            print(f"  scout check failed for {tok[:8]}: {type(ex).__name__}", file=sys.stderr); continue
        if isinstance(j, dict) and j.get("verdict"):
            atomic_write(dst, json.dumps({"captured_at": time.time(), "signal_t": r["t"], "how": "ran_script", "verdict": j["verdict"], "raw": j}))
        time.sleep(F.get("scout_spacing_s", 3))
    return f"{n_copy} copied from Scout cache, {n_run} script runs"

if __name__ == "__main__":
    main()
