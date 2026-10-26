#!/usr/bin/env python3
"""
Self-run Solana copy-trading bot. PAPER for all leaders; optional LIVE for _benjitrades only (see live.py).
- PAPER part: read-only, never signs or sends.
- LIVE part (live.py): OFF unless ./LIVE exists or `run --live`; dedicated bot wallet only; hard caps in code.
- Read-only calls only: Solana JSON-RPC (getSignaturesForAddress/getTransaction/getTokenSupply),
  Jupiter public quote + price API (lite-api.jup.ag), DexScreener, rugcheck.xyz.
Usage:
  python3 selfcopy.py run                       # long-running poller (use run_loop.sh)
  python3 selfcopy.py dryrun --leader NAME [--sig SIG] [--force] [--requotes N]
  python3 selfcopy.py summary                   # rebuild summary.md from state
"""
import os, sys, json, time, csv, urllib.request, urllib.error, argparse, traceback, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
OI = "/workspace/onchain-intel"
DUB = ZoneInfo("Europe/Dublin")
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
QUOTE_MINTS = {WSOL, USDC, USDT}

CFG = dict(
    stake_usd=5.0, min_leader_usd=50.0, min_mcap=100_000, max_chase=0.15,
    entry_delay_s=3.0, priority_fee_sol=0.0005, base_fee_sol=0.000005,
    leader_full_exit=0.95,   # exits: live.exit_plan (v3, shared with LIVE)
    poll_every_s=8.0, requote_every_s=12.0, jup_min_gap_s=2.2,
    slippage_bps=1500, close_hour_dublin=8, no_entry_from=(7, 45),
    copyfomo_fee_side=0.02, copyfomo_flat_rt=0.053,
    noroute_rug_s=600,
)

LEADERS = ["_benjitrades", "bystevenr", "pointfarmcap", "ExactTallTakin"]   # seed for roster.json only
ROSTER_FN = os.path.join(HERE, "roster.json")
PRUNE_LOG = os.path.join(HERE, "prune-log.jsonl")
CHUNK_POS = "/workspace/runner-radar/copylive/positions.json"   # Chunk's real copies (read-only)
INBOX_FN = os.path.join(HERE, "roster_inbox.json")      # Scout writes [{label, wallet, confidence, source}]; merged every minute
import roster as R

