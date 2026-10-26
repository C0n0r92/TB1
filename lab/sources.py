"""Entry sources for the harness. Each returns dicts: ts, token, pair, price (or None), liq, mcap, age_h, score,
rejects, symbol, src, extra. Everything is read-only; missing files just yield []."""
import csv, glob, json, os, re
from labcore import read_jsonl, load_json, ts_of, parse_ts, valid_sol, clean, fnum, PAIRS, _ADDR_IN

def radar_rows(cfg):
    out = []
    for r in read_jsonl(cfg["paths"]["radar_scanned"]):
        if not (valid_sol(r.get("token")) and r.get("pair")): continue
        out.append({**r, "t": ts_of(r["ts"]), "src": "radar", "lp_locked": None})
    out.sort(key=lambda r: r["t"])
    return out

def _pair_for(token, radar, pairs):
    best = None
    for r in radar:
        if r["token"] == token and (best is None or r["liq"] > best["liq"]): best = r
    if best: return best["pair"], best
    return pairs.get(token), None

def chunk_live(cfg, radar):
    """Parse Chunk's live buys from trades-log.md. Only lines that clearly record a BUY (not 'skipped')."""
    p = cfg["paths"]["chunk_trades_md"]
    if not os.path.exists(p): return []
    pairs, out, night = load_json(PAIRS, {}), [], None
    from zoneinfo import ZoneInfo; import datetime as dt
    for line in open(p):
        m = re.match(r"##\s*Night of (\d{4}-\d{2}-\d{2})", line)
        if m: night = m.group(1); continue
        low = line.lower()
        if not night or "skip" in low or "paper" in low or "paused" in low or not re.search(r"\b(bought|buy filled|entered|opened position|aped)\b", low): continue
        mt = re.search(r"(\d{1,2}):(\d{2})\s*(dublin|utc)", low); mints = [a for a in _ADDR_IN.findall(line) if valid_sol(a)]
        if not mt or not mints: continue
        tz = ZoneInfo("Europe/Dublin") if mt.group(3) == "dublin" else dt.timezone.utc
        d = dt.datetime.fromisoformat(night).replace(hour=int(mt.group(1)), minute=int(mt.group(2)), tzinfo=tz)
        if d.hour < 12: d += dt.timedelta(days=1)          # after-midnight entries belong to the same night
        tok = mints[0]; pair, ref = _pair_for(tok, radar, pairs)
        out.append({"t": d.timestamp(), "ts": d.isoformat(), "token": tok, "pair": pair, "price": None,
                    "liq": ref["liq"] if ref else None, "mcap": ref["mcap"] if ref else None, "age_h": None,
                    "score": ref["score"] if ref else None, "rejects": [], "symbol": ref["symbol"] if ref else tok[:6],
                    "src": "chunk_live", "note": clean(line, 120)})
    return out

def _tolerant_rows(path):
    if path.endswith(".csv"):
        try: return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(open(path, newline=""))]
        except Exception: return []
    return read_jsonl(path)

def copyfomo(cfg, radar, kind):
    """kind='skips' -> skips-log.csv (counterfactual entries); 'trades' -> trades*.csv/jsonl (actual copies)."""
    d = cfg["paths"]["copyfomo_dir"]
    files = [os.path.join(d, "skips-log.csv")] if kind == "skips" else \
        sorted(glob.glob(os.path.join(d, "trades*.csv")) + glob.glob(os.path.join(d, "trades*.jsonl")) + glob.glob(os.path.join(d, "copies*.csv")))
    pairs, out = load_json(PAIRS, {}), []
    for fp in files:
        if not os.path.exists(fp): continue
        for r in _tolerant_rows(fp):
            tok = next((r[k] for k in ("token", "mint", "ca", "contract_address", "address") if valid_sol(r.get(k))), None)
            t = next((parse_ts(r[k]) for k in ("ts", "time", "timestamp", "entry_ts", "buy_ts", "skipped_at", "logged_at") if r.get(k)), None)
            side = str(r.get("side", r.get("action", "buy"))).lower()
            if not tok or not t or (kind == "trades" and "sell" in side): continue
            pair, ref = _pair_for(tok, radar, pairs)
            out.append({"t": t, "ts": r.get("ts") or str(t), "token": tok, "pair": r.get("pair") if valid_sol(r.get("pair")) else pair,
                        "price": fnum(r.get("price") or r.get("entry_price"), None) if kind == "trades" else None,
                        "liq": ref["liq"] if ref else None, "mcap": ref["mcap"] if ref else None, "age_h": None,
                        "score": ref["score"] if ref else None, "rejects": [], "symbol": clean(r.get("symbol") or (ref or {}).get("symbol") or tok[:6]),
                        "src": "copyfomo_" + kind, "note": clean(r.get("reason") or r.get("trader") or "", 80)})
    return out

def all_entries(cfg):
    radar = radar_rows(cfg)
    return {"radar": radar, "chunk_live": chunk_live(cfg, radar),
            "copyfomo_skips": copyfomo(cfg, radar, "skips"), "copyfomo_trades": copyfomo(cfg, radar, "trades")}

