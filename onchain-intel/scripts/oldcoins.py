#!/usr/bin/env python3
"""
oldcoins.py - Scout READ-ONLY intel for Chunk's OLDER-COINS book.  Never trades, signs, or touches keys.

Writes /workspace/onchain-intel/oldcoins-intel.json (atomic tmp+rename) and appends
data/oldcoins_history.jsonl.  State for incremental hourly runs: data/oldcoins_state.json.

Universe: Solana tokens whose earliest DexScreener pair is >= 7 d old, mcap (fallback FDV) $5M-$200M,
liquidity (sum over the token's pairs) >= $500k; top ~30 by 24h volume.  Candidates from GeckoTerminal
(top pools by 24h volume + trending, 4 calls), DexScreener (boosts/search), and Chunk's own
live/oldcoins-universe.json (read only).  Stables, SOL wrappers/LSTs, bridged majors and tokenized stocks excluded.

Per token (free sources first):
  holders   rugcheck.xyz report topHolders (top 20 token accounts + owner).  Public RPC refuses
            getTokenLargestAccounts, so Helius is used for it only as a fallback when credits allow.
            Owner excluded as pool/vault/program when: (a) owner is OFF the ed25519 curve (a PDA, so
            program-controlled: AMM authorities, lockers, vaults), or (b) owner account is owned by a
            program other than the System Program (public getMultipleAccounts), or (c) owner/token account
            is a pool vault/authority in rugcheck markets/lockers/knownAccounts, or (d) burn/incinerator.
            On-curve system wallets holding > 20k SOL are flagged 'custodial?' (heuristic for CEX hot
            wallets) and reported separately; top10_share_ex_pools includes them, *_ex_custodial does not.
  smart     wallets from smart_wallets.json (smart), wallets.csv (profitable: realized_pnl > 0),
            copyfomo leader wallets (data/leader_mappings.json, data/trader_wallets.json).  For each wallet
            the mint's ATA is derived locally; balances via public getMultipleAccounts; recent swaps via
            getSignaturesForAddress(ATA) + getTransaction (public RPC, cached).  Net USD = token delta x price.
  sells     top-10 holder token accounts and the creator's ATA: txs in the last 6h, token outflow with
            SOL/WSOL/USDC/USDT proceeds = sell, without = transfer.
  LP        DexScreener total liquidity vs previous runs (history); price-adjusted change =
            liq_ratio / sqrt(price_ratio) - 1 (constant-product approximation).  <= -20% = LP pull.
  avoid     creator (rugcheck) or top-10 wallet owners in avoid.csv / known_ruggers.json / known_funders.csv.
Credits: Helius only as fallback; <= 1500 credits/run and never past 30k/day (all of Scout's usage, from
data/rpc_calls.log).  Otherwise credit_mode = free_only.
"""
import csv, json, math, os, sys, time, urllib.request, urllib.error, concurrent.futures as cf
from datetime import datetime, timezone

BASE = "/workspace/onchain-intel"
sys.path.insert(0, os.path.join(BASE, "scripts"))
from pda import b58d, b58e, on_curve, find_pda   # pure python, no deps

OUT = os.path.join(BASE, "oldcoins-intel.json")
HIST = os.path.join(BASE, "data", "oldcoins_history.jsonl")
STATE_F = os.path.join(BASE, "data", "oldcoins_state.json")
SEED_F = os.path.join(BASE, "data", "oldcoins_seed.json")
CACHE = os.path.join(BASE, "data", "oldcoins_cache")
TXCACHE = os.path.join(BASE, "data", "txcache")
LOG = os.path.join(BASE, "data", "rpc_calls.log")
RUNLOG = os.path.join(BASE, "data", "oldcoins.log")
LIVE = "/workspace/runner-radar/live"
HELD_F = os.path.join(LIVE, "oldcoins-live.jsonl")
PAPER_F = os.path.join(LIVE, "oldcoins-positions.json")
CHUNK_UNI = os.path.join(LIVE, "oldcoins-universe.json")
PAPER_LOG = os.path.join(LIVE, "oldcoins-paper.jsonl")
TEAM_BOARD = "/workspace/commander/TEAM-BOARD.md"
COPYFOMO_LOG = "/workspace/copyfomo/x-watch-log.md"
SELFCOPY_STATE = "/workspace/selfcopy/state.json"
SELFCOPY_TRADES = "/workspace/selfcopy/live-trades.jsonl"
for d in (CACHE, TXCACHE): os.makedirs(d, exist_ok=True)

CFG = dict(min_age_d=3, min_mcap=3e6, max_mcap=1e9, min_liq=300e3, min_vol24=750e3, top_n=None,
           rotate_n=8, hyp_public_call_cap=700, hyp_mint_ttl_s=6 * 3600, fresh_days=7, hyp_sig_pages=2, light_rugcheck_ttl_s=3 * 3600, setup_window_s=3600,
           run_credit_cap=1500, daily_budget=30000, enhanced_credits=100,
           tx_parse_cap=300, per_acct_parse=6, sig_limit=20, window_h=6,
           custodial_sol=20000, rugcheck_ttl_s=50 * 60, max_runtime_s=1500)
SYSTEM = "11111111111111111111111111111111"
ATA_PROG = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
TOKEN_PROG = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
BURN = {"1nc1nerator11111111111111111111111111111111", SYSTEM}
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"; USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
QUOTES = {WSOL, USDC, USDT}
EXCL_SYM = {s.upper() for s in """SOL WSOL USDC USDT PYUSD USDS USDE USDH UXD USDY DAI FDUSD TUSD USD1 USDG EURC EURI
EUROE FRAX USDC.E USDT.E SUSD SUSDE USX USDB AUSD HYUSD USDO USDU USR CASH ONYC MSOL JITOSOL BSOL JUPSOL INF HSOL
STSOL LAINESOL BNSOL DSOL VSOL PICOSOL HUBSOL STRONGSOL COMPASSSOL EDGESOL BONKSOL CGNTSOL JSOL LST SSOL FPSOL
ADRASOL PATHSOL BBSOL PSOL XSOL CBSOL WBTC CBBTC WETH ETH BTC ZBTC TBTC XBTC FBTC LBTC SOBTC WBNB BNB WAVAX WMATIC
WSTETH STETH XAUT PAXG ZEC WZEC HYPE WHYPE NEAR WNEAR TRX USDV JLP JUPSOL""".split()}
EXCL_NAME = ("staked sol", "liquid staking", "wrapped", "bridged", "(wormhole)", "(portal)", "xstock", "tokenized",
             "usd coin", "tether", "stablecoin", "common stock", "securities", " etf")
T0 = time.time(); NOW = int(T0)
def iso(t=None): return datetime.fromtimestamp(t if t is not None else time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True)
    try: open(RUNLOG, "a").write(iso() + " " + s + "\n")
    except Exception: pass

# ---------------------------------------------------------------- HTTP (free sources)
_last = {}
def http_json(url, gap=1.0, tries=3, timeout=40, headers=None):
    host = url.split("/")[2]
    for a in range(tries):
        w = _last.get(host, 0) + gap - time.time()
        if w > 0: time.sleep(w)
        _last[host] = time.time()
        try:
            h = {"User-Agent": "scout-oldcoins/1.0 (read-only)", "Accept": "application/json"}
            h.update(headers or {})
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout).read())
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(3 * (a + 1) if e.code == 429 else 1.5)
        except Exception:
            time.sleep(1.5 * (a + 1))
    return None

# ---------------------------------------------------------------- credit budget
def _helius_key():
    k = os.environ.get("HELIUS_API_KEY")
    fn = "/home/box/.scout-secrets/helius.env"
    if not k and os.path.exists(fn):
        for line in open(fn):
            line = line.strip().replace("export ", "", 1)
            if line.startswith("HELIUS_API_KEY="): k = line.split("=", 1)[1].strip().strip('"').strip("'")
    return k or None