def now(): return time.time()
def iso(t=None): return datetime.datetime.fromtimestamp(t or now(), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class Bot:
    def __init__(self, tag=""):
        self.tag = tag
        self.trades_fn = os.path.join(HERE, f"{tag}paper-trades.jsonl")
        self.quotes_fn = os.path.join(HERE, f"{tag}quotes.jsonl")
        self.state_fn = os.path.join(HERE, f"{tag}state.json")
        self.summary_fn = os.path.join(HERE, f"{tag}summary.md")
        self.state = json.load(open(self.state_fn)) if os.path.exists(self.state_fn) else {}
        s = self.state
        s.setdefault("cursors", {}); s.setdefault("seen", {}); s.setdefault("positions", [])
        s.setdefault("stats", {}); s.setdefault("started", iso()); s.setdefault("closed_days", [])
        s.setdefault("skips", {}); s.setdefault("detected", 0)
        self.load_leaders(); self.load_avoid(); self.load_history()
        rpcs = [("publicnode", "https://solana-rpc.publicnode.com", 0.25), ("mainnet-beta", "https://api.mainnet-beta.solana.com", 0.6)]
        k = os.environ.get("HELIUS_API_KEY")   # env var only; never printed or logged
        if k: rpcs.insert(0, ("helius", "https://mainnet.helius-rpc.com/?api-key=" + k, 0.2))
        self.rpcs = [dict(name=n, url=u, gap=g, last=0.0, cool=0.0) for n, u, g in rpcs]
        self.jup_last = 0.0; self.jup_cool = 0.0
        self.solpx = None; self.solpx_t = 0
        self.pending = []      # entries waiting for 3s delay
        self.status_fn = os.path.join(HERE, f"{tag}roster-status.md")
        self.dec_cache = {}
        self.live = None

    # ---------- inputs ----------
    def seed_roster(self):
        m = json.load(open(os.path.join(OI, "data", "leader_mappings.json")))
        wj = json.load(open("/workspace/trader-analysis/wallets.json"))
        L = []
        for n in LEADERS:
            assert m[n]["wallet"] in wj.get(n, []), f"wallet mismatch for {n}"
            L.append(dict(label=n, wallet=m[n]["wallet"], source="onchain-intel leader_mappings.json (seed)", confidence=m[n]["confidence"], added=iso(), active=True))
        json.dump(dict(note="Edited by Zero only (from /workspace/scout/copy-candidates.md). The bot never adds wallets. Max 20 active. Set active:false to drop one.",
                       leaders=L), open(ROSTER_FN, "w"), indent=1)
    def load_leaders(self):
        if not os.path.exists(ROSTER_FN): self.seed_roster()
        ents, warn = R.load_roster(ROSTER_FN)
        self.roster_mtime = os.path.getmtime(ROSTER_FN)
        old = getattr(self, "leaders", {})
        self.leaders = {e["label"]: dict(wallet=e["wallet"], confidence=e["confidence"], source=e["source"]) for e in ents}
        for n, v in old.items():      # dropped leaders with open paper positions keep being polled (mirror sells) until flat
            if n not in self.leaders and any(p["leader"] == n and p["status"] == "open" for p in self.state["positions"]):
                self.leaders[n] = dict(v, dropped=True)
        self.names = list(self.leaders)
        for w in warn: print("roster:", w, flush=True)
        return warn
    def load_avoid(self):
        self.avoid_addr, self.avoid_mints = set(), set()
        for r in csv.DictReader(open(os.path.join(OI, "avoid.csv"))):
            if r.get("address"): self.avoid_addr.add(r["address"].strip())
            for mm in (r.get("mints") or "").replace(",", " ").split(): self.avoid_mints.add(mm.strip())
        self.avoid_mtime = os.path.getmtime(os.path.join(OI, "avoid.csv"))
    def load_history(self):
        """Mints each leader already traded (30d Helius history) -> not a FIRST buy."""
        self.hist = {}
        try:
            for r in csv.DictReader(open(os.path.join(OI, "trader_swaps.csv"))):
                self.hist.setdefault(r["trader"], set()).add((r["mint"], r["timestamp"]))
        except Exception: pass

    # ---------- logging ----------
    def log(self, ev, **kw):
        rec = dict(ts=iso(), event=ev, paper=True, **kw)
        with open(self.trades_fn, "a") as f: f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec), flush=True)
    def qlog(self, **kw):
        with open(self.quotes_fn, "a") as f: f.write(json.dumps(dict(ts=iso(), **kw)) + "\n")
    def stat(self, name, key):
        st = self.state["stats"].setdefault(name, {}); st[key] = st.get(key, 0) + 1
    def save(self):
        tmp = self.state_fn + ".tmp"; json.dump(self.state, open(tmp, "w"), indent=1); os.replace(tmp, self.state_fn)

    # ---------- http ----------
    def http(self, url, data=None, timeout=15, name=None):
        req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json", "User-Agent": "selfcopy-paper/1.0"})
        try:
            r = urllib.request.urlopen(req, timeout=timeout); body = r.read()
            if name: self.stat(name, "ok")
            return json.loads(body)
        except urllib.error.HTTPError as e:
            if name: self.stat(name, f"http_{e.code}")
            try: return {"_http_error": e.code, "_body": e.read()[:300].decode("utf8", "ignore")}
            except Exception: return {"_http_error": e.code}
        except Exception as e:
            if name: self.stat(name, "err_" + type(e).__name__)
            return None

    def rpc(self, method, params, tries=4):
        for a in range(tries):
            cands = sorted([r for r in self.rpcs if r["cool"] <= now()], key=lambda r: r["last"]) or sorted(self.rpcs, key=lambda r: r["cool"])
            r = cands[a % len(cands)]
            w = r["last"] + r["gap"] - now()
            if w > 0: time.sleep(w)
            r["last"] = now()
            j = self.http(r["url"], {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, name="rpc:" + r["name"])
            if j and "result" in j:
                if j["result"] is not None or method != "getTransaction": return j["result"]
                self.stat("rpc:" + r["name"], "null_tx"); continue      # non-archival node / not yet visible: try another
            if j and j.get("_http_error") == 429: r["cool"] = now() + 10
            elif j is None or "_http_error" in j: r["cool"] = now() + 3
            time.sleep(0.4 * (a + 1))
        return None

    def jup(self, path, params, purpose):
        url = "https://lite-api.jup.ag" + path + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        for a in range(4):
            w = max(self.jup_last + CFG["jup_min_gap_s"], self.jup_cool) - now()
            if w > 0: time.sleep(w)
            self.jup_last = now()
            j = self.http(url, timeout=10, name="jupiter")
            if j and "_http_error" not in j: return j
            if j and j.get("_http_error") == 429: self.jup_cool = now() + 6
            elif j and j.get("_http_error") in (400, 404):   # e.g. no route
                return j
            time.sleep(1)
        return None

    def sol_price(self):
        if self.solpx and now() - self.solpx_t < 120: return self.solpx
        j = self.jup("/price/v3", {"ids": WSOL}, "solpx")
        try: self.solpx = float(j[WSOL]["usdPrice"]); self.solpx_t = now()
        except Exception: pass
        return self.solpx

    def quote(self, inp, out, amount, purpose):
        j = self.jup("/swap/v1/quote", {"inputMint": inp, "outputMint": out, "amount": int(amount),
                                        "slippageBps": CFG["slippage_bps"], "swapMode": "ExactIn"}, purpose)
        if not j or "outAmount" not in j:
            return None, (j or {}).get("_body") or (j or {}).get("error") or "no response"
        return dict(out=int(j["outAmount"]), impact=float(j.get("priceImpactPct") or 0),
                    route="+".join(x["swapInfo"].get("label", "?") for x in j.get("routePlan", [])),
                    usd=float(j.get("swapUsdValue") or 0), slot=j.get("contextSlot")), None

    # ---------- token info ----------
    def token_info(self, mint):
        info = dict(mcap=None, liq=None, price=None, src=None, age_s=None)
        j = self.http(f"https://api.dexscreener.com/tokens/v1/solana/{mint}", name="dexscreener")
        if isinstance(j, list) and j:
            p = max(j, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
            pc = p.get("pairCreatedAt")    # main (deepest) pool: creation = graduation pool for pump tokens
            info.update(pair_created_ms=pc, age_s=(now() - pc / 1000) if pc else None, dex=p.get("dexId"))
            info.update(mcap=p.get("marketCap") or p.get("fdv"), liq=(p.get("liquidity") or {}).get("usd"),
                        price=float(p["priceUsd"]) if p.get("priceUsd") else None, src="dexscreener")
        if info["mcap"] is None:
            pj = self.jup("/price/v3", {"ids": mint}, "tokpx")
            sup = self.rpc("getTokenSupply", [mint])
            try:
                px = float(pj[mint]["usdPrice"]); s = float(sup["value"]["uiAmountString"])
                info.update(mcap=px * s, price=px, src="jupiter_price*supply")
            except Exception: pass
        return info

    def creator(self, mint):
        j = self.http(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", timeout=10, name="rugcheck")
        if isinstance(j, dict) and "_http_error" not in j: return j.get("creator")
        return None

    # ---------- swap parsing ----------
    def parse_swap(self, tx, wallet, sig):
        if not tx or tx.get("meta") is None or tx["meta"].get("err"): return None
        m = tx["meta"]; msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
        tok, pre_bal, dec = {}, {}, {}
        for side, sg in (("preTokenBalances", -1), ("postTokenBalances", 1)):
            for b in m.get(side) or []:
                if b.get("owner") != wallet: continue
                a = float(b["uiTokenAmount"]["uiAmountString"] or 0)
                tok[b["mint"]] = tok.get(b["mint"], 0) + sg * a
                dec[b["mint"]] = b["uiTokenAmount"]["decimals"]
                if sg == -1: pre_bal[b["mint"]] = pre_bal.get(b["mint"], 0) + a
        sol = 0.0
        if wallet in keys:
            i = keys.index(wallet); sol = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
            if i == 0: sol += m.get("fee", 0) / 1e9          # don't count tx fee as trade size
        sol += tok.pop(WSOL, 0)
        usd_q = tok.pop(USDC, 0) + tok.pop(USDT, 0)
        moved = {k: v for k, v in tok.items() if abs(v) > 1e-12}
        if len(moved) != 1: return None
        mint, d = next(iter(moved.items()))
        px = self.sol_price() or 0
        quote_usd = sol * px + usd_q          # + = received, - = spent
        side = "buy" if d > 0 and quote_usd < 0 else "sell" if d < 0 and quote_usd > 0 else None
        if not side: return None
        size = abs(quote_usd)
        return dict(sig=sig, side=side, mint=mint, tokens=abs(d), usd=round(size, 2), decimals=dec.get(mint),
                    fill_px=size / abs(d) if d else None, pre_bal=pre_bal.get(mint, 0.0),
                    block_time=tx.get("blockTime"), quote_leg="USDC/USDT" if usd_q else "SOL")

    def get_tx(self, sig):
        return self.rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}])

    # ---------- polling ----------
    def poll(self, name):
        w = self.leaders[name]["wallet"]; cur = self.state["cursors"].get(name)
        p = {"limit": 25, "commitment": "confirmed"}
        if cur: p["until"] = cur
        r = self.rpc("getSignaturesForAddress", [w, p])
        if r is None: return
        if not cur:
            if r: self.state["cursors"][name] = r[0]["signature"]; self.state.setdefault("cursor_bt", {})[name] = r[0].get("blockTime")
            self.log("cursor_init", leader=name, wallet=w, newest=r[0]["signature"] if r else None)
            return
        if not r: return
        done = self.state.setdefault("done", {}).setdefault(name, [])
        cbt = self.state.setdefault("cursor_bt", {}).get(name) or 0
        new = [s for s in r if s["signature"] not in done and (s.get("blockTime") or 1e12) >= cbt - 5]
        if not new: return
        self.state["cursors"][name] = new[0]["signature"]; self.state["cursor_bt"][name] = new[0].get("blockTime") or cbt
        for s in reversed(new):         # oldest first
            done.append(s["signature"]); del done[:-300]
            if s.get("err"): continue
            sw = self.parse_swap(self.get_tx(s["signature"]), w, s["signature"])
            if sw: self.on_leader_swap(name, sw, detected=now())

    # ---------- strategy ----------
    def on_leader_swap(self, name, sw, detected, force=False):
        self.state["detected"] += 1
        lt = self.state.setdefault("last_trade", {}); t = min(sw.get("block_time") or detected, detected)
        lt[name] = max(lt.get(name) or 0, t)          # for the roster inactivity rule (any buy or sell seen)
        lag = round(detected - sw["block_time"], 1) if sw.get("block_time") else None
        self.log("leader_swap", leader=name, side=sw["side"], mint=sw["mint"], usd=sw["usd"], tokens=sw["tokens"],
                 fill_px=sw["fill_px"], pre_bal=sw["pre_bal"], sig=sw["sig"], detect_lag_s=lag, quote_leg=sw["quote_leg"])
        if sw["side"] == "buy": self.consider_entry(name, sw, detected, force)
        else: self.mirror_sell(name, sw)

    def skip(self, name, sw, reason, **kw):
        self.state["skips"].setdefault(name, {}); self.state["skips"][name][reason] = self.state["skips"][name].get(reason, 0) + 1
        self.log("skip", leader=name, mint=sw["mint"], reason=reason, leader_usd=sw["usd"], sig=sw["sig"], **kw)

    def consider_entry(self, name, sw, detected, force=False):
        seen = self.state["seen"].setdefault(name, [])
        mint = sw["mint"]
        prior = [t for (mm, t) in self.hist.get(name, ()) if mm == mint and (not sw.get("block_time") or t < iso(sw["block_time"]))]
        first = sw["pre_bal"] <= 1e-9 and mint not in seen and not prior
        if mint not in seen: seen.append(mint)
        topup = None
        if not first:
            self.note_add(name, sw, detected)
            topup, why = self.topup_eligible(name, mint)
            if not topup:
                return self.skip(name, sw, "not_first_buy", pre_bal=sw["pre_bal"], prior_hist=len(prior), **({"topup_skip": why} if why else {}))
        if sw["usd"] < self.sess_val("min_leader_usd", CFG["min_leader_usd"]): return self.skip(name, sw, "leader_buy_lt_min")
        if os.path.getmtime(os.path.join(OI, "avoid.csv")) != self.avoid_mtime: self.load_avoid()
        if mint in self.avoid_mints or mint in self.avoid_addr: return self.skip(name, sw, "avoid_mint")
        if any(p["mint"] == mint and p["status"] == "open" for p in self.state["positions"]):
            return self.skip(name, sw, "already_open_same_mint")
        loc = datetime.datetime.now(DUB)
        if (loc.hour, loc.minute) >= CFG["no_entry_from"] and loc.hour < CFG["close_hour_dublin"] and not force:
            return self.skip(name, sw, "too_close_to_0800")
        import live as livemod
        sb = livemod.session_entry_block(loc, livemod.load_session(HERE))
        if sb and not force: return self.skip(name, sw, sb)
        self.pending.append(dict(name=name, sw=sw, due=detected + CFG["entry_delay_s"], detected=detected, force=force, topup=topup))

    def tiny_rule(self, k):
        """15:15Z tiny tier keys from session.json (raw) while the session applies; None = off"""
        try:
            import live as _lm
            s = _lm.load_session(HERE)
            if not (s and _lm.session_applies(now(), s)): return None
            v = json.load(open(os.path.join(HERE, "session.json"))).get(k)
            return float(v) if v not in (None, "") else None
        except Exception: return None

    def sess_val(self, k, default):
        """15:10Z: while the day session applies, its (clamped) min_mcap_usd / min_leader_usd / max_chase govern the paper gate."""
        try:
            import live as _lm
            s = _lm.load_session(HERE)
            if s and _lm.session_applies(now(), s) and s.get(k) is not None: return s[k]
        except Exception: pass
        return default

    def topup_eligible(self, name, mint, t=None):
        """session.json topup_entry (manual-live wallets only, this session only): a buy of a token the leader already
        holds may open ONE entry per mint per session (even after we exit), never while we hold the mint.
        -> (session_key, None) if eligible, else (None, reason or None when the wallet isn't a top-up wallet)."""
        import live as livemod
        t = now() if t is None else t
        sess = livemod.load_session(HERE)
        if not sess or not livemod.session_applies(t, sess): return None, None
        live_now = (self.state.get("rotation") or {}).get("live") or []
        if not (name in (sess.get("topup_entry") or []) or (sess.get("topup_all_live") and name in live_now)): return None, None
        if livemod.session_entry_block(t, sess): return None, "topup_session_blocked"
        if mint in self.state.setdefault("topup_entries", {}).get(sess["key"], {}): return None, "topup_already_entered_this_session"
        if any(p["mint"] == mint and p["status"] == "open" for p in self.state["positions"]): return None, "topup_already_open_same_mint"
        return sess["key"], None

    def do_entry(self, pe):
        name, sw, force = pe["name"], pe["sw"], pe["force"]; mint = sw["mint"]
        topup = pe.get("topup")
        if topup:   # re-check at entry time (two top-up buys inside the delay, or a position opened meanwhile)
            k2, why = self.topup_eligible(name, mint)
            if k2 != topup: return self.skip(name, sw, why or "topup_session_changed")
        info = self.token_info(mint)
        overrides = []
        _mm = self.sess_val("min_mcap_usd", CFG["min_mcap"])
        tier = "normal"
        if info["mcap"] is not None and info["mcap"] < _mm and self.tiny_rule("tiny_min_mcap_usd") and info["mcap"] >= self.tiny_rule("tiny_min_mcap_usd"):
            tier = "tiny"   # 15:15Z tiny tier: Chunk sizes 0.02 SOL and re-checks liq/age/rugguard/impact
        if tier == "normal" and (info["mcap"] is None or info["mcap"] < _mm):
            if force: overrides.append("mcap")
            else: return self.skip(name, sw, "mcap_lt_100k" if info["mcap"] is not None else "mcap_unknown", mcap=info["mcap"])
        cr = self.creator(mint)
        if cr and cr in self.avoid_addr:
            if force: overrides.append("avoid_creator")
            else: return self.skip(name, sw, "avoid_creator", creator=cr)
        px = self.sol_price()
        if not px: return self.skip(name, sw, "no_sol_price")
        lam = int(CFG["stake_usd"] / px * 1e9)
        q, err = self.quote(WSOL, mint, lam, "entry")
        t_q = now()
        if not q: return self.skip(name, sw, "no_jupiter_route", err=str(err)[:200])
        dec = sw["decimals"] if sw["decimals"] is not None else 6
        tokens_ui = q["out"] / 10 ** dec
        our_px = CFG["stake_usd"] / tokens_ui
        chase = our_px / sw["fill_px"] - 1 if sw["fill_px"] else None
        filt = dict(mcap=info["mcap"], liq=info["liq"], creator=cr, chase=round(chase, 4) if chase is not None else None)
        if chase is not None and chase > self.sess_val("max_chase", CFG["max_chase"]):
            if force: overrides.append("chase")
            else: return self.skip(name, sw, "chase_gt_15pct", **filt, our_px=our_px, leader_px=sw["fill_px"])
        import live as livemod
        info["leader_age_s"] = (pe["detected"] - sw["block_time"]) if sw.get("block_time") else None
        _ss = livemod.load_session(HERE)
        _ss = _ss if _ss and livemod.session_applies(now(), _ss) else None
        v2f = livemod.signal_filters(mcap=info["mcap"], liq=info["liq"], age_s=info.get("age_s"), leader_age_s=info["leader_age_s"], chase=chase, sess=_ss)
        filt.update(age_min=round(info["age_s"] / 60, 1) if info.get("age_s") else None, leader_age_s=round(info["leader_age_s"], 1) if info["leader_age_s"] is not None else None,
                    v2_pass=not v2f, v2_fails=v2f)
        if topup and v2f and self.tiny_rule("tiny_min_mcap_usd") and set(v2f) <= {"mcap_lt_min", "liq_lt_min", "age_lt_min"} \
                and (info["mcap"] or 0) >= self.tiny_rule("tiny_min_mcap_usd") and (info["liq"] or 0) >= self.tiny_rule("tiny_min_liq_usd") \
                and (info.get("age_s") or 0) >= self.tiny_rule("tiny_min_age_min") * 60:
            tier = "tiny"; v2f = []
        # 16:20Z curve tier: pump.fun bonding-curve top-ups (liq unknown/0) with mcap >= $8k, age >= 1 min; copylive checks Jupiter impact at 0.02 SOL
        if topup and v2f and mint.endswith("pump") and not info.get("liq") and set(v2f) <= {"mcap_lt_min", "liq_lt_min", "age_lt_min"} \
                and (info["mcap"] or 0) >= 8000 and (info.get("age_s") or 0) >= 60:
            tier = "curve"; v2f = []
        filt["tier"] = tier
        if topup and v2f: return self.skip(name, sw, "topup_v2_fail", **filt)   # top-ups must pass every LIVE filter
        fee_usd = (CFG["priority_fee_sol"] + CFG["base_fee_sol"]) * px
        pos = dict(id=f"{name}:{mint[:8]}:{int(t_q)}", leader=name, wallet=self.leaders[name]["wallet"],
                   confidence=self.leaders[name]["confidence"], mint=mint, decimals=dec, status="open",
                   opened=iso(t_q), leader_sig=sw["sig"], leader_usd=sw["usd"], leader_px=sw["fill_px"],
                   entry_delay_s=round(t_q - pe["detected"], 1),
                   entry_lamports=lam, entry_sol_px=px, tokens_raw=q["out"], tokens_left=q["out"],
                   entry_px=our_px, entry_impact=q["impact"], route=q["route"], cost_usd=CFG["stake_usd"],
                   fees_usd=fee_usd, proceeds_usd=0.0, cf_proceeds_usd=0.0, tp_done=False, sells=[],
                   last_value=CFG["stake_usd"], next_q=now() + CFG["requote_every_s"], noroute_since=None,
                   forced_filter_override=",".join(overrides) or False, **{"filters": filt})
        if topup:
            pos.update(topup=topup, opened_ts=t_q)
            self.state.setdefault("topup_entries", {}).setdefault(topup, {})[mint] = dict(pos=pos["id"], ts=iso(t_q), leader=name)
        self.state["positions"].append(pos)
        self.log("entry", pos=pos["id"], leader=name, confidence=pos["confidence"], mint=mint, stake_usd=CFG["stake_usd"],
                 sol_in=lam / 1e9, tokens=tokens_ui, entry_px=our_px, leader_px=sw["fill_px"], chase=filt["chase"],
                 impact_pct=q["impact"], route=q["route"], priority_fee_usd=round(fee_usd, 4), delay_s=pos["entry_delay_s"],
                 mcap=info["mcap"], liq=info["liq"], forced=pos["forced_filter_override"],
                 v2_pass=filt["v2_pass"], v2_fails=filt["v2_fails"], age_min=filt["age_min"], leader_age_s=filt["leader_age_s"],
                 leader_usd=sw["usd"], tier=tier, leader_ts=iso(sw["block_time"]) if sw.get("block_time") else None,
                 **(dict(topup=True, topup_session=topup, leader_pre_bal=sw["pre_bal"]) if topup else {}))
        self.save()
        if self.live:
            try:
                self.live.on_paper_entry(name, sw, info, avoid=False, first_buy=not topup, forced=bool(overrides) or bool(force),
                                         loc=datetime.datetime.now(DUB), solpx=px)
            except Exception as e:
                self.live.log("error", where="entry", err=repr(e), tb=traceback.format_exc()[-800:])

    def sell(self, pos, frac, reason, q=None):
        amt = int(pos["tokens_left"] * frac) if frac < 0.999 else pos["tokens_left"]
        if amt <= 0: return
        if q is None or frac < 0.999:
            q, err = self.quote(pos["mint"], WSOL, amt, "exit")
        if not q:
            self.log("exit_quote_fail", pos=pos["id"], reason=reason); return False
        px = self.sol_price() or pos["entry_sol_px"]
        usd = q["out"] / 1e9 * px
        fee = (CFG["priority_fee_sol"] + CFG["base_fee_sol"]) * px
        pos["tokens_left"] -= amt; pos["proceeds_usd"] += usd; pos["fees_usd"] += fee
        pos["cf_proceeds_usd"] += usd * (1 - CFG["copyfomo_fee_side"])
        pos["sells"].append(dict(ts=iso(), reason=reason, frac=round(frac, 4), tokens=amt, usd=round(usd, 4), impact=q["impact"]))
        if pos["tokens_left"] <= 0: self.close(pos)
        self.log("exit", pos=pos["id"], leader=pos["leader"], mint=pos["mint"], reason=reason, frac=round(frac, 4),
                 usd=round(usd, 4), impact_pct=q["impact"], route=q["route"], status=pos["status"],
                 net_usd=round(self.net(pos), 4) if pos["status"] == "closed" else None)
        self.save(); return True

    def close(self, pos):
        pos["status"] = "closed"; pos["closed"] = iso()
    def net(self, pos, mark=None):
        """our net $ (Jupiter quotes + priority fees)"""
        v = pos["proceeds_usd"] + (mark or 0)
        return v - pos["cost_usd"] - pos["fees_usd"]
    def cf_net(self, pos, mark=None):
        """same fills, copyfomo 2%/side fee, no priority fee (relayed)"""
        v = pos["cf_proceeds_usd"] + (mark or 0) * (1 - CFG["copyfomo_fee_side"])   # exit fee 2%
        return v * (1 - CFG["copyfomo_fee_side"]) - pos["cost_usd"]                    # entry fee 2% => 2% fewer tokens
    def cf_flat(self, pos, mark=None):
        """same fills, flat 5.3% round-trip all-in, no priority fee"""
        return pos["proceeds_usd"] + (mark or 0) - pos["cost_usd"] - CFG["copyfomo_flat_rt"] * pos["cost_usd"]

    def requote_gap(self):
        """Jupiter budget ~4.5 calls/10s shared by paper marks, live marks and entries: space marks by open count."""
        n = sum(1 for p in self.state["positions"] if p["status"] == "open")
        return max(CFG["requote_every_s"], 3.0 * n)
    def requote(self, pos):
        pos["next_q"] = now() + self.requote_gap()
        q, err = self.quote(pos["mint"], WSOL, pos["tokens_left"], "mark")
        if not q:
            pos["noroute_since"] = pos["noroute_since"] or now()
            self.qlog(pos=pos["id"], err=str(err)[:120]); return
        pos["noroute_since"] = None
        px = self.sol_price() or pos["entry_sol_px"]
        val = q["out"] / 1e9 * px; pos["last_value"] = val; pos["last_q"] = iso()
        frac_left = pos["tokens_left"] / pos["tokens_raw"]
        basis = pos["cost_usd"] * frac_left
        self.qlog(pos=pos["id"], value_usd=round(val, 4), basis=round(basis, 4), x=round(val / basis, 4) if basis else None, impact=q["impact"])
        self.apply_exit(pos, val, basis, q, px)

    def apply_exit(self, pos, val, basis, q, px):
        """paper uses the SAME v3 exit rules as LIVE (live.exit_plan) so roster scores match live exits."""
        import live as livemod
        if basis <= 0: return
        if pos.get("leader_sold") and pos["tokens_left"] > (pos.get("keep_raw") or 0) * 1.01 + 1:
            f, _ = livemod.mirror_keep(pos["tokens_left"], pos["tokens_raw"])
            if f > 0 and self.sell(pos, f, "leader_sold_keep10_retry"): return
        x = val / basis
        adding = now() - (pos.get("last_add_ts") or 0) < livemod.HARD["add_window_s"]
        tx_fee = (CFG["priority_fee_sol"] + CFG["base_fee_sol"]) * px
        lvl = pos.get("tp_level", 1 if pos.get("tp_done") else 0)
        dec = livemod.exit_plan(x, tp_level=lvl, peak_x=pos.get("peak_x"), be_x=livemod.breakeven_x(pos["cost_usd"], 2 * tx_fee),   # paper basis excludes entry fee
                                leader_sold=pos.get("leader_sold", False), adding=adding)
        pos["peak_x"] = max(pos.get("peak_x") or 0, x)
        if not dec: return
        kind, frac, reason = dec
        if kind == "defer":
            if pos.get("deferred") != reason: pos["deferred"] = reason; self.log("tp_deferred", pos=pos["id"], reason=reason, x=round(x, 4))
            return
        pos["deferred"] = None
        ok = self.sell(pos, frac, reason, q=q if frac >= 0.999 else None)
        if ok and kind in ("tp1", "tp2", "tp12"):
            pos["tp_level"] = {"tp1": 1, "tp2": 2, "tp12": 2}[kind]; pos["tp_done"] = True

    def note_add(self, name, sw, detected):
        """leader bought more of a token we hold (paper + live): TPs deferred, trail widened for 10 min."""
        ts = sw.get("block_time") or detected
        for pos in self.state["positions"]:
            if pos["status"] == "open" and pos["leader"] == name and pos["mint"] == sw["mint"]:
                if pos.get("topup") and ts < (pos.get("opened_ts") or 0):
                    self.log("leader_add_before_entry_ignored", pos=pos["id"], add_ts=ts); continue
                pos["last_add_ts"] = max(pos.get("last_add_ts") or 0, ts); self.log("leader_add", pos=pos["id"], add_ts=ts)
        if self.live:
            try: self.live.note_add(name, sw["mint"], ts)
            except Exception as e: self.live.log("error", where="note_add", err=repr(e))

    def mirror_sell(self, name, sw):
        import live as livemod
        for pos in self.state["positions"]:
            if pos["status"] != "open" or pos["leader"] != name or pos["mint"] != sw["mint"]: continue
            if pos.get("topup") and (sw.get("block_time") or now()) < (pos.get("opened_ts") or 0):   # top-up: only sells AFTER our entry
                self.log("leader_sell_before_entry_ignored", pos=pos["id"], sig=sw["sig"], block_time=sw.get("block_time")); continue
            lf = sw["tokens"] / sw["pre_bal"] if sw["pre_bal"] else 1.0
            if pos.get("leader_sold"):
                self.log("leader_sell_ignored_leftover", pos=pos["id"], leader_frac=round(lf, 4), sig=sw["sig"]); continue
            f, keep = livemod.mirror_keep(pos["tokens_left"], pos["tokens_raw"])
            pos["leader_sold"] = True; pos["keep_raw"] = keep
            self.log("leader_sell_mirror", pos=pos["id"], leader_frac=round(lf, 4), our_frac=round(f, 4), keep_raw=keep, sig=sw["sig"])
            if f > 0: self.sell(pos, f, f"leader_sold_{round(lf*100)}%_keep10")
        if self.live:
            lf = sw["tokens"] / sw["pre_bal"] if sw["pre_bal"] else 1.0
            frac = 1.0 if lf >= CFG["leader_full_exit"] else max(0.0, min(1.0, lf))
            try: self.live.mirror(name, sw, frac, lf)
            except Exception as e: self.live.log("error", where="mirror", err=repr(e), tb=traceback.format_exc()[-800:])

    def session_note(self):
        import live as livemod
        x = livemod.load_session(HERE)
        if not x: return ""
        return f"; SESSION {x['key']}: entries until {iso(x['end_ts'] - x['no_entry_s'])}, flat at {iso(x['end_ts'])}"
    def forced_close(self, reason="close_0800_dublin"):
        for pos in self.state["positions"]:
            if pos["status"] != "open": continue
            ok = self.sell(pos, 1.0, reason)
            if not ok:   # no route: rugged/illiquid -> mark at 0
                pos["sells"].append(dict(ts=iso(), reason=reason + "_no_route_zero", frac=1, tokens=pos["tokens_left"], usd=0))
                pos["tokens_left"] = 0; self.close(pos)
                self.log("exit", pos=pos["id"], leader=pos["leader"], mint=pos["mint"], reason=reason + "_no_route_zero", usd=0, status="closed", net_usd=round(self.net(pos), 4))
        self.save()

    # ---------- summary ----------
    def write_summary(self):
        P = self.state["positions"]; rows = []
        L = ["# Self-copy summary (PAPER all roster leaders + LIVE rotation slots)", "", "> **Paper rows are simulated** from live Jupiter quotes (read-only). **The LIVE section at the bottom is real money** in the dedicated bot wallet.", "",
             f"Updated {iso()} (Dublin {datetime.datetime.now(DUB):%Y-%m-%d %H:%M}). Running since {self.state['started']}. Leader swaps detected: {self.state['detected']}.", "",
             f"Rules: ${CFG['stake_usd']:.0f}/trade, leader buy ≥ ${CFG['min_leader_usd']:.0f}, mcap ≥ ${CFG['min_mcap']:,}, first buys only, avoid.csv, max chase {CFG['max_chase']:.0%}, {CFG['entry_delay_s']:.0f}s delay, exits = LIVE v3 rules (SL −15% → breakeven after first TP; TP 25% at +40% and 25% at +100%, deferred while the leader adds; trail 25%/35% below peak after TP1; leader's first sell → keep 10% leftover that exits at +500% or its stop), flat by 08:00 Dublin{self.session_note()}. Trades opened before 24 Oct 00:20 UTC used −25%/+100% until then. Costs (ours): Jupiter quote (route fees + impact) + {CFG['priority_fee_sol']} SOL priority fee per tx.", "",
             "| leader | conf. | trades (closed/open) | wins | losses | our net $ | our net % | copyfomo 2%/side $ | copyfomo % | copyfomo flat 5.3% $ |",
             "|---|---|---|---|---|---|---|---|---|---|"]
        tot = dict(n=0, c=0, o=0, w=0, l=0, net=0, cf=0, cff=0, cost=0)
        for name in self.names + sorted({p["leader"] for p in P} - set(self.names)):
            ps = [p for p in P if p["leader"] == name]
            if name not in self.leaders: self.leaders[name] = dict(confidence="removed", wallet="?")
            c = [p for p in ps if p["status"] == "closed"]; o = [p for p in ps if p["status"] == "open"]
            net = sum(self.net(p, p["last_value"] if p["status"] == "open" else 0) for p in ps)
            cf = sum(self.cf_net(p, p["last_value"] if p["status"] == "open" else 0) for p in ps)
            cff = sum(self.cf_flat(p, p["last_value"] if p["status"] == "open" else 0) for p in ps)
            cost = sum(p["cost_usd"] for p in ps)
            w = sum(1 for p in c if self.net(p) > 0); l = len(c) - w
            pct = f"{net/cost*100:+.1f}%" if cost else "–"; cpct = f"{cf/cost*100:+.1f}%" if cost else "–"
            L.append(f"| {name} | {self.leaders[name]['confidence']} | {len(ps)} ({len(c)}/{len(o)}) | {w} | {l} | {net:+.2f} | {pct} | {cf:+.2f} | {cpct} | {cff:+.2f} |")
            for k, v in dict(n=len(ps), c=len(c), o=len(o), w=w, l=l, net=net, cf=cf, cff=cff, cost=cost).items(): tot[k] += v
        pct = f"{tot['net']/tot['cost']*100:+.1f}%" if tot["cost"] else "–"; cpct = f"{tot['cf']/tot['cost']*100:+.1f}%" if tot["cost"] else "–"
        L.append(f"| **total** | | {tot['n']} ({tot['c']}/{tot['o']}) | {tot['w']} | {tot['l']} | {tot['net']:+.2f} | {pct} | {tot['cf']:+.2f} | {cpct} | {tot['cff']:+.2f} |")
        v2 = [p for p in P if p["filters"].get("v2_pass")]
        v2net = sum(self.net(p, p["last_value"] if p["status"] == "open" else 0) for p in v2)
        L += ["", f"Paper trades that would pass the new LIVE filters (mcap ≥$1M, liq ≥$100k, age ≥60 min, leader buy seen ≤2 min, chase ≤8%): {len(v2)} of {len(P)}, paper net {v2net:+.2f} $."]
        L += ["", "Open positions are marked at the latest Jupiter SELL quote. Wins/losses count closed trades only.",
              "copyfomo 2%/side = same quoted fills with a 2% fee on each side and no priority fee; flat 5.3% = same fills minus 5.3% of stake.", "",
              "## Trades", "", "| opened (UTC) | leader | mint | status | entry delay s | chase | impact | exits | our net $ | copyfomo $ | new live filters |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in P[-40:]:
            mk = p["last_value"] if p["status"] == "open" else 0
            ex = "; ".join(f"{s['reason']} ${s['usd']:.2f}" for s in p["sells"]) or "–"
            L.append(f"| {p['opened']} | {p['leader']} | `{p['mint'][:6]}…` | {p['status']}{' (forced)' if p.get('forced_filter_override') else ''} | {p['entry_delay_s']} | {p['filters'].get('chase')} | {p['entry_impact']:.4f} | {ex} | {self.net(p, mk):+.2f} | {self.cf_net(p, mk):+.2f} | {('pass' if p['filters'].get('v2_pass') else 'fail: ' + ','.join(p['filters'].get('v2_fails') or [])) if 'v2_pass' in p['filters'] else 'n/a (pre-v2)'} |")
        L += ["", "## Skipped leader buys (by reason)", ""]
        for n, d in self.state["skips"].items(): L.append(f"- {n}: " + ", ".join(f"{k} {v}" for k, v in sorted(d.items())))
        L += ["", "## Endpoint calls", ""]
        for n, d in sorted(self.state["stats"].items()): L.append(f"- {n}: " + ", ".join(f"{k} {v}" for k, v in sorted(d.items())))
        L += self.roster_lines(short=True)
        if self.live:
            try: L += self.live.summary_lines(self.sol_price() or 0)
            except Exception as e: L += ["", f"LIVE summary error {e!r}"]
        open(self.summary_fn, "w").write("\n".join(L) + "\n")

    # ---------- roster rotation ----------
    def poll_gap(self):
        """each wallet costs 1 getSignaturesForAddress per poll: 8s for <=16 wallets, 0.5s per wallet above (20 -> 10s)."""
        return max(CFG["poll_every_s"], 0.5 * len(self.names))
    def last_trade(self):
        """label -> ts of the last buy/sell seen. Seeded once from paper-trades.jsonl (leader_swap events) for restarts."""
        lt = self.state.setdefault("last_trade", {})
        if not self.state.get("last_trade_seeded"):
            try:
                for line in open(self.trades_fn):
                    if '"leader_swap"' not in line: continue
                    r = json.loads(line); t = R.ts_of(r["ts"]) - (r.get("detect_lag_s") or 0)
                    lt[r["leader"]] = max(lt.get(r["leader"]) or 0, t)
            except Exception: pass
            self.state["last_trade_seeded"] = True
        return lt
    def leader_scores(self, t=None):
        t = t or now(); act = [n for n in self.names if not self.leaders[n].get("dropped")]
        return {n: R.score(R.qualifying(self.state["positions"], n, t, self.net)) for n in act}
    def session_roster(self, t=None):
        """daytime session (session.json, roster_fill on, entries still open) -> context for R.session_fill, else None"""
        import live as livemod
        sess = livemod.load_session(HERE); loc = datetime.datetime.now(DUB)
        if not sess or not sess.get("roster_fill") or not livemod.session_applies(loc, sess) or livemod.session_entry_block(loc, sess): return None
        t = t or now(); rec = {}
        for p in self.state["positions"]:
            ot = R.ts_of(p.get("opened"))
            if ot is None or ot < t - R.P["window_h"] * 3600: continue
            r = rec.setdefault(p.get("leader"), dict(n=0, net_usd=0.0))
            r["n"] += 1; r["net_usd"] += self.net(p, p.get("last_value", 0) if p.get("status") == "open" else 0)
        return dict(conf={n: self.leaders[n].get("confidence") for n in self.names if not self.leaders[n].get("dropped")}, record=rec,
                    manual=list(sess.get("manual_live") or []), max_slots=sess.get("max_live_slots"),
                    any_conf=bool(sess.get("roster_fill_any_conf")), ignore_neg=bool(sess.get("fill_ignore_negative")))
    def rotate_if_due(self, force=False):
        t = now(); key = iso(t)[:13]
        st = self.state.get("rotation") or R.new_state(t); self.state["rotation"] = st
        if st.get("last_rank_key") == key and not force: return False
        st["last_rank_key"] = key
        act = [n for n in self.names if not self.leaders[n].get("dropped")]
        before = (st["mode"], list(st["live"])); nlog = len(st["log"])
        R.rank_and_rotate(st, self.leader_scores(t), act, self.real_closed_by_leader(), t, self.last_trade(), session=self.session_roster(t))
        self.log("rotation", key=key, mode=st["mode"], live=st["live"], ranked=st["last_rank"], changed=(st["mode"], st["live"]) != before,
                 events=st["log"][nlog:] if len(st["log"]) >= nlog else st["log"][-5:])
        if self.live: self.live.log("rotation", mode=st["mode"], live_set=list(self.live.live_set()), ranked=st["last_rank"])
        self.write_status(); self.save(); return True
    def roster_lines(self, short=False):
        st = self.state.get("rotation") or {}; sc = st.get("scores", {}); order = st.get("last_rank", [])
        P_ = R.P
        L = ["", "## Leader roster and LIVE rotation" if short else "## Ranking", "",
             f"Mode **{st.get('mode', '?')}**. LIVE slots ({len(st.get('live', []))}/{R.slots(self.session_roster())}): **{', '.join(st.get('live') or []) or 'none'}**. Last rank {st.get('last_rank_key', '?')}:00 UTC.", "",
             f"Score = EV per trade after costs (mean paper net % of stake; Jupiter quotes + fees) over the last {P_['window_h']}h of paper trades that pass the v2 live filters, open trades marked to market. Eligible: ≥{P_['min_trades']} qualifying trades and score > 0.", "",
             "| rank | leader | source | qualifying trades (open) | EV/trade | EV $/trade | win rate | max DD $ | net $ | top-3 streak | last buy/sell seen | LIVE | note |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        rows = sorted(sc, key=lambda k: (order.index(k) if k in order else 99, -(sc[k]["n"]), k))
        for k in rows:
            s = sc[k]; rk = order.index(k) + 1 if k in order else "–"
            note = ("cooldown until " + R.iso_of(st["cooldown_until"][k])) if st.get("cooldown_until", {}).get(k, 0) > now() else \
                   ("eligible" if s["eligible"] else f"needs ≥{P_['min_trades']} trades" if s["n"] < P_["min_trades"] else "score ≤ 0")
            f = lambda v, fmt: (fmt.format(v) if v is not None else "–")
            L.append(f"| {rk} | {k} | {(self.leaders.get(k) or {}).get('source', '?')[:40]} | {s['n']} ({s['n_open']}) | {f(s['ev_pct'] and s['ev_pct']*100, '{:+.1f}%') if s['ev_pct'] is not None else '–'} | {f(s['ev_usd'], '{:+.2f}')} | {f(s['win_rate'] and s['win_rate']*100, '{:.0f}%') if s['win_rate'] is not None else '–'} | {s['max_dd_usd']:.2f} | {s['net_usd']:+.2f} | {st.get('streak', {}).get(k, 0)} | {(lambda t: f"{int((now()-t)//60)} min ago" if t else 'none')(self.last_trade().get(k))} | {'**yes**' if k in st.get('live', []) else ''} | {note} |")
        if short: return L + ["", "Full table and rotation log: roster-status.md"]
        return L
    def merge_inbox(self):
        """every minute: new wallets from roster_inbox.json (Scout) -> roster.json (max 20 active) -> reload"""
        st = self.state.get("rotation") or {}
        sess = self.session_roster() or {}
        protect = set(st.get("live") or []) | set(sess.get("manual") or []) | {p["leader"] for p in self.state["positions"] if p["status"] == "open"}
        seen = self.state.setdefault("inbox_seen", {})
        res = R.merge_inbox(ROSTER_FN, INBOX_FN, seen, self.last_trade(), protect, now())
        waiting = [w for w in res["waiting"] if w not in self.state.setdefault("inbox_waiting_logged", [])]
        if res["added"] or res["dropped"] or res["skipped"] or waiting:
            self.state["inbox_waiting_logged"] = sorted(set(self.state["inbox_waiting_logged"]) | set(waiting))
            self.log("roster_inbox_merge", **res); self.save()
        return res
    def prune_copies(self):
        """label -> closed copies [dict(opened_ts, closed_ts, net_frac, stop_hit, src, mint)]: Chunk + selfcopy live (real) and paper, deduped"""
        stop = lambda sells: any(str(x.get("reason", "")).startswith("sl_-15") for x in (sells or []))
        live, paper = {}, {}
        try:
            for p in (json.load(open(CHUNK_POS)) if os.path.exists(CHUNK_POS) else {}).values():
                if p.get("status") != "closed" or not p.get("sol_in"): continue
                live.setdefault(p.get("leader"), []).append(dict(src="chunk", mint=p.get("mint"), opened_ts=R.ts_of(p.get("opened_ts")), closed_ts=R.ts_of(p.get("closed_ts")),
                                                                net_frac=(p.get("sol_out", 0) - p["sol_in"]) / p["sol_in"], stop_hit=stop(p.get("sells"))))
        except Exception as e: self.log("prune_read_error", src="chunk", err=repr(e)[:160])
        if self.live:
            for p in self.live.s.get("positions", []):
                if p.get("status") != "closed" or not p.get("sol_in"): continue
                live.setdefault(p.get("leader"), []).append(dict(src="selfcopy_live", mint=p.get("mint"), opened_ts=R.ts_of(p.get("opened")), closed_ts=R.ts_of(p.get("closed")),
                                                                net_frac=(p.get("sol_out", 0) - p["sol_in"]) / p["sol_in"], stop_hit=stop(p.get("sells"))))
        for p in self.state["positions"]:
            if p.get("status") != "closed" or not p.get("closed") or not p.get("cost_usd"): continue
            paper.setdefault(p.get("leader"), []).append(dict(src="paper", mint=p.get("mint"), opened_ts=R.ts_of(p.get("opened")), closed_ts=R.ts_of(p.get("closed")),
                                                             net_frac=self.net(p) / p["cost_usd"], stop_hit=stop(p.get("sells"))))
        return {k: R.dedupe_copies(live.get(k, []), paper.get(k, [])) for k in set(live) | set(paper) if k}
    def real_closed_by_leader(self):
        """REAL copies for the 2-losses-in-a-row demotion: selfcopy live wallet + Chunk's positions.json (read-only). label -> [(closed_ts, pnl)]"""
        out = {k: list(v) for k, v in (self.live.closed_by_leader() if self.live else {}).items()}
        try:
            for p in (json.load(open(CHUNK_POS)) if os.path.exists(CHUNK_POS) else {}).values():
                if p.get("status") == "closed" and p.get("closed_ts") and p.get("sol_in"):
                    out.setdefault(p.get("leader"), []).append((R.ts_of(p["closed_ts"]), p.get("sol_out", 0) - p["sol_in"]))
        except Exception as e: self.log("prune_read_error", src="chunk_losses", err=repr(e)[:160])
        for v in out.values(): v.sort()
        return out
    def run_prune(self):
        """every minute, daytime session only: extra prune rules (last 4 copies net < 0; -15% stop within 15 min) -> 12h cooldown"""
        import live as livemod
        if not self.session_roster(): return []
        st = self.state.get("rotation")
        if not st: return []
        sess = livemod.load_session(HERE) or {}
        ev = R.prune_check(st, self.prune_copies(), now(), since_ts=sess.get("start_ts") or 0, real_only=set(sess.get("manual_live") or []))
        for e in ev:
            with open(PRUNE_LOG, "a") as f: f.write(json.dumps(e) + "\n")
            self.log("prune", **e)
        if ev: self.write_status(); self.save()
        return ev
    def write_status(self):
        import live as livemod
        st = self.state.get("rotation") or {}; P_ = R.P; ns = R.slots(self.session_roster()); livemod_max = livemod.HARD["max_live_leaders"]
        sf = [k for k in (st.get("session_fill") or []) if k in (st.get("live") or [])]
        why = ("daytime session slot(s) (session.json; ends at the 19:30Z entry cutoff)" if sf and set(st.get("live") or []) <= set(sf) else
               "no live leader: _benjitrades is inactive (no buy/sell seen in 60 min) or in loss cooldown, and no eligible leader is active" if not st.get("live") else
               "default: no leader has qualified yet, so the current behaviour holds (_benjitrades only, while active)" if st.get("mode") == "default" else
               "rotation: best-scoring eligible leaders that stayed in the top 3 for 2 consecutive hourly ranks")
        L = ["# Roster status (PAPER scoring → LIVE slots)", "", f"Updated {iso()} (Dublin {datetime.datetime.now(DUB):%Y-%m-%d %H:%M}). Roster: {len([n for n in self.names if not self.leaders[n].get('dropped')])} wallets (max {P_['max_roster']}), from roster.json (Zero) + roster_inbox.json (Scout, merged every minute; when full the idlest low-confidence wallet is dropped).", "",
             f"**LIVE now:** {', '.join(st.get('live') or []) or 'none'} ({why}{'; daytime session fill: ' + ', '.join(sf) if sf and not set(st.get('live') or []) <= set(sf) else ''}).", "",
             f"Daytime session fill ({'ON' if self.session_roster() else 'off'}): while session.json is open for entries, up to {ns} LIVE slots (Chunk's own ≤3 open positions stays the risk cap; this bot's own live wallet stays at {livemod_max} slots); an empty LIVE slot goes to {'ANY roster wallet (any confidence)' if (self.session_roster() or {}).get('any_conf') else 'a roster wallet with confidence medium or better'} that had a buy/sell seen in the last 60 min and no clearly negative record (≥2 trades with negative EV/net), most recently active first, then score; the ≥4-trade rule and 2-rank hysteresis are skipped for it (hysteresis is 1 rank for everyone). session.json manual_live ({', '.join((self.session_roster() or {}).get('manual') or []) or 'none'}) is user-approved: it may take a slot regardless of confidence and the paper 'clearly negative' rule does not apply to it; it is judged only by REAL copies (2 losses in a row, last 4 net < 0, fast −15% stop) and the 60-min idle demotion. An idle-demoted wallet regains a free slot within a minute of its next buy/sell. 60-min idle demotion, 2-loss demotion and all exits are unchanged.", "",
             f"Rules: up to {P_['max_slots']} LIVE leaders outside a daytime session. Promote: eligible and in the top 3 for {P_['hysteresis']} consecutive hourly ranks (fills a free slot, or replaces a live leader that fell out of the top 3). Demote: score ≤ 0, fewer than {P_['min_trades']} qualifying trades, removed from roster, or {P_['loss_demote']} live losses in a row (then {P_['loss_cooldown_h']}h cooldown). Inactivity (checked every minute): a live leader with no buy/sell seen in 60 min loses its slot (no cooldown) and it goes straight to the best eligible leader that traded in the last 30 min (hysteresis skipped), else the slot stays empty; the default _benjitrades slot holds only while he is active. Demotion only stops new entries; open live positions keep their exits and still mirror the leader's sells. All live caps are unchanged (size min($10, 15%), ≤3 open live positions in total, night −20% limit, 07:45/08:00, every filter)."]
        L += ["", f"Session prune rules (on top of the {P_['loss_demote']}-losses-in-a-row demotion, while the daytime session is open): (a) a LIVE leader whose last {P_['prune_n']} closed copies (Chunk / live / paper, deduped) net below 0 after costs is demoted; (b) a leader whose last copy hit the −15% stop within {P_['prune_quick_stop_s']//60} min of entry is demoted (or kept out if not live). Both: {P_['prune_cooldown_h']}h cooldown. Every prune is in prune-log.jsonl.", ""]
        try: pl = [json.loads(x) for x in open(PRUNE_LOG)][-15:] if os.path.exists(PRUNE_LOG) else []
        except Exception: pl = []
        L += ["## Prune log (newest first)", ""] + ([f"- {e['ts']} **{e['rule']}** {e['leader']}{'' if e.get('was_live') else ' (not live)'}: {e['why']}" for e in reversed(pl)] or ["- none yet"])
        L += self.roster_lines()
        L += ["", "## Rotation log (newest first)", ""]
        L += [f"- {e['ts']} **{e['action']}** {e['leader']}: {e['why']}" for e in reversed(st.get("log", [])[-40:])] or ["- none yet"]
        open(self.status_fn, "w").write("\n".join(L) + "\n")

    # ---------- main loop ----------
    def run(self, live_flag=False):
        import live as livemod
        if os.path.exists(livemod.KEY_FN):
            self.live = livemod.Live(self, HERE, live_flag)
            self.live.log("start", pid=os.getpid(), enabled=self.live.enabled, caps=dict(livemod.HARD), cfg=self.live.cfg)
        sess = livemod.load_session(HERE)
        self.log("session", **({k: (iso(v) if k.endswith("_ts") and v else v) for k, v in sess.items()} if sess else dict(key=None, note="no session override: normal nightly rules")))
        self.log("start", pid=os.getpid(), leaders={n: v for n, v in self.leaders.items()},
                 rpc=[r["name"] for r in self.rpcs], cfg=CFG, live=bool(self.live and self.live.enabled))
        nxt = {n: now() + i * self.poll_gap() / len(self.names) for i, n in enumerate(self.names)}
        last_sum = last_roster = last_loss = 0
        self.rotate_if_due()
        while not os.path.exists(os.path.join(HERE, "STOP")):
            try:
                t = now()
                for pe in [p for p in self.pending if p["due"] <= t]:
                    self.pending.remove(pe); self.do_entry(pe)
                if now() - last_roster > 60:
                    last_roster = now()
                    try: self.run_prune()
                    except Exception as e: self.log("prune_error", err=repr(e)[:200])
                    try: self.merge_inbox()
                    except Exception as e: self.log("roster_inbox_error", err=repr(e)[:200])
                    if os.path.getmtime(ROSTER_FN) != self.roster_mtime:
                        before = set(self.names); warn = self.load_leaders()
                        self.log("roster_reload", added=sorted(set(self.names) - before), removed=sorted(before - set(self.names)), warnings=warn, n=len(self.names))
                    self.rotate_if_due()
                    if self.live and now() - last_loss > 60:
                        last_loss = now(); st = self.state.get("rotation")
                        if st and (R.check_loss_demotions(st, self.real_closed_by_leader(), now()) | R.check_inactivity(st, self.last_trade(), now(), session=self.session_roster())):
                            self.log("rotation", live=st["live"], mode=st["mode"], events=st["log"][-3:]); self.write_status(); self.save()
                for n in list(self.names):
                    if nxt.get(n, 0) <= now():
                        nxt[n] = now() + self.poll_gap(); self.poll(n)
                        for pe in [p for p in self.pending if p["due"] <= now()]:
                            self.pending.remove(pe); self.do_entry(pe)
                opn = sorted([p for p in self.state["positions"] if p["status"] == "open"], key=lambda p: p["next_q"])
                for p in opn[:2]:
                    if p["next_q"] <= now(): self.requote(p)
                loc = datetime.datetime.now(DUB); day = loc.strftime("%Y-%m-%d")
                if loc.hour == CFG["close_hour_dublin"] and day not in self.state["closed_days"]:
                    self.forced_close(); self.state["closed_days"].append(day); self.save()
                sess = livemod.load_session(HERE)
                if livemod.session_must_close(loc, sess) and sess["key"] not in self.state.setdefault("closed_sessions", []):
                    self.forced_close("close_session_end"); self.state["closed_sessions"].append(sess["key"]); self.save()
                    self.log("session_close", key=sess["key"])
                if self.live:
                    try: self.live.tick(loc, self.sol_price() or 0)
                    except Exception as e: self.live.log("error", where="tick", err=repr(e), tb=traceback.format_exc()[-800:]); time.sleep(5)
                if now() - last_sum > 30:
                    self.write_summary(); self.save(); last_sum = now()
                time.sleep(0.5)
            except Exception as e:
                self.log("error", err=repr(e), tb=traceback.format_exc()[-800:]); time.sleep(5)
        stopf = os.path.join(HERE, "STOP")
        if self.live and "flatten" in (open(stopf).read() if os.path.exists(stopf) else ""):
            try: self.live.flatten("stop_flatten")
            except Exception as e: self.live.log("error", where="stop_flatten", err=repr(e))
        if self.live: self.live.log("stop", open_positions=sum(1 for p in self.live.s["positions"] if p["status"] == "open"))
        self.log("stop", reason="STOP file"); self.write_summary(); self.save()

# ---------- dry run ----------
def dryrun(a):
    b = Bot(tag="dryrun-")
    name = a.leader; w = b.leaders[name]["wallet"]
    rows = sorted([r for r in csv.DictReader(open(os.path.join(OI, "trader_swaps.csv"))) if r["trader"] == name], key=lambda r: r["timestamp"])
    if a.sig: buy = next(r for r in rows if r["signature"] == a.sig)
    else:
        firsts = []; seenm = set()
        sells = {r["mint"] for r in rows if r["side"] == "sell"}
        for r in rows:
            if r["side"] == "buy" and r["mint"] not in seenm: firsts.append(r)
            seenm.add(r["mint"])
        cands = [r for r in firsts if float(r["usd_size"]) >= 50 and (not a.with_sell or r["mint"] in sells)]
        buy = None
        for r in reversed(cands[-8:]):     # newest candidate whose on-chain pre-balance is really 0
            t = b.parse_swap(b.get_tx(r["signature"]), w, r["signature"])
            if t and t["side"] == "buy" and t["pre_bal"] <= 1e-9: buy = r; break
        buy = buy or cands[-1]
    print(f"DRY RUN leader={name} wallet={w} hist buy {buy['timestamp']} {buy['mint']} ${buy['usd_size']} sig={buy['signature'][:20]}…")
    b.state["seen"][name] = []
    b.hist[name] = {(m, t) for (m, t) in b.hist[name] if not (m == buy["mint"] and t >= buy["timestamp"])}
    sw = b.parse_swap(b.get_tx(buy["signature"]), w, buy["signature"])
    print("parsed:", json.dumps(sw))
    assert sw and sw["side"] == "buy", "parser failed"
    b.on_leader_swap(name, sw, detected=now(), force=a.force)
    while b.pending:
        pe = b.pending.pop(0); time.sleep(max(0, pe["due"] - now())); b.do_entry(pe)
    pos = [p for p in b.state["positions"] if p["status"] == "open"]
    if not pos: print("no entry (see skip above)"); b.write_summary(); b.save(); return
    for i in range(a.requotes):
        time.sleep(CFG["requote_every_s"]); 
        for p in pos:
            if p["status"] == "open": b.requote(p); print("mark", p["id"], round(p["last_value"], 4))
    later = [r for r in rows if r["mint"] == buy["mint"] and r["side"] == "sell" and r["timestamp"] > buy["timestamp"]]
    if later and pos[0]["status"] == "open":
        sw2 = b.parse_swap(b.get_tx(later[0]["signature"]), w, later[0]["signature"])
        print("historical leader sell parsed:", json.dumps(sw2))
        if sw2: b.on_leader_swap(name, sw2, detected=now())
    if any(p["status"] == "open" for p in pos): b.forced_close("dryrun_forced_close")
    b.write_summary(); b.save(); print(open(b.summary_fn).read())

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["run", "dryrun", "summary"])
    ap.add_argument("--leader", default="_benjitrades"); ap.add_argument("--sig"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--requotes", type=int, default=2); ap.add_argument("--with-sell", action="store_true")
    ap.add_argument("--live", action="store_true", help="enable LIVE for _benjitrades (same as creating ./LIVE)")
    a = ap.parse_args()
    if a.mode == "run": Bot().run(live_flag=a.live)
    elif a.mode == "dryrun": dryrun(a)
    else: Bot().write_summary()
