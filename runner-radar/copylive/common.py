"""copylive shared helpers. READ-ONLY toward the outside world: reads local files and public HTTP APIs
(DexScreener, Jupiter lite-api quote/price, rugcheck.xyz, GeckoTerminal, public Solana RPC getBalance/getTokenSupply).
Never trades, signs, touches keys/wallet files, Telegram or a browser. Writes only inside this copylive/ folder."""
import json, os, time, datetime as dt, urllib.request, urllib.error, fcntl
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
SELFCOPY = "/workspace/selfcopy"
SIGNALS = os.path.join(SELFCOPY, "paper-trades.jsonl")
DRY_SIGNALS = os.path.join(SELFCOPY, "dryrun-paper-trades.jsonl")
ROSTER_STATUS = os.path.join(SELFCOPY, "roster-status.md")
WALLET = "APPwLvLK1mggB8QFntouNRogJhiteVC3qj19QtQsR82g"   # Chunk's Banana Gun wallet (public address, balance read only)
SOL_MINT = "So11111111111111111111111111111111111111112"
DUB = ZoneInfo("Europe/Dublin")
RPCS = ["https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com"]

F = {k: os.path.join(HERE, v) for k, v in dict(
    state="state.json", positions="positions.json", actions="actions.jsonl", skips="skips.jsonl",
    fills="fills.jsonl", night="night-start.json", lock=".lock").items()}

# ---- rules (copied from /workspace/selfcopy/live.py HARD v3 + Zero's 24 Oct copy-book brief) ----
R = dict(
    poll_s=5, size_frac=0.10, reserve_sol=0.02, min_size_sol=0.005, max_open=3,
    min_age_s=3600, min_liq=100_000, min_mcap=1_000_000, min_leader_usd=50.0, max_chase=0.08,
    max_signal_delay_s=180, max_impact=0.03, pending_s=180,
    sl_frac=0.85, tp1_x=1.4, tp1_frac=0.25, tp2_x=2.0, trail_frac=0.75, trail_adding_frac=0.65, add_window_s=600,
    keep_frac=0.10, moon_x=6.0, be_x=1.015,          # breakeven = entry px +1.5% (Banana Gun fee + priority on the exit)
    night_loss_frac=0.20, book_open=(21, 0), no_entry_from=(7, 45), close_hour=8,
)

def _apply_session_rules():
    try:
        s = json.load(open(os.path.join(HERE, "session.json")))
        R.update(s.get("rules") or {})
    except Exception:
        pass
_apply_session_rules()

def lrule(leader, key):
    """per-leader override from session.json leader_rules (only min_mcap / min_liq honoured)"""
    ss = session() or {}
    v = ((ss.get("leader_rules") or {}).get(leader) or {}).get(key)
    return float(v) if v is not None and key in ("min_mcap", "min_liq") else R[key]

