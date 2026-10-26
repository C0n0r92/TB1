#!/usr/bin/env python3
"""
LIVE execution layer for selfcopy.py (dedicated bot wallet only).
- OFF unless the file ./LIVE exists (or `run --live`). `rm LIVE` = no new live buys; ./stop.sh = sell all + halt.
- Copies only the leaders holding a LIVE slot from the roster rotation (roster.py; max 3; default _benjitrades). Everyone else stays PAPER.
- The only transactions this module ever sends: Jupiter swaps built for THIS wallet (verified
  instruction-by-instruction before signing) and closeAccount of our own emptied token accounts
  (rent goes back to this wallet). No transfers out, ever.
- The private key is read from /home/box/.selfcopy-wallet/keypair.json (must be chmod 600) and is
  never printed, logged or written anywhere else.
"""
import os, json, time, base64, datetime, struct
from types import MappingProxyType

KEY_FN = "/home/box/.selfcopy-wallet/keypair.json"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SYS = "11111111111111111111111111111111"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PQnBqCXEpPxuEb"
ATA = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
CB = "ComputeBudget111111111111111111111111111111"
JUP = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
MEMO = {"MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr", "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo"}
ALLOWED_PROGRAMS = {SYS, TOKEN, TOKEN22, ATA, CB, JUP} | MEMO

# ---- HARD CAPS: read-only, cannot be loosened by live-config.json (config may only tighten) ----
HARD = MappingProxyType(dict(
    default_live_leaders=("_benjitrades",), max_live_leaders=3,   # live set comes from roster rotation, hard-capped at 3
    max_usd=10.0, max_wallet_frac=0.15, min_usd=1.0,
    reserve_sol=0.02, overhead_sol=0.0045,     # ATA rent + temp wSOL rent + fees headroom
    max_open=3, max_chase=0.08, min_leader_usd=50.0, min_mcap=1_000_000, min_liq=100_000, min_age_s=3600,
    max_leader_age_s=120, max_impact=0.03,
    sl_frac=0.85, tp1_x=1.4, tp1_frac=0.25, tp2_x=2.0, trail_frac=0.75, trail_adding_frac=0.65, add_window_s=600,
    keep_frac=0.10, moon_x=6.0, leader_full_exit=0.95,
    no_entry_from=(7, 45), close_hour=8, night_loss_frac=0.20,
    prio_default_sol=0.0001, prio_max_sol=0.0001,
    min_gas_sol=0.01, usdc_convert_min=5.0, usdc_keep=1.0, usdc_slip_bps=100, usdc_retry_s=600,
    entry_slip_bps=500, exit_slip_bps=500, urgent_exit_slip_steps=(500, 1000, 1500), sell_tries=3,
))
URGENT = ("sl", "close", "loss_limit", "stop")

def load_cfg(here):
    """live-config.json can only TIGHTEN: values are clamped to HARD."""
    c = {}
    fn = os.path.join(here, "live-config.json")
    if os.path.exists(fn):
        try: c = json.load(open(fn))
        except Exception: c = {}
    out = dict(size_usd=HARD["max_usd"], priority_fee_sol=HARD["prio_default_sol"], max_open=HARD["max_open"],
               max_impact=HARD["max_impact"], max_chase=HARD["max_chase"])
    for k in out:
        if isinstance(c.get(k), (int, float)) and c[k] >= 0: out[k] = c[k]
    out["size_usd"] = min(out["size_usd"], HARD["max_usd"])
    out["priority_fee_sol"] = min(out["priority_fee_sol"], HARD["prio_max_sol"])
    out["max_open"] = int(min(out["max_open"], HARD["max_open"]))
    out["max_impact"] = min(out["max_impact"], HARD["max_impact"])
    out["max_chase"] = min(out["max_chase"], HARD["max_chase"])
    return out

# ---------------- pure cap logic (unit-tested) ----------------
def live_size_usd(cfg, wallet_usd):
    return max(0.0, min(cfg["size_usd"], HARD["max_usd"], HARD["max_wallet_frac"] * wallet_usd))

def funded_check(sol_bal, size_usd, solpx):
    """-> (ok, reason). Needs size + 0.02 SOL reserve + overhead."""
    if size_usd < HARD["min_usd"]: return False, "unfunded"
    need = size_usd / solpx + HARD["reserve_sol"] + HARD["overhead_sol"]
    if sol_bal < need: return False, "unfunded"
    return True, None

def gas_ok(sol_bal):
    return sol_bal >= HARD["min_gas_sol"]

def usdc_convert_amount(usdc, sol_bal):
    """-> USDC (ui) to swap into SOL, or 0. Needs >= $5 USDC and >= 0.01 SOL for gas; keeps ~$1 USDC."""
    if usdc < HARD["usdc_convert_min"] or not gas_ok(sol_bal): return 0.0
    return round(usdc - HARD["usdc_keep"], 6)

def in_no_entry_window(loc):
    return (loc.hour, loc.minute) >= HARD["no_entry_from"] and loc.hour < HARD["close_hour"]

def night_key(loc):
    """A 'night' runs 08:00 -> 08:00 Dublin."""
    return (loc - datetime.timedelta(hours=HARD["close_hour"])).strftime("%Y-%m-%d")

# ---- optional session override (session.json / env). It can only ADD an earlier cutoff + close; the 07:45/08:00 rules stay. ----
SESSION_DEFAULT_NO_ENTRY_MIN = 30
def _parse_utc(v):
    return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(datetime.timezone.utc).timestamp()

SESSION_MIN_MCAP_FLOOR = 20_000   # 15:10Z user 14:08Z "lessing the rules" (was 300_000)
#     # user-approved 24 Oct 09:56Z for the day session; signal filter only (live entry_gate stays HARD)
SESSION_MIN_AGE_FLOOR_S = 3 * 60   # was 15 min
SESSION_MAX_LIVE_SLOTS = 15         # session-only rotation slots (roster.py P["session_max_slots"])