def credits_today():
    day = time.strftime("%Y-%m-%d", time.gmtime()); tot = 0
    try:
        for l in open(LOG):
            p = l.split()
            if len(p) != 3: continue
            try:
                d = p[0] if "-" in p[0] else time.strftime("%Y-%m-%d", time.gmtime(int(p[0])))
                if d != day: continue
                n = int(p[2]); tot += n * CFG["enhanced_credits"] if p[1] == "helius-enhanced" else n
            except Exception: continue
    except FileNotFoundError: pass
    return tot
DAY_USED = credits_today()
RUN_CAP = max(0, min(CFG["run_credit_cap"], CFG["daily_budget"] - DAY_USED))
KEY = _helius_key()
CREDIT_MODE = "full" if (KEY and RUN_CAP > 0) else "free_only"
USED = [0]
HELIUS = ("https://mainnet.helius-rpc.com/?api-key=" + KEY) if KEY else None
PUBLIC = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]
STATS = {"public_rpc": 0, "public_fail": 0, "helius": 0}
def _charge(n, kind="oldcoins-rpc"):
    USED[0] += n
    try: open(LOG, "a").write(f"{int(time.time())} {kind} {n}\n")    # count only; never the URL/key
    except Exception: pass
_pi = [0]
import threading
_rl = threading.Lock()
GAP = {PUBLIC[0]: 0.3, PUBLIC[1]: 0.12}
def _wait(url):
    with _rl:
        w = _last.get(url, 0) + GAP.get(url, 0.3) - time.time()
        _last[url] = max(time.time(), _last.get(url, 0) + GAP.get(url, 0.3))
    if w > 0: time.sleep(w)
def rpc(method, params, helius_ok=True, public=True):
    if public:
        for a in range(3):
            url = PUBLIC[(_pi[0] + a) % 2]
            _wait(url)
            try:
                STATS["public_rpc"] += 1
                r = json.loads(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": "scout-oldcoins/1.0"}), timeout=30).read())
                if "result" in r: _pi[0] += 1; return r["result"]
            except Exception: pass
            STATS["public_fail"] += 1; time.sleep(0.4 * (a + 1))
    if helius_ok and CREDIT_MODE == "full" and USED[0] + 1 <= RUN_CAP:
        for a in range(2):
            try:
                time.sleep(0.15); _charge(1); STATS["helius"] += 1
                r = json.loads(urllib.request.urlopen(urllib.request.Request(HELIUS, data=json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                    headers={"Content-Type": "application/json"}), timeout=30).read())
                if "result" in r: return r["result"]
            except Exception: pass
    return None

def get_tx(sig, helius_ok=True):
    fn = os.path.join(TXCACHE, sig + ".json")
    if os.path.exists(fn):
        try: return json.load(open(fn))
        except Exception: pass
    r = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}], helius_ok=helius_ok)
    if r:
        try: json.dump(r, open(fn, "w"))
        except Exception: pass
    return r

def multi_accounts(addrs, parsed=True):
    out = {}
    for i in range(0, len(addrs), 100):
        chunk = addrs[i:i + 100]
        opt = {"encoding": "jsonParsed"} if parsed else {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}
        r = rpc("getMultipleAccounts", [chunk, opt])
        if r is None: continue
        for a, v in zip(chunk, r["value"]): out[a] = v
    return out

def ata(owner, mint, prog):
    try: return find_pda([b58d(owner).rjust(32, b"\0"), b58d(prog).rjust(32, b"\0"), b58d(mint).rjust(32, b"\0")], ATA_PROG)[0]
    except Exception: return None
def is_on_curve(addr):
    try: return on_curve(b58d(addr).rjust(32, b"\0"))
    except Exception: return False

# ---------------------------------------------------------------- reference lists
def load_avoid():
    s = {}
    try:
        for r in csv.DictReader(open(os.path.join(BASE, "avoid.csv"))):
            if r.get("address"): s[r["address"]] = "avoid.csv: " + (r.get("reason") or "")[:80]
    except Exception: pass
    try:
        k = json.load(open(os.path.join(BASE, "known_ruggers.json")))
        for a, v in (k.get("wallets") or {}).items(): s.setdefault(a, "known_ruggers.json: " + str(v.get("role", ""))[:60])
        f = k.get("funders") or {}
        for a in (f.keys() if isinstance(f, dict) else [x.get("address") for x in f if isinstance(x, dict)]):
            if a: s.setdefault(a, "known_ruggers.json funder")
    except Exception: pass
    try:
        for r in csv.DictReader(open(os.path.join(BASE, "known_funders.csv"))):
            if r.get("address"): s.setdefault(r["address"], f"known_funders.csv: funded {r.get('n_ruggers_funded')} ruggers ({r.get('strength')})")
    except Exception: pass
    return s
def load_smart():
    w = {}
    try:
        d = json.load(open(os.path.join(BASE, "smart_wallets.json")))
        for a, v in (d.get("smart") or {}).items(): w[a] = "smart_wallets.json"
    except Exception: pass
    try:
        for r in csv.DictReader(open(os.path.join(BASE, "wallets.csv"))):
            pnl = (r.get("realized_pnl") or "").strip()
            if pnl.startswith("+") and not pnl.startswith("+0.000") and "unprofitable" not in r.get("type", ""):
                w.setdefault(r["address"], "wallets.csv: " + r["type"].split(" [")[0][:50])
    except Exception: pass
    try:
        m = json.load(open(os.path.join(BASE, "data", "leader_mappings.json")))
        for h, v in m.items():
            if isinstance(v, dict) and v.get("wallet"): w.setdefault(v["wallet"], f"copyfomo leader {h} ({v.get('confidence')})")
    except Exception: pass
    try:
        t = json.load(open(os.path.join(BASE, "data", "trader_wallets.json")))
        for h, v in t.items():
            if isinstance(v, dict) and v.get("solana"): w.setdefault(v["solana"], f"copyfomo trader {h}")
    except Exception: pass
    return {a: s for a, s in w.items() if 32 <= len(a) <= 44}

def load_held():
    """Chunk's LIVE holdings from oldcoins-live.jsonl (format unknown until Chunk writes it: tolerate
    any JSON lines with address/mint/token_address; entry/buy/open adds, exit/sell/close removes)."""
    held, status = {}, "missing"
    if os.path.exists(HELD_F):
        status = "empty"
        for line in open(HELD_F):
            try: e = json.loads(line)
            except Exception: continue
            m = e.get("address") or e.get("mint") or e.get("token_address") or e.get("ca")
            if not m: continue
            status = "ok"
            ev = str(e.get("event") or e.get("action") or e.get("side") or "").lower()
            if ev in ("exit", "sell", "close", "closed", "stop", "sold", "eod_close"): held.pop(m, None)
            else: held[m] = e.get("token") or e.get("symbol") or "?"
    paper = {}
    try:
        for p in json.load(open(PAPER_F)).get("positions") or []:
            m = p.get("address") or p.get("mint")
            if m: paper[m] = p.get("token") or "?"
    except Exception: pass
    return held, paper, status