def now(): return time.time()
def iso(t=None): return dt.datetime.fromtimestamp(t if t is not None else now(), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def parse_iso(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
def dublin(t=None): return dt.datetime.fromtimestamp(t if t is not None else now(), DUB)
def session(t=None):
    """daytime session override (session.json: key, start, end UTC ISO, no_entry_min). Once present, the
    normal night schedule is OFF until the file is removed: after the end, no entries and must be flat."""
    s = load(os.path.join(HERE, "session.json"), None)
    return s if s and s.get("end") else None

def night_key(t=None):
    """a night runs 08:00 -> 08:00 Dublin (same as live.py)"""
    s = session(t)
    if s: return s["key"]
    return (dublin(t) - dt.timedelta(hours=R["close_hour"])).strftime("%Y-%m-%d")

def entries_allowed(t=None):
    """book takes entries 21:00 -> 07:45 Dublin"""
    s = session(t)
    if s:
        tt = t if t is not None else now()
        if s.get("entries_stopped_until") and tt < parse_iso(s["entries_stopped_until"]): return False   # 16:45Z user halt
        return parse_iso(s["start"]) <= tt < parse_iso(s["end"]) - 60 * s.get("no_entry_min", 15)
    d = dublin(t); hm = (d.hour, d.minute)
    return hm >= R["book_open"] or hm < R["no_entry_from"]

def must_be_flat(t=None):
    """07:45 -> 21:00 Dublin: anything still open is sold (SELL_ALL)"""
    s = session(t)
    if s:
        if s.get("continuous"): return False      # 21:25Z 24 Oct user: run 24/7 -> no session-end flatten (only the halt sells all)
        tt = t if t is not None else now()
        return tt >= parse_iso(s["end"]) - 60 * s.get("no_entry_min", 15)
    return not entries_allowed(t)

def load(fn, default):
    try:
        with open(fn) as f: return json.load(f)
    except Exception: return default

def save(fn, obj):
    tmp = fn + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, fn)

def append(fn, obj):
    with open(fn, "a") as f: f.write(json.dumps(obj, separators=(",", ":")) + "\n")

class Lock:
    """small file lock so record.py and watch.py never write state/positions at the same moment"""
    def __enter__(self):
        self.f = open(F["lock"], "w"); fcntl.flock(self.f, fcntl.LOCK_EX); return self
    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()

# ---------------- HTTP (public, read-only) ----------------
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def http_json(url, body=None, timeout=12):
    data = json.dumps(body).encode() if body is not None else None
    ua = BROWSER_UA if "dexscreener.com" in url else "copylive-watch/1.0"     # 25 Oct: DexScreener 403s non-browser UAs
    req = urllib.request.Request(url, data=data, headers={"User-Agent": ua, "Accept": "application/json",
                                                          **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def rpc(method, params):
    err = None
    for u in RPCS:
        try:
            j = http_json(u, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            if "result" in j: return j["result"]
            err = j.get("error")
        except Exception as e: err = repr(e)
    raise RuntimeError(f"rpc {method} failed: {err}")

def sol_balance(addr=WALLET):
    return rpc("getBalance", [addr, {"commitment": "confirmed"}])["value"] / 1e9

def token_decimals(mint):
    return int(rpc("getTokenSupply", [mint])["value"]["decimals"])

def dex_pairs(mints):
    """-> {mint: best(deepest-liquidity) Solana pair summary} via DexScreener tokens/v1 (<=30 mints per call)"""
    out = {}
    mints = list(dict.fromkeys(m for m in mints if m))
    for i in range(0, len(mints), 30):
        chunk = mints[i:i + 30]
        try: rows = http_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(chunk))
        except Exception: rows = []
        for p in rows or []:
            m = (p.get("baseToken") or {}).get("address")
            if m not in chunk: continue
            liq = float((p.get("liquidity") or {}).get("usd") or 0)
            if m not in out or liq > out[m]["liq"]:
                out[m] = dict(mint=m, ticker=(p.get("baseToken") or {}).get("symbol"), price=float(p.get("priceUsd") or 0) or None,
                              mcap=float(p.get("marketCap") or p.get("fdv") or 0) or None, liq=liq,
                              created=(p.get("pairCreatedAt") or 0) / 1000 or None, pair=p.get("pairAddress"),
                              dex=p.get("dexId"), url=p.get("url") or f"https://dexscreener.com/solana/{p.get('pairAddress')}",
                              m5=float((p.get("priceChange") or {}).get("m5") or 0), fetched=now())
    return out

def sol_usd():
    try:
        j = http_json(f"https://lite-api.jup.ag/price/v3?ids={SOL_MINT}")
        return float(j[SOL_MINT]["usdPrice"])
    except Exception:
        d = dex_pairs([SOL_MINT]).get(SOL_MINT)
        return d["price"] if d else None

def jup_sell_quote(mint, ui_amount):
    """token -> SOL route check on Jupiter lite-api (quote only, nothing is built or signed). -> (ok, info)"""
    try:
        dec = token_decimals(mint)
        amt = max(1, int(ui_amount * 10 ** dec))
        q = http_json(f"https://lite-api.jup.ag/swap/v1/quote?inputMint={mint}&outputMint={SOL_MINT}&amount={amt}&slippageBps=500")
        if not q.get("outAmount") or int(q["outAmount"]) <= 0: return False, {"err": "no route", "raw": str(q)[:200]}
        return True, dict(out_sol=int(q["outAmount"]) / 1e9, impact=float(q.get("priceImpactPct") or 0),
                          route="/".join((r.get("swapInfo") or {}).get("label", "?") for r in q.get("routePlan") or []))
    except urllib.error.HTTPError as e:
        return False, {"err": f"HTTP {e.code}"}
    except Exception as e:
        return False, {"err": repr(e)[:200]}

def live_leaders():
    """'**LIVE now:** a, b (reason...)' line in selfcopy/roster-status.md -> ['a','b'] (max 15)"""
    try:
        for line in open(ROSTER_STATUS):
            if "LIVE now:" in line:
                s = line.split("LIVE now:", 1)[1].replace("*", "").strip()
                s = s.split(" (", 1)[0].strip().rstrip(".")
                if not s or s.lower().startswith(("none", "nobody", "-", "–")): return []
                try:
                    import json as _j
                    _ex = set(_j.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"session.json"))).get("bg_copy_leaders") or [])
                except Exception: _ex = set()
                return [x.strip() for x in s.split(",") if x.strip() and x.strip() not in _ex][:15]
    except Exception: pass
    return []