def load_session(here):
    """session.json {key, start, end (UTC ISO), no_entry_min, resume} or env SELFCOPY_SESSION_START/END/NO_ENTRY_MIN
    (env wins). -> dict(key, start_ts, end_ts, no_entry_s, resume_ts) or None. Max length 24h; invalid -> None.
    While the session file exists: entries only from start until end - no_entry_min; flat at end; after end NO new
    entries (paper or live) until `resume` (if set) or until the file is removed. The -20% halt is keyed to the session."""
    d = {}
    fn = os.path.join(here, "session.json")
    if os.path.exists(fn):
        try: d = json.load(open(fn)) or {}
        except Exception: d = {}
    for k, e in (("start", "SELFCOPY_SESSION_START"), ("end", "SELFCOPY_SESSION_END"), ("no_entry_min", "SELFCOPY_SESSION_NO_ENTRY_MIN"),
                 ("roster_fill", "SELFCOPY_SESSION_ROSTER_FILL"), ("manual_live", "SELFCOPY_SESSION_MANUAL_LIVE"),
                 ("topup_entry", "SELFCOPY_SESSION_TOPUP_ENTRY"), ("min_mcap_usd", "SELFCOPY_SESSION_MIN_MCAP_USD"),
                 ("min_age_min", "SELFCOPY_SESSION_MIN_AGE_MIN"), ("halt_loss_pct", "SELFCOPY_SESSION_HALT_LOSS_PCT"),
                 ("max_live_leaders", "SELFCOPY_SESSION_MAX_LIVE_LEADERS"), ("roster_fill_any_conf", "SELFCOPY_SESSION_FILL_ANY_CONF")):
        if os.environ.get(e): d[k] = os.environ[e]
    if not d.get("end"): return None
    try:
        end = _parse_utc(d["end"]); start = _parse_utc(d["start"]) if d.get("start") else end - 24 * 3600
        ne = max(0.0, float(d.get("no_entry_min", SESSION_DEFAULT_NO_ENTRY_MIN))) * 60
        resume = _parse_utc(d["resume"]) if d.get("resume") else None
    except Exception: return None
    if not (start < end <= start + 24 * 3600): return None
    key = d.get("key") or ("session-" + datetime.datetime.fromtimestamp(end, datetime.timezone.utc).strftime("%Y-%m-%dT%H%MZ"))
    rf = d.get("roster_fill", True)
    rf = rf if isinstance(rf, bool) else str(rf).strip().lower() not in ("0", "false", "no", "off", "")
    ml = d.get("manual_live") or []
    ml = [x.strip() for x in (ml.split(",") if isinstance(ml, str) else ml) if str(x).strip()][:SESSION_MAX_LIVE_SLOTS]
    tu = d.get("topup_entry") or []
    tu = [x.strip() for x in (tu.split(",") if isinstance(tu, str) else tu) if str(x).strip()]
    tall = "all_live" in tu                                    # user 09:56Z: top-ups for every LIVE-rotation leader
    tu = [x for x in tu if x in ml]                            # named wallets: only manual-live ones
    def num(k, lo, hi):
        try: v = float(d[k]) if d.get(k) not in (None, "") else None
        except Exception: v = None
        return None if v is None else min(max(v, lo), hi)
    ac = d.get("roster_fill_any_conf", False)
    ac = ac if isinstance(ac, bool) else str(ac).strip().lower() in ("1", "true", "yes", "on")
    return dict(key=key, start_ts=start, end_ts=end, no_entry_s=ne, resume_ts=resume, roster_fill=rf, manual_live=ml, topup_entry=tu,
                topup_all_live=tall, roster_fill_any_conf=ac,
                # rotation / LIVE-line slots (Chunk follows them; Chunk's own max_open 3 stays the risk cap). This bot's own
                # live wallet still uses HARD["max_live_leaders"] (3) via Live.live_set()/entry_gate.
                max_live_slots=None if num("max_live_leaders", 0, 1e9) is None else int(num("max_live_leaders", 1, SESSION_MAX_LIVE_SLOTS)),
                min_mcap_usd=num("min_mcap_usd", SESSION_MIN_MCAP_FLOOR, HARD["min_mcap"]),     # session may loosen, never below the floor
                min_age_s=None if num("min_age_min", 0, 1e9) is None else num("min_age_min", SESSION_MIN_AGE_FLOOR_S / 60, HARD["min_age_s"] / 60) * 60,
                min_liq_usd=num("min_liq_usd", 15_000, HARD["min_liq"]), max_chase=num("max_chase", 0.0, 0.20),
                min_leader_usd=num("min_leader_usd", 20.0, 1e9),
                halt_loss_frac=None if num("halt_loss_pct", 0, 1e9) is None else num("halt_loss_pct", 1, HARD["night_loss_frac"] * 100) / 100)   # can only tighten

def _ts(loc): return loc.timestamp() if hasattr(loc, "timestamp") else float(loc)
def session_applies(loc, sess):
    """the session governs from its start until `resume` (or forever while the file exists)"""
    if not sess: return False
    t = _ts(loc)
    return t >= sess["start_ts"] and not (sess.get("resume_ts") and t >= sess["resume_ts"])

def session_entry_block(loc, sess):
    """-> None or a skip reason. Only ever blocks (never opens a window the normal rules close)."""
    if not session_applies(loc, sess): return None
    t = _ts(loc)
    if t >= sess["end_ts"]: return "session_ended"
    if t >= sess["end_ts"] - sess["no_entry_s"]: return "no_entry_before_session_end"
    return None

def session_must_close(loc, sess):
    return session_applies(loc, sess) and _ts(loc) >= sess["end_ts"]

def period_key(loc, sess=None):
    """loss-limit period: the session key while a session applies, else the 08:00->08:00 Dublin night."""
    return sess["key"] if session_applies(loc, sess) else night_key(loc)

def loss_limit_hit(value_sol, start_sol, frac=None):
    f = min(HARD["night_loss_frac"], frac) if frac else HARD["night_loss_frac"]     # session can only tighten
    return bool(start_sol) and value_sol <= (1 - f) * start_sol

def session_halt_frac(loc, sess):
    return sess.get("halt_loss_frac") if session_applies(loc, sess) else None

def breakeven_x(basis_usd, extra_cost_usd):
    """price ratio (vs entry) at which the position is flat after costs: entry + costs not already in the basis."""
    return 1 + (extra_cost_usd / basis_usd if basis_usd else 0)

