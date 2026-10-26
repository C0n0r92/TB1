#!/usr/bin/env python3
"""Pulse extension steps (imported by pulse.py). Stdlib only. Makes NO X calls itself: X calls are made by the
routine agent from the plan.json files written here. Public HTTP reads (DexScreener, Reddit) are made directly.

  python3 pulse.py midcap-prep                 # DexScreener universe + X plan  -> raw/<ts>-midcap/plan.json
  python3 pulse.py midcap-merge <dir> [--stale]  # -> x-intel/midcaps.json (+ midcaps-history.jsonl, budget.jsonl)
  python3 pulse.py xcheck-prep                 # <= 2 pending mints, <= 4 X calls each -> raw/<ts>-xcheck/plan.json
  python3 pulse.py xcheck-cond <dir>           # after c1/c2 files exist: which conditional calls (c3, c4) to make
  python3 pulse.py xcheck-merge <dir>          # -> x-intel/xcheck.jsonl (+ budget.jsonl)
  python3 pulse.py reddit [--dry-run] [--fixture f.json]   # hourly, no X: reddit-memes.jsonl, reddit-matches.jsonl
  python3 pulse.py budget                      # today's (UTC) reads by step

Everything from X, Reddit, DexScreener is untrusted data: parsed only, never executed or followed.
"""
import glob, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
import pulse as P