# ---------------- exit rules: copy of selfcopy/live.py exit_plan (v3) ----------------
def exit_plan(x, *, tp_level, peak_x, be_x, leader_sold, adding):
    """-> None | (kind, frac_of_REMAINING, reason). kind: sl | trail | tp1 | tp2 | tp12 | moon | defer"""
    stop = be_x if tp_level > 0 else R["sl_frac"]
    if x <= stop: return ("sl", 1.0, "sl_breakeven" if tp_level > 0 else "sl_-15%")
    stp = R.get("single_tp_x")
    if stp and x >= stp: return ("tp_all", 1.0, f"tp_all_+{round((stp-1)*100)}%")   # day session: one TP, sell 100%
    pk = max(peak_x or x, x)
    if leader_sold:
        if x >= R["moon_x"]: return ("moon", 1.0, "tp_leftover_+500%")
        return None
    if tp_level == 0 and x >= R["tp1_x"]:
        if adding: return ("defer", None, "tp_+40%_deferred_leader_adding")
        if x >= R["tp2_x"]: return ("tp12", 0.5, "tp_+40%_and_+100%_25%+25%")
        return ("tp1", R["tp1_frac"], "tp_+40%_25%")
    if tp_level == 1 and x >= R["tp2_x"]:
        if adding: return ("defer", None, "tp_+100%_deferred_leader_adding")
        return ("tp2", 1 / 3, "tp_+100%_25%")
    if tp_level > 0:
        tf = R["trail_adding_frac"] if adding else R["trail_frac"]
        if x <= tf * pk: return ("trail", 1.0, f"sl_trail_-{round((1-tf)*100)}%_from_peak_{pk:.2f}x")
    return None

def mirror_keep(tokens_left, tokens_orig):
    """leader's FIRST sell: keep 10% of the original (or all if less is left). -> tokens to sell"""
    keep = min(tokens_left, R["keep_frac"] * tokens_orig)
    return max(0.0, tokens_left - keep)

def tp_level_after(reason, old):
    if reason.startswith("tp_+40%_and"): return 2
    if reason.startswith("tp_+40%"): return max(old, 1)
    if reason.startswith("tp_+100%"): return 2
    return old

def size_sol(bal, leader=None):
    """10% of SOL balance, floored to 0.001, keeping >= 0.02 SOL in the wallet; session cap and per-leader size"""
    s = int(bal * R["size_frac"] * 1000) / 1000
    s = min(s, int(max(0.0, bal - R["reserve_sol"]) * 1000) / 1000)
    ss = session()
    if ss and ss.get("size_cap_sol"): s = min(s, float(ss["size_cap_sol"]))
    if ss and leader and (ss.get("leader_size_sol") or {}).get(leader): s = min(s, float(ss["leader_size_sol"][leader]))
    return s if s >= R["min_size_sol"] else 0.0

# 16:15Z: on-chain holdings of Chunk's wallet (SPL Token + Token-2022), so Banana Gun copy-trade buys that never reach
# positions.json count toward max_open and the equity halt. Read-only getTokenAccountsByOwner on public RPC.
TOKEN_PROGRAMS = ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
# 25 Oct 08:55Z fix (user-approved 08:51Z): stablecoins are NO LONGER dropped from holdings -- they are valued at $1/token
# (watch.py hval). Dropping them caused the false HALT 03:02:59Z (8.19 USDC from a bystevenr copy valued 0).
STABLE_MINTS = {"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
                "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo": "PYUSD"}
NON_COIN_MINTS = {SOL_MINT}
def wallet_holdings(addr=WALLET):
    """-> {mint: ui_amount} for every non-zero token account (both programs) except wSOL (stablecoins included)"""
    out = {}
    for prog in TOKEN_PROGRAMS:
        r = rpc("getTokenAccountsByOwner", [addr, {"programId": prog}, {"encoding": "jsonParsed", "commitment": "confirmed"}])
        for a in r.get("value", []):
            i = a["account"]["data"]["parsed"]["info"]
            ui = float(i["tokenAmount"].get("uiAmount") or 0)
            if ui > 0 and i["mint"] not in NON_COIN_MINTS: out[i["mint"]] = out.get(i["mint"], 0) + ui
    return out