def exit_plan(x, *, tp_level, peak_x, be_x, leader_sold, adding):
    """v3 exit rules (shared by LIVE and paper). x = current value / entry basis of the tokens still held (price ratio).
    -> None | (kind, frac_of_remaining, reason). kind: 'sl' | 'trail' | 'tp1' | 'tp2' | 'tp12' | 'moon' | 'defer'.
      * hard stop is never skipped: -15% before the first TP, breakeven (entry + costs) after it.
      * TP1 sells 25% at +40%, TP2 another 25% of the original at +100% (= 1/3 of what's left); jumping past +100% sells both.
        While the leader is adding (bought the same token in the last 10 min) TPs are deferred ('defer').
      * after TP1 the remainder trails 25% below the peak since entry (35% while the leader is adding).
      * after the leader's first sell only a <=10% leftover remains: it exits at +500% (all), or its stop;
        no trailing stop, and later leader sells are ignored."""
    stop = be_x if tp_level > 0 else HARD["sl_frac"]
    if x <= stop: return ("sl", 1.0, "sl_breakeven" if tp_level > 0 else "sl_-15%")
    pk = max(peak_x or x, x)
    if leader_sold:
        if x >= HARD["moon_x"]: return ("moon", 1.0, "tp_leftover_+500%")
        return None
    if tp_level == 0 and x >= HARD["tp1_x"]:
        if adding: return ("defer", None, "tp_+40%_deferred_leader_adding")
        if x >= HARD["tp2_x"]: return ("tp12", 0.5, "tp_+40%_and_+100%_25%+25%")
        return ("tp1", HARD["tp1_frac"], "tp_+40%_25%")
    if tp_level == 1 and x >= HARD["tp2_x"]:
        if adding: return ("defer", None, "tp_+100%_deferred_leader_adding")
        return ("tp2", 1 / 3, "tp_+100%_25%")
    if tp_level > 0:
        tf = HARD["trail_adding_frac"] if adding else HARD["trail_frac"]
        if x <= tf * pk: return ("trail", 1.0, f"sl_trail_-{round((1-tf)*100)}%_from_peak_{pk:.2f}x")
    return None

def mirror_keep(tokens_left, tokens_raw):
    """leader's FIRST sell: keep 10% of the original size (or what's left if less). -> (sell_frac_of_remaining, keep_raw)"""
    keep = min(tokens_left, int(HARD["keep_frac"] * tokens_raw))
    if tokens_left <= 0 or keep >= tokens_left: return 0.0, tokens_left
    return 1 - keep / tokens_left, keep

def v2_filters(*, mcap, liq, age_s, leader_age_s, chase):
    """New tighter LIVE filters; also used to tag paper trades. -> list of failed checks ([] = pass)."""
    f = []
    if mcap is None or mcap < HARD["min_mcap"]: f.append("mcap_lt_1m")
    if liq is None or liq < HARD["min_liq"]: f.append("liq_lt_100k")
    if age_s is None or age_s < HARD["min_age_s"]: f.append("age_lt_60m")
    if leader_age_s is None or leader_age_s > HARD["max_leader_age_s"]: f.append("leader_buy_gt_2m_old")
    if chase is None or chase > HARD["max_chase"]: f.append("chase_gt_8pct")
    return f

def signal_filters(*, mcap, liq, age_s, leader_age_s, chase, sess=None):
    """entry-SIGNAL filters (paper entries Chunk consumes): v2 thresholds, but a session may set min_mcap_usd (>= $300k)
    and min_age_min (>= 15). liq $100k, 2-min signal age and 8% chase stay HARD. -> list of failed checks."""
    mm = (sess or {}).get("min_mcap_usd") or HARD["min_mcap"]; ma = (sess or {}).get("min_age_s") or HARD["min_age_s"]
    f = []
    if mcap is None or mcap < mm: f.append("mcap_lt_min")
    ml = (sess or {}).get("min_liq_usd") or HARD["min_liq"]; mc = (sess or {}).get("max_chase") or HARD["max_chase"]
    if liq is None or liq < ml: f.append("liq_lt_min")
    if age_s is None or age_s < ma: f.append("age_lt_min")
    if leader_age_s is None or leader_age_s > HARD["max_leader_age_s"]: f.append("leader_buy_gt_2m_old")
    if chase is None or chase > mc: f.append("chase_gt_max")
    return f

def entry_gate(cfg, *, leader, first_buy, leader_usd, mcap, avoid, chase, impact, n_open, same_mint_open, loc, halted, forced,
               liq=None, age_s=None, leader_age_s=None, live_set=None, session=None):
    """-> None if OK else skip reason. Every check here is a HARD cap."""
    ls = tuple(live_set if live_set is not None else HARD["default_live_leaders"])[:HARD["max_live_leaders"]]
    if leader not in ls: return "leader_not_live"
    if forced: return "forced_override_never_live"
    if halted: return "night_loss_limit_halt"
    if not first_buy: return "not_first_buy"
    if leader_usd < HARD["min_leader_usd"]: return "leader_buy_lt_50"
    v2 = v2_filters(mcap=mcap, liq=liq, age_s=age_s, leader_age_s=leader_age_s, chase=chase)
    if v2: return v2[0]
    if avoid: return "avoid"
    if in_no_entry_window(loc): return "no_entry_0745_0800"
    sb = session_entry_block(loc, session)
    if sb: return sb
    if n_open >= min(cfg["max_open"], HARD["max_open"]): return "max_open_3"
    if same_mint_open: return "already_open_same_mint"
    if chase is None or chase > min(cfg["max_chase"], HARD["max_chase"]): return "chase_gt_8pct"
    if impact is None or impact > min(cfg["max_impact"], HARD["max_impact"]): return "impact_gt_3pct"
    return None