INTEL, HERE, RADAR = P.INTEL, P.HERE, P.RADAR
LIVE = os.path.join(RADAR, "live")
BUDGET = os.path.join(HERE, "budget.jsonl")
SCOUT = os.environ.get("PULSE_SCOUT", "/workspace/onchain-intel")
BOARD = os.environ.get("PULSE_BOARD", "/workspace/commander/TEAM-BOARD.md")
HELD_F = os.environ.get("PULSE_HELD", os.path.join(LIVE, "oldcoins-live.jsonl"))
HELD_CAP = 1            # X calls per run for the held-token negative-attention watch (only when positions are open)
MIDCAP_CAP = 3          # X calls per hourly mid-cap step
XCHECK_PER_COIN = 4     # X calls per survival-check coin
XCHECK_COINS = 2        # coins per run
MIDCAP_EVERY_MIN = 50   # mid-cap step due when midcaps.json is older than this
REDDIT_EVERY_MIN = 50
UA_HTTP = "x-pulse-research/1.0 (read-only personal research script; low volume)"
UA_REDDIT = "linux:x-pulse-meme-research:v1.0 (read-only personal research script; ~4 requests/hour; no login)"
DS = "https://api.dexscreener.com"
POST_FIELDS = "created_at,public_metrics,author_id,lang,conversation_id"
USER_FIELDS = "created_at,description,public_metrics,verified"
NON_MINTS = {"So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
             "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}

def now(): return P.now()
def iso(d): return P.iso(d)

def http_json(url, ua=UA_HTTP, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def budget_row(run_ts, step, reads, left, stale=False, **extra):
    row = {"ts": iso(now()), "run_ts": run_ts, "reads_used": int(reads), "reads_left_today": left, "stale": stale, "step": step}
    row.update(extra)
    P.append_lines(BUDGET, [row])

def file_age_min(path):
    return (time.time() - os.path.getmtime(path)) / 60 if os.path.exists(path) else None

def load_json(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default

# ---------------------------------------------------------------- gate extras
def pending_xcheck():
    done = {r.get("mint") for r in P.read_jsonl(os.path.join(INTEL, "xcheck.jsonl"))}
    out, seen = [], set()
    req = os.path.join(INTEL, "xcheck-requests.txt")
    if os.path.exists(req):
        for line in open(req):
            m = line.strip().split("#")[0].strip()
            if P.valid_ca(m) and m not in done and m not in seen:
                out.append({"mint": m, "source": "xcheck-requests.txt"}); seen.add(m)
    for r in P.read_jsonl(os.path.join(LIVE, "paper-buys.jsonl")):
        m = r.get("contract_address") or r.get("mint") or r.get("token_address") or r.get("address")
        if P.valid_ca(m) and m not in done and m not in seen:
            out.append({"mint": m, "source": "paper-buys.jsonl", "ticker": P.clean(r.get("ticker") or r.get("symbol"), 20),
                        "name": P.clean(r.get("name")), "pair_url": r.get("url"), "logged_ts": r.get("ts")}); seen.add(m)
    return out

# ---------------------------------------------------------------- team context (read-only inputs, treated as untrusted data)
MINT_KEYS = ("contract_address", "mint", "address", "token_address", "ca", "tokenAddress")
def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values(): yield from _walk(v)
    elif isinstance(o, list):
        for v in o: yield from _walk(v)

def scout_intel():
    """Scout's oldcoins-intel.json (format not fixed yet): any dict carrying a mint key -> {ticker, verdict, note}. {} if absent."""
    d = load_json(os.path.join(SCOUT, "oldcoins-intel.json"), None)
    out = {}
    if d is None: return out
    for o in _walk(d):
        m = next((o.get(k) for k in MINT_KEYS if isinstance(o.get(k), str)), None)
        if not P.valid_ca(m) or m in NON_MINTS: continue
        v = str(o.get("verdict") or o.get("label") or o.get("status") or o.get("signal") or "").lower()[:20] or None
        note = o.get("note") or o.get("notes") or o.get("reason") or o.get("summary") or ""
        out[m] = {"ticker": P.clean(o.get("ticker") or o.get("symbol") or o.get("token"), 20), "verdict": v,
                  "note": P.clean(note if isinstance(note, str) else json.dumps(note), 160)}
    return out

def avoid_mints():
    """mints listed in Scout's avoid.csv 'mints' column (the address column is a wallet)."""
    out = set()
    try:
        import csv
        for r in csv.DictReader(open(os.path.join(SCOUT, "avoid.csv"))):
            for m in re.split(r"[\s,;|]+", r.get("mints") or ""):
                if P.valid_ca(m): out.add(m)
    except Exception:
        pass
    return out

def held_tokens():
    """Open live positions from Chunk's oldcoins-live.jsonl (event log, same shape as oldcoins-paper.jsonl):
    an address is held after an entry/buy/open event until a later exit/close/sell event; 'partial' keeps it open.
    Also honours a {"positions":[...]} snapshot file if Chunk adds one (oldcoins-live-positions.json)."""
    held = {}
    for r in P.read_jsonl(HELD_F):
        m = next((r.get(k) for k in MINT_KEYS if isinstance(r.get(k), str)), None)
        if not P.valid_ca(m): continue
        ev = str(r.get("event") or r.get("action") or r.get("side") or "").lower()
        if ev in ("entry", "buy", "open", "long", "add"):
            held[m] = {"contract_address": m, "ticker": P.clean(r.get("token") or r.get("ticker") or r.get("symbol"), 20),
                       "entry_ts": r.get("ts"), "entry_price": r.get("price") or r.get("entry_price")}
        elif ev in ("exit", "close", "sell", "stop", "closed") and m in held:
            held.pop(m)
    snap = load_json(os.path.join(LIVE, "oldcoins-live-positions.json"), None)
    if isinstance(snap, dict):
        for p in snap.get("positions") or []:
            m = next((p.get(k) for k in MINT_KEYS if isinstance(p.get(k), str)), None) if isinstance(p, dict) else None
            if P.valid_ca(m) and m not in held:
                held[m] = {"contract_address": m, "ticker": P.clean(p.get("token") or p.get("ticker") or p.get("symbol"), 20),
                           "entry_ts": p.get("ts") or p.get("entry_ts"), "entry_price": p.get("entry_price") or p.get("price")}
    return list(held.values())

def cmd_context():
    """Start-of-run read of the team board + upstream bots' files. Context only: nothing here changes Pulse's rules."""
    def tail(p, n):
        try: return [l.rstrip("\n") for l in open(p).readlines()[-n:]]
        except Exception: return None
    paper = P.read_jsonl(os.path.join(LIVE, "oldcoins-paper.jsonl")); live = P.read_jsonl(HELD_F)
    sc = scout_intel(); vc = {}
    for v in sc.values(): vc[v["verdict"]] = vc.get(v["verdict"], 0) + 1
    out = {"board_tail": tail(BOARD, 20), "scout_oldcoins_intel": {"present": os.path.exists(os.path.join(SCOUT, "oldcoins-intel.json")),
           "tokens": len(sc), "verdicts": vc}, "scout_avoid_mints": len(avoid_mints()),
           "chunk_oldcoins_live": {"present": os.path.exists(HELD_F), "events": len(live), "open": held_tokens()},
           "chunk_oldcoins_paper": {"present": os.path.exists(os.path.join(LIVE, "oldcoins-paper.jsonl")), "events": len(paper),
                                    "last": paper[-1].get("ts") if paper else None},
           "chunk_trades_log_tail": tail(os.path.join(LIVE, "trades-log.md"), 3)}
    print(json.dumps(out, indent=1))

def cmd_board(args):
    """Append ONE line to the team board: pulse.py board --for "Chunk, Scout" --finding "..." --evidence "path or URL".
    Append-only (O_APPEND, one write); never rewrites the file. Max one Pulse line per run (keyed on the .lock timestamp
    or --run), and the same finding text is not re-posted if it is already in the last 20 lines."""
    def opt(k):
        return args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None
    who, finding, ev = opt("--for"), opt("--finding"), opt("--evidence")
    if not (who and finding and ev):
        print(json.dumps({"board": "error", "why": "need --for, --finding, --evidence"})); sys.exit(2)
    clean = lambda x, n: re.sub(r"\s+", " ", x.replace("|", "/")).strip()[:n]
    who, finding, ev = clean(who, 60), clean(finding, 280), clean(ev, 200)
    run = opt("--run") or (open(P.LOCK).read().strip() if os.path.exists(P.LOCK) else now().strftime("%Y-%m-%dT%H:%M"))
    stp = os.path.join(HERE, ".board-last")
    if os.path.exists(stp) and open(stp).read().strip() == run:
        print(json.dumps({"board": "skipped", "why": f"already posted one line for run {run}"})); return
    try: recent = open(BOARD).readlines()[-20:]
    except FileNotFoundError:
        print(json.dumps({"board": "error", "why": f"{BOARD} not found"})); return
    if any(finding in l for l in recent):
        print(json.dumps({"board": "skipped", "why": "same finding already in last 20 lines"})); return
    line = f"{now().strftime('%Y-%m-%dT%H:%MZ')} | Pulse | for: {who} | {finding} | {ev}"
    with open(BOARD, "rb") as f:
        f.seek(0, 2); size = f.tell(); needs_nl = False
        if size: f.seek(size - 1); needs_nl = f.read(1) != b"\n"
    fd = os.open(BOARD, os.O_WRONLY | os.O_APPEND)
    try: os.write(fd, (("\n" if needs_nl else "") + line + "\n").encode())
    finally: os.close(fd)
    P.atomic_write(stp, run + "\n")
    print(json.dumps({"board": "appended", "line": line}))

def midcaps_updated_at():
    d = load_json(os.path.join(INTEL, "midcaps.json"), None) or {}
    t = P.parse_ts(d.get("updated_at")) if not d.get("stale") else None
    return (now() - t).total_seconds() / 60 if t else None

def gate_extras(mode, used):
    extra_ok = mode == "full" and used < P.DAILY_SOFT
    mc_age = midcaps_updated_at()   # the mid-cap step's own updated_at (held-watch writes do not reset it)
    held = held_tokens() if mode in ("full", "counts_only") else []
    st = load_json(os.path.join(HERE, "reddit-state.json"), {}) or {}
    last = P.parse_ts(st.get("last_run")); boff = P.parse_ts(st.get("backoff_until"))
    reddit_due = (not last or now() - last >= timedelta(minutes=REDDIT_EVERY_MIN)) and not (boff and boff > now())
    pend = pending_xcheck() if extra_ok else []
    return {"midcap_due": bool(extra_ok and (mc_age is None or mc_age >= MIDCAP_EVERY_MIN)), "midcap_cap": MIDCAP_CAP,
            "xcheck_due": min(XCHECK_COINS, len(pend)), "xcheck_pending_total": len(pend), "xcheck_cap_per_coin": XCHECK_PER_COIN,
            "held_due": bool(held), "held_open": len(held), "held_cap": HELD_CAP if held else 0,
            "reddit_due": bool(reddit_due), "reddit_backoff_until": st.get("backoff_until"),
            "extras_skipped_reason": None if extra_ok else (f"{used} reads today >= {P.DAILY_SOFT}" if mode == "full" else f"core mode {mode}")}

# ---------------------------------------------------------------- DexScreener helpers
def ds_tokens(addrs):
    """/tokens/v1/solana/<<=30 csv> -> {mint: aggregated}"""
    pairs = []
    addrs = [a for a in dict.fromkeys(addrs) if P.valid_ca(a)]
    for i in range(0, len(addrs), 30):
        try:
            d = http_json(f"{DS}/tokens/v1/solana/" + ",".join(addrs[i:i + 30]))
            pairs += d if isinstance(d, list) else (d.get("pairs") or [])
        except Exception as e:
            print(f"# dexscreener tokens error: {e}", file=sys.stderr)
        time.sleep(0.3)
    return aggregate_pairs(pairs, set(addrs))

def aggregate_pairs(pairs, only=None):
    agg = {}
    for p in pairs:
        if p.get("chainId") != "solana": continue
        bt = p.get("baseToken") or {}
        m = bt.get("address")
        if not m or (only and m not in only): continue
        liq = float((p.get("liquidity") or {}).get("usd") or 0)
        a = agg.setdefault(m, {"contract_address": m, "ticker": P.clean(bt.get("symbol"), 20), "name": P.clean(bt.get("name")),
                               "vol24": 0.0, "liq": -1, "pair_created_ms": None, "pairs": 0})
        a["vol24"] += float((p.get("volume") or {}).get("h24") or 0); a["pairs"] += 1
        pc = p.get("pairCreatedAt")
        if pc and (a["pair_created_ms"] is None or pc < a["pair_created_ms"]): a["pair_created_ms"] = pc
        if liq > a["liq"]:
            a.update(liq=liq, mcap=float(p.get("marketCap") or p.get("fdv") or 0), price_usd=float(p.get("priceUsd") or 0),
                     price_change_h1=(p.get("priceChange") or {}).get("h1"), price_change_h24=(p.get("priceChange") or {}).get("h24"),
                     pair_address=p.get("pairAddress"), dex=p.get("dexId"), url=p.get("url"))
    for a in agg.values():
        a["age_days"] = round((time.time() * 1000 - a["pair_created_ms"]) / 86400000, 1) if a["pair_created_ms"] else None
    return agg

def ds_search(q):
    try:
        return http_json(f"{DS}/latest/dex/search?q=" + urllib.parse.quote(q)).get("pairs") or []
    except Exception as e:
        print(f"# dexscreener search error ({q}): {e}", file=sys.stderr); return []

# ---------------------------------------------------------------- sectors (hand-made, small; 'other' fallback)
SECTOR_TICKERS = {
    "ai_agents": {"GOAT", "AI16Z", "ZEREBRO", "ARC", "AIXBT", "GRIFFAIN", "SWARMS", "ALCH", "ACT", "AVA", "TAI", "ELIZA",
                  "VVAIFU", "LUNA", "TRUTH", "NOS", "PIPPIN", "BULLY", "MAX", "SNAI", "ANTFUN", "VIRTUAL"},
    "dog": {"WIF", "BONK", "MYRO", "WEN", "SAMO", "PONKE", "BILLY", "HABIBI", "DOGE", "SHIB", "DOGS", "LHD", "SC", },
    "cat": {"MEW", "POPCAT", "MOG", "MICHI", "CATE", "ZCAT", "MANEKI", "CHAT", },
    "frog": {"PEPE", "FWOG", "PEPECOIN", },
    "political": {"TRUMP", "MELANIA", "MAGA", "BODEN", "TREMP", "JAILSTOOL", "LIBRA", "WLFI"},
    "celebrity_ct": {"ANSEM", "MRBEAST", "KANYE", "DADDY", "IGGY", "TATE", "ELON", "SPX", "MOTHER"},
    "animal_other": {"MOODENG", "PNUT", "CHILLGUY", "BIRB", "HIPPO", "PENGU", "LOCKIN", "DOOD", "PUDGY"},
}
SECTOR_WORDS = [("ai_agents", r"\b(ai|agent|agents|gpt|neural|llm|bot|terminal|virtual|sentient)\b"),
                ("dog", r"\b(dog|doge|inu|shib|puppy|pup|dachshund|corgi|shiba|wif)\b"),
                ("cat", r"\b(cat|kitty|kitten|meow|neko|popcat|mew)\b"),
                ("frog", r"\b(pepe|frog|fwog|kek)\b"),
                ("political", r"\b(trump|maga|biden|melania|president|election|vance|musk ?gov|doge gov)\b"),
                ("celebrity_ct", r"\b(elon|kanye|ansem|mrbeast|tate|drake|iggy)\b")]

def sector_of(ticker, name):
    t = (ticker or "").upper()
    for sec, s in SECTOR_TICKERS.items():
        if t in s: return sec
    txt = f"{ticker} {name}".lower()
    for sec, rx in SECTOR_WORDS:
        if re.search(rx, txt): return sec
    return "other"

# ---------------------------------------------------------------- mid-caps
MC_SEARCHES = ["raydium", "pumpswap", "meteora", "orca", "SOL", "USDC", "pump", "bonk", "dog", "cat", "ai agent", "trump", "pepe", "meme",
               # hand seed of known Solana meme/mid-cap names (discovery only; the mcap/liq/vol filter decides)
               "popcat", "pnut", "moodeng", "goat", "ai16z", "chillguy", "michi", "pengu", "wif", "fwog", "ponke", "retardio",
               "mother", "jailstool", "aura", "spx6900", "pippin", "griffain", "swarms", "aixbt", "alch", "lockin", "billy",
               "giga", "mew", "useless", "titcoin", "house", "vine", "kled", "launchcoin", "neet", "nub", "wen"]
EXCLUDE_SYM = re.compile(r"^(W?SOL|USDC|USDT|USDS|PYUSD|USDE|EURC|JITOSOL|MSOL|BSOL|JUPSOL|INF|.*SOL|W?BTC|CBBTC|W?ETH|ERC20.*|JUP|JTO|PYTH|RAY|ORCA|DRIFT|KMNO|W|TNSR|RENDER|HNT|ZEUS|CLOUD)$", re.I)
EXCLUDE_NAME = re.compile(r"\b(wrapped|bridged|wormhole|staked|usd coin|tether|stablecoin|portal)\b", re.I)
AMBIGUOUS_CASHTAGS = {"SPX", "ARC", "MASK", "PUMP", "AI", "ACT", "MAX", "LUNA", "GME", "SC", "CHAT", "NOS", "SIGMA", "DOGE", "SHIB",
                      "PEPE", "TRUMP", "BTC", "ETH", "W", "X", "MOTHER", "ELON", "CAT", "DOG", "STONK", "GIGA", "BITCOIN"}

def midcap_universe():
    notes = []
    old = {}
    for r in P.read_jsonl(os.path.join(LIVE, "oldcoins-paper.jsonl")):
        m = r.get("address") or r.get("contract_address") or r.get("mint")
        t = P.parse_ts(r.get("ts"))
        if P.valid_ca(m) and (not t or now() - t <= timedelta(hours=48)):
            old[m] = {"symbol": P.clean(r.get("token") or r.get("symbol"), 20), "event": r.get("event"), "ts": r.get("ts")}
    if not os.path.exists(os.path.join(LIVE, "oldcoins-paper.jsonl")):
        notes.append("oldcoins-paper.jsonl not present yet")
    # Chunk's own older-coins universe (what it can actually trade) and open live positions: always included
    chunk_u = {}
    for t in (load_json(os.path.join(LIVE, "oldcoins-universe.json"), {}) or {}).get("tokens") or []:
        if P.valid_ca(t.get("address")): chunk_u[t["address"]] = P.clean(t.get("symbol"), 20)
    held = {h["contract_address"]: h for h in held_tokens()}
    scout = scout_intel(); avoid = avoid_mints()
    notes.append(f"chunk oldcoins-universe {len(chunk_u)}, held live {len(held)}, scout oldcoins-intel "
                 + (f"{len(scout)} tokens" if os.path.exists(os.path.join(SCOUT, "oldcoins-intel.json")) else "not present yet"))
    for m, sym in chunk_u.items(): old.setdefault(m, {"symbol": sym, "event": "universe", "ts": None})
    for m, h in held.items(): old.setdefault(m, {"symbol": h.get("ticker"), "event": "held", "ts": h.get("entry_ts")})
    cache_p = os.path.join(HERE, "midcap-universe.json")
    cache = load_json(cache_p, {}) or {}
    cand = set(old) | set(scout) | {m for m, v in cache.items() if now() - (P.parse_ts(v) or now() - timedelta(days=9)) < timedelta(hours=24)}
    raw_pairs = []
    for q in MC_SEARCHES:
        raw_pairs += ds_search(q); time.sleep(0.3)
    for p in raw_pairs:
        if p.get("chainId") == "solana":
            mc = float(p.get("marketCap") or p.get("fdv") or 0); lq = float((p.get("liquidity") or {}).get("usd") or 0)
            if 2e6 <= mc <= 3e8 and lq >= 2e5:
                cand.add((p.get("baseToken") or {}).get("address"))
    cand = {c for c in cand if P.valid_ca(c) and c not in NON_MINTS}
    agg = ds_tokens(sorted(cand))
    for m in agg: cache[m] = iso(now())
    cache = {m: v for m, v in cache.items() if now() - (P.parse_ts(v) or now()) < timedelta(hours=48)}
    P.atomic_write(cache_p, json.dumps(cache, indent=0))
    good = []
    for m, a in agg.items():
        if EXCLUDE_SYM.match(a["ticker"] or "") or EXCLUDE_NAME.search(a["name"] or ""): continue
        if re.fullmatch(r"[A-Z]{1,6}x", (a["ticker"] or "").strip()): continue   # tokenized stocks (TSLAx, NVDAx...)
        if not (5e6 <= (a.get("mcap") or 0) <= 2e8 and (a.get("liq") or 0) >= 5e5): continue
        if a["vol24"] < 1e5: continue
        good.append(a)
    # same ticker twice -> keep the most liquid (the other is likely a copy)
    best = {}
    for a in sorted(good, key=lambda a: -a["liq"]):
        best.setdefault((a["ticker"] or "").upper(), a)
    top = sorted(best.values(), key=lambda a: -a["vol24"])[:20]
    # Scout candidates that pass the same filters are added on top of the volume top-20
    extra = [a for a in good if a["contract_address"] in scout and a not in top]
    chosen = {a["contract_address"]: dict(a, in_top20=a in top, in_oldcoins=a["contract_address"] in old) for a in top + extra}
    for m, o in old.items():
        if m in chosen: continue
        a = agg.get(m) or {"contract_address": m, "ticker": o["symbol"], "name": o["symbol"], "vol24": 0, "liq": None, "mcap": None}
        chosen[m] = dict(a, in_top20=False, in_oldcoins=True)
    for m, c in chosen.items():
        c["held_live"] = m in held; c["in_chunk_universe"] = m in chunk_u; c["avoid_listed"] = m in avoid
        if m in scout: c["scout"] = scout[m]
    notes.append(f"dexscreener: {len(raw_pairs)} search pairs, {len(cand)} candidate mints, {len(agg)} priced, {len(good)} pass mcap/liq/vol, "
                 f"{len(top)} top-20 by vol24, {len(old)} from Chunk oldcoins universe/paper")
    return list(chosen.values()), notes

NOISY_WORDS = {"USELESS", "NEET", "CATE", "DOOD", "DOAS", "ANSEM", "ALCH", "VINE", "STONK", "ARC", "MEW", "GOAT", "PNUT"}  # words/names used outside the coin

def distinctive_word(t):
    """X's search tool strips '$' (no cashtag operator; verified 2026-10-23 23:38Z: "$ was removed from query"), so a
    ticker can only be searched as a bare word. Only do that when the word is distinctive: 4-12 alnum chars, not a
    top-10k English word, not a stopword, not a cross-market ticker."""
    t = (t or "").strip()
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9]{3,11}", t)) and t.lower() not in common_words() \
        and t.lower() not in STOP and t.upper() not in AMBIGUOUS_CASHTAGS and t.upper() not in NOISY_WORDS

XC_CONTEXT = "pump OR pumpfun OR solana OR sol OR dexscreener OR CA OR mint OR memecoin"   # X strips '$', so add crypto context

def mc_terms(coins):
    """CA for every coin (unambiguous) plus the bare ticker word when distinctive. Locally a post is attributed only by
    CA, $TICKER, or the ticker written in CAPS (see word_attributor), so bare-word noise is filtered out after the read."""
    terms = []
    for c in coins:
        t = (c.get("ticker") or "").strip()
        if distinctive_word(t):
            c["match"] = "ca+word"; terms.append((c, c["contract_address"] + " OR " + t.upper()))
        else:
            c["match"] = "ca"; terms.append((c, c["contract_address"]))
    return terms

def word_attributor(items, cas):
    """items: [(ticker, ca, word_ok)]. Hit on CA substring, $TICKER (any case), or TICKER in CAPS when word_ok."""
    tag = {}; caps = {}
    for t, ca, ok in items:
        t = (t or "").strip()
        if not t: continue
        tag[t.upper()] = ca
        if ok: caps[t.upper()] = ca
    capre = re.compile(r"(?<![A-Za-z0-9$])(" + "|".join(map(re.escape, sorted(caps, key=len, reverse=True))) + r")(?![A-Za-z0-9])") if caps else None
    def attribute(txt):
        hit = {ca for ca in cas if ca in txt}
        for t in re.findall(r"\$([A-Za-z][A-Za-z0-9]{1,11})\b", txt):
            if t.upper() in tag: hit.add(tag[t.upper()])
        if capre:
            for t in capre.findall(txt): hit.add(caps[t])
        return sorted(hit)
    return attribute

def build_mc_query(coins):
    terms = mc_terms(coins)
    # priority: oldcoins first, then by volume
    terms.sort(key=lambda ct: (not ct[0].get("held_live"), not ct[0].get("in_oldcoins"), -(ct[0].get("vol24") or 0)))
    used, dropped = [], []
    for c, t in terms:
        q = "(" + " OR ".join([x for _, x in used] + [t]) + ")" + P.QUERY_SUFFIX
        if len(q) <= P.QUERY_MAX: used.append((c, t))
        else: dropped.append(c)
    for c in dropped: c["match"] = "dropped_query_length"
    return "(" + " OR ".join(t for _, t in used) + ")" + P.QUERY_SUFFIX, used, dropped

def cmd_midcap_prep():
    run_ts = now().strftime("%Y%m%dT%H%M%SZ")
    coins, notes = midcap_universe()
    q, used, dropped = build_mc_query(coins)
    start = iso(now() - timedelta(minutes=60))
    for c in coins: c["sector"] = sector_of(c.get("ticker"), c.get("name"))
    calls = [{"file": "counts_mc.json", "tool": "get_posts_counts_recent", "args": {"query": q, "granularity": "minute", "start_time": start}},
             {"file": "search_mc_p1.json", "tool": "search_posts_all",
              "args": {"query": q, "start_time": start, "max_results": 25, "sort_order": "recency", "post.fields": POST_FIELDS,
                       "user.fields": USER_FIELDS, "expansions": "author_id"}},
             {"file": "search_mc_p2.json", "tool": "search_posts_all", "when": "only if p1 has meta.next_token and its oldest post is newer than now-30m; add next_token",
              "args": {"query": q, "start_time": start, "max_results": 25, "sort_order": "recency", "post.fields": POST_FIELDS,
                       "user.fields": USER_FIELDS, "expansions": "author_id"}}]
    d = os.path.join(HERE, "raw", run_ts + "-midcap"); os.makedirs(d, exist_ok=True)
    plan = {"run_ts": run_ts, "step": "midcap", "cap": MIDCAP_CAP, "start_time": start, "coins": coins, "query": q,
            "query_len": len(q), "dropped": [c["contract_address"] for c in dropped], "notes": notes, "calls": calls}
    P.atomic_write(os.path.join(d, "plan.json"), json.dumps(plan, indent=1))
    print(json.dumps({"dir": d, "coins": len(coins), "query_chars": len(q), "terms": len(used), "dropped": len(dropped),
                      "calls": [c["file"] for c in calls], "notes": notes}, indent=1))

def load_dir_posts(d, prefix=""):
    posts, users, reads, counts = {}, {}, [], {}
    for f in sorted(glob.glob(os.path.join(d, prefix + "*.json"))):
        n = os.path.basename(f)
        if n == "plan.json": continue
        obj, r = P.load_raw(f)
        if r: reads.append(r)
        for u in (obj.get("includes") or {}).get("users") or []: users[u["id"]] = u
        if n.startswith("counts") or "counts" in n:
            counts[n] = P.counts_series(obj)
        else:
            for p in obj.get("data") or []:
                if "text" in p: p["_file"] = n; posts[p["id"]] = p
    return posts, users, reads, counts

def prep_posts(posts, users, cas, tickers, attribute):
    plist = []
    for p in posts.values():
        txt = p.get("text") or ""
        p["_coins"] = attribute(txt)
        p["_dt"] = P.parse_ts(p.get("created_at"))
        p["_norm"] = P.norm_text(txt, cas, tickers)
        p["_brag"] = bool(P.BRAG_RE.search(txt))
        p["_url"] = p.get("url") or f"https://x.com/{(users.get(p.get('author_id')) or {}).get('username', 'i')}/status/{p['id']}"
        if p["_dt"]: plist.append(p)
    return plist

MIN_SAMPLE_MIN = 10    # X returns <=25 posts/call; a sample spanning <10 min is too short to rank on

def heat_from(w15, ratio, n15, nq, has_posts, prev_exists, sample_min=15.0):
    base = 70 * (1 - pow(2.718281828, -w15 / 4))
    bonus = max(-15, min(30, (ratio - 1) * 15)) if (has_posts and prev_exists) else 0
    short = sample_min < MIN_SAMPLE_MIN
    low = has_posts and (n15 < P.LOW_POSTS_15M or nq < P.LOW_QUALITY or short)
    if low: bonus = min(bonus, P.LOW_BONUS_CAP)
    heat = 0 if not has_posts else round(max(0, min(100, base + bonus)) * (1 if nq else 0.6), 1)
    note = ""
    if low:
        why = " and ".join(x for x in (f"{n15} posts/15m-equiv (<{P.LOW_POSTS_15M})" if n15 < P.LOW_POSTS_15M else "",
                                       f"{nq} quality accts (<{P.LOW_QUALITY})" if nq < P.LOW_QUALITY else "",
                                       f"sample spans {sample_min:.0f}m (<{MIN_SAMPLE_MIN}m)" if short else "") if x)
        note = f"LOW-SAMPLE CAP: {why} -> trend bonus <= {P.LOW_BONUS_CAP:g}, heat <= {P.LOW_HEAT_CAP:g} (uncapped {heat}); "
        heat = min(heat, P.LOW_HEAT_CAP)
    return heat, note

def midcap_load(d):
    """Parse a raw/<ts>-midcap dir: shared by cmd_midcap_merge and the first-mentions backfill. No writes."""
    d = os.path.abspath(d) if os.path.isdir(d) else os.path.join(HERE, "raw", d)
    plan = json.load(open(os.path.join(d, "plan.json")))
    coins = plan["coins"]
    posts, users, reads, counts = load_dir_posts(d)
    run_dt = datetime.strptime(plan["run_ts"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    cas = [c["contract_address"] for c in coins]; tickers = [c.get("ticker") or "" for c in coins]
    attribute = word_attributor([(c.get("ticker"), c["contract_address"], c.get("match") in ("ca+word", "cashtag")) for c in coins
                                 if c.get("match") in ("ca+word", "cashtag")], cas)
    plist = prep_posts(posts, users, cas, tickers, attribute)
    if plist: run_dt = max(run_dt, max(p["_dt"] for p in plist))
    authors = {aid: P.author_profile(u, run_dt) for aid, u in users.items()}
    flags = P.classify_authors(plist, authors, run_dt)
    return dict(d=d, plan=plan, coins=coins, posts=posts, users=users, reads=reads, counts=counts, run_dt=run_dt, cas=cas,
                tickers=tickers, plist=plist, authors=authors, flags=flags)

def cmd_midcap_merge(d, stale=False):
    out_p = os.path.join(INTEL, "midcaps.json")
    if stale:
        cur = load_json(out_p, None)
        if cur:
            cur["stale"] = True; cur["stale_marked_at"] = iso(now())
            P.atomic_write(out_p, json.dumps(cur, indent=1))
        budget_row(now().strftime("%Y%m%dT%H%M%SZ"), "midcap", 0, None, stale=True)
        print(json.dumps({"midcaps": "marked stale"})); return
    L = midcap_load(d)
    d, plan, coins, posts, users, reads, counts = L["d"], L["plan"], L["coins"], L["posts"], L["users"], L["reads"], L["counts"]
    run_dt, cas, tickers, plist, authors, flags = L["run_dt"], L["cas"], L["tickers"], L["plist"], L["authors"], L["flags"]
    oldest = min((p["_dt"] for p in plist), default=run_dt)
    sample_min = max(1.0, (run_dt - oldest).total_seconds() / 60)
    scale15 = min(1.0, 15 / sample_min)
    hist = P.read_jsonl(os.path.join(HERE, "midcaps-history.jsonl"))
    prev = {}
    for h in hist:
        t = P.parse_ts(h.get("run_ts"))
        if t and timedelta(minutes=20) <= run_dt - t <= timedelta(minutes=180): prev[h["contract_address"]] = h
    prev_sec = {}
    for h in P.read_jsonl(os.path.join(HERE, "midcaps-sectors.jsonl")):
        t = P.parse_ts(h.get("run_ts"))
        if t and timedelta(minutes=20) <= run_dt - t <= timedelta(minutes=180): prev_sec[h["sector"]] = h
    obs = iso(run_dt); out, hist_rows = [], []
    for c in coins:
        ca = c["contract_address"]
        cp = [p for p in plist if ca in p["_coins"]]
        aall = {p["author_id"] for p in cp}
        q = [a for a in aall if P.is_quality(flags.get(a, {"new"}))]
        qposts = [p for p in cp if P.is_quality(flags.get(p["author_id"], {"new"}))]
        promo = sum(1 for p in cp if {"promo", "template", "ring"} & flags.get(p["author_id"], set()))
        w = sum(P.author_weight(flags.get(a, {"new"})) for a in aall)
        brag_frac = sum(1 for p in cp if p["_brag"]) / max(1, len(cp))
        w15 = w * scale15 * (1 - 0.7 * brag_frac)
        rate_h = round(len(cp) / sample_min * 60, 1)       # posts per hour (sample-based)
        q_rate_h = round(len(qposts) / sample_min * 60, 1)
        pv = prev.get(ca)
        ratio = (rate_h + 0.5) / (float(pv.get("rate_per_h") or 0) + 0.5) if pv else 1.0
        trend = "rising" if (pv and rate_h > float(pv.get("rate_per_h") or 0)) else "fading"
        n15 = round(len(cp) * scale15)
        heat, cap_note = heat_from(w15, ratio, n15, len(q), bool(cp), bool(pv), sample_min)
        conf = "high" if (len(cp) >= 15 and len(q) >= 5) else "med" if (len(cp) >= 5 and len(q) >= 2) else "low"
        if c.get("match") == "dropped_query_length": conf = "low"
        notes = (f"{cap_note}{len(cp)} posts/{len(aall)} accts in {sample_min:.0f}m sample (match by {c.get('match')}); "
                 f"{rate_h}/h ({q_rate_h}/h from quality accts); trend vs prev hourly run "
                 + (f"ratio {ratio:.2f}" if pv else "n/a (no prior run 20-180 min old) -> fading")
                 + f"; brag share {brag_frac:.0%}" + ("; HELD LIVE by Chunk" if c.get("held_live") else "")
                 + ("; in Chunk oldcoins universe/log" if c.get("in_oldcoins") else "")
                 + (f"; Scout verdict {c['scout'].get('verdict')}: {c['scout'].get('note')}" if c.get("scout") else "")
                 + ("; mint in Scout avoid.csv" if c.get("avoid_listed") else "")
                 + (f"; age {c.get('age_days')}d" if c.get("age_days") is not None else "") + f"; vol24 ${c.get('vol24') or 0:,.0f}")
        if c.get("match") == "dropped_query_length": notes = "NOT QUERIED (query length cap); " + notes
        row = {"contract_address": ca, "ticker": c.get("ticker"), "name": c.get("name"), "sector": c.get("sector") or "other",
               "observed_at": obs, "mcap": c.get("mcap"), "liq": c.get("liq"), "price_change_h1": c.get("price_change_h1"),
               "heat_score": heat, "trend": trend, "mentions": len(cp), "distinct_accounts": len(aall), "quality_accounts": len(q),
               "promo_share": round(promo / max(1, len(cp)), 2), "confidence": conf, "notes": notes[:600],
               "in_oldcoins": bool(c.get("in_oldcoins")), "in_top20": bool(c.get("in_top20")), "vol24": c.get("vol24"),
               "held_live": bool(c.get("held_live")), "in_chunk_universe": bool(c.get("in_chunk_universe")),
               "scout_verdict": (c.get("scout") or {}).get("verdict"), "avoid_listed": bool(c.get("avoid_listed")),
               "price_usd": c.get("price_usd"), "rate_per_h": rate_h, "quality_rate_per_h": q_rate_h,
               "evidence": [p["_url"] for p in sorted(qposts, key=lambda p: p["_dt"])][:3]}
        out.append(row)
        hist_rows.append({k: row[k] for k in ("contract_address", "ticker", "sector", "heat_score", "mentions", "distinct_accounts",
                                               "quality_accounts", "rate_per_h", "quality_rate_per_h", "price_usd", "price_change_h1")} | {"run_ts": obs})
    out = [r for r in out if P.valid_ca(r["contract_address"])]
    out.sort(key=lambda r: -r["heat_score"])
    # sectors
    secs = {}
    for r in out:
        s = secs.setdefault(r["sector"], {"q_rate": 0.0, "quality_mentions": 0, "coins": []})
        s["q_rate"] += r["quality_rate_per_h"]; s["quality_mentions"] += round(r["quality_rate_per_h"] * sample_min / 60)
        s["coins"].append(r["ticker"])
    sectors, sec_rows, fl = [], [], []
    for name, s in sorted(secs.items(), key=lambda kv: -kv[1]["q_rate"]):
        pv = prev_sec.get(name)
        q_rate = round(s["q_rate"], 1)
        trend = "rising" if (pv and q_rate > float(pv.get("quality_rate_per_h") or 0)) else "fading"
        note = (f"{len(s['coins'])} coins ({', '.join(map(str, s['coins'][:6]))}); quality-account posts {q_rate}/h"
                + (f" vs {pv.get('quality_rate_per_h')}/h prev hourly run" if pv else "; no prior hourly run -> fading"))
        sectors.append({"sector": name, "observed_at": obs, "trend": trend, "quality_mentions": s["quality_mentions"],
                        "quality_rate_per_h": q_rate, "note": note})
        sec_rows.append({"run_ts": obs, "sector": name, "quality_rate_per_h": q_rate, "quality_mentions": s["quality_mentions"]})
        if pv and s["quality_mentions"] >= 3 and q_rate >= 1.5 * float(pv.get("quality_rate_per_h") or 0) + 2:
            fl.append({"type": "sector_rotation", "sector": name, "observed_at": obs,
                       "evidence": f"quality-account posts/h {pv.get('quality_rate_per_h')} -> {q_rate} ({', '.join(map(str, s['coins'][:6]))})"})
    for r in out:
        pv = prev.get(r["contract_address"])
        h1 = r.get("price_change_h1")
        if pv and r["quality_accounts"] >= 3 and r["quality_rate_per_h"] >= 2 * float(pv.get("quality_rate_per_h") or 0) + 2 \
                and h1 is not None and abs(float(h1)) < 5:
            fl.append({"type": "quality_attention_before_move", "contract_address": r["contract_address"], "observed_at": obs,
                       "ticker": r["ticker"], "price_usd": r.get("price_usd"),
                       "evidence": f"quality posts/h {pv.get('quality_rate_per_h')} -> {r['quality_rate_per_h']} with price 1h {h1}%; "
                                   + " ".join(r["evidence"])})
        # pre-breakout momentum: in-range mid-cap, quality attention rising, 1h price still small
        in_range = 5e6 <= float(r.get("mcap") or 0) <= 2e8 and float(r.get("liq") or 0) >= 5e5
        if pv and in_range and sample_min >= MIN_SAMPLE_MIN and r["quality_accounts"] >= 2 and r["quality_rate_per_h"] >= 1.5 * float(pv.get("quality_rate_per_h") or 0) + 1 \
                and h1 is not None and abs(float(h1)) <= 3:
            fl.append({"type": "pre_breakout_momentum", "contract_address": r["contract_address"], "observed_at": obs,
                       "ticker": r["ticker"], "price_usd": r.get("price_usd"), "alert": True,
                       "evidence": f"quality accts {r['quality_accounts']}; quality posts/h {pv.get('quality_rate_per_h')} -> {r['quality_rate_per_h']}; "
                                   f"1h price {h1}%; mcap ${float(r.get('mcap') or 0):,.0f}; " + " ".join(r["evidence"])})
    # follow-up: earlier pre-move flags (<= 6h) whose price later moved >= +10%
    for f0 in P.read_jsonl(os.path.join(HERE, "midcaps-flags.jsonl")):
        t = P.parse_ts(f0.get("observed_at"))
        if f0.get("type") not in ("quality_attention_before_move", "pre_breakout_momentum") or not t or run_dt - t > timedelta(hours=6) or f0.get("followed_up"): continue
        r = next((x for x in out if x["contract_address"] == f0.get("contract_address")), None)
        if r and f0.get("price_usd") and r.get("price_usd"):
            chg = r["price_usd"] / f0["price_usd"] - 1
            if chg >= 0.10:
                fl.append({"type": "early_attention_then_moved", "contract_address": r["contract_address"], "observed_at": obs,
                           "ticker": r["ticker"], "evidence": f"flagged {f0['observed_at']} at ${f0['price_usd']:.6g}; now ${r['price_usd']:.6g} ({chg:+.0%}). {f0.get('evidence','')[:200]}"})
    fl = [f for f in fl if (P.valid_ca(f.get("contract_address")) or f.get("sector")) and f.get("observed_at")]
    rl = min((r["day_left"] for r in reads), default=None)
    res = {"updated_at": iso(now()), "stale": not reads, "sample_minutes": round(sample_min, 1), "posts_sampled": len(plist),
           "query_chars": plan.get("query_len"), "universe_notes": plan.get("notes"),
           "budget": {"reads_used_this_step": len(reads), "reads_left_today_reported": rl},
           "coins": out, "sectors": sectors, "flags": fl, "alerts": [f for f in fl if f.get("alert")]}
    cur = load_json(out_p, None) or {}
    for k in ("held", "held_updated_at", "held_note"):      # written every run by held-merge; keep it
        if k in cur: res[k] = cur[k]
    P.atomic_write(out_p, json.dumps(res, indent=1))
    done = {(r.get("run_ts"), r.get("step")) for r in P.read_jsonl(BUDGET)}
    if (plan["run_ts"], "midcap") not in done:
        if reads:
            P.append_lines(os.path.join(HERE, "midcaps-history.jsonl"), hist_rows)
            P.append_lines(os.path.join(HERE, "midcaps-sectors.jsonl"), sec_rows)
            if fl: P.append_lines(os.path.join(HERE, "midcaps-flags.jsonl"), fl)
        budget_row(plan["run_ts"], "midcap", len(reads), rl, stale=not reads)
    fm = P.safe_first_mentions(plist, authors, flags, "midcap", run_dt, {c["contract_address"]: c.get("ticker") for c in coins}) if reads else 0
    print(json.dumps({"first_mentions_new": fm, "coins": len(out), "posts": len(plist), "sample_min": round(sample_min, 1), "calls": len(reads),
                      "reads_left_today": rl, "flags": len(fl), "alerts": [f for f in fl if f.get("alert")], "top": [(r["ticker"], r["heat_score"], r["quality_accounts"]) for r in out[:5]]}))

# ---------------------------------------------------------------- held-token negative-attention watch (every run)
NEG_TERMS = ['rug', 'rugged', 'rugpull', '"rug pull"', 'exploit', 'exploited', 'hack', 'hacked', 'drained', 'drainer',
             '"dev dump"', '"dev dumped"', '"dev dumping"', '"dev sold"', '"dev selling"', 'honeypot', '"can\'t sell"', '"cant sell"',
             '"unable to sell"', '"pulled liquidity"', '"liquidity pulled"', '"lp pulled"', '"removed liquidity"', 'scam', 'compromised']
NEG_RE = re.compile(r"\b(rug(ged|pull)?|rug pull|exploit(ed)?|hack(ed)?|drain(ed|er)|dev (dump(ed|ing)?|sold|sell(ing)?)|honey ?pot|"
                    r"can'?t sell|unable to sell|(pulled|removed) (the )?(liquidity|lp)|(liquidity|lp) pulled|scam|compromised)\b", re.I)

def held_terms(held):
    terms = []
    for h in held:
        terms.append(h["contract_address"])
        t = (h.get("ticker") or "").strip().upper()
        if distinctive_word(t): terms.append(t)     # bare word: X strips '$'
    return terms

def cmd_held_prep():
    run_ts = now().strftime("%Y%m%dT%H%M%SZ"); held = held_tokens()
    if not held:
        print(json.dumps({"held": 0, "calls": [], "note": "no open live positions" + ("" if os.path.exists(HELD_F) else f" ({os.path.basename(HELD_F)} not present yet)")}))
        return
    neg = "(" + " OR ".join(NEG_TERMS) + ")"
    terms = held_terms(held); used = []
    for t in terms:
        q = "(" + " OR ".join(used + [t]) + ") " + neg + P.QUERY_SUFFIX
        if len(q) <= P.QUERY_MAX: used.append(t)
    q = "(" + " OR ".join(used) + ") " + neg + P.QUERY_SUFFIX
    start = iso(now() - timedelta(minutes=60))
    d = os.path.join(HERE, "raw", run_ts + "-held"); os.makedirs(d, exist_ok=True)
    plan = {"run_ts": run_ts, "step": "held", "cap": HELD_CAP, "held": held, "query": q, "query_len": len(q),
            "terms_dropped": [t for t in terms if t not in used],
            "calls": [{"file": "search_held.json", "tool": "search_posts_all",
                       "args": {"query": q, "start_time": start, "max_results": 25, "sort_order": "recency", "post.fields": POST_FIELDS,
                                "user.fields": USER_FIELDS, "expansions": "author_id"}}]}
    P.atomic_write(os.path.join(d, "plan.json"), json.dumps(plan, indent=1))
    print(json.dumps({"dir": d, "held": len(held), "query_chars": len(q), "calls": ["search_held.json"]}, indent=1))

def held_load(d):
    """Parse a raw/<ts>-held dir (shared by cmd_held_merge and the first-mentions backfill). No writes.
    plist/flags = negative-wording posts only (alerts); plist_all/flags_all = every fetched post (first-mentions log)."""
    d = os.path.abspath(d) if os.path.isdir(d) else os.path.join(HERE, "raw", d)
    plan = json.load(open(os.path.join(d, "plan.json")))
    posts, users, reads, _ = load_dir_posts(d)
    run_dt = datetime.strptime(plan["run_ts"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    held = plan["held"]; cas = [h["contract_address"] for h in held]
    attribute = word_attributor([(h.get("ticker"), h["contract_address"], distinctive_word(h.get("ticker"))) for h in held], cas)
    plist = prep_posts(posts, users, cas, [h.get("ticker") or "" for h in held], attribute)
    plist_all = list(plist)
    plist = [p for p in plist if NEG_RE.search(p.get("text") or "")]     # X matches loosely; keep only real negative wording
    if plist: run_dt = max(run_dt, max(p["_dt"] for p in plist))
    authors = {aid: P.author_profile(u, run_dt) for aid, u in users.items()}
    flags = P.classify_authors(plist, authors, run_dt)
    run_all = max([run_dt] + [p["_dt"] for p in plist_all])
    authors_all = {aid: P.author_profile(u, run_all) for aid, u in users.items()}
    flags_all = P.classify_authors(plist_all, authors_all, run_all)
    return dict(d=d, plan=plan, posts=posts, users=users, reads=reads, run_dt=run_dt, held=held, cas=cas, plist=plist,
                authors=authors, flags=flags, plist_all=plist_all, authors_all=authors_all, flags_all=flags_all, run_all=run_all)

def cmd_held_merge(d):
    out_p = os.path.join(INTEL, "midcaps.json")
    cur = load_json(out_p, None) or {"updated_at": None, "stale": True, "coins": [], "sectors": [], "flags": []}
    if not d:   # no open positions -> record that, 0 reads
        cur["held"] = []; cur["held_updated_at"] = iso(now())
        cur["held_note"] = "no open live positions in " + os.path.basename(HELD_F) + ("" if os.path.exists(HELD_F) else " (file not present yet)")
        P.atomic_write(out_p, json.dumps(cur, indent=1)); print(json.dumps({"held": 0, "alerts": []})); return
    L = held_load(d)
    d, plan, posts, users, reads, run_dt, held, cas = L["d"], L["plan"], L["posts"], L["users"], L["reads"], L["run_dt"], L["held"], L["cas"]
    plist, authors, flags = L["plist"], L["authors"], L["flags"]
    hist_p = os.path.join(HERE, "held-history.jsonl")
    prev = {}
    for h in P.read_jsonl(hist_p):
        t = P.parse_ts(h.get("run_ts"))
        if t and timedelta(minutes=5) <= run_dt - t <= timedelta(minutes=60): prev[h["contract_address"]] = h   # latest wins
    obs = iso(run_dt); rows, hist_rows, alerts = [], [], []
    for h in held:
        ca = h["contract_address"]
        cp = [p for p in plist if ca in p["_coins"] and run_dt - p["_dt"] <= timedelta(minutes=15)]
        c60 = [p for p in plist if ca in p["_coins"]]
        qa = sorted({p["author_id"] for p in cp if P.is_quality(flags.get(p["author_id"], {"new"}))})
        n15 = len({p["author_id"] for p in cp})                     # distinct accounts, not raw posts
        pv = prev.get(ca); p15 = int(pv.get("negative_mentions_15m") or 0) if pv else 0
        jump = n15 >= 3 and n15 >= 2 * p15 + 2
        alert = len(qa) >= 2 or jump
        why = []
        if len(qa) >= 2: why.append(f"{len(qa)} distinct quality (aged, non-promo) accounts with negative posts in 15m")
        if jump: why.append(f"negative accounts/15m jumped {p15} -> {n15} vs previous run" + ("" if pv else " (no previous run in 60m)"))
        ev = [p["_url"] for p in sorted(cp, key=lambda p: (not P.is_quality(flags.get(p["author_id"], {"new"})), p["_dt"]))][:5]
        row = {"contract_address": ca, "ticker": h.get("ticker"), "observed_at": obs, "negative_mentions_15m": n15,
               "negative_quality_accounts": len(qa), "evidence": ev, "alert": bool(alert),
               "negative_posts_15m": len(cp), "negative_accounts_60m": len({p["author_id"] for p in c60}),
               "prev_negative_mentions_15m": p15 if pv else None, "alert_reason": "; ".join(why) or None,
               "stale": not reads, "entry_ts": h.get("entry_ts")}
        rows.append(row); hist_rows.append({"run_ts": obs, "contract_address": ca, "negative_mentions_15m": n15, "negative_quality_accounts": len(qa)})
        if alert: alerts.append(row)
    cur["held"] = rows; cur["held_updated_at"] = iso(now())
    cur["held_note"] = (f"{len(held)} open live positions; 1 X search for CA/$ticker + negative terms (60m window); "
                        "negative_mentions_15m = distinct accounts; alert = >=2 quality accounts or a jump to >=3 and >=2x+2 the previous run")
    P.atomic_write(out_p, json.dumps(cur, indent=1))
    done = {(r.get("run_ts"), r.get("step")) for r in P.read_jsonl(BUDGET)}
    if (plan["run_ts"], "held") not in done:
        if reads: P.append_lines(hist_p, hist_rows)
        if alerts: P.append_lines(os.path.join(HERE, "alerts.jsonl"), [dict(a, type="held_negative_wave") for a in alerts])
        budget_row(plan["run_ts"], "held", len(reads), min((r["day_left"] for r in reads), default=None), stale=not reads)
    if reads:
        P.safe_first_mentions(L["plist_all"], L["authors_all"], L["flags_all"], "held", L["run_all"],
                              {h["contract_address"]: h.get("ticker") for h in held})
    print(json.dumps({"held": len(rows), "alerts": alerts, "rows": [(r["ticker"], r["negative_mentions_15m"], r["negative_quality_accounts"]) for r in rows]}))

# ---------------------------------------------------------------- survival check (copycat / coordinated launch)
CA_IN_TEXT = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])([1-9A-HJ-NP-Za-km-z]{32,44})(?![1-9A-HJ-NP-Za-km-z])")
GENERIC = set("the and for you this that with coin token solana sol pump moon cat dog ai inu meme memes new gem send buy sell "
              "official real just love life money time world king queen baby elon trump pepe doge".split())

def cmd_xcheck_prep():
    run_ts = now().strftime("%Y%m%dT%H%M%SZ")
    pend = pending_xcheck()[:XCHECK_COINS]
    if not pend:
        print(json.dumps({"dir": None, "coins": 0, "note": "nothing pending"})); return
    info = ds_tokens([c["mint"] for c in pend])
    d = os.path.join(HERE, "raw", run_ts + "-xcheck"); os.makedirs(d, exist_ok=True)
    coins = []
    for c in pend:
        a = info.get(c["mint"], {})
        tk = (c.get("ticker") or a.get("ticker") or "").strip()
        nm = (c.get("name") or a.get("name") or "").strip()
        created = datetime.fromtimestamp(a["pair_created_ms"] / 1000, timezone.utc) if a.get("pair_created_ms") else None
        start = max(now() - timedelta(hours=24), (created - timedelta(minutes=10)) if created else now() - timedelta(hours=24))
        sub = os.path.join(d, c["mint"]); os.makedirs(sub, exist_ok=True)
        base = {"max_results": 25, "sort_order": "recency", "post.fields": POST_FIELDS, "user.fields": USER_FIELDS, "expansions": "author_id"}
        calls = [{"file": "c1_ca.json", "tool": "search_posts_all", "args": dict(base, query=c["mint"] + P.QUERY_SUFFIX, start_time=iso(start))}]
        if re.fullmatch(r"[A-Za-z0-9]{2,12}", tk):
            calls.append({"file": "c2_ticker.json", "tool": "search_posts_all",
                          "args": dict(base, query=f"{tk} ({XC_CONTEXT})" + P.QUERY_SUFFIX, start_time=iso(now() - timedelta(hours=24)))})
        nmq = re.sub(r"[^A-Za-z0-9 ]", " ", nm).strip()
        if len(nmq) >= 4 and nmq.lower() != tk.lower() and nmq.lower() not in GENERIC:
            calls.append({"file": "c3_name.json", "tool": "search_posts_all", "when": "only if c2 found < 20 posts (max 25) or was skipped",
                          "args": dict(base, query=f'"{nmq}"' + P.QUERY_SUFFIX, start_time=iso(now() - timedelta(hours=24)))})
        if created:
            calls.append({"file": "c4_launch.json", "tool": "search_posts_all",
                          "when": "only if c1 returned 25 posts (the per-call max) and its oldest post is later than launch+60m (launch window not covered)",
                          "args": dict(base, query=c["mint"] + P.QUERY_SUFFIX, start_time=iso(created - timedelta(minutes=10)),
                                       end_time=iso(min(now() - timedelta(seconds=30), created + timedelta(minutes=60))))})
        calls = calls[:XCHECK_PER_COIN]
        coin = dict(c, ticker=tk, name=nm, pair_created_at=iso(created) if created else None, liq=a.get("liq"), mcap=a.get("mcap"),
                    calls=calls, dir=sub)
        P.atomic_write(os.path.join(sub, "plan.json"), json.dumps(coin, indent=1))
        coins.append(coin)
    P.atomic_write(os.path.join(d, "plan.json"), json.dumps({"run_ts": run_ts, "step": "xcheck", "coins": coins}, indent=1))
    print(json.dumps({"dir": d, "coins": [{"mint": c["mint"], "ticker": c["ticker"], "calls": [x["file"] for x in c["calls"]]} for c in coins]}, indent=1))

def cmd_xcheck_cond(d):
    d = os.path.abspath(d) if os.path.isdir(d) else os.path.join(HERE, "raw", d)
    plan = json.load(open(os.path.join(d, "plan.json")))
    res = {}
    for c in plan["coins"]:
        need = []
        c2 = os.path.join(c["dir"], "c2_ticker.json")
        n2 = len((P.load_raw(c2)[0].get("data") or [])) if os.path.exists(c2) else 0
        if any(x["file"] == "c3_name.json" for x in c["calls"]) and n2 < 20: need.append("c3_name.json")
        c1 = os.path.join(c["dir"], "c1_ca.json")
        if os.path.exists(c1) and c.get("pair_created_at") and any(x["file"] == "c4_launch.json" for x in c["calls"]):
            data = P.load_raw(c1)[0].get("data") or []
            oldest = min((P.parse_ts(p["created_at"]) for p in data), default=None)
            if len(data) >= 25 and oldest and oldest > P.parse_ts(c["pair_created_at"]) + timedelta(minutes=60): need.append("c4_launch.json")
        res[c["mint"]] = need
    print(json.dumps(res))

def coordinated_clusters(posts, authors):
    """near-identical text (Jaccard >= 0.6) across distinct authors within 10 minutes."""
    ps = [p for p in posts if len(p["_norm"]) >= 4]
    ps.sort(key=lambda p: p["_dt"])
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a: a = parent[a]
        return a
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            if (ps[j]["_dt"] - ps[i]["_dt"]) > timedelta(minutes=10): break
            if ps[i]["author_id"] != ps[j]["author_id"] and P.jacc(ps[i]["_norm"], ps[j]["_norm"]) >= 0.6:
                parent[find(ps[i]["id"])] = find(ps[j]["id"])
    cl = {}
    for p in ps:
        if p["id"] in parent: cl.setdefault(find(p["id"]), []).append(p)
    out = []
    for members in cl.values():
        accs = {p["author_id"] for p in members}
        weak = {a for a in accs if (authors.get(a, {}).get("age_days") is None or authors[a]["age_days"] < 90)
                or (authors.get(a, {}).get("followers") or 0) < 100}
        span = (max(p["_dt"] for p in members) - min(p["_dt"] for p in members)).total_seconds() / 60
        out.append({"accounts": len(accs), "weak_accounts": len(weak), "span_min": round(span, 1),
                    "urls": [p["_url"] for p in members][:4], "first": iso(min(p["_dt"] for p in members))})
    return sorted(out, key=lambda c: -c["accounts"])

def cmd_xcheck_merge(d):
    d = os.path.abspath(d) if os.path.isdir(d) else os.path.join(HERE, "raw", d)
    plan = json.load(open(os.path.join(d, "plan.json")))
    done = {r.get("mint") for r in P.read_jsonl(os.path.join(INTEL, "xcheck.jsonl"))}
    rows, total_reads, rl = [], 0, None
    for c in plan["coins"]:
        mint = c["mint"]
        posts, users, reads, _ = load_dir_posts(c["dir"])
        total_reads += len(reads)
        rl = min([r["day_left"] for r in reads] + ([rl] if rl is not None else []), default=rl)
        if mint in done or not reads:
            continue
        run_dt = max([P.parse_ts(p["created_at"]) for p in posts.values()] + [now()])
        cas_seen = {}
        plist = prep_posts(posts, users, [mint], [c.get("ticker") or ""], lambda txt: [mint] if mint in txt else [])
        authors = {aid: P.author_profile(u, run_dt) for aid, u in users.items()}
        flags = P.classify_authors(plist, authors, run_dt)
        ours = [p for p in plist if mint in (p.get("text") or "")]
        our_acc = {p["author_id"] for p in ours}
        our_q = {a for a in our_acc if P.is_quality(flags.get(a, {"new"}))}
        for p in plist:
            if p["_file"] not in ("c2_ticker.json", "c3_name.json"): continue
            for ca in set(CA_IN_TEXT.findall(p.get("text") or "")):
                if ca == mint or ca in NON_MINTS or not P.valid_ca(ca): continue
                e = cas_seen.setdefault(ca, {"accs": set(), "q": set(), "urls": []})
                e["accs"].add(p["author_id"]); e["urls"].append(p["_url"])
                if P.is_quality(flags.get(p["author_id"], {"new"})): e["q"].add(p["author_id"])
        top_other = sorted(cas_seen.items(), key=lambda kv: -len(kv[1]["accs"]))[:10]
        ds = ds_tokens([ca for ca, _ in top_other]) if top_other else {}
        tk = (c.get("ticker") or "").lower(); nm = (c.get("name") or "").lower()
        same = []
        for ca, e in top_other:
            a = ds.get(ca)
            if a and ((tk and (a.get("ticker") or "").lower() == tk) or (nm and (a.get("name") or "").lower() == nm)):
                same.append((ca, e, a))
        copycat, copy_clear, ev = False, False, []
        for ca, e, a in same:
            n, nq = len(e["accs"]), len(e["q"])
            if n >= 3 and n >= 2 * max(1, len(our_acc)):
                copycat = True
                copy_clear = copy_clear or (n >= 5 and nq >= 2 and len(our_acc) * 3 <= n)
            ev.append(f"same-ticker CA {ca[:8]}.. ({a.get('ticker')}, liq ${a.get('liq') or 0:,.0f}) in {n} accts/{nq} quality vs ours "
                      f"{len(our_acc)}/{len(our_q)}: {' '.join(e['urls'][:2])}")
        cl = coordinated_clusters(ours, authors)
        coordinated, coord_clear = False, False
        if cl:
            c0 = cl[0]
            if c0["accounts"] >= 5 and c0["weak_accounts"] >= 0.6 * c0["accounts"]:
                coordinated = True
                coord_clear = c0["accounts"] >= 8 or c0["weak_accounts"] >= 0.8 * c0["accounts"]
            if c0["accounts"] >= 3:
                ev.append(f"near-identical text: {c0['accounts']} accts ({c0['weak_accounts']} new/low-follower) within {c0['span_min']} min "
                          f"from {c0['first']}: {' '.join(c0['urls'][:3])}")
        weak_signal = any(len(e["accs"]) >= 2 for _, e, _ in same) or (cl and cl[0]["accounts"] >= 3)
        verdict = "block" if (copy_clear or coord_clear) else "caution" if (copycat or coordinated or weak_signal) else "ok"
        summary = (f"{len(ours)} posts/{len(our_acc)} accts ({len(our_q)} quality) mention our CA; {len(cas_seen)} other CAs in ticker/name "
                   f"posts, {len(same)} with same ticker/name on DexScreener.")
        if not plist: summary = "0 posts found for CA/ticker/name in the searched window."
        rows.append({"mint": mint, "checked_at": iso(now()), "copycat": copycat, "coordinated": coordinated,
                     "evidence": (summary + " " + " | ".join(ev))[:900], "verdict": verdict,
                     "ticker": c.get("ticker"), "name": c.get("name"), "source": c.get("source"), "reads_used": len(reads),
                     "pair_created_at": c.get("pair_created_at"), "posts_seen": len(plist)})
    if rows: P.append_lines(os.path.join(INTEL, "xcheck.jsonl"), rows)
    bdone = {(r.get("run_ts"), r.get("step")) for r in P.read_jsonl(BUDGET)}
    if (plan["run_ts"], "xcheck") not in bdone:
        budget_row(plan["run_ts"], "xcheck", total_reads, rl, coins=len(plan["coins"]))
    print(json.dumps({"checked": [(r["ticker"], r["verdict"], r["copycat"], r["coordinated"]) for r in rows], "reads": total_reads,
                      "reads_left_today": rl}))

# ---------------------------------------------------------------- Reddit side experiment (no X)
REDDIT_URLS = ["https://www.reddit.com/r/all/rising.json?limit=100", "https://www.reddit.com/r/popular.json?limit=100",
               "https://www.reddit.com/r/memes/rising.json?limit=50"]
STOP = set("""the a an and or but if of to in on at by for with from up down out over under again further then once here there when
where why how all any both each few more most other some such no nor not only own same so than too very can will just don should now
this that these those what which who whom is are was were be been being have has had having do does did doing i me my we our you your
he him his she her it its they them their about after before into through during above below between ever never new old good bad best
first last next one two three four five year years day days time today people man woman men women guy guys girl girls kid kids life
world thing things way made make like look looks looking got get gets going went said says say know think want need really still
cat cats dog dogs meme memes coin token pump moon crypto solana bitcoin happy found finally actually always every someone something
nothing everyone anyone because while until since back front little big small long great right left home work help used using
reddit post posts thread comment comments video pic picture photo image til psa ama oc update""".split())

def reddit_state():
    return load_json(os.path.join(HERE, "reddit-state.json"), {}) or {}

def save_reddit_state(st):
    P.atomic_write(os.path.join(HERE, "reddit-state.json"), json.dumps(st, indent=0))

def notes_reddit_status(text):
    npath = os.path.join(INTEL, "NOTES.md")
    body = open(npath).read() if os.path.exists(npath) else ""
    a, b = "<!-- reddit-status -->", "<!-- /reddit-status -->"
    block = f"{a}\nReddit side experiment status ({iso(now())}): {text}\n{b}"
    body = re.sub(re.escape(a) + r".*?" + re.escape(b), lambda m: block, body, flags=re.S) if a in body else body.rstrip("\n") + "\n\n" + block + "\n"
    P.atomic_write(npath, body)

_COMMON = None
def common_words():
    """Top-10k English words (google-10000-english, saved locally in x-pulse/common-words.txt). Single-word keywords that are
    ordinary English are dropped so 'monday'/'meeting' can't match random pump.fun names."""
    global _COMMON
    if _COMMON is None:
        try: _COMMON = {w.strip().lower() for w in open(os.path.join(HERE, "common-words.txt")) if w.strip()}
        except Exception: _COMMON = set()
    return _COMMON

def keywords(title):
    t = re.sub(r"https?://\S+", " ", title)
    words = re.findall(r"[A-Za-z][A-Za-z']{2,}", t)
    out = []
    for w in words:
        lw = w.lower().strip("'")
        if len(lw) >= 4 and lw not in STOP and lw not in common_words() and lw.isalpha(): out.append(lw)
    # capitalised bigrams ("Moo Deng" -> "moodeng")
    for a, b in re.findall(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b", t):
        if a.lower() not in STOP and b.lower() not in STOP: out.append(f"{a} {b}".lower())
    return list(dict.fromkeys(out))

def strict_match(kw, sym, name):
    s = re.sub(r"[^a-z0-9]", "", (sym or "").lower())
    n = (name or "").lower()
    kwn = re.sub(r"[^a-z0-9]", "", kw)
    if s == kwn: return True
    if re.sub(r"[^a-z0-9]", "", n) == kwn: return True
    if " " in kw:   # proper-noun phrase ("barry bag"): whole-phrase containment in the token name
        return bool(re.search(r"(?<![a-z0-9'])" + re.escape(kw) + r"(?![a-z0-9'])", n))
    # whole-word containment only for distinctive (non-dictionary) keywords of >= 5 chars
    return len(kw) >= 5 and kw not in common_words() and bool(re.search(r"(?<![a-z0-9'])" + re.escape(kw) + r"(?![a-z0-9'])", n))

def cmd_reddit(args):
    dry = "--dry-run" in args
    fixture = args[args.index("--fixture") + 1] if "--fixture" in args else None
    st = reddit_state()
    boff = P.parse_ts(st.get("backoff_until"))
    if boff and boff > now() and not fixture:
        print(json.dumps({"reddit": "backoff", "until": st["backoff_until"]})); return
    ts = iso(now()); posts, errors = [], []
    if fixture:
        for ch in (load_json(fixture, {}) or {}).get("data", {}).get("children", []): posts.append(ch.get("data") or {})
    else:
        for i, u in enumerate(REDDIT_URLS):
            try:
                d = http_json(u, ua=UA_REDDIT, timeout=15)
                posts += [ch.get("data") or {} for ch in (d.get("data") or {}).get("children", [])]
            except urllib.error.HTTPError as e:
                errors.append(f"{u} HTTP {e.code}")
                if e.code in (403, 429): break
            except Exception as e:
                errors.append(f"{u} {type(e).__name__}: {str(e)[:120]}"); break
            time.sleep(2)
    if errors and not posts:
        hours = 2 if any("429" in e for e in errors) else 6
        st["backoff_until"] = iso(now() + timedelta(hours=hours)); st["last_run"] = ts
        st.setdefault("errors", []).append({"ts": ts, "errors": errors}); st["errors"] = st["errors"][-20:]
        if not dry:
            save_reddit_state(st)
            notes_reddit_status(f"BLOCKED/FAILED from this box ({'; '.join(errors)}). Backing off {hours}h until {st['backoff_until']}. "
                                "No workaround (no proxies, alternate hosts or logins) by design.")
        print(json.dumps({"reddit": "error", "errors": errors, "backoff_h": hours})); return
    seen = st.get("seen", {})
    mem_rows, cands = [], {}
    for p in posts:
        pid = p.get("name") or p.get("id")
        if not pid or p.get("over_18"): continue
        cu = float(p.get("created_utc") or 0)
        age_h = max(0.1, (now().timestamp() - cu) / 3600) if cu else None
        score = int(p.get("score") or 0)
        prev = seen.get(pid)
        first_seen = prev["first_seen"] if prev else ts
        delta = (score - prev["score"]) if prev else None
        vel = {"score_per_h": round(score / age_h, 1) if age_h else None, "score_change_since_last_seen": delta,
               "last_seen": prev.get("ts") if prev else None}
        mem_rows.append({"ts": ts, "reddit_id": pid, "title": (p.get("title") or "")[:300], "subreddit": p.get("subreddit"), "score": score,
                         "num_comments": p.get("num_comments"), "created_utc": cu, "velocity": vel,
                         "permalink": "https://www.reddit.com" + (p.get("permalink") or ""), "first_seen": first_seen})
        seen[pid] = {"first_seen": first_seen, "score": score, "ts": ts, "title": (p.get("title") or "")[:200]}
        for kw in keywords(p.get("title") or ""):
            c = cands.setdefault(kw, {"vel": 0, "posts": []})
            c["vel"] = max(c["vel"], vel["score_per_h"] or 0); c["posts"].append((pid, first_seen, (p.get("title") or "")[:200]))
    top = sorted(cands.items(), key=lambda kv: -kv[1]["vel"])[:12]
    matched_before = set(tuple(x) for x in st.get("matched", []))
    matches = []
    for kw, c in top:
        for pr in ds_search(kw):
            if pr.get("chainId") != "solana": continue
            bt = pr.get("baseToken") or {}
            pc = pr.get("pairCreatedAt")
            if not pc or now().timestamp() * 1000 - pc > 48 * 3600 * 1000: continue
            if not strict_match(kw, bt.get("symbol"), bt.get("name")): continue
            for pid, first_seen, title in c["posts"][:3]:
                key = (pid, pr.get("pairAddress"))
                if key in matched_before: continue
                matched_before.add(key)
                pcdt = datetime.fromtimestamp(pc / 1000, timezone.utc)
                matches.append({"ts": ts, "reddit_id": pid, "reddit_title": title, "reddit_first_seen": first_seen,
                                "pair_address": pr.get("pairAddress"), "token": bt.get("address"), "symbol": P.clean(bt.get("symbol"), 20),
                                "name": P.clean(bt.get("name")), "pair_created_at": iso(pcdt), "mcap": pr.get("marketCap") or pr.get("fdv"),
                                "liq": (pr.get("liquidity") or {}).get("usd"), "keyword": kw,
                                "lead_minutes": round((P.parse_ts(first_seen) - pcdt).total_seconds() / 60, 1)})
        time.sleep(0.4)
    cutoff = now() - timedelta(hours=48)
    st["seen"] = {k: v for k, v in seen.items() if (P.parse_ts(v.get("ts")) or now()) > cutoff}
    st["matched"] = [list(k) for k in list(matched_before)[-2000:]]
    st["last_run"] = ts; st.pop("backoff_until", None)
    if dry:
        print(json.dumps({"dry_run": True, "posts": len(mem_rows), "keywords_top": [k for k, _ in top], "matches": matches[:10]}, indent=1)); return
    P.append_lines(os.path.join(INTEL, "reddit-memes.jsonl"), mem_rows)
    if matches: P.append_lines(os.path.join(INTEL, "reddit-matches.jsonl"), matches)
    save_reddit_state(st)
    notes_reddit_status(f"OK: {len(mem_rows)} posts, {len(top)} keywords searched on DexScreener, {len(matches)} new matches"
                        + (f"; partial errors: {'; '.join(errors)}" if errors else ""))
    print(json.dumps({"reddit": "ok", "posts": len(mem_rows), "keywords": [k for k, _ in top], "matches": len(matches), "errors": errors}))

def cmd_budget():
    day = now().strftime("%Y-%m-%d"); by = {}
    for r in P.read_jsonl(BUDGET):
        if str(r.get("ts", "")).startswith(day): by[r.get("step", "core")] = by.get(r.get("step", "core"), 0) + int(r.get("reads_used") or 0)
    print(json.dumps({"day": day, "total": sum(by.values()), "by_step": by}))

def main(cmd, args):
    if cmd == "midcap-prep": cmd_midcap_prep()
    elif cmd == "midcap-merge": cmd_midcap_merge(args[0] if args and not args[0].startswith("--") else "", stale="--stale" in args)
    elif cmd == "xcheck-prep": cmd_xcheck_prep()
    elif cmd == "xcheck-cond": cmd_xcheck_cond(args[0])
    elif cmd == "xcheck-merge": cmd_xcheck_merge(args[0])
    elif cmd == "reddit": cmd_reddit(args)
    elif cmd == "budget": cmd_budget()
    elif cmd == "held-prep": cmd_held_prep()
    elif cmd == "held-merge": cmd_held_merge(args[0] if args else "")
    elif cmd == "context": cmd_context()
    elif cmd == "board": cmd_board(args)