B58 = r"[1-9A-HJ-NP-Za-km-z]{32,44}"
def _ts(v):
    try: return datetime.strptime(str(v)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except Exception: return None

def load_setups():
    """Tier 2: any event (entry/setup/filtered/exit...) for a token in Chunk's paper or live jsonl in the last hour."""
    out = {}
    for fn, book in ((PAPER_LOG, "paper"), (HELD_F, "live")):
        try:
            for line in open(fn):
                try: e = json.loads(line)
                except Exception: continue
                m = e.get("address") or e.get("mint") or e.get("token_address") or e.get("ca"); t = _ts(e.get("ts") or e.get("time"))
                if m and t and NOW - t <= CFG["setup_window_s"]:
                    out.setdefault(m, {"symbol": e.get("token") or e.get("symbol") or "?", "events": []})["events"].append(f"{book}:{e.get('event')}@{e.get('ts')}")
        except FileNotFoundError: pass
    return out

def load_copycat():
    """Tier 3: tokens held by Copycat's copies. Sources (read-only, best effort):
    selfcopy/state.json open positions; selfcopy/live-trades.jsonl buy/sell events with a mint;
    the latest Copycat status in copyfomo/x-watch-log.md and commander/TEAM-BOARD.md (only if it reports >0 open,
    mints taken from 'CA <mint>' mentions, symbols resolved through CA mentions in the same files)."""
    import re
    held, notes = {}, []
    try:
        for p in json.load(open(SELFCOPY_STATE)).get("positions") or []:
            if p.get("mint") and str(p.get("status", "open")).lower() == "open":
                held.setdefault(p["mint"], {"symbol": p.get("symbol") or "?", "sources": []})["sources"].append("selfcopy/state.json open position (leader " + str(p.get("leader")) + ")")
    except Exception as ex: notes.append(f"selfcopy/state.json unreadable: {ex}")
    try:
        pos = {}
        for line in open(SELFCOPY_TRADES):
            try: e = json.loads(line)
            except Exception: continue
            m = e.get("mint"); ev = str(e.get("event") or e.get("side") or "").lower()
            if not m: continue
            if ev in ("buy", "entry", "open", "fill"): pos[m] = e.get("symbol") or "?"
            elif ev in ("sell", "exit", "close", "closed"): pos.pop(m, None)
        for m, sy in pos.items(): held.setdefault(m, {"symbol": sy, "sources": []})["sources"].append("selfcopy/live-trades.jsonl net open")
    except FileNotFoundError: notes.append("selfcopy/live-trades.jsonl missing")
    ca_sym, txt_all = {}, ""
    for fn in (COPYFOMO_LOG, TEAM_BOARD):
        try: txt_all += open(fn).read() + "\n"
        except Exception: notes.append(f"{fn} unreadable")
    sym_ca = {}
    for mo in re.finditer(r"\bCA\s+(" + B58 + ")", txt_all):
        win = txt_all[max(0, mo.start() - 120):mo.start()]
        for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,20}", win): sym_ca[w.lower()] = mo.group(1)
        o = re.findall(r"[Oo]pen:\s*([A-Za-z0-9]+)", win)
        if o: ca_sym[mo.group(1)] = o[-1]
    def latest_status(fn, who=None):
        try: L = open(fn).read().splitlines()
        except Exception: return None
        for i in range(len(L) - 1, -1, -1):
            l = L[i]
            if who and f"| {who} |" not in l: continue
            mo = re.search(r"open positions?:?\s*(\d+)|(\d+)\s+open\b", l, re.I)
            if mo: return l, int(mo.group(1) or mo.group(2)), L[i:]
        return None
    for fn, who in ((COPYFOMO_LOG, None), (TEAM_BOARD, "Copycat")):
        st_ = latest_status(fn, who)
        if not st_: notes.append(f"{os.path.basename(fn)}: no Copycat holdings line found"); continue
        line, n, tail = st_
        notes.append(f"{os.path.basename(fn)}: latest status says {n} open")
        if n <= 0: continue
        found = set(re.findall(r"\bCA\s+(" + B58 + ")", "\n".join(tail)))
        for sy in re.findall(r"[Oo]pen:\s*([A-Za-z0-9]+)", "\n".join(tail)):
            if sy.lower() in sym_ca: found.add(sym_ca[sy.lower()])
        for m in found: held.setdefault(m, {"symbol": ca_sym.get(m, "?"), "sources": []})["sources"].append(f"{os.path.basename(fn)} latest Copycat status ({n} open)")
        if not found: notes.append(f"{os.path.basename(fn)}: {n} open but no contract address resolved")
    return held, notes

# ---------------------------------------------------------------- universe
def excluded(sym, name, price, ch24):
    s = (sym or "").upper(); n = (name or "").lower()
    if s in EXCL_SYM: return "stable/wrapper/LST symbol"
    if any(x in n for x in EXCL_NAME): return "wrapped/staked/stable/tokenized name"
    if s.endswith("X") and "xstock" in n.replace(" ", ""): return "tokenized stock"
    if price and 0.97 <= price <= 1.03 and abs(ch24 or 0) < 2: return "stable peg"
    return None