# ---------------- queue loaders (tolerant; missing files -> []) ----------------
def chunk_paper(cfg, radar):
    """Chunk's would-be buys while live buying is paused: live/paper-buys.jsonl (entry at ds_price, logged time)."""
    p = cfg["paths"].get("chunk_paper", "/workspace/runner-radar/live/paper-buys.jsonl")
    pairs, out = load_json(PAIRS, {}), []
    for r in read_jsonl(p):
        tok = r.get("contract_address") or r.get("token")
        if not valid_sol(tok) or not r.get("ts"): continue
        pair, ref = _pair_for(tok, radar, pairs)
        m = re.search(r"dexscreener\.com/solana/([1-9A-HJ-NP-Za-km-z]{32,44})", str(r.get("url") or ""))
        if m: pair = m.group(1)
        v = str(r.get("scout_creator_check") or "unknown").split()[0].strip("(:,").lower()
        out.append({"t": ts_of(r["ts"]), "ts": r["ts"], "token": tok, "pair": pair, "price": fnum(r.get("ds_price"), None),
                    "liq": fnum(r.get("liq_usd"), None) or (ref or {}).get("liq"), "mcap": fnum(r.get("mcap_usd"), None),
                    "age_h": fnum(r.get("pair_age_min"), 0) / 60 if r.get("pair_age_min") is not None else None,
                    "score": fnum(r.get("signal_score"), None), "rejects": [], "symbol": clean(r.get("ticker") or tok[:6]),
                    "src": "chunk_paper", "scout_verdict": v if v in ("block", "caution", "ok", "unknown") else "unknown",
                    "scout_pit": True, "note": clean(r.get("scout_creator_check"), 80)})
    out.sort(key=lambda r: r["t"]); return out

def cluster_buys(cfg, radar):
    """Scout's cluster_buys.jsonl: >=3 early-buyer smart wallets in the same coin; entry at the 3rd buy time.
    Accepted keys: mint|token, ts_3rd|third_buy_ts|ts, n_wallets, pair (optional), price (optional)."""
    p = os.path.join(cfg["paths"]["onchain"], "cluster_buys.jsonl"); pairs, out = load_json(PAIRS, {}), []
    for r in read_jsonl(p):
        tok = r.get("mint") or r.get("token")
        t = next((parse_ts(r[k]) for k in ("ts_3rd", "third_buy_ts", "trigger_ts", "last_buy_in_window_at", "ts") if r.get(k)), None)
        if not valid_sol(tok) or not t or r.get("is_seed_runner"): continue   # seed runners = the coins the wallets were mined from
        det = parse_ts(r["detected_at"]) if r.get("detected_at") else None
        pit = det is None or det - t <= 900     # Scout's 2026-10-23 file is a retro backfill (wallets mined from runners) -> not point-in-time
        if int(fnum(r.get("n_wallets") or r.get("n") or 3)) < int(cfg.get("queue", {}).get("cluster_min_wallets", 3)): continue
        pair, ref = _pair_for(tok, radar, pairs)
        out.append({"t": t, "ts": str(r.get("ts")), "token": tok, "pair": r.get("pair") if valid_sol(r.get("pair")) else pair,
                    "price": fnum(r.get("price"), None), "liq": fnum(r.get("liq_usd"), None) or (ref or {}).get("liq"),
                    "mcap": fnum(r.get("mcap_usd"), None), "age_h": None, "score": None, "rejects": [],
                    "symbol": clean(r.get("symbol") or tok[:6]), "src": "cluster", "pit": pit})
    out.sort(key=lambda r: r["t"]); return out

def copy_lag(cfg):
    """Copycat's fill-vs-leader log. Any csv/jsonl in copyfomo_dir with leader & our entry mcap (or price) columns."""
    d = cfg["paths"]["copyfomo_dir"]; out = []
    for fp in sorted(glob.glob(os.path.join(d, "*.csv")) + glob.glob(os.path.join(d, "*.jsonl"))):
        for r in _tolerant_rows(fp):
            lm = fnum(r.get("leader_mcap") or r.get("leader_entry_mcap") or r.get("leader_price"), None)
            om = fnum(r.get("our_mcap") or r.get("our_entry_mcap") or r.get("fill_mcap") or r.get("our_price") or r.get("fill_price"), None)
            if not lm or not om: continue
            tok = next((r[k] for k in ("token", "mint", "ca", "contract_address") if valid_sol(r.get(k))), None)
            out.append({"file": os.path.basename(fp), "token": tok, "t": next((parse_ts(r[k]) for k in ("ts", "time", "timestamp") if r.get(k)), None),
                        "trader": r.get("trader") or r.get("leader") or "", "lag": om / lm - 1,
                        "ret": fnum(r.get("pnl_pct") or r.get("ret_pct"), None)})
    return out

def trader_trades(cfg):
    """Scout's trader_trades.csv: trader,wallet,mint,buy_at,sell_at,buy_usd,pnl_pct (closed rounds only)."""
    p = os.path.join(cfg["paths"]["onchain"], "trader_trades.csv"); out = []
    if not os.path.exists(p): return out
    for r in _tolerant_rows(p):
        if not r.get("sell_at") or r.get("pnl_pct") in (None, ""): continue
        try:
            out.append({"trader": r["trader"], "mint": r.get("mint"), "t": ts_of(r["buy_at"]), "t_exit": ts_of(r["sell_at"]),
                        "buy_usd": fnum(r.get("buy_usd")), "ret": fnum(r["pnl_pct"]) / 100.0})
        except Exception: continue
    out.sort(key=lambda r: r["t"]); return out

_all_entries_v1 = all_entries
def all_entries(cfg):
    d = _all_entries_v1(cfg)
    d["chunk_paper"] = chunk_paper(cfg, d["radar"]); d["cluster"] = cluster_buys(cfg, d["radar"])
    return d