# ---------------- transaction guard ----------------
def verify_swap_tx(tx, me, wsol_ata):
    """Reject anything that is not a plain Jupiter swap for `me`. -> (ok, reason)"""
    m = tx.message
    keys = [str(k) for k in m.account_keys]
    if keys[0] != me: return False, "fee payer is not bot wallet"
    nst = len(keys)
    for ix in m.instructions:
        prog = keys[ix.program_id_index]; acc = list(ix.accounts); d = bytes(ix.data)
        if prog not in ALLOWED_PROGRAMS: return False, f"program not allowed {prog}"
        def k(i): return keys[acc[i]] if i < len(acc) and acc[i] < nst else None
        if prog == SYS:
            if len(d) < 4 or struct.unpack("<I", d[:4])[0] != 2: return False, "system ix other than transfer"
            if k(0) != me or k(1) != wsol_ata: return False, "system transfer not to own wSOL account"
        elif prog in (TOKEN, TOKEN22):
            op = d[0] if d else None
            if op == 17: continue                                    # syncNative
            if op == 9:                                              # closeAccount
                if k(1) != me or k(2) != me: return False, "closeAccount destination/owner not bot wallet"
                continue
            return False, f"token ix {op} not allowed at top level"
        elif prog == ATA:
            if k(0) != me or k(2) != me: return False, "ATA create not for bot wallet"
    return True, None