def build_universe(extra=()):
    cands, src = {}, {"geckoterminal": 0, "dexscreener": 0, "chunk_universe": 0, "jupiter": 0, "seed": 0}
    jtags = {}
    for c in ("toptraded", "toporganicscore", "toptrending"):
        for x in http_json(f"https://lite-api.jup.ag/tokens/v2/{c}/24h?limit=100", gap=1.0) or []:
            if isinstance(x, dict) and x.get("id"):
                cands[x["id"]] = 1; src["jupiter"] += 1; jtags[x["id"]] = set(x.get("tags") or [])
    try:
        for m_, ts_ in json.load(open(SEED_F)).items():
            if NOW - ts_ < 3 * 86400: cands[m_] = 1; src["seed"] += 1
    except Exception: pass
    GT = "https://api.geckoterminal.com/api/v2/networks/solana"
    for url in [GT + f"/pools?sort=h24_volume_usd_desc&page={p}" for p in range(1, 11)] + [GT + f"/trending_pools?page={p}" for p in (1, 2)]:
        j = http_json(url, gap=3.0, headers={"Accept": "application/json;version=20230302"})
        for p in (j or {}).get("data") or []:
            bid = (((p.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", "")
            if bid.startswith("solana_"): cands[bid[7:]] = 1; src["geckoterminal"] += 1
    try:
        cu = json.load(open(CHUNK_UNI))
        for t in (cu.get("tokens") or []) + (cu.get("core") or []) + (cu.get("wide") or []):
            if t.get("address"): cands[t["address"]] = 1; src["chunk_universe"] += 1
    except Exception: pass
    for url in ["https://api.dexscreener.com/token-boosts/top/v1", "https://api.dexscreener.com/token-boosts/latest/v1"]:
        for t in http_json(url, gap=1.0) or []:
            if t.get("chainId") == "solana" and t.get("tokenAddress"): cands[t["tokenAddress"]] = 1; src["dexscreener"] += 1
    for q in ("SOL", "USDC", "solana meme"):
        for p in (http_json("https://api.dexscreener.com/latest/dex/search?q=" + urllib.request.quote(q), gap=1.0) or {}).get("pairs") or []:
            if p.get("chainId") == "solana": cands[p["baseToken"]["address"]] = 1; src["dexscreener"] += 1
    for m_ in extra: cands[m_] = 1
    cands.pop(WSOL, None)
    mints = list(cands)
    pairs = {}
    for i in range(0, len(mints), 30):
        for p in http_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(mints[i:i + 30]), gap=1.0) or []:
            b = (p.get("baseToken") or {}).get("address")
            if b in cands: pairs.setdefault(b, []).append(p)
    rej, toks = {}, []
    for m, ps in pairs.items():
        ps = [p for p in ps if p.get("chainId") == "solana"]
        if not ps: continue
        main = max(ps, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        sym, name = main["baseToken"].get("symbol"), main["baseToken"].get("name")
        price = float(main.get("priceUsd") or 0); pc = main.get("priceChange") or {}
        why = excluded(sym, name, price, pc.get("h24"))
        if not why and jtags.get(m, set()) & {"stocks", "lst", "stablecoin"}: why = "jupiter tag: " + ",".join(sorted(jtags[m] & {"stocks", "lst", "stablecoin"}))
        created = [p["pairCreatedAt"] / 1000 for p in ps if p.get("pairCreatedAt")]
        age = (NOW - min(created)) / 86400 if created else None
        mcap = main.get("marketCap") or main.get("fdv") or 0
        liq = sum((p.get("liquidity") or {}).get("usd") or 0 for p in ps)
        vol = sum((p.get("volume") or {}).get("h24") or 0 for p in ps)
        if not why:
            if age is None or age < CFG["min_age_d"]: why = "too_young"
            elif not (CFG["min_mcap"] <= mcap <= CFG["max_mcap"]): why = "mcap"
            elif liq < CFG["min_liq"]: why = "liquidity"
            elif vol < CFG["min_vol24"]: why = "volume"
        if why: rej[why] = rej.get(why, 0) + 1
        if why and m not in extra: continue
        toks.append(dict(symbol=sym, name=name, mint=m, main_pair=main["pairAddress"], main_pair_dex=main.get("dexId"),
                         main_pair_quote=main["quoteToken"].get("symbol"), age_days=round(age, 1), mcap_usd=round(mcap),
                         mcap_is_fdv=not main.get("marketCap"), liq_usd=round(liq), main_pair_liq_usd=round((main.get("liquidity") or {}).get("usd") or 0),
                         vol24h_usd=round(vol), price_usd=price, price_change_pct={k: pc.get(k) for k in ("h1", "h6", "h24")},
                         txns_h1=(main.get("txns") or {}).get("h1"), n_pairs=len(ps),
                         pair_addresses=[p["pairAddress"] for p in ps], in_universe=not why, universe_reject=why))
    toks.sort(key=lambda t: -t["vol24h_usd"])
    try: seed = json.load(open(SEED_F))
    except Exception: seed = {}
    for t in toks:
        if t["in_universe"]: seed[t["mint"]] = NOW
    seed = {k: v for k, v in seed.items() if NOW - v < 3 * 86400}
    tmp = SEED_F + ".tmp"; json.dump(seed, open(tmp, "w")); os.replace(tmp, SEED_F)
    missing = [m_ for m_ in extra if m_ not in pairs]
    return toks, {"candidates": len(mints), "with_pairs": len(pairs), "passed": sum(t["in_universe"] for t in toks), "rejected": rej,
                  "candidate_sources": src, "priority_not_on_dexscreener": missing}

# ---------------------------------------------------------------- rugcheck
def rugcheck(mint, ttl=None):
    fn = os.path.join(CACHE, f"rc_{mint}.json")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < (ttl or CFG["rugcheck_ttl_s"]):
        try: return json.load(open(fn))
        except Exception: pass
    j = http_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", gap=1.5, timeout=60)
    if not j: 
        try: return json.load(open(fn)) | {"_stale": True}
        except Exception: return None
    pools = set()
    for mk in j.get("markets") or []:
        pools.add(mk.get("pubkey"))
        for k in ("liquidityAAccount", "liquidityBAccount"):
            o = (mk.get(k) or {}).get("owner"); pools.add(o)
        pools.add(mk.get("liquidityA")); pools.add(mk.get("liquidityB"))
    for lk, lv in (j.get("lockers") or {}).items():
        pools.add(lk); pools.add((lv or {}).get("tokenAccount")); pools.add((lv or {}).get("owner"))
    known = {a: v for a, v in (j.get("knownAccounts") or {}).items() if (v or {}).get("type") in ("AMM", "LOCKER")}
    slim = {"creator": j.get("creator"), "creatorBalance": j.get("creatorBalance"), "tokenProgram": j.get("tokenProgram"),
            "topHolders": j.get("topHolders") or [], "supply": (j.get("token") or {}).get("supply"),
            "decimals": (j.get("token") or {}).get("decimals"), "mintAuthority": j.get("mintAuthority"),
            "freezeAuthority": j.get("freezeAuthority"), "rugged": j.get("rugged"), "score_normalised": j.get("score_normalised"),
            "risks": [{"name": r.get("name"), "level": r.get("level")} for r in j.get("risks") or []],
            "lp_locked_pct_main": None, "pool_accounts": sorted(a for a in pools if a), "known_pool_accounts": sorted(known),
            "fetched_at": iso()}
    mk = sorted(j.get("markets") or [], key=lambda m: -((m.get("lp") or {}).get("quoteUSD") or 0) - ((m.get("lp") or {}).get("baseUSD") or 0))
    if mk: slim["lp_locked_pct_main"] = (mk[0].get("lp") or {}).get("lpLockedPct")
    try: json.dump(slim, open(fn, "w"))
    except Exception: pass
    return slim

def largest_accounts_helius(mint):
    """Fallback only: public RPC refuses getTokenLargestAccounts."""
    r = rpc("getTokenLargestAccounts", [mint], public=False)
    if not r: return None
    accts = [v["address"] for v in r["value"]]
    info = multi_accounts(accts)
    out = []
    for v in r["value"]:
        o = (((info.get(v["address"]) or {}).get("data") or {}).get("parsed") or {}).get("info", {}).get("owner")
        out.append({"address": v["address"], "owner": o, "uiAmount": v.get("uiAmount"), "amount": int(v["amount"]), "insider": None})
    return out

# ---------------------------------------------------------------- tx flow parsing
def owner_flow(t, owner, mint):
    """(token delta, quote proceeds dict) for owner in a parsed tx."""
    m = t.get("meta") or {}
    if m.get("err"): return 0.0, {}
    tok, q = 0.0, {}
    for side, sg in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for b in m.get(side) or []:
            if b.get("owner") != owner: continue
            amt = float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
            if b.get("mint") == mint: tok += sg * amt
            elif b.get("mint") in QUOTES: q[b["mint"]] = q.get(b["mint"], 0) + sg * amt
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
    if owner in keys:
        i = keys.index(owner); q["SOL"] = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
    return tok, q

PARSED = [0]
def acct_events(state_acct, token_acct, owner, mint, price, sol_usd, force=False):
    """New txs (<= window) on a token account -> list of flow events. Uses/updates state."""
    cut = NOW - CFG["window_h"] * 3600
    seen = set(state_acct.get("seen", []))
    evs = []
    sigs = rpc("getSignaturesForAddress", [token_acct, {"limit": CFG["sig_limit"]}]) or []
    state_acct["checked"] = NOW
    todo = []
    for s in sigs:
        if (s.get("blockTime") or 0) < cut: break
        if s["signature"] in seen or s.get("err"): continue
        if len(todo) >= CFG["per_acct_parse"] or PARSED[0] + len(todo) >= CFG["tx_parse_cap"]: state_acct["truncated"] = True; break
        todo.append(s)
    if len(sigs) >= CFG["sig_limit"] and (sigs[-1].get("blockTime") or 0) >= cut: state_acct["truncated"] = True
    PARSED[0] += len(todo)
    with cf.ThreadPoolExecutor(5) as ex: txs = list(ex.map(lambda s: get_tx(s["signature"]), todo))
    for s, t in zip(todo, txs):
        if t: seen.add(s["signature"])
        if not t: continue
        d, q = owner_flow(t, owner, mint)
        if abs(d) < 1e-9: continue
        sol = q.get("SOL", 0) + q.get(WSOL, 0); stab = q.get(USDC, 0) + q.get(USDT, 0)
        proceeds_usd = sol * sol_usd + stab
        kind = ("sell" if proceeds_usd > 1 else "transfer_out") if d < 0 else ("buy" if proceeds_usd < -1 else "transfer_in")
        evs.append({"sig": s["signature"], "ts": s.get("blockTime"), "owner": owner, "token_delta": d,
                    "usd": round(d * price, 2), "proceeds_usd": round(proceeds_usd, 2), "kind": kind})
    state_acct["seen"] = [x for x in seen][-200:]
    return evs

# ---------------------------------------------------------------- main
# ---------------------------------------------------------------- hypothesis fields (recorded only; never change the verdict)
HYP = {"public_calls": 0, "capped": False}
def _hrpc(method, params):
    if HYP["public_calls"] >= CFG["hyp_public_call_cap"] or time.time() - T0 > 0.8 * CFG["max_runtime_s"]:
        HYP["capped"] = True; return "CAP"
    HYP["public_calls"] += 1
    return rpc(method, params, helius_ok=False)          # public RPC only: 0 Helius credits
def _jload(fn):
    try: return json.load(open(fn))
    except Exception: return None

def wallet_profile(owner):
    """First signature (age) and first funder of a wallet. Cached in cache/wp_<owner>.json.
    Complete history is only paged up to hyp_sig_pages x 1000 signatures; busier wallets get a lower-bound age."""
    fn = os.path.join(CACHE, f"wp_{owner}.json"); c = _jload(fn)
    if c and (c.get("complete") or NOW - c.get("checked", 0) < 24 * 3600): return c
    before, oldest, complete = None, None, False
    for _ in range(CFG["hyp_sig_pages"]):
        opt = {"limit": 1000}
        if before: opt["before"] = before
        r = _hrpc("getSignaturesForAddress", [owner, opt])
        if r == "CAP" or r is None: return c or {"status": "cap" if r == "CAP" else "rpc_fail"}
        if not r: complete = oldest is not None; break
        oldest = r[-1]; before = r[-1]["signature"]
        if len(r) < 1000: complete = True; break
        if (r[-1].get("blockTime") or NOW) < NOW - CFG["fresh_days"] * 86400: break   # already older than the fresh window
    if oldest is None: return {"status": "no_history"}
    c = {"checked": NOW, "complete": complete, "oldest_seen_sig": oldest["signature"], "oldest_seen_ts": oldest.get("blockTime"),
         "oldest_seen_slot": oldest.get("slot"), "funder": None}
    if complete:
        tx = None if HYP["public_calls"] >= CFG["hyp_public_call_cap"] else get_tx(oldest["signature"], helius_ok=False)
        HYP["public_calls"] += 1
        if tx:
            ins = list(((tx.get("transaction") or {}).get("message") or {}).get("instructions") or [])
            for ii in (tx.get("meta") or {}).get("innerInstructions") or []: ins += ii.get("instructions") or []
            for i in ins:
                pi = i.get("parsed") if isinstance(i, dict) else None
                if isinstance(pi, dict) and pi.get("type") in ("transfer", "createAccount", "transferWithSeed") and (pi.get("info") or {}).get("destination", (pi.get("info") or {}).get("newAccount")) == owner:
                    c["funder"] = (pi["info"].get("source")); break
            if not c["funder"]:
                keys = [k["pubkey"] if isinstance(k, dict) else k for k in ((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or []]
                fp = keys[0] if keys else None
                if fp and fp != owner: c["funder"] = fp; c["funder_method"] = "fee payer of first tx"
    try: json.dump(c, open(fn, "w"))
    except Exception: pass
    return c

def first_acq_slot(token_acct):
    fn = os.path.join(CACHE, f"fa_{token_acct}.json"); c = _jload(fn)
    if c: return c
    r = _hrpc("getSignaturesForAddress", [token_acct, {"limit": 1000}])
    if r == "CAP" or r is None: return {"status": "cap" if r == "CAP" else "rpc_fail"}
    c = {"slot": r[-1].get("slot") if r and len(r) < 1000 else None, "ts": r[-1].get("blockTime") if r and len(r) < 1000 else None,
         "complete": bool(r) and len(r) < 1000}
    try: json.dump(c, open(fn, "w"))
    except Exception: pass
    return c

CUST_FUNDERS = set()
try: CUST_FUNDERS = set((_jload(os.path.join(BASE, "data", "custodial_funders.json")) or {}).keys()) if isinstance(_jload(os.path.join(BASE, "data", "custodial_funders.json")), dict) else {x.get("address") for x in (_jload(os.path.join(BASE, "data", "custodial_funders.json")) or []) if isinstance(x, dict)}
except Exception: pass

def linked_and_fresh(mint, wallet_holders, supply):
    """top_holders_linked_pct + fresh_holder_pct_top50 over the wallet holders rugcheck returns (<= 20 token accounts)."""
    fn = os.path.join(CACHE, f"hyp_{mint}.json"); c = _jload(fn)
    key = sorted(h["owner"] for h in wallet_holders)
    if c and c.get("holders_key") == key and NOW - c.get("ts", 0) < CFG["hyp_mint_ttl_s"] and not c.get("partial"):
        c = dict(c); c["from_cache"] = True; return c
    prof, partial = {}, False
    for h in wallet_holders:
        if h["class"] != "wallet": continue          # custodial? wallets: age/funder meaningless
        wp = wallet_profile(h["owner"]); fa = first_acq_slot(h["token_account"])
        if wp.get("status") in ("cap", "rpc_fail") or fa.get("status") in ("cap", "rpc_fail"): partial = True
        prof[h["owner"]] = (h, wp, fa)
    # funders that are exchange-like do not link holders
    funders = {wp.get("funder") for _, wp, _ in prof.values() if wp.get("funder")}
    cust = set(f for f in funders if f in CUST_FUNDERS)
    rest = [f for f in funders if f not in cust and is_on_curve(f)]
    if rest and HYP["public_calls"] < CFG["hyp_public_call_cap"]:
        HYP["public_calls"] += 1
        for f, v in multi_accounts(rest, parsed=False).items():
            if v and v.get("lamports", 0) / 1e9 > CFG["custodial_sol"]: cust.add(f)
    by_f, by_s = {}, {}
    for o, (h, wp, fa) in prof.items():
        f = wp.get("funder")
        if f and f not in cust: by_f.setdefault(f, []).append(o)
        if fa.get("slot"): by_s.setdefault(fa["slot"], []).append(o)
    groups = [{"type": "shared_funder", "key": k, "owners": v} for k, v in by_f.items() if len(v) >= 2] + \
             [{"type": "same_first_acquisition_slot", "key": k, "owners": v} for k, v in by_s.items() if len(v) >= 2]
    linked = {o for g in groups for o in g["owners"]}
    pct = lambda os_: round(sum(prof[o][0]["pct"] or 0 for o in os_), 3) if supply else None
    fresh, unknown = [], []
    for o, (h, wp, fa) in prof.items():
        ts0 = wp.get("oldest_seen_ts")
        if ts0 is None: unknown.append(o)
        elif ts0 >= NOW - CFG["fresh_days"] * 86400:
            (fresh if wp.get("complete") else unknown).append(o)   # incomplete history inside the window = too busy to tell
    c = {"ts": NOW, "holders_key": key, "partial": partial, "holders_examined": len(prof),
         "top_holders_linked_pct": pct(linked), "linked_holders": len(linked), "link_groups": groups[:10],
         "exchange_like_funders_ignored": sorted(cust)[:10],
         "fresh_holder_pct_top50": pct(fresh), "fresh_holders": len(fresh), "age_unknown_holders": len(unknown),
         "fresh_holders_list": [{"owner": o, "first_sig_ts": iso(prof[o][1]["oldest_seen_ts"])} for o in fresh][:20]}
    try: json.dump(c, open(fn, "w"))
    except Exception: pass
    return c

def stair_step(pool):
    """GeckoTerminal 1-min OHLCV, last 60 candles. Definition documented in NOTES.md (Old-coins intel)."""
    j = http_json(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=1&limit=60&currency=usd",
                  gap=2.2, headers={"Accept": "application/json;version=20230302"})
    ol = ((((j or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list")) or []
    ol = sorted([x for x in ol if len(x) >= 6], key=lambda x: x[0])
    if len(ol) < 40: return {"stair_step": None, "reason": f"only {len(ol)} 1-min candles", "candles": len(ol)}
    o_, c_, v_ = [float(x[1]) for x in ol], [float(x[4]) for x in ol], [float(x[5]) for x in ol]
    up = sum(1 for a, b in zip(o_, c_) if b > a) / len(ol)
    net = c_[-1] / o_[0] - 1 if o_[0] else 0
    maxc = max(abs(b / a - 1) for a, b in zip(o_, c_) if a)
    hi, dd = c_[0], 0.0
    for x in c_: hi = max(hi, x); dd = max(dd, 1 - x / hi)
    mv = sum(v_) / len(v_); cv = (sum((x - mv) ** 2 for x in v_) / len(v_)) ** 0.5 / mv if mv else 9
    h = len(v_) // 2; vr = (sum(v_[h:]) / max(sum(v_[:h]), 1e-9)) if sum(v_[:h]) else 9
    comp = {"candles": len(ol), "window_start": iso(ol[0][0]), "up_candle_frac": round(up, 3), "net_change_pct": round(100 * net, 2),
            "max_candle_move_pct": round(100 * maxc, 2), "max_drawdown_pct": round(100 * dd, 2),
            "volume_cv": round(cv, 2), "volume_2nd_half_vs_1st": round(vr, 2)}
    comp["stair_step"] = bool(up >= 0.6 and net >= 0.02 and maxc <= 0.01 and dd <= 0.015 and cv <= 0.6 and 0.67 <= vr <= 1.5)
    return comp

def main():
    log(f"start: credit_mode={CREDIT_MODE} day_used={DAY_USED} run_cap={RUN_CAP}")
    try: state = json.load(open(STATE_F))
    except Exception: state = {}
    prev = {}
    try:
        old = json.load(open(OUT)); prev = {t["mint"]: t for t in old.get("tokens") or []}
    except Exception: pass
    hist = []
    try:
        for l in open(HIST):
            try: hist.append(json.loads(l))
            except Exception: pass
    except FileNotFoundError: pass
    AV, SM = load_avoid(), load_smart()
    held, paper, held_status = load_held()
    sol_usd = 0
    sp = http_json("https://api.dexscreener.com/tokens/v1/solana/" + WSOL, gap=1.0) or []
    if sp: sol_usd = float(max(sp, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0).get("priceUsd") or 0)
    setups = load_setups(); cc_held, cc_notes = load_copycat()
    pri = {}
    for m_ in held: pri.setdefault(m_, 1)
    for m_ in setups: pri.setdefault(m_, 2)
    for m_ in cc_held: pri.setdefault(m_, 3)
    toks, uni_meta = build_universe(extra=set(pri))
    rot = state.setdefault("_rotation", {})
    for t in toks: t["tier"] = pri.get(t["mint"], 4)
    t4 = [t for t in toks if t["tier"] == 4]
    rot_pick = {t["mint"] for t in sorted(t4, key=lambda t: (rot.get(t["mint"], 0), -t["vol24h_usd"]))[:CFG["rotate_n"]]}
    toks.sort(key=lambda t: (t["tier"], 0 if t["mint"] in rot_pick else 1, -t["vol24h_usd"]))
    log(f"universe {uni_meta['passed']} in-universe + {sum(not t['in_universe'] for t in toks)} priority-only; tiers {[sum(t['tier']==k for t in toks) for k in (1,2,3,4)]}; rotation picks {len(rot_pick)}; {uni_meta}")
    # derive ATAs for smart wallets x mints (program from rugcheck)
    out = []
    for t in toks:
        if time.time() - T0 > CFG["max_runtime_s"]: log("runtime cap hit; remaining tokens skipped"); break
        m = t["mint"]; st = state.setdefault(m, {"accts": {}, "events": []})
        el = time.time() - T0
        full = t["tier"] <= 3 or (m in rot_pick and el < 0.6 * CFG["max_runtime_s"] and (CREDIT_MODE == "free_only" or USED[0] < RUN_CAP - 150))
        depth = "full" if full else "light"
        rc = rugcheck(m, ttl=None if full else CFG["light_rugcheck_ttl_s"])
        notes, reasons_av, reasons_sup, cautions = [], [], [], []
        holders_src = "rugcheck.xyz topHolders"
        th = (rc or {}).get("topHolders") or []
        if not th:
            th = largest_accounts_helius(m) or []; holders_src = "helius getTokenLargestAccounts" if th else "unavailable"
        dec = (rc or {}).get("decimals")
        supply = ((rc or {}).get("supply") or 0) / (10 ** dec) if dec is not None and (rc or {}).get("supply") else None
        if supply is None:
            s = rpc("getTokenSupply", [m]); supply = float(s["value"]["uiAmountString"]) if s else None
        pool_set = set((rc or {}).get("pool_accounts") or []) | set((rc or {}).get("known_pool_accounts") or []) | set(t["pair_addresses"])
        owners = list({h.get("owner") for h in th if h.get("owner")})
        on_c = {o: is_on_curve(o) for o in owners}
        oinfo = multi_accounts([o for o in owners if on_c[o]], parsed=False)
        holders = []
        for h in th:
            o = h.get("owner"); amt = float(h.get("uiAmount") or 0)
            cls, why = "wallet", "on-curve, System-owned"
            if not o: cls, why = "unknown", "no owner"
            elif o in BURN: cls, why = "burn", "burn/incinerator"
            elif o in pool_set or h.get("address") in pool_set: cls, why = "pool", "pool vault/authority/locker per rugcheck markets/lockers or DexScreener pair"
            elif not on_c[o]: cls, why = "program", "owner off-curve (PDA => program-controlled: AMM/vault/locker)"
            else:
                ai = oinfo.get(o)
                if ai is None and o in oinfo: why = "on-curve, account not funded (wallet)"
                elif ai and ai.get("owner") != SYSTEM: cls, why = "program", f"owner account owned by program {ai.get('owner')}"
                elif ai and ai.get("lamports", 0) / 1e9 > CFG["custodial_sol"]: cls, why = "wallet_custodial?", f"on-curve wallet holding {ai['lamports']/1e9:,.0f} SOL (heuristic: CEX/custodian)"
                elif o not in oinfo: why = "on-curve (owner lookup failed)"
            holders.append({"token_account": h.get("address"), "owner": o, "amount": amt,
                            "pct": round(100 * amt / supply, 3) if supply else h.get("pct"), "class": cls, "why": why,
                            "rugcheck_insider": h.get("insider"), "avoid_link": AV.get(o)})
        wallets = [h for h in holders if h["class"].startswith("wallet")][:10]
        top10 = round(sum(h["pct"] or 0 for h in wallets), 2) if supply else None
        top10_nc = round(sum(h["pct"] or 0 for h in wallets if h["class"] == "wallet"), 2) if supply else None
        # --- avoid links
        links = []
        creator = (rc or {}).get("creator")
        if creator and creator in AV: links.append({"role": "creator", "address": creator, "list": AV[creator]})
        ignored_links = []
        for h in wallets:
            if h["owner"] in AV:
                l = {"role": f"top holder {h['pct']}%", "address": h["owner"], "list": AV[h["owner"]]}
                if "funder" in AV[h["owner"]] and h["class"] == "wallet_custodial?":
                    l["ignored_because"] = "funder-list entry is an exchange-like wallet (> 20k SOL); funding ruggers via withdrawals is not evidence against this token"
                    ignored_links.append(l)
                else: links.append(l)
        # --- top-holder + dev sells (incremental via state)
        events = [e for e in st.get("events", []) if (e.get("ts") or 0) >= NOW - CFG["window_h"] * 3600]
        known = {(e["sig"], e["owner"]) for e in events}
        def scan(acct, owner, role, cur_bal):
            sa = st["accts"].setdefault(acct, {})
            changed = sa.get("bal") is None or abs((sa.get("bal") or 0) - (cur_bal or 0)) > 1e-6 or NOW - sa.get("checked", 0) > 3 * 3600
            sa["bal"] = cur_bal
            if not changed: return
            for e in acct_events(sa, acct, owner, m, t["price_usd"], sol_usd):
                if (e["sig"], owner) not in known: e["role"] = role; events.append(e); known.add((e["sig"], owner))
        for h in wallets:
            if h["class"] == "wallet_custodial?" or not full:
                sa = st["accts"].setdefault(h["token_account"], {}); pb = sa.get("bal"); sa["bal"] = h["amount"]
                if pb is not None and supply and pb - h["amount"] >= 0.001 * supply:
                    cautions.append(f"{'custodial? ' if h['class'] != 'wallet' else ''}holder {h['owner'][:6]}… balance down {100*(pb-h['amount'])/supply:.2f}% of supply since last run")
                continue
            if full: scan(h["token_account"], h["owner"], "top10", h["amount"])
        tp = (rc or {}).get("tokenProgram") or TOKEN_PROG
        if full and creator and creator not in BURN:
            ca = ata(creator, m, tp)
            if ca: scan(ca, creator, "creator", (rc or {}).get("creatorBalance"))
        # --- smart wallets: ATA balances (public getMultipleAccounts), then tx history for holders/changers
        amap = {}
        for w in (SM if full else []):
            a = ata(w, m, tp)
            if a: amap[a] = w
        info = multi_accounts(list(amap))
        smart_hold = []
        for a, w in amap.items():
            v = info.get(a)
            bal = float((((v or {}).get("data") or {}).get("parsed") or {}).get("info", {}).get("tokenAmount", {}).get("uiAmount") or 0) if v else 0.0
            sa = st["accts"].get(a)
            if bal > 0 or (sa and (sa.get("bal") or 0) > 0):
                if bal > 0: smart_hold.append({"wallet": w, "source": SM[w], "amount": bal, "usd": round(bal * t["price_usd"], 2)})
                scan(a, w, "smart", bal)
            elif sa is not None: sa["bal"] = 0.0
        st["events"] = events
        def flow(role, h):
            c = NOW - h * 3600; es = [e for e in events if e.get("role") == role and (e.get("ts") or 0) >= c]
            return es
        sm6, sm1 = flow("smart", 6), flow("smart", 1)
        def net(es): return round(sum(e["usd"] for e in es if e["kind"] in ("buy", "sell")), 2)
        smart = {"checked": full, "wallets_checked": len(amap), "holding_now": smart_hold,
                 "net_usd_1h": net(sm1), "net_usd_6h": net(sm6),
                 "buyers_6h": sorted({e["owner"] for e in sm6 if e["kind"] == "buy"}),
                 "sellers_6h": sorted({e["owner"] for e in sm6 if e["kind"] == "sell"}),
                 "events_6h": sm6[-20:]}
        big = lambda e: (supply and abs(e["token_delta"]) >= 0.001 * supply) or abs(e["usd"]) >= 10000
        top_out = [e for e in flow("top10", 6) if e["kind"] in ("sell", "transfer_out") and big(e)]
        dev_out = [e for e in flow("creator", 6) if e["kind"] in ("sell", "transfer_out") and big(e)]
        top_sell_pct = round(100 * sum(-e["token_delta"] for e in top_out if e["kind"] == "sell") / supply, 3) if supply else None
        # --- LP change vs history
        ph = [h for h in hist if h.get("mint") == m]
        def ago(hrs):
            c = [h for h in ph if NOW - h["ts"] >= hrs * 3600 * 0.75]
            return c[-1] if c else None
        lp = {"liq_usd_now": t["liq_usd"], "lp_locked_pct_main_rugcheck": (rc or {}).get("lp_locked_pct_main")}
        for lbl, hrs in (("1h", 1), ("6h", 6)):
            h0 = ago(hrs) if hrs > 1 else (ph[-1] if ph else None)
            if h0 and h0.get("liq_usd") and h0.get("price_usd"):
                raw = t["liq_usd"] / h0["liq_usd"] - 1; pr = t["price_usd"] / h0["price_usd"] if h0["price_usd"] else 1
                adj = t["liq_usd"] / h0["liq_usd"] / math.sqrt(pr) - 1 if pr > 0 else raw
                lp[f"change_{lbl}_pct"] = round(100 * raw, 1); lp[f"change_{lbl}_price_adj_pct"] = round(100 * adj, 1)
                lp[f"vs_{lbl}_run_at"] = iso(h0["ts"])
        # --- hypothesis fields (recorded only, NOT used in the verdict)
        nonlp = [h for h in holders if h["class"].startswith("wallet") or h["class"] == "unknown"]
        msh = max([h["pct"] or 0 for h in nonlp] or [0]) if supply else None
        msh_nc = max([h["pct"] or 0 for h in nonlp if h["class"] == "wallet"] or [0]) if supply else None
        hyp = {"affects_verdict": False, "status": "untested hypothesis fields; recorded for back-testing only",
               "max_single_holder_pct": msh, "max_single_holder_pct_ex_custodial": msh_nc,
               "max_single_holder_flag_over_5pct": (msh_nc or 0) > 5 if supply else None,
               "vol24h_mcap": round(t["vol24h_usd"] / t["mcap_usd"], 3) if t.get("mcap_usd") else None}
        try: hyp.update({"stair": stair_step(t["main_pair"])}); hyp["stair_step"] = hyp["stair"].get("stair_step")
        except Exception as ex: hyp["stair_step"] = None; hyp["stair"] = {"error": str(ex)[:120]}
        if full:
            try:
                lf = linked_and_fresh(m, [h for h in holders if h["class"].startswith("wallet")][:20], supply)
                hyp.update({k: lf.get(k) for k in ("top_holders_linked_pct", "fresh_holder_pct_top50")})
                hyp["holder_links_detail"] = {k: v for k, v in lf.items() if k not in ("holders_key", "top_holders_linked_pct", "fresh_holder_pct_top50")}
                hyp["holders_examined_note"] = "rugcheck returns <= 20 top token accounts, so 'top50' is computed over the wallet holders among those (see holders_examined)"
            except Exception as ex: hyp["holder_links_detail"] = {"error": str(ex)[:120]}
        else:
            hyp["top_holders_linked_pct"] = hyp["fresh_holder_pct_top50"] = None
            hyp["holder_links_detail"] = {"skipped": "light check (full-check tiers only)"}
        # --- verdict
        lpd = min([lp.get(k) for k in ("change_1h_price_adj_pct", "change_6h_price_adj_pct") if lp.get(k) is not None] or [0])
        if links: reasons_av.append(f"avoid-list link: {len(links)} ({', '.join(l['role'] for l in links[:3])})")
        if lpd <= -20: reasons_av.append(f"LP drop {lpd}% (price-adjusted)")
        if [e for e in dev_out if e["kind"] == "sell"]: reasons_av.append(f"creator sold {len([e for e in dev_out if e['kind']=='sell'])}x in 6h (${-sum(e['usd'] for e in dev_out if e['kind']=='sell'):,.0f})")
        sellers = {e["owner"] for e in top_out if e["kind"] == "sell"}
        if (top_sell_pct or 0) >= 1 or len(sellers) >= 2: reasons_av.append(f"top-10 distribution: {len(sellers)} holders sold {top_sell_pct}% of supply in 6h")
        if smart["net_usd_6h"] <= -10000 and len(smart["sellers_6h"]) >= 2: reasons_av.append(f"smart money net selling ${smart['net_usd_6h']:,.0f} (6h)")
        if (rc or {}).get("rugged"): reasons_av.append("rugcheck.xyz marks token rugged")
        if dev_out and not reasons_av: cautions.append("creator moved tokens out (transfer) in 6h")
        if top_out and not reasons_av: cautions.append(f"{len(top_out)} large top-10 outflows in 6h")
        if top10_nc is not None and top10_nc > 35: cautions.append(f"concentrated: top-10 non-custodial wallets {top10_nc}%")
        if (rc or {}).get("mintAuthority"): cautions.append("mint authority still set")
        if (rc or {}).get("freezeAuthority"): cautions.append("freeze authority still set")
        if -20 < lpd <= -10: cautions.append(f"LP down {lpd}% (price-adjusted)")
        healthy = top10_nc is not None and top10_nc <= 35 and not top_out
        sbuy = smart["net_usd_6h"]
        if sbuy >= 2000 and smart["buyers_6h"]: reasons_sup.append(f"smart net buy ${sbuy:,.0f} 6h by {len(smart['buyers_6h'])} wallet(s)")
        if reasons_av: verdict = "avoid"
        elif reasons_sup and healthy: verdict = "support"
        else: verdict = "neutral"
        strong = verdict == "support" and (sbuy >= 10000 or (len(smart["buyers_6h"]) >= 2 and sbuy >= 5000)) and \
            top10_nc <= 25 and lpd > -10 and (t["price_change_pct"].get("h6") or 0) > -15
        cov = []
        if holders_src == "unavailable": cov.append("no holder data")
        if any(sa.get("truncated") for sa in st["accts"].values()): cov.append("tx history truncated on busy accounts")
        if not ph: cov.append("first run for this token (no LP history)")
        if (rc or {}).get("_stale"): cov.append("rugcheck stale")
        if not full: cov.append("light check: no smart-money flow or dev/top-holder sell scan this run (support cannot fire)")
        conf = "low" if "no holder data" in cov else ("medium" if cov else "high")
        if full: rot[m] = NOW
        if verdict == "support" and len(smart["buyers_6h"]) < 2 and conf == "high": conf = "medium"
        pv = (prev.get(m) or {}).get("verdict")
        rec = dict(t, holders_source=holders_src, supply=supply, creator=creator,
                   holder_concentration={"top10_share_ex_pools_pct": top10, "top10_share_ex_pools_ex_custodial_pct": top10_nc,
                                         "method": "rugcheck top-20 token accounts; excluded owners: off-curve PDAs, program-owned accounts, rugcheck market vaults/authorities/lockers, DexScreener pair addresses, burn",
                                         "top10": wallets, "excluded": [h for h in holders if not h["class"].startswith("wallet")][:12]},
                   smart_money=smart, large_sells_6h={"checked": full, "top10": top_out[-15:], "creator": dev_out[-10:], "top10_sold_pct_supply": top_sell_pct},
                   lp=lp, avoid_links=links, avoid_links_ignored=ignored_links, verdict=verdict, strong=bool(strong),
                   reasons=reasons_av or reasons_sup or ["no smart-money flow or distribution signal"], cautions=cautions,
                   confidence=conf, coverage_notes=cov, previous_verdict=pv, hypothesis_fields=hyp,
                   held_by_chunk_live=m in held, held_by_chunk_paper=m in paper,
                   tier=t["tier"], tier_name={1: "chunk_held", 2: "chunk_setup_1h", 3: "copycat_held", 4: "universe"}[t["tier"]],
                   check_depth=depth, rotation_full_check=(t["tier"] == 4 and full),
                   tags=[x for x, c in (("chunk_held", m in held), ("chunk_paper", m in paper), ("chunk_setup_1h", m in setups), ("copycat_held", m in cc_held)) if c],
                   copycat_sources=(cc_held.get(m) or {}).get("sources"), chunk_setup_events=(setups.get(m) or {}).get("events"),
                   rugcheck={k: (rc or {}).get(k) for k in ("score_normalised", "risks", "rugged", "mintAuthority", "freezeAuthority")})
        out.append(rec)
        log(f"T{t['tier']} {depth:5} {t['symbol']:>10} {verdict:7} conf={conf} top10={top10}/{top10_nc} smart6h={sbuy} lp={lpd} links={len(links)} helius_used={USED[0]} | maxh={hyp.get('max_single_holder_pct_ex_custodial')} linked={hyp.get('top_holders_linked_pct')} fresh={hyp.get('fresh_holder_pct_top50')} v/m={hyp.get('vol24h_mcap')} stair={hyp.get('stair_step')} hypcalls={HYP['public_calls']}")
    # --- alerts
    alerts = []
    for r in out:
        if r["strong"]: alerts.append({"type": "strong_support", "symbol": r["symbol"], "mint": r["mint"], "reasons": r["reasons"], "confidence": r["confidence"], "held_live": r["held_by_chunk_live"]})
        if r["verdict"] == "avoid" and (r["held_by_chunk_live"] or r["held_by_chunk_paper"]) and r["previous_verdict"] != "avoid":
            alerts.append({"type": "new_avoid_on_held", "book": "live" if r["held_by_chunk_live"] else "paper", "symbol": r["symbol"], "mint": r["mint"], "reasons": r["reasons"], "confidence": r["confidence"]})
        if r["verdict"] == "avoid" and "copycat_held" in r["tags"] and r["previous_verdict"] != "avoid":
            alerts.append({"type": "new_avoid_on_copycat_held", "symbol": r["symbol"], "mint": r["mint"], "reasons": r["reasons"], "confidence": r["confidence"], "copycat_sources": r["copycat_sources"]})
    vc = {}
    for r in out: vc[r["verdict"]] = vc.get(r["verdict"], 0) + 1
    doc = {"generated_at": iso(), "schema": "scout-oldcoins-intel/1", "read_only": True,
           "sources": ["DexScreener (tokens/v1, search, boosts)", "GeckoTerminal (solana top pools by 24h vol, trending)",
                       "Chunk live/oldcoins-universe.json (read-only seed)", "rugcheck.xyz report (topHolders, creator, markets, lockers)",
                       "public Solana RPC (getMultipleAccounts, getSignaturesForAddress, getTransaction)",
                       "Helius RPC fallback only" if CREDIT_MODE == "full" else "Helius disabled (free_only)",
                       "Scout lists: smart_wallets.json, wallets.csv, leader_mappings.json, avoid.csv, known_ruggers.json, known_funders.csv"],
           "credit_mode": CREDIT_MODE, "helius_credits_used_this_run": USED[0], "helius_run_cap": RUN_CAP,
           "helius_credits_today_before_run": DAY_USED, "rpc_stats": STATS, "txs_parsed": PARSED[0],
           "universe": uni_meta, "criteria": {k: CFG[k] for k in ("min_age_d", "min_mcap", "max_mcap", "min_liq", "min_vol24", "rotate_n")},
           "coverage": {"universe_size": uni_meta["passed"], "priority_only_tokens": sum(not r["in_universe"] for r in out), "tokens_reported": len(out),
                        "by_depth": {d: sum(r["check_depth"] == d for r in out) for d in ("full", "light")},
                        "by_tier": {f"tier{k}": {"n": sum(r["tier"] == k for r in out), "full": sum(r["tier"] == k and r["check_depth"] == "full" for r in out)} for k in (1, 2, 3, 4)},
                        "tier4_rotation_full": sum(r["rotation_full_check"] for r in out), "skipped_runtime_cap": len(toks) - len(out),
                        "tiers": "1 chunk_held (oldcoins-live.jsonl), 2 chunk setup/event in last 1h (oldcoins-paper.jsonl / oldcoins-live.jsonl), 3 copycat_held (selfcopy state/live-trades, copyfomo x-watch-log, TEAM-BOARD Copycat lines), 4 rest of universe by 24h volume",
                        "depth": "full = holders + avoid links + LP + smart-money flow + dev/top-10 sell scan; light = DexScreener metrics + rugcheck top holders (cached <= 3h) + holder classification via public RPC + LP vs history + avoid links. Tier 4 gets full checks by rotation (oldest-checked first) while runtime/credits allow.",
                        "copycat_parse_notes": cc_notes, "chunk_setups_1h": setups, "copycat_held": cc_held},
           "chunk_holdings": {"live_file": HELD_F, "live_file_status": held_status, "live_mints": held, "paper_positions": paper},
           "smart_wallets_tracked": len(SM), "verdict_counts": vc, "alerts": alerts,
           "verdict_rules": {"support": "smart net buy >= $2k in 6h AND top-10 non-custodial <= 35% AND no large top-10 outflows AND no avoid trigger",
                             "strong_support": "support AND (smart net >= $10k OR >=2 buyers & >= $5k) AND top-10 <= 25% AND LP not down >10% AND 6h price > -15%",
                             "avoid": "avoid-list link (creator/top-10 owner) OR price-adjusted LP drop >= 20% (1h/6h) OR creator sold in 6h OR top-10 sold >= 1% supply / >= 2 top holders sold OR smart net sell <= -$10k by >= 2 wallets OR rugcheck rugged",
                             "neutral": "everything else"},
           "runtime_s": round(time.time() - T0), "tokens": out}
    tmp = OUT + ".tmp"
    json.dump(doc, open(tmp, "w"), indent=1, default=str); os.replace(tmp, OUT)
    with open(HIST, "a") as f:
        for r in out:
            f.write(json.dumps({"ts": NOW, "mint": r["mint"], "symbol": r["symbol"], "liq_usd": r["liq_usd"], "price_usd": r["price_usd"],
                                "mcap_usd": r["mcap_usd"], "vol24h_usd": r["vol24h_usd"], "top10": r["holder_concentration"]["top10_share_ex_pools_pct"],
                                "smart_net_6h": r["smart_money"]["net_usd_6h"], "verdict": r["verdict"]}) + "\n")
    # prune state for mints no longer tracked > 2 days
    keep = {r["mint"] for r in out}
    for mm in list(state):
        if mm.startswith("_"): continue
        if mm not in keep and not state[mm].get("events"): state.pop(mm)
    tmp = STATE_F + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, STATE_F)
    log(f"done: {len(out)} tokens {vc} alerts={len(alerts)} helius_credits={USED[0]} public_calls={STATS['public_rpc']} txs={PARSED[0]} runtime={round(time.time()-T0)}s")

if __name__ == "__main__":
    main()