class Live:
    def __init__(self, bot, here, enabled):
        self.bot = bot; self.here = here; self.enabled_flag = enabled
        self.fn = os.path.join(here, "live-trades.jsonl")
        self.night_fn = os.path.join(here, "live-night-start.json")
        self.cfg = load_cfg(here)
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        st = os.stat(KEY_FN)
        if st.st_mode & 0o077: raise SystemExit("keypair file permissions too open; refusing (need 600)")
        self._kp = Keypair.from_bytes(bytes(json.load(open(KEY_FN))))   # never printed
        self.pub = str(self._kp.pubkey())
        self.Pubkey = Pubkey
        self.wsol_ata = self.ata(self.pub, WSOL, TOKEN)
        s = bot.state.setdefault("live", {})
        s.setdefault("positions", []); s.setdefault("halted_nights", []); s.setdefault("closed_days", [])
        self.s = s
        self.last_unfunded_log = 0; self.last_val_t = 0; self.sol_bal = None; self.usdc_bal = None; self.last_close_try = 0; self.last_gas_log = 0

    def __repr__(self): return f"<Live {self.pub}>"      # never exposes key

    @property
    def enabled(self):
        return self.enabled_flag or os.path.exists(os.path.join(self.here, "LIVE"))

    def ata(self, owner, mint, prog):
        P = self.Pubkey.from_string
        a, _ = self.Pubkey.find_program_address([bytes(P(owner)), bytes(P(prog)), bytes(P(mint))], P(ATA))
        return str(a)

    def log(self, ev, **kw):
        rec = dict(ts=self.bot_iso(), event=ev, live=True, wallet=self.pub, **kw)
        with open(self.fn, "a") as f: f.write(json.dumps(rec) + "\n")
        print("LIVE " + json.dumps(rec), flush=True)
    def bot_iso(self):
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---------- chain reads ----------
    def get_sol(self):
        r = self.bot.rpc("getBalance", [self.pub, {"commitment": "confirmed"}])
        if r is None: return self.sol_bal
        self.sol_bal = r["value"] / 1e9; return self.sol_bal

    def token_accounts(self, mint):
        out = []
        for prog in (TOKEN, TOKEN22):
            r = self.bot.rpc("getTokenAccountsByOwner", [self.pub, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}])
            if r is None: return None
            for a in r["value"]:
                info = a["account"]["data"]["parsed"]["info"]
                out.append(dict(addr=a["pubkey"], prog=a["account"]["owner"], raw=int(info["tokenAmount"]["amount"]),
                                dec=info["tokenAmount"]["decimals"]))
            break     # getTokenAccountsByOwner with mint filter already covers both programs
        return out

    def get_usdc(self):
        a = self.token_accounts(USDC)
        if a is None: return self.usdc_bal
        self.usdc_bal = sum(x["raw"] for x in a) / 1e6; return self.usdc_bal

    def wallet_value_sol(self, solpx):
        """SOL + USDC at face value ($1) + open tokens at latest Jupiter sell quote, expressed in SOL."""
        sol = self.get_sol() or 0.0
        usdc = self.get_usdc() or 0.0
        toks = sum((p.get("last_value_usd") or 0) for p in self.s["positions"] if p["status"] == "open")
        return sol + ((toks + usdc) / solpx if solpx else 0), sol

    def maybe_convert_usdc(self, solpx):
        """One-shot per deposit: USDC -> SOL via Jupiter (same tx guard), keep ~$1 USDC."""
        usdc = self.usdc_bal or 0.0; sol = self.sol_bal or 0.0
        amt = usdc_convert_amount(usdc, sol)
        if amt <= 0 or time.time() - self.s.get("usdc_last_try", 0) < HARD["usdc_retry_s"]: return None
        self.s["usdc_last_try"] = time.time(); self.bot.save()
        raw = int(amt * 1e6)
        res, err = self.swap(USDC, WSOL, raw, HARD["usdc_slip_bps"], True, "usdc_to_sol")
        if not res or not res["ok"] or not res.get("fill"):
            self.log("usdc_convert_failed", usdc_in=amt, err=str(err)[:300], sig=(res or {}).get("sig")); return False
        f = res["fill"]; got = f["lamports"] / 1e9
        rec = dict(ts=self.bot_iso(), sig=res["sig"], usdc_in=-f["token_raw"] / 1e6, sol_out=got, eff_px=round((-f["token_raw"] / 1e6) / got, 4) if got else None,
                   sol_px=solpx, slip_bps=res["slip_bps"], tx_fee_lamports=f["fee"])
        self.s.setdefault("conversions", []).append(rec)
        self.log("usdc_to_sol", **{k: v for k, v in rec.items() if k != "ts"})
        self.get_sol(); self.get_usdc(); self.bot.save(); return True

    # ---------- jupiter ----------
    def jq(self, inp, out, amount, slip_bps):
        j = self.bot.jup("/swap/v1/quote", {"inputMint": inp, "outputMint": out, "amount": int(amount),
                                            "slippageBps": int(slip_bps), "swapMode": "ExactIn"}, "live")
        if not j or "outAmount" not in j: return None, (j or {}).get("_body") or (j or {}).get("error") or "no response"
        return j, None

    def build(self, quote, dynamic, max_slip_bps):
        b = self.bot
        w = max(b.jup_last + 2.2, b.jup_cool) - time.time()
        if w > 0: time.sleep(w)
        b.jup_last = time.time()
        body = dict(quoteResponse=quote, userPublicKey=self.pub, wrapAndUnwrapSol=True, dynamicComputeUnitLimit=True,
                    dynamicSlippage=bool(dynamic), prioritizationFeeLamports=int(round(self.cfg["priority_fee_sol"] * 1e9)))
        r = b.http("https://lite-api.jup.ag/swap/v1/swap", body, timeout=15, name="jupiter_swap")
        if not r or "swapTransaction" not in r: return None, f"swap build failed {str(r)[:200]}"
        rep = r.get("dynamicSlippageReport") or {}
        if dynamic and (rep.get("slippageBps") or 0) > max_slip_bps:
            return None, f"dynamic slippage {rep.get('slippageBps')} > cap {max_slip_bps}"
        if int(r.get("prioritizationFeeLamports") or 0) > int(HARD["prio_max_sol"] * 1e9):
            return None, "priority fee above hard cap"
        from solders.transaction import VersionedTransaction
        tx = VersionedTransaction.from_bytes(base64.b64decode(r["swapTransaction"]))
        ok, why = verify_swap_tx(tx, self.pub, self.wsol_ata)
        if not ok: return None, "tx guard: " + why
        return dict(tx=tx, lvbh=r.get("lastValidBlockHeight"), slip=rep.get("slippageBps"), prio=r.get("prioritizationFeeLamports")), None

    def sign(self, tx):
        from solders.transaction import VersionedTransaction
        return VersionedTransaction(tx.message, [self._kp])

    def simulate(self, stx):
        return self.bot.rpc("simulateTransaction", [base64.b64encode(bytes(stx)).decode(),
                            {"encoding": "base64", "sigVerify": True, "commitment": "processed"}])

    def send_and_confirm(self, stx, lvbh, timeout=75):
        raw = base64.b64encode(bytes(stx)).decode(); sig = str(stx.signatures[0])
        t0 = time.time(); last_send = 0; first = True
        while time.time() - t0 < timeout:
            if time.time() - last_send > 3:
                for r in self.bot.rpcs:      # broadcast to every endpoint
                    j = self.bot.http(r["url"], {"jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
                                      "params": [raw, {"encoding": "base64", "skipPreflight": not first,
                                                       "preflightCommitment": "processed", "maxRetries": 0}]}, name="send:" + r["name"])
                    if first and j and "error" in j:
                        return sig, False, f"preflight: {json.dumps(j['error'])[:300]}"
                first = False; last_send = time.time()
            time.sleep(2)
            st = self.bot.rpc("getSignatureStatuses", [[sig], {"searchTransactionHistory": False}])
            v = (st or {}).get("value", [None])[0] if st else None
            if v and v.get("confirmationStatus") in ("confirmed", "finalized"):
                return sig, v.get("err") is None, (json.dumps(v.get("err")) if v.get("err") else None)
            if lvbh:
                bh = self.bot.rpc("getBlockHeight", [{"commitment": "confirmed"}])
                if bh and bh > lvbh: return sig, False, "blockhash expired"
        return sig, False, "confirm timeout"

    def fill(self, sig, mint):
        """real fill from chain: lamports delta (incl. fees/rent) and token raw delta for the bot wallet."""
        for _ in range(8):
            tx = self.bot.get_tx(sig)
            if tx and tx.get("meta"):
                m = tx["meta"]; keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]
                i = keys.index(self.pub)
                lam = m["postBalances"][i] - m["preBalances"][i]
                tok = 0; wsol = 0
                for side, sg in (("preTokenBalances", -1), ("postTokenBalances", 1)):
                    for b in m.get(side) or []:
                        if b.get("owner") != self.pub: continue
                        if b["mint"] == mint: tok += sg * int(b["uiTokenAmount"]["amount"])
                        elif b["mint"] == WSOL: wsol += sg * int(b["uiTokenAmount"]["amount"])
                return dict(lamports=lam + wsol, fee=m.get("fee"), token_raw=tok, slot=tx.get("slot"))
            time.sleep(2)
        return None

    def swap(self, inp, out, amount, slip_bps, dynamic, purpose):
        q, err = self.jq(inp, out, amount, slip_bps)
        if not q: return None, f"quote: {err}"
        built, err = self.build(q, dynamic, slip_bps)
        if not built: return None, err
        stx = self.sign(built["tx"])
        sig, ok, err = self.send_and_confirm(stx, built["lvbh"])
        res = dict(sig=sig, ok=ok, err=err, quote_out=int(q["outAmount"]), impact=float(q.get("priceImpactPct") or 0),
                   slip_bps=built["slip"] if dynamic else slip_bps, prio_lamports=built["prio"],
                   route="+".join(x["swapInfo"].get("label", "?") for x in q.get("routePlan", [])))
        if ok: res["fill"] = self.fill(sig, out if out != WSOL else inp)
        return res, None if ok else err

    # ---------- strategy hooks ----------
    def live_set(self):
        """leaders allowed NEW live entries now (roster rotation, max 3). Exits/mirrors of open positions ignore this."""
        rot = (self.bot.state.get("rotation") if hasattr(self.bot, "state") else None)
        ls = tuple((rot or {}).get("live") or ()) if rot else HARD["default_live_leaders"]
        return ls[:HARD["max_live_leaders"]]
    def closed_by_leader(self):
        out = {}
        for p in self.s["positions"]:
            if p["status"] == "closed" and p.get("closed"):
                import calendar; t = calendar.timegm(time.strptime(p["closed"], "%Y-%m-%dT%H:%M:%SZ"))
                out.setdefault(p["leader"], []).append((t, p["sol_out"] - p["sol_in"]))
        return out

    def session(self):
        return load_session(self.here)
    def halted(self, loc):
        return period_key(loc, self.session()) in self.s["halted_nights"]

    def on_paper_entry(self, name, sw, info, avoid, first_buy, forced, loc, solpx):
        """Called right after a PAPER entry for a leader. Decides and executes the LIVE buy."""
        if not self.enabled: return
        if name not in self.live_set(): return
        pre = v2_filters(mcap=info.get("mcap"), liq=info.get("liq"), age_s=info.get("age_s"), leader_age_s=info.get("leader_age_s"), chase=0.0)
        if pre or forced:     # cheap pre-check before any wallet/Jupiter calls (chase re-checked on the live quote)
            return self.log("skip", leader=name, mint=sw["mint"], reason=(pre or ["forced_override_never_live"])[0], all_fails=pre,
                            mcap=info.get("mcap"), liq=info.get("liq"), age_s=info.get("age_s"), leader_age_s=info.get("leader_age_s"))
        self.cfg = load_cfg(self.here)
        opn = [p for p in self.s["positions"] if p["status"] == "open"]
        # wallet / funding
        val_sol, sol = self.wallet_value_sol(solpx)
        if not gas_ok(sol):
            return self.log("needs gas SOL", leader=name, mint=sw["mint"], sol_balance=sol, usdc=self.usdc_bal, min_gas_sol=HARD["min_gas_sol"])
        if self.enabled and usdc_convert_amount(self.usdc_bal or 0, sol) > 0:
            self.maybe_convert_usdc(solpx); val_sol, sol = self.wallet_value_sol(solpx)
        size = live_size_usd(self.cfg, val_sol * solpx)
        ok, why = funded_check(sol, size, solpx)
        if not ok:
            return self.log("unfunded", leader=name, mint=sw["mint"], sol_balance=sol, wallet_value_sol=round(val_sol, 6),
                            size_usd=round(size, 2), need_sol=round(size / solpx + HARD["reserve_sol"] + HARD["overhead_sol"], 5) if size else None)
        lam = int(size / solpx * 1e9)
        q, err = self.jq(WSOL, sw["mint"], lam, HARD["entry_slip_bps"])
        if not q: return self.log("skip", leader=name, mint=sw["mint"], reason="no_route", err=str(err)[:200])
        dec = sw["decimals"] if sw["decimals"] is not None else 6
        our_px = size / (int(q["outAmount"]) / 10 ** dec)
        chase = our_px / sw["fill_px"] - 1 if sw["fill_px"] else None
        impact = float(q.get("priceImpactPct") or 0)
        reason = entry_gate(self.cfg, leader=name, first_buy=first_buy, leader_usd=sw["usd"], mcap=info.get("mcap"), avoid=avoid,
                            chase=chase, impact=impact, n_open=len(opn), same_mint_open=any(p["mint"] == sw["mint"] for p in opn),
                            loc=loc, halted=self.halted(loc), forced=forced, liq=info.get("liq"), age_s=info.get("age_s"),
                            leader_age_s=info.get("leader_age_s"), live_set=self.live_set(), session=self.session())
        if reason:
            return self.log("skip", leader=name, mint=sw["mint"], reason=reason, chase=chase, impact=impact, size_usd=round(size, 2))
        night = self.night_start(loc, val_sol, solpx)
        res, err = self.swap(WSOL, sw["mint"], lam, HARD["entry_slip_bps"], True, "entry")
        if not res or not res["ok"] or not res.get("fill"):
            return self.log("entry_failed", leader=name, mint=sw["mint"], err=str(err)[:300], sig=(res or {}).get("sig"))
        f = res["fill"]; sol_spent = -f["lamports"] / 1e9
        pos = dict(id=f"live:{sw['mint'][:8]}:{int(time.time())}", leader=name, mint=sw["mint"], decimals=dec, status="open",
                   opened=self.bot_iso(), leader_sig=sw["sig"], leader_px=sw["fill_px"], buy_sig=res["sig"],
                   sol_in=sol_spent, sol_px_in=solpx, usd_in=sol_spent * solpx, size_usd=size, lamports_swapped=lam,
                   tokens_raw=f["token_raw"], tokens_left=f["token_raw"], quote_out=res["quote_out"], impact=impact, chase=chase,
                   slip_bps=res["slip_bps"], route=res["route"], sol_out=0.0, usd_out=0.0, tp_done=False, sells=[], txs=[res["sig"]],
                   last_value_usd=size, next_q=time.time() + 12, fails=0)
        self.s["positions"].append(pos); self.bot.save()
        self.log("buy", pos=pos["id"], sig=res["sig"], mint=sw["mint"], sol_in=sol_spent, usd_in=round(sol_spent * solpx, 4),
                 tokens_raw=f["token_raw"], quoted_tokens_raw=res["quote_out"], fill_vs_quote=round(f["token_raw"] / res["quote_out"] - 1, 4) if res["quote_out"] else None,
                 impact=impact, chase=chase, slip_bps=res["slip_bps"], prio_lamports=res["prio_lamports"], tx_fee_lamports=f["fee"],
                 route=res["route"], night_start_sol=night.get("start_sol"))

    def night_start(self, loc, val_sol, solpx):
        nk = period_key(loc, self.session())
        d = json.load(open(self.night_fn)) if os.path.exists(self.night_fn) else {}
        if d.get("night") != nk and val_sol > 0:
            d = dict(night=nk, start_sol=val_sol, sol_px=solpx, start_usd=val_sol * solpx, recorded=self.bot_iso())
            json.dump(d, open(self.night_fn, "w"), indent=1); self.log("night_start", **d)
        return d

    def sell(self, pos, frac, reason):
        urgent = reason.startswith(URGENT)
        steps = HARD["urgent_exit_slip_steps"] if urgent else (HARD["exit_slip_bps"],) * HARD["sell_tries"]
        for i, slip in enumerate(steps[:HARD["sell_tries"]]):
            accts = self.token_accounts(pos["mint"])
            bal = sum(a["raw"] for a in accts) if accts is not None else pos["tokens_left"]
            amt = bal if frac >= 0.999 else min(bal, int(pos["tokens_left"] * frac))
            if amt <= 0:
                pos["tokens_left"] = bal
                if bal <= 0: self.finish(pos, accts)
                return True
            res, err = self.swap(pos["mint"], WSOL, amt, slip, i == 0, reason)
            if res and res["ok"] and res.get("fill"):
                f = res["fill"]; got = f["lamports"] / 1e9; px = self.bot.sol_price() or pos["sol_px_in"]
                pos["sol_out"] += got; pos["usd_out"] += got * px; pos["tokens_left"] = max(0, bal + f["token_raw"])
                pos["sells"].append(dict(ts=self.bot_iso(), reason=reason, sig=res["sig"], tokens_raw=-f["token_raw"], sol_out=got,
                                         usd_out=round(got * px, 4), slip_bps=res["slip_bps"], attempt=i + 1)); pos["txs"].append(res["sig"])
                self.log("sell", pos=pos["id"], reason=reason, sig=res["sig"], mint=pos["mint"], tokens_raw=-f["token_raw"], sol_out=got,
                         usd_out=round(got * px, 4), tx_fee_lamports=f["fee"], slip_bps=res["slip_bps"], attempt=i + 1, impact=res["impact"])
                if frac >= 0.999 or pos["tokens_left"] <= 0:
                    self.finish(pos, None)
                self.bot.save(); return True
            self.log("sell_failed", pos=pos["id"], reason=reason, attempt=i + 1, slip_bps=slip, err=str(err)[:300], sig=(res or {}).get("sig"))
        pos["fails"] = pos.get("fails", 0) + 1; self.bot.save(); return False

    def finish(self, pos, accts):
        """position flat: close our now-empty token account(s) to reclaim rent to THIS wallet."""
        accts = accts if accts is not None else self.token_accounts(pos["mint"])
        for a in accts or []:
            if a["raw"] == 0: self.close_token_account(a["addr"], a["prog"], pos)
        rest = sum(a["raw"] for a in accts or [])
        if rest == 0 or pos.get("tokens_left", 0) <= 0:
            pos["status"] = "closed"; pos["closed"] = self.bot_iso()
            self.log("closed", pos=pos["id"], mint=pos["mint"], sol_in=pos["sol_in"], sol_out=pos["sol_out"],
                     net_sol=round(pos["sol_out"] - pos["sol_in"], 6), net_usd=round(pos["usd_out"] - pos["usd_in"], 4),
                     rent_reclaimed_sol=pos.get("rent_back", 0))
        self.bot.save()

    def close_token_account(self, addr, prog, pos):
        from solders.instruction import Instruction, AccountMeta
        from solders.message import Message
        from solders.transaction import Transaction
        from solders.hash import Hash
        P = self.Pubkey.from_string; me = P(self.pub)
        ix = Instruction(P(prog), bytes([9]), [AccountMeta(P(addr), False, True), AccountMeta(me, False, True), AccountMeta(me, True, False)])
        bh = self.bot.rpc("getLatestBlockhash", [{"commitment": "confirmed"}])
        if not bh: return
        h = Hash.from_string(bh["value"]["blockhash"])
        tx = Transaction([self._kp], Message.new_with_blockhash([ix], me, h), h)
        from solders.transaction import VersionedTransaction
        vtx = VersionedTransaction.from_legacy(tx)
        ok, why = verify_swap_tx(vtx, self.pub, self.wsol_ata)
        if not ok: return self.log("close_acct_blocked", why=why)
        sig, ok, err = self.send_and_confirm(vtx, bh["value"]["lastValidBlockHeight"], timeout=45)
        if ok:
            f = self.fill(sig, pos["mint"]); back = (f or {}).get("lamports", 0) / 1e9
            pos["rent_back"] = pos.get("rent_back", 0) + back; pos["sol_out"] += back; pos["txs"].append(sig)
        self.log("close_token_account", pos=pos["id"], sig=sig, ok=ok, err=err, rent_back_sol=pos.get("rent_back"))

    def mirror(self, name, sw, frac, lf):
        """leader's first sell: sell all but 10% of the original size; later leader sells are ignored (leftover rules)."""
        for pos in [p for p in self.s["positions"] if p["status"] == "open" and p["leader"] == name and p["mint"] == sw["mint"]]:
            if pos.get("leader_sold"):
                self.log("leader_sell_ignored_leftover", pos=pos["id"], leader_frac=round(lf, 4), sig=sw["sig"]); continue
            f, keep = mirror_keep(pos["tokens_left"], pos["tokens_raw"])
            pos["leader_sold"] = True; pos["keep_raw"] = keep
            self.log("leader_sell_mirror", pos=pos["id"], leader_frac=round(lf, 4), our_frac=round(f, 4), keep_raw=keep, sig=sw["sig"])
            if f > 0: self.sell(pos, f, f"leader_sold_{round(lf*100)}%_keep10")

    def note_add(self, name, mint, ts):
        """the copied leader bought more of a token we hold -> TPs deferred / trail widened for 10 min."""
        for pos in [p for p in self.s["positions"] if p["status"] == "open" and p["leader"] == name and p["mint"] == mint]:
            pos["last_add_ts"] = max(pos.get("last_add_ts") or 0, ts); self.log("leader_add", pos=pos["id"], add_ts=ts)

    def flatten(self, reason):
        for pos in [p for p in self.s["positions"] if p["status"] == "open"]:
            self.sell(pos, 1.0, reason)

    def tick(self, loc, solpx):
        """requote open live positions, TP/SL, night/session loss limit, 08:00 and session-end close-outs (retry until flat)."""
        opn = [p for p in self.s["positions"] if p["status"] == "open"]
        if loc.hour == HARD["close_hour"] and opn and time.time() - self.last_close_try > 30:
            self.last_close_try = time.time(); return self.flatten("close_0800_dublin")
        sess = self.session()
        if session_must_close(loc, sess) and opn and time.time() - self.last_close_try > 30:
            self.last_close_try = time.time(); return self.flatten("close_session_end")
        for p in sorted(opn, key=lambda p: p["next_q"])[:1]:
            if p["next_q"] > time.time(): continue
            p["next_q"] = time.time() + 12
            q, err = self.bot.quote(p["mint"], WSOL, p["tokens_left"], "live_mark")
            if not q: continue
            p["last_value_usd"] = q["out"] / 1e9 * solpx; p["last_q"] = self.bot_iso()
            self.apply_exit(p, solpx)
        if (opn or self.enabled) and time.time() - self.last_val_t > 60:
            self.last_val_t = time.time()
            val, sol = self.wallet_value_sol(solpx)
            if self.enabled and not gas_ok(sol) and (self.usdc_bal or 0) > 0 and time.time() - self.last_gas_log > 1800:
                self.last_gas_log = time.time()
                self.log("needs gas SOL", sol_balance=sol, usdc=self.usdc_bal, min_gas_sol=HARD["min_gas_sol"], action="idle")
            if self.enabled and self.maybe_convert_usdc(solpx): val, sol = self.wallet_value_sol(solpx)
            self.s["wallet"] = dict(ts=self.bot_iso(), sol=sol, usdc=self.usdc_bal, value_sol=val, value_usd=val * solpx,
                                    state=("needs_gas_sol" if not gas_ok(sol) else "ok"))
            d = json.load(open(self.night_fn)) if os.path.exists(self.night_fn) else {}
            nk = period_key(loc, sess)
            if d.get("night") != nk and val > 0 and self.enabled: d = self.night_start(loc, val, solpx)
            if d.get("night") == nk and nk not in self.s["halted_nights"] and loss_limit_hit(val, d.get("start_sol"), session_halt_frac(loc, sess)):
                self.s["halted_nights"].append(nk)
                self.log("night_loss_limit", value_sol=val, start_sol=d["start_sol"], action="sell all, no more buys tonight")
                self.flatten("loss_limit")
            self.bot.save()

    def apply_exit(self, p, solpx):
        basis = p["usd_in"] * (p["tokens_left"] / p["tokens_raw"]) if p["tokens_raw"] else 0
        if basis <= 0: return
        if p.get("leader_sold") and p["tokens_left"] > (p.get("keep_raw") or 0) * 1.01 + 1:   # mirror sell failed earlier: retry
            f, _ = mirror_keep(p["tokens_left"], p["tokens_raw"])
            if f > 0 and self.sell(p, f, "leader_sold_keep10_retry"): return
        x = p["last_value_usd"] / basis
        adding = time.time() - (p.get("last_add_ts") or 0) < HARD["add_window_s"]
        lvl = p.get("tp_level", 1 if p.get("tp_done") else 0)
        fee_usd = (self.cfg["priority_fee_sol"] + 0.000005) * solpx          # one exit tx; entry costs are already in usd_in
        dec = exit_plan(x, tp_level=lvl, peak_x=p.get("peak_x"), be_x=breakeven_x(p["usd_in"], fee_usd), leader_sold=p.get("leader_sold", False), adding=adding)
        p["peak_x"] = max(p.get("peak_x") or 0, x)
        if not dec: return
        kind, frac, reason = dec
        if kind == "defer":
            if p.get("deferred") != reason: p["deferred"] = reason; self.log("tp_deferred", pos=p["id"], reason=reason, x=round(x, 4), add_ts=p.get("last_add_ts"))
            return
        p["deferred"] = None
        ok = self.sell(p, frac, reason)
        if ok and kind in ("tp1", "tp2", "tp12"):
            p["tp_level"] = {"tp1": 1, "tp2": 2, "tp12": 2}[kind]; p["tp_done"] = True

    def session_text(self):
        x = self.session()
        if not x: return ""
        f = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
        return (f" SESSION {x['key']}: {f(x['start_ts'])} → {f(x['end_ts'])}, no entries from {f(x['end_ts'] - x['no_entry_s'])}, flat at {f(x['end_ts'])}, "
                f"−20% halt from the balance at session start; after the end no entries until {f(x['resume_ts']) if x.get('resume_ts') else 'session.json is removed'}.")
    def summary_lines(self, solpx):
        P = self.s["positions"]; w = self.s.get("wallet", {})
        L = ["", "## LIVE (bot wallet, real fills)", "",
             f"Mode: **{'ON' if self.enabled else 'OFF'}** (file `LIVE`). Wallet `{self.pub}`. SOL {w.get('sol')}; USDC {w.get('usdc')}; state {w.get('state')}; USDC→SOL conversions {len(self.s.get('conversions', []))}; value ≈ {w.get('value_sol')} SOL (${(w.get('value_usd') or 0):.2f}) at {w.get('ts')}.",
             f"Caps (hard): size min(${HARD['max_usd']:.0f}, 15% wallet), keep {HARD['reserve_sol']} SOL, ≤{HARD['max_open']} open, chase ≤8%, impact ≤3%, leader ≥$50 and seen ≤2 min after it, mcap ≥$1M, liquidity ≥$100k, token/pool age ≥60 min, exits v3: SL −15% → breakeven after first TP, TP 25% at +40% and 25% at +100% (deferred while the leader adds), trail 25% below peak after TP1 (35% while adding); leader's first sell → sell all but 10% of original, leftover exits at +500% or its stop, no entries 07:45–08:00, flat by 08:00 Dublin, night loss limit −20%.{self.session_text()} Priority fee {self.cfg['priority_fee_sol']} SOL. Halted nights: {self.s['halted_nights'] or 'none'}.", "",
             "| opened | mint | status | SOL in | SOL out | net SOL | net $ (in/out at fill-time SOL px) | open mark $ | buy sig |", "|---|---|---|---|---|---|---|---|---|"]
        tin = tout = 0
        for p in P[-40:]:
            mk = p["last_value_usd"] if p["status"] == "open" else 0
            tin += p["usd_in"]; tout += p["usd_out"] + mk
            L.append(f"| {p['opened']} | `{p['mint'][:6]}…` | {p['status']} | {p['sol_in']:.5f} | {p['sol_out']:.5f} | {p['sol_out']-p['sol_in']:+.5f} | {p['usd_out']+mk-p['usd_in']:+.2f} | {mk:.2f} | `{p['buy_sig'][:10]}…` |")
        if P: L.append(f"| **total** | | {len(P)} | | | | {tout-tin:+.2f} ({(tout-tin)/tin*100 if tin else 0:+.1f}%) | | |")
        else: L.append("| – | no live trades yet | | | | | | | |")
        return L
