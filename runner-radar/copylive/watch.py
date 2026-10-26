#!/usr/bin/env python3
"""copylive signal watcher for Chunk's MANUAL Banana Gun copy book.

NEVER trades, signs, reads keys, opens Telegram or a browser. It reads /workspace/selfcopy (read-only),
public APIs (DexScreener, Jupiter quote/price, rugcheck.xyz, GeckoTerminal, public RPC getBalance), and writes only
inside copylive/. When a manual trade is needed it prints ONE JSON action line, appends it to actions.jsonl, and
(since 15:50Z) KEEPS RUNNING under run_watch.sh (supervisor, auto-restart). Chunk reads actions.jsonl / pending_actions.json,
trades by hand and records the fill with record.py. No restart needed. --exit-on-action restores the old one-shot mode.

  python3 watch.py              # loop (poll ~5s) until an action is needed
  python3 watch.py --once       # one tick only (exit 0 + action, or exit 3 = nothing to do)
  python3 watch.py --dry-run    # replay paper-trades.jsonl (+ dryrun file) and explain every decision
"""
import argparse, json, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *            # noqa
import checks

URGENT = ("SELL_ALL", "sl", "trail", "leader_sold")

def new_state():
    return dict(cursor=0, inode=None, handled={}, queue=[], first_swaps={}, adds={}, leader_sells={},
                pending={}, peaks={}, halted_nights=[], started=iso())

def k(leader, mint): return f"{leader}|{mint}"

def block_ts(sw):
    t = parse_iso(sw["ts"])
    return t - float(sw.get("detect_lag_s") or 0)

# ---------------- signal ingestion ----------------
def ingest(st, fn=SIGNALS):
    try: s = os.stat(fn)
    except FileNotFoundError: return 0
    if st.get("inode") != s.st_ino or s.st_size < st.get("cursor", 0):
        st["inode"], st["cursor"] = s.st_ino, 0
    n = 0
    with open(fn, "rb") as f:
        f.seek(st["cursor"])
        while True:
            line = f.readline()
            if not line or not line.endswith(b"\n"): break      # partial line: wait for the writer
            st["cursor"] = f.tell()
            try: ev = json.loads(line)
            except Exception: continue
            handle_event(st, ev); n += 1
    return n

# ---------------- trial bridge (15:25Z, user 15:22Z: retire lab, "just start trying things") ----------------
LAB_DIR = "/workspace/lab/forward"
TRIAL_STRATS = ("consensus", "graduation", "dipbuy", "revival")      # dlmm = LP estimate, never a buy
def ingest_lab(st):
    """lab ideas_fwd.py ENTRY rows -> trial entry signals (tier 'trial', leader 'trial:<strategy>')"""
    offs = st.setdefault("lab_off", {}); n = 0
    for s in TRIAL_STRATS:
        fn = os.path.join(LAB_DIR, f"{s}_fwd.jsonl")
        try: size = os.path.getsize(fn)
        except OSError: continue
        if s not in offs: offs[s] = size; continue          # first sight: start at the end (no back-fill of old rows)
        if size < offs[s]: offs[s] = 0
        with open(fn, "rb") as f:
            f.seek(offs[s])
            while True:
                line = f.readline()
                if not line or not line.endswith(b"\n"): break
                offs[s] = f.tell()
                try: r = json.loads(line)
                except Exception: continue
                if r.get("event") != "entry" or not r.get("token_mint") or r.get("strategy") != s: continue
                pos = f"trial:{s}:{r['token_mint']}:{r['ts_utc']}"
                if pos in st["handled"] or any(q.get("pos") == pos for q in st["queue"]): continue
                st["queue"].append(dict(event="entry", tier="trial", strategy=s, leader=f"trial:{s}", mint=r["token_mint"],
                                        ts=r["ts_utc"], leader_ts=r["ts_utc"], leader_px=r.get("price_usd"), leader_usd=None,
                                        lab_symbol=r.get("symbol"), lab_pool=r.get("pool"), pos=pos)); n += 1
    return n

def trial_cut(strategy):
    """per-strategy cut: the last 2 CLOSED trial positions of this strategy both lost -> strategy off"""
    P = load(F["positions"], {})
    cl = sorted([p for p in P.values() if p.get("leader") == f"trial:{strategy}" and p.get("status") == "closed"],
                key=lambda p: p.get("closed_ts") or "")
    return len(cl) >= 2 and all((p.get("pnl_sol") or 0) < 0 for p in cl[-2:])

def eval_trial(ev, st, positions, d, ctx):
    t, chk = ctx["now"], []
    mint, s = ev["mint"], ev["strategy"]
    lead_ts = parse_iso(ev["leader_ts"]); delay = t - lead_ts; ref = ev.get("leader_px")
    info = dict(mint=mint, leader=ev["leader"], tier="trial", strategy=s, leader_px=ref, leader_usd=None,
                leader_ts=iso(lead_ts), signal_age_s=round(delay, 1), checks=chk)
    def fail(reason): info["reason"] = reason; return "skip", info
    def ok(name, cond, detail=""):
        chk.append(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail else "")); return cond
    if not ok("mint not blocked (session.json blocked_mints)", mint not in blocked_mints()): return fail("blocked_mint")
    if not ok("TRIAL strategy enabled", s in R.get("trial_strategies", TRIAL_STRATS)): return fail("trial_strategy_off")
    if not ok("TRIAL strategy not cut (2 losses in a row)", not trial_cut(s)): return fail("trial_strategy_cut_2_losses")
    if not ok(f"<={R['max_signal_delay_s']//60} min after lab entry", delay <= R["max_signal_delay_s"], f"{delay:.0f}s"): return fail("too_late")
    if not ok("session entry hours", entries_allowed(t), iso(t)[11:16] + "Z"): return fail("outside_entry_hours")
    if not ok("session halt not hit", not ctx["halted"]): return fail("night_halt")
    opn = [p for p in positions.values() if p.get("status") == "open"]
    if not ok(f"< {R['max_open']} open copy positions (all tiers)", ctx.get("n_open", len(opn)) < R["max_open"],
              f"{ctx.get('n_open', len(opn))} (wallet holdings {ctx.get('n_hold')}, positions.json {len(opn)})"): return fail("max_open")
    held = any(p["mint"] == mint for p in opn) or (mint in st["pending"] and st["pending"][mint]["type"] == "BUY")
    if not ok("not already holding mint", not held): return fail("already_holding")
    if not d:
        chk.append("WAIT DexScreener data unavailable")
        return (fail("no_dexscreener_data") if delay > R["max_signal_delay_s"] else ("wait", info))
    chase = (d["price"] / ref - 1) if (d.get("price") and ref) else None
    info.update(ticker=d.get("ticker") or ev.get("lab_symbol"), current_px=d.get("price"), chase_pct=None if chase is None else round(chase * 100, 2),
                age_s=int(t - d["created"]) if d.get("created") else None, liq=d.get("liq"), mcap=d.get("mcap"), dexscreener=d.get("url"))
    if not ok(f"price <= {R['max_chase']*100:.0f}% above lab entry price", chase is not None and chase <= R["max_chase"],
              "n/a" if chase is None else f"{chase*100:+.1f}%"): return fail("chase")
    size = min(size_sol(ctx["bal"], None), float(R.get("trial_size_sol", 0.02))) if ctx.get("bal") is not None else 0.0
    if not ok("size > 0 keeping reserve", size > 0, f"bal {ctx.get('bal')} -> {size}"): return fail("unfunded")
    rok, rinfo = checks.rug_check(mint, d, t); info["rugguard"] = rinfo
    if not ok("rugguard", rok, "; ".join(rinfo.get("rejects") or rinfo.get("notes") or []) or "clean"): return fail("rugguard")
    qok, q = checks.route_check(mint, size, d.get("price"), ctx.get("solpx")); info["sell_route"] = q
    if not ok("Jupiter token->SOL quote impact < 3%", qok, q.get("err") or f"impact {q.get('impact',0)*100:.2f}% via {q.get('route')}"): return fail("no_sell_route")
    info["size_sol"] = size
    return "buy", info

def handle_event(st, ev):
    e = ev.get("event")
    if e == "leader_swap":
        kk = k(ev.get("leader"), ev.get("mint"))
        if ev.get("side") == "buy":
            if not ev.get("pre_bal"): st["first_swaps"][kk] = ev
            else: st["adds"].setdefault(kk, []).append(parse_iso(ev["ts"])); st["adds"][kk] = st["adds"][kk][-20:]
        elif ev.get("side") == "sell":
            v = st["leader_sells"].get(kk)
            v = [v] if isinstance(v, (int, float)) else list(v or [])
            v.append(parse_iso(ev["ts"])); st["leader_sells"][kk] = v[-50:]
    elif e == "entry":
        sid = ev.get("pos") or f"{ev.get('leader')}:{ev.get('mint')}:{ev.get('ts')}"
        if sid not in st["handled"] and not any(q.get("pos") == sid for q in st["queue"]):
            ev["pos"] = sid; st["queue"].append(ev)

# ---------------- entry gate ----------------
def eval_entry(ev, st, positions, d, ctx, dry=False):
    """-> (decision, info). decision: 'buy' | 'skip' | 'wait'. ctx: now, bal, solpx, live, halted"""
    t, chk = ctx["now"], []
    mint, leader = ev["mint"], ev.get("leader")
    sw = st["first_swaps"].get(k(leader, mint))
    if sw:
        lead_ts = block_ts(sw); leader_usd = sw.get("usd")
    else:   # top-up entries (topup: true) carry the leader's buy on the entry event itself
        lt = ev.get("leader_ts")
        lead_ts = (float(lt) if isinstance(lt, (int, float)) else parse_iso(lt)) if lt else parse_iso(ev["ts"])
        leader_usd = ev.get("leader_usd")
    leader_px = ev.get("leader_px") or (sw or {}).get("fill_px")
    delay = t - lead_ts
    info = dict(mint=mint, leader=leader, leader_px=leader_px, leader_usd=leader_usd, leader_ts=iso(lead_ts),
                signal_age_s=round(delay, 1), checks=chk)
    def fail(reason): info["reason"] = reason; return "skip", info
    def ok(name, cond, detail=""):
        chk.append(("PASS " if cond else "FAIL ") + name + (f" ({detail})" if detail else "")); return cond

    if not ok("mint not blocked (session.json blocked_mints)", mint not in blocked_mints()): return fail("blocked_mint")
    if not ok("leader LIVE", leader in ctx["live"], f"live={ctx['live']}"): return fail("leader_not_live")
    if not ok("not a forced override", not ev.get("forced"), str(ev.get("forced"))): return fail("forced_override")
    if not ok(f"leader buy >= ${R['min_leader_usd']:,.0f}", (leader_usd or 0) >= R["min_leader_usd"], f"${leader_usd}"): return fail("leader_buy_lt_min")
    in_win = delay <= R["max_signal_delay_s"]
    if dry: chk.append(f"{'PASS' if in_win else 'INFO'} <=3 min after leader buy (would be {delay:.0f}s now; ignored in dry run)")
    elif not ok(f"<={R['max_signal_delay_s']//60} min after leader buy", in_win, f"{delay:.0f}s"): return fail("too_late")
    if not dry:
        if not ok("session entry hours", entries_allowed(t), iso(t)[11:16] + "Z"): return fail("outside_entry_hours")
        if not ok("night halt not hit", not ctx["halted"]): return fail("night_halt")
        opn = [p for p in positions.values() if p.get("status") == "open"]
        if not ok(f"< {R['max_open']} open copy positions (all tiers)", ctx.get("n_open", len(opn)) < R["max_open"],
              f"{ctx.get('n_open', len(opn))} (wallet holdings {ctx.get('n_hold')}, positions.json {len(opn)})"): return fail("max_open")
        held = any(p["mint"] == mint for p in opn) or (mint in st["pending"] and st["pending"][mint]["type"] == "BUY")
        if not ok("not already holding mint", not held): return fail("already_holding")
    if not d:
        chk.append("WAIT DexScreener data unavailable")
        if dry or delay > R["max_signal_delay_s"]: return fail("no_dexscreener_data")
        return "wait", info
    age_s = t - d["created"] if d.get("created") else None
    chase = (d["price"] / leader_px - 1) if (d.get("price") and leader_px) else None
    info.update(ticker=d.get("ticker"), current_px=d.get("price"), chase_pct=None if chase is None else round(chase * 100, 2),
                age_s=None if age_s is None else int(age_s), liq=d.get("liq"), mcap=d.get("mcap"), dexscreener=d.get("url"),
                paper_entry=dict(mcap=ev.get("mcap"), liq=ev.get("liq"), chase_pct=round((ev.get("chase") or 0) * 100, 2)))
    if dry:
        ok(f"[at signal] mcap >= ${R['min_mcap']:,.0f} (paper)", (ev.get("mcap") or 0) >= R["min_mcap"], f"${ev.get('mcap'):,.0f}")
        ok("[at signal] liq >= $100k (paper)", (ev.get("liq") or 0) >= R["min_liq"], f"${ev.get('liq'):,.0f}")
        sa = (parse_iso(ev["ts"]) - d["created"]) if d.get("created") else None
        ok(f"[at signal] token age >= {R['min_age_s']//60} min", sa is not None and sa >= R["min_age_s"], f"{(sa or 0)/60:.0f} min")
        ok("[at signal] chase <= 8% (paper quote)", (ev.get("chase") or 0) <= R["max_chase"], f"{(ev.get('chase') or 0)*100:+.1f}%")
    mm, ml = lrule(leader, "min_mcap"), lrule(leader, "min_liq")
    r = []
    if not ok(f"token age >= {R['min_age_s']//60} min", age_s is not None and age_s >= R["min_age_s"], f"{(age_s or 0)/60:.0f} min"): r.append("age_lt_min")
    if not ok(f"liq >= ${ml:,.0f}", (d.get("liq") or 0) >= ml, f"${d.get('liq') or 0:,.0f}"): r.append("liq_lt_min")
    if not ok(f"mcap >= ${mm:,.0f}", (d.get("mcap") or 0) >= mm, f"${d.get('mcap') or 0:,.0f}"): r.append("mcap_lt_min")
    if not ok(f"price <= {R['max_chase']*100:.0f}% above leader fill", chase is not None and chase <= R["max_chase"],
              "n/a" if chase is None else f"{chase*100:+.1f}%"): r.append("chase_gt_max")
    # 15:15Z tiny tier (user 15:12Z): coins failing only the normal mcap/age/liq gates pass at tiny_size_sol if they meet
    # mcap >= tiny_min_mcap, liq >= tiny_min_liq, age >= tiny_min_age_s; chase, rugguard and <3% sell impact still required.
    tier = "normal"
    if r and R.get("tiny_size_sol") and set(r) <= {"age_lt_min", "liq_lt_min", "mcap_lt_min"}:
        tok = ok(f"TINY tier: mcap >= ${R['tiny_min_mcap']:,.0f}, liq >= ${R['tiny_min_liq']:,.0f}, age >= {R['tiny_min_age_s']//60} min",
                 (d.get("mcap") or 0) >= R["tiny_min_mcap"] and (d.get("liq") or 0) >= R["tiny_min_liq"]
                 and age_s is not None and age_s >= R["tiny_min_age_s"],
                 f"mcap ${d.get('mcap') or 0:,.0f}, liq ${d.get('liq') or 0:,.0f}, age {(age_s or 0)/60:.1f} min")
        if tok: info["tiny_waived"] = list(r); r = []; tier = "tiny"
        # 16:20Z curve tier: pump.fun mints still on the bonding curve (DexScreener liq 0 / dex 'pumpfun'); the Jupiter sell
        # quote below at 0.02 SOL (<3% impact) is the liquidity proof. mcap >= curve_min_mcap, age >= curve_min_age_s.
        elif mint.endswith("pump") and R.get("curve_size_sol") and (not d.get("liq") or d.get("dex") == "pumpfun"):
            cok = ok(f"CURVE tier: pump.fun bonding curve, mcap >= ${R['curve_min_mcap']:,.0f}, age >= {R['curve_min_age_s']//60} min",
                     (d.get("mcap") or 0) >= R["curve_min_mcap"] and age_s is not None and age_s >= R["curve_min_age_s"],
                     f"mcap ${d.get('mcap') or 0:,.0f}, dex {d.get('dex')}, age {(age_s or 0)/60:.1f} min")
            if cok: info["tiny_waived"] = list(r); r = []; tier = "curve"
    info["tier"] = tier
    if r and not dry: return fail(r[0])
    size = size_sol(ctx["bal"], leader) if ctx.get("bal") is not None else 0.0
    if tier == "tiny": size = min(size, float(R["tiny_size_sol"]))
    if tier == "curve": size = min(size, float(R["curve_size_sol"]))
    if not dry and not ok("size >= 0.005 SOL keeping 0.02", size > 0, f"bal {ctx.get('bal')} -> {size}"): return fail("unfunded")
    rok, rinfo = checks.rug_check(mint, d, t)
    info["rugguard"] = rinfo
    if not ok("rugguard", rok, "; ".join(rinfo.get("rejects") or rinfo.get("notes") or []) or "clean"):
        if not dry: return fail("rugguard")
        r.append("rugguard")
    qok, q = checks.route_check(mint, size or 0.09, d.get("price"), ctx.get("solpx"))
    info["sell_route"] = q
    if not ok("Jupiter token->SOL quote", qok, q.get("err") or f"impact {q.get('impact',0)*100:.2f}% via {q.get('route')}"):
        if not dry: return fail("no_sell_route")
        r.append("no_sell_route")
    info["size_sol"] = size
    if r: info["all_fails"] = r; return fail(r[0])
    return "buy", info

# ---------------- exits ----------------
def pos_id(p): return f"{p['mint']}:{p.get('opened_ts')}"

def eval_position(p, st, d, t):
    """-> list of candidate SELL actions (most urgent first) for one open position"""
    out = []
    if not d or not d.get("price") or not p.get("entry_px"): return out
    x = d["price"] / p["entry_px"]
    pid = pos_id(p)
    pk = max(st["peaks"].get(pid) or x, x); st["peaks"][pid] = pk
    kk = k(p["leader"], p["mint"])
    opened = parse_iso(p["opened_ts"])
    adding = any(a > opened - 5 and t - a < R["add_window_s"] for a in st["adds"].get(kk, []))
    tp = int(p.get("tp_level") or 0)
    orig, left = float(p["tokens_orig"]), float(p["tokens_left"])
    base = dict(mint=p["mint"], ticker=p.get("ticker"), leader=p["leader"], entry_px=p["entry_px"], current_px=d["price"],
                x=round(x, 4), pnl_pct=round((x - 1) * 100, 2), peak_x=round(pk, 4), tp_level=tp, leader_adding=adding,
                tokens_left=left, dexscreener=d.get("url"))
    def sell(kind, tokens, reason):
        tokens = min(tokens, left)
        if tokens <= 0: return
        frac = tokens / orig
        out.append(dict(type="SELL", kind=kind, fraction=round(frac, 4), tokens=round(tokens, 6),
                        sell_pct_of_holding=round(100 * tokens / left, 1), reason=reason,
                        record_cmd=f"python3 record.py sell {p['mint']} {round(frac, 4)} <sol_out> {reason.replace(' ', '_')}", **base))
    # 16:20Z breakeven ratchet: once +10% is reached, stop moves to entry x 1.02 (MOVE_STOP emitted once; emit() records it)
    sm = p.get("stop_moved")
    if sm and x <= float(sm.get("stop_x", R.get("ratchet_stop_x", 1.02))):
        sell("sl", left, f"sl_ratchet_+{round((float(sm.get('stop_x', 1.02)) - 1) * 100)}%"); return out
    if not sm and x >= R.get("ratchet_trigger_x", 1.10) and x < (R.get("single_tp_x") or 99):
        sx = R.get("ratchet_stop_x", 1.02)
        emc = d["mcap"] * p["entry_px"] / d["price"] if d.get("mcap") else None
        out.append(dict(type="MOVE_STOP", kind="move_stop", mint=p["mint"], ticker=p.get("ticker"), leader=p["leader"],
                        entry_px=p["entry_px"], current_px=d["price"], x=round(x, 4), pnl_pct=round((x - 1) * 100, 2),
                        new_stop_px=p["entry_px"] * sx, entry_mcap=None if emc is None else round(emc), new_stop_mcap=None if emc is None else round(emc * sx),
                        stop_x=sx, dexscreener=d.get("url"),
                        note=f"Position reached +{(x-1)*100:.1f}%: in Banana Gun move the SL to entry +{round((sx-1)*100)}% "
                             f"(price {p['entry_px']*sx:.10g}" + ("" if emc is None else f", mcap ${emc*sx:,.0f}") + "). TP +20% unchanged. No record.py needed."))
    # 16:20Z time stop: open >= 30 min and still within +-5% -> sell 100% to free the slot
    ts_s, band = R.get("time_stop_s", 1800), R.get("time_stop_band", 0.05)
    if t - opened >= ts_s and abs(x - 1) <= band:
        sell("time_stop", left, f"time stop {ts_s // 60}m flat"); return out
    dec = exit_plan(x, tp_level=tp, peak_x=pk, be_x=R["be_x"], leader_sold=p.get("leader_sold", False), adding=adding)
    lsv = st["leader_sells"].get(kk)
    lsv = [lsv] if isinstance(lsv, (int, float)) else (lsv or [])
    ls = any(x_ > opened for x_ in lsv)          # only leader sells after OUR entry count
    if dec and dec[0] == "sl": sell("sl", left, dec[2])
    elif dec and dec[0] == "tp_all": sell("tp_all", left, dec[2])
    elif ls and not p.get("leader_sold"):
        sell("leader_sold", mirror_keep(left, orig), "leader_sold_keep10")
    elif dec and dec[0] == "trail": sell("trail", left, dec[2])
    elif dec and dec[0] in ("tp1", "tp2", "tp12", "moon"): sell(dec[0], dec[1] * left, dec[2])
    elif dec and dec[0] == "defer": base["deferred"] = dec[2]
    return out

# ---------------- main tick ----------------
class Ctx: pass

def wallet_cached(st, force=False):
    c = st.get("bal_cache") or {}
    if force or now() - (c.get("t") or 0) > 30:
        try: st["bal_cache"] = c = dict(t=now(), sol=sol_balance())
        except Exception as e:
            if not c: raise
    return c["sol"]

def solpx_cached(st):
    c = st.get("solpx_cache") or {}
    if now() - (c.get("t") or 0) > 120:
        p = sol_usd()
        if p: st["solpx_cache"] = c = dict(t=now(), px=p)
    return c.get("px")

def holdings_cached(st, force=False):
    """wallet token holdings, re-read every ~45 s (or when forced: free SOL dropped > 0.01 since the last read, i.e. a
    Banana Gun copy probably just bought); on RPC failure the last good read is kept for up to 5 min"""
    c = st.get("hold_cache") or {}
    if force or now() - (c.get("t") or 0) > 45:
        try:
            bal0 = wallet_cached(st, force=True)
            st["hold_cache"] = c = dict(t=now(), h=wallet_holdings(), bal=bal0)
        except Exception as e:
            st["hold_err"] = dict(ts=iso(), err=repr(e)[:200])
            # 24 Oct night fix: never silently fall back to positions.json; keep the last good snapshot (caller flags stale > 5 min)
            if not c.get("t"): return None
    return c.get("h")

def holdings_stale_min(st):
    """minutes since the last good holdings read if > 5 min, else 0"""
    c = st.get("hold_cache") or {}
    age = now() - (c.get("t") or 0) if c.get("t") else 0
    return int(age // 60) if age > 300 else 0

DUST_USD = 0.5

def buy_cost_sol(st, mint):
    """16:45Z fallback for an UNPRICED wallet holding not in positions.json (e.g. a Banana Gun copy): SOL that left the
    wallet in the most recent tx that increased this mint's balance. Cached per mint; None if not found (retried after 5 min)."""
    bc = st.setdefault("buy_cost", {})
    c = bc.get(mint)
    if c and (c.get("sol") is not None or now() - c["t"] < 300): return c.get("sol")
    sol = None
    try:
        sigs = rpc("getSignaturesForAddress", [WALLET, {"limit": 30}])
        for s in sigs:
            if s.get("err"): continue
            try: tx = rpc("getTransaction", [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
            except Exception: continue
            if not tx: continue
            m_ = tx["meta"]
            def amt(rows): return sum(float(r["uiTokenAmount"].get("uiAmount") or 0) for r in rows or [] if r["mint"] == mint and r.get("owner") == WALLET)
            if amt(m_.get("postTokenBalances")) > amt(m_.get("preTokenBalances")):
                keys = [k_["pubkey"] if isinstance(k_, dict) else k_ for k_ in tx["transaction"]["message"]["accountKeys"]]
                i = keys.index(WALLET)
                sol = max(0.0, (m_["preBalances"][i] - m_["postBalances"][i]) / 1e9); break
    except Exception as e: st["hold_err"] = dict(ts=iso(), err="buy_cost: " + repr(e)[:150])
    bc[mint] = dict(t=now(), sol=sol)
    return sol

def blocked_mints():
    s = load(os.path.join(HERE, "session.json"), {}) or {}
    return set(s.get("blocked_mints") or [])
def tick(st, verbose=False):
    t = now()
    ingest(st)
    try: ingest_lab(st)
    except Exception: traceback.print_exc()
    positions = load(F["positions"], {})
    opn = {m: p for m, p in positions.items() if p.get("status") == "open"}
    nk = night_key(t); ns = load(F["night"], {})
    halted = nk in st["halted_nights"]
    live = live_leaders()
    # drop stale pendings (>3 min without a fill -> may be re-emitted)
    for m, pd in list(st["pending"].items()):
        if t - pd["t"] > R["pending_s"]:
            if pd["type"] == "BUY" and m not in opn:
                append(F["skips"], dict(ts=iso(), mint=m, reason="buy_not_filled_within_3min", action_id=pd["id"]))
            st.setdefault("expired", {})[m] = pd["id"]
            st["pending"].pop(m)
    # fresh holdings read if free SOL dropped > 0.01 since the last holdings read (copy buy in flight)
    try:
        b_now = wallet_cached(st)
        hc = st.get("hold_cache") or {}
        fresh = hc.get("bal") is not None and hc["bal"] - b_now > 0.01
    except Exception: fresh = False
    hold = holdings_cached(st, force=fresh)
    stale_min = holdings_stale_min(st) if hold is not None else 0
    if stale_min:
        nid = f"NOTICE:HOLD_STALE:{int((st.get('hold_cache') or {}).get('t') or 0)}"
        first = nid not in (st.get("notices") or {})
        n_ = dict(ts=iso(t), id=nid, type="NOTICE", kind="holdings_stale", expires=iso(t + 600),
                  note=f"holdings read stale for {stale_min} min (last good read {iso((st.get('hold_cache') or {}).get('t'))}; "
                       f"err {(st.get('hold_err') or {}).get('err')}). Equity uses the last good holdings snapshot; watcher halt suspended "
                       f"until holdings read again. Check the wallet by hand.")
        st.setdefault("notices", {})[nid] = n_
        if first or stale_min % 15 == 0 and (st.get("stale_logged") != stale_min):
            st["stale_logged"] = stale_min; append(F["actions"], n_)
    mints = list(opn) + [q["mint"] for q in st["queue"]] + list(hold or {})
    dex = dex_pairs(mints) if mints else {}
    cands = []
    solpx = solpx_cached(st)
    # 16:15Z: wallet holdings (Banana Gun copies included). value = ui x DexScreener USD / SOL-USD; no price -> positions.json
    # sol_in x 0.85 x fraction held if we know the position, else 0 (conservative). Non-dust = value >= $0.50 or price unknown.
    # price = priceUsd of the HIGHEST-LIQUIDITY pair (dex_pairs); dust = ui x priceUsd < $0.50 (so a $200 stock token
    # with 0.04 units counts). No price: positions.json sol_in x 0.85 x held fraction; else wallet buy tx SOL out x 0.85;
    # else 0 and flagged. Unpriced holdings always count as open.
    # 25 Oct 08:55Z: stablecoins = $1/token; every good price is remembered in st["last_px"] and reused when a later
    # lookup fails; a holding with no price at all is flagged UNPRICED and the halt decision is skipped for that cycle.
    lpx = st.setdefault("last_px", {})
    def hval(m, ui):
        if m in STABLE_MINTS:
            return (ui / solpx if solpx else 0.0), ui, "stablecoin_1usd" + ("" if solpx else "_NO_SOLPX")
        d = dex.get(m) or {}
        if d.get("price") and solpx:
            lpx[m] = dict(px=d["price"], t=t)
            return ui * d["price"] / solpx, ui * d["price"], "dexscreener_priceUsd"
        if (lpx.get(m) or {}).get("px") and solpx:
            return ui * lpx[m]["px"] / solpx, ui * lpx[m]["px"], "last_known_priceUsd"
        p = opn.get(m)
        if p: return float(p.get("sol_in") or 0) * 0.85 * float(p["tokens_left"]) / float(p["tokens_orig"] or 1), None, "positions_sol_in_x0.85"
        c = buy_cost_sol(st, m)
        if c: return c * 0.85, None, "wallet_buy_tx_sol_out_x0.85"
        return 0.0, None, "UNPRICED_valued_0"
    held = {}
    for m, ui in (hold or {}).items():
        v, usd, how = hval(m, ui)
        if usd is not None and usd < DUST_USD: continue
        held[m] = dict(ui=ui, sol=round(v, 6), usd=None if usd is None else round(usd, 2), ticker=STABLE_MINTS.get(m) or (dex.get(m) or {}).get("ticker"),
                       in_positions=m in opn, valued_by=how, **({"ticker_stable": STABLE_MINTS[m]} if m in STABLE_MINTS else {}), **({"flag": "unpriced, no buy cost found; valued 0"} if how.startswith("UNPRICED") else {}))
    n_open = max(len(opn), len(held)) if hold is not None else len(opn)
    st["open_count"] = dict(ts=iso(t), n=n_open, positions_json=len(opn), wallet_holdings=None if hold is None else len(held), holdings=held)
    # night halt (only after the first live entry wrote night-start.json for this night)
    if ns.get("night") == nk and ns.get("sol"):
        bal = wallet_cached(st)
        if hold is not None:        # equity from the wallet itself (no double count with positions.json)
            val = bal + sum(h["sol"] for h in held.values()); src = "wallet_holdings" + (f"_STALE_{stale_min}min" if stale_min else "")
        else:                       # holdings unreadable: positions.json marks
            val = bal + sum(hval(m, float(p["tokens_left"]))[0] for m, p in opn.items()); src = "positions_json"
        halt_at = (1 - R["night_loss_frac"]) * ns["sol"]
        unpriced = [m for m, h in held.items() if h["valued_by"].startswith("UNPRICED") or h["valued_by"].endswith("_NO_SOLPX")]
        if hold is not None and not solpx and held: unpriced = unpriced or ["SOLPX"]
        st["equity"] = dict(ts=iso(t), free_sol=round(bal, 6), equity_sol=round(val, 6), halt_at=round(halt_at, 6), source=src,
                            **({"unpriced": unpriced, "note": "halt decision skipped this cycle (unpriced holding)"} if unpriced else {}))
        below = st.get("halt_below")
        if unpriced:                 # 25 Oct: never halt on a holding valued 0 for lack of a price
            if st.get("unpriced_logged") != sorted(unpriced):
                st["unpriced_logged"] = sorted(unpriced)
                append(F["skips"], dict(ts=iso(), event="halt_check_skipped_unpriced", mints=unpriced, value_sol=round(val, 6)))
            st.pop("halt_below", None); below = None
        elif stale_min: st.pop("halt_below", None); below = None       # never halt on stale holdings
        elif val > halt_at: st.pop("halt_below", None); below = None
        elif not below: st["halt_below"] = below = dict(first_ts=t, first_val=round(val, 6)); 
        confirmed = below is not None and t - below["first_ts"] >= 20
        if val <= halt_at and confirmed and not halted:
            st["halted_nights"].append(nk); halted = True
            reason = (f"equity {val:.6f} SOL <= {halt_at:.6f} (-{R['night_loss_frac']*100:.0f}% of {ns['sol']}); "
                      f"confirmed: below since {iso(below['first_ts'])} ({below['first_val']})")
            st["halt"] = dict(halt=True, ts=iso(t), reason=reason, equity_sol=round(val, 6))
            append(F["skips"], dict(ts=iso(), event="night_halt", value_sol=round(val, 6), start_sol=ns["sol"], source=src))
            notice = dict(ts=iso(t), id=f"NOTICE:HALT:{int(t)}", type="NOTICE", kind="halt", reason=reason,
                          note="SESSION HALT: Pause All Banana Gun copy configs now (all " + str(len((session() or {}).get("bg_copy_leaders") or [])) + " bg_copy_leaders), then sell every token held. No new entries this session.")
            append(F["actions"], notice); print(json.dumps(notice, separators=(",", ":"))); sys.stdout.flush()
    extra = {m: h for m, h in held.items() if m not in opn}       # Banana Gun copies / anything not in positions.json
    if halted and (opn or extra):
        sa = sell_all(opn, dex, f"night_halt_-{R['night_loss_frac']*100:.0f}%")
        sa["positions"] += [dict(mint=m, ticker=h["ticker"], fraction=1.0, tokens=h["ui"], sell_pct_of_holding=100.0, source="wallet_holding",
                                 current_px=(dex.get(m) or {}).get("price"), record_cmd=None,
                                 note="not in positions.json (Banana Gun copy): sell 100% in Banana Gun, no record.py needed")
                            for m, h in extra.items()]
        cands.append(sa)
    if (opn or extra) and must_be_flat(t):
        sa = sell_all(opn, dex, "flat_by_2000Z")
        sa["positions"] += [dict(mint=m, ticker=h["ticker"], fraction=1.0, tokens=h["ui"], sell_pct_of_holding=100.0, source="wallet_holding",
                                 current_px=(dex.get(m) or {}).get("price"), record_cmd=None,
                                 note="not in positions.json (Banana Gun copy): sell 100% in Banana Gun, no record.py needed")
                            for m, h in extra.items()]
        cands.append(sa)
    for m, p in opn.items():
        cands += eval_position(p, st, dex.get(m), t)
    # entries
    keep = []
    if st["queue"]:
        bal = None
        try: bal = wallet_cached(st)
        except Exception: pass
        ctx = dict(now=t, bal=bal, solpx=solpx, live=live, halted=halted, n_open=n_open, n_hold=None if hold is None else len(held))
        for ev in st["queue"]:
            if ev.get("tier") == "trial": dec, info = eval_trial(ev, st, positions, dex.get(ev["mint"]), ctx)
            else: dec, info = eval_entry(ev, st, positions, dex.get(ev["mint"]), ctx)
            if dec == "wait": keep.append(ev); continue
            if dec == "skip":
                st["handled"][ev["pos"]] = "skip:" + info["reason"]
                append(F["skips"], dict(ts=iso(), pos=ev["pos"], **{a: b for a, b in info.items() if a != "checks"}, checks=info["checks"]))
                if verbose: print(f"[skip] {ev['pos']} {info['reason']}", file=sys.stderr)
                continue
            keep.append(ev)
            cands.append(dict(type="BUY", kind="buy", pos_signal=ev["pos"], reasons=info.pop("checks"), **info,
                              record_cmd=f"python3 record.py buy {ev['mint']} <sol_in> <tokens> <entry_px_usd> {info['leader']} {info['leader_px']} {info['leader_ts']}"))
    st["queue"] = keep
    # choose: SELL_ALL > sl/trail/leader_sold > BUY > tp/moon
    prio = {"SELL_ALL": 0, "sl": 1, "trail": 1, "leader_sold": 2, "time_stop": 2, "move_stop": 2, "buy": 3}
    cands.sort(key=lambda a: prio.get(a["kind"], 4))
    for a in cands:
        if a["type"] == "MOVE_STOP":
            r_ = emit(st, a, None)
            if r_: return r_
            continue
        key = "__ALL__" if a["type"] == "SELL_ALL" else a["mint"]
        pd = st["pending"].get(key)
        if pd and pd["kind"] == a["kind"]: continue                 # same action already waiting for a fill
        if pd and a["kind"] not in URGENT and pd["kind"] in URGENT: continue
        if pd and a["kind"] not in URGENT and pd["kind"] not in URGENT and a["type"] != "BUY": continue
        return emit(st, a, pd)
    return None

def sell_all(opn, dex, reason):
    items = [dict(mint=m, ticker=p.get("ticker"), fraction=round(float(p["tokens_left"]) / float(p["tokens_orig"]), 4),
                  sell_pct_of_holding=100.0, current_px=(dex.get(m) or {}).get("price"),
                  record_cmd=f"python3 record.py sell {m} {round(float(p['tokens_left']) / float(p['tokens_orig']), 4)} <sol_out> {reason}")
             for m, p in opn.items()]
    return dict(type="SELL_ALL", kind="SELL_ALL", reason=reason, positions=items)

def emit(st, a, prev_pending):
    t = now()
    a = dict(ts=iso(t), id=f"{a['type']}:{(a.get('mint') or 'ALL')[:8]}:{int(t)}", **a)
    if a["type"] == "MOVE_STOP":
        P = load(F["positions"], {}); p = P.get(a["mint"])
        if not p or p.get("stop_moved"): return None
        p["stop_moved"] = dict(ts=a["ts"], stop_x=a["stop_x"], stop_px=a["new_stop_px"], action_id=a["id"])
        save(F["positions"], P)
        st.setdefault("notices", {})[a["id"]] = dict(a, expires=iso(t + R["pending_s"]))
        append(F["actions"], a)
        return a
    key0 = "__ALL__" if a["type"] == "SELL_ALL" else a.get("mint")
    exp = (st.get("expired") or {}).pop(key0, None)
    if prev_pending or exp: a["reemit_of"] = (prev_pending or {}).get("id") or exp
    if a["type"] == "BUY":
        bal = wallet_cached(st, force=True)
        a["size_sol"] = size_sol(bal, a.get("leader")); a["wallet_sol"] = bal
        if a.get("tier") == "trial":
            a["size_sol"] = min(a["size_sol"], float(R.get("trial_size_sol", 0.02))); a["note"] = f"TRIAL ({a.get('strategy')}): buy {a['size_sol']} SOL only"
        if a.get("tier") == "curve": a["size_sol"] = min(a["size_sol"], float(R["curve_size_sol"])); a["note"] = f"CURVE TIER (pump.fun bonding curve): buy {a['size_sol']} SOL only"
        if a.get("tier") == "tiny": a["size_sol"] = min(a["size_sol"], float(R["tiny_size_sol"])); a["note"] = f"TINY TIER: buy {a['size_sol']} SOL only"
        if a["size_sol"] <= 0: return None
        nk = night_key(t)
        if load(F["night"], {}).get("night") != nk:     # first live entry of the night: baseline for the -20% halt
            save(F["night"], dict(night=nk, sol=bal, ts=iso(t), note="wallet SOL at first live copy entry"))
        if a["size_sol"] <= 0: return None
        st["queue"] = [q for q in st["queue"] if q["pos"] != a["pos_signal"]]
        st["handled"][a["pos_signal"]] = "buy_emitted:" + a["id"]
    key = "__ALL__" if a["type"] == "SELL_ALL" else a["mint"]
    st["pending"][key] = dict(id=a["id"], type=a["type"], kind=a["kind"], t=t)
    if a["type"] == "SELL_ALL":
        for it in a["positions"]: st["pending"][it["mint"]] = dict(id=a["id"], type="SELL", kind="SELL_ALL", t=t)
    st.setdefault("pending_actions", {})[a["id"]] = a
    append(F["actions"], a)
    return a

PENDING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_actions.json")
def write_pending(st):
    """pending_actions.json: every emitted action not yet recorded by record.py and not expired, with expiry time."""
    live_ids = {pd["id"]: pd for pd in st["pending"].values()}
    pa = {i: a for i, a in (st.get("pending_actions") or {}).items() if i in live_ids}
    st["pending_actions"] = pa
    out = [dict(id=i, type=a["type"], kind=a["kind"], ticker=a.get("ticker"), mint=a.get("mint"), leader=a.get("leader"),
                tier=a.get("tier"), size_sol=a.get("size_sol"), reason=a.get("reason"), emitted=a["ts"],
                expires=iso(live_ids[i]["t"] + R["pending_s"]), record_cmd=a.get("record_cmd"),
                positions=a.get("positions"), note=a.get("note")) for i, a in pa.items()]
    for i, n_ in list((st.get("notices") or {}).items()):
        if n_["expires"] < iso(): st["notices"].pop(i); continue
        out.append(dict(id=i, type=n_["type"], kind=n_["kind"], ticker=n_.get("ticker"), mint=n_.get("mint"), emitted=n_["ts"],
                        expires=n_["expires"], new_stop_px=n_.get("new_stop_px"), new_stop_mcap=n_.get("new_stop_mcap"), note=n_.get("note")))
    out.sort(key=lambda x: x["emitted"])
    tmp = PENDING_FILE + ".tmp"
    with open(tmp, "w") as f: json.dump(dict(updated=iso(), halt=st.get("halt"), n=len(out), actions=out), f, indent=1)
    os.replace(tmp, PENDING_FILE)

def run(args):
    # 15:50Z (user: Chunk reacts too slowly): runs CONTINUOUSLY. Each action is printed + appended to actions.jsonl and the
    # watcher keeps going (queues, entries, -15% stop / +20% TP / halt / flat). Single instance via flock on watch.lock.
    import fcntl
    lf = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "watch.lock"), "a+")
    try: fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("watch.py already running (see watch.pid); actions -> actions.jsonl / pending_actions.json", file=sys.stderr); return 4
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "watch.pid"), "w") as f: f.write(str(os.getpid()))
    st = new_state()
    last_err = 0
    while True:
        try:
            with Lock():
                st = {**new_state(), **(load(F["state"], None) or {})}   # record.py may have changed pendings
                a = tick(st, verbose=args.verbose)
                try: write_pending(st)
                except Exception: traceback.print_exc()
                save(F["state"], st)
            if a:
                print(json.dumps(a, separators=(",", ":"))); sys.stdout.flush()
                if args.once or getattr(args, "exit_on_action", False): return 0
                continue                                                  # next tick right away: more actions may be due
        except Exception:
            if now() - last_err > 60: traceback.print_exc(); last_err = now()
        if args.once: return 3
        time.sleep(R["poll_s"])

# ---------------- dry run ----------------
def dry_run(args):
    from collections import defaultdict
    print("DRY RUN: replaying selfcopy paper signals. Nothing is written except to stdout; no trades.\n")
    live = live_leaders(); solpx = sol_usd()
    print(f"LIVE leaders now (roster-status.md): {live}   SOL=${solpx}")
    try: bal = sol_balance(); print(f"wallet {WALLET} balance {bal:.6f} SOL -> size would be {size_sol(bal)} SOL\n")
    except Exception as e: bal = None; print("wallet balance unavailable:", e)
    for fn, qfn in ((SIGNALS, os.path.join(SELFCOPY, "quotes.jsonl")), (DRY_SIGNALS, os.path.join(SELFCOPY, "dryrun-quotes.jsonl"))):
        if not os.path.exists(fn): continue
        evs = [json.loads(l) for l in open(fn) if l.strip()]
        quotes = defaultdict(list)
        if os.path.exists(qfn):
            for l in open(qfn):
                try: q = json.loads(l); quotes[q["pos"]].append(q)
                except Exception: pass
        st = new_state()
        ents = [e for e in evs if e.get("event") == "entry"]
        swaps = [e for e in evs if e.get("event") == "leader_swap"]
        print(f"=== {os.path.basename(fn)}: {len(ents)} entry, {len(swaps)} leader_swap events ===")
        for e in swaps:
            print(f"  {e['ts']} leader_swap {e['leader']:<14} {e['side']:<4} {e['mint'][:8]}.. ${e['usd']:>8,.0f} px {e['fill_px']:.3g}"
                  f" pre_bal={'0 (FIRST BUY)' if not e.get('pre_bal') else 'held'}")
        dex = dex_pairs([e["mint"] for e in ents])
        for ev in evs:
            handle_event(st, ev)
            if ev.get("event") != "entry": continue
            ev["pos"] = ev.get("pos")
            dec, info = eval_entry(ev, st, {}, dex.get(ev["mint"]), dict(now=now(), bal=bal, solpx=solpx, live=live, halted=False), dry=True)
            print(f"\n  ENTRY {ev['ts']} {ev['leader']} {ev['mint']} (pos {ev['pos']})")
            print(f"    leader fill ${info.get('leader_px')}  leader buy ${info.get('leader_usd')} at {info.get('leader_ts')}")
            for c in info["checks"]: print("    " + c)
            if info.get("rugguard"): print("    rugguard detail:", json.dumps({a: info['rugguard'].get(a) for a in ('holders','buyers5','lp_locked','creator_pct','notes','rejects','rugcheck_err')}))
            if info.get("sell_route"): print("    sell route:", json.dumps(info["sell_route"]))
            print(f"    => NOW it would: {'BUY ' + str(info.get('size_sol')) + ' SOL' if dec == 'buy' else 'SKIP (' + ', '.join(info.get('all_fails') or [info.get('reason', '?')]) + ')'}"
                  f"   [live run would also need <=3 min after leader buy: it is {info['signal_age_s']/60:.0f} min old]")
            simulate_exits(ev, evs, quotes.get(ev["pos"], []))
        print()
    return 0

def simulate_exits(ev, evs, qs):
    """hypothetical: if this entry had been copied at the paper entry, what SELL actions would the exit rules emit,
    using the paper bot's mark-to-market sell quotes (x vs entry) and the leader's adds/sells."""
    t0 = parse_iso(ev["ts"]); kk = (ev["leader"], ev["mint"])
    timeline = [(parse_iso(q["ts"]), "q", q) for q in qs]
    timeline += [(parse_iso(e["ts"]), "s", e) for e in evs if e.get("event") == "leader_swap" and (e["leader"], e["mint"]) == kk and parse_iso(e["ts"]) > t0]
    timeline.sort(key=lambda r: r[0])
    left, tp, pk, sold, adds, out = 1.0, 0, None, False, [], []
    print(f"    hypothetical exits if copied ({len(qs)} paper quotes, {sum(1 for r in timeline if r[1]=='s')} later leader swaps):")
    last_basis = None
    xprice = 1.0
    for ts, kind, r in timeline:
        if left <= 1e-9: break
        if kind == "s":
            if r["side"] == "buy": adds.append(ts); out.append(f"      {r['ts']} leader ADD ${r['usd']:,.0f} -> TPs deferred until {iso(ts + R['add_window_s'])}")
            elif not sold:
                s = mirror_keep(left, 1.0); sold = True
                if s > 0: out.append(f"      {r['ts']} SELL {s:.2%} of original: leader_sold_keep10 (leader sold ${r['usd']:,.0f})"); left -= s
            continue
        # paper quote x = value / remaining basis (sell-side quote, includes impact) ~= price ratio vs entry
        xprice = r.get("x") or ((r.get("value_usd") or 0) / r["basis"] if r.get("basis") else None)
        if not xprice: continue
        adding = any(0 <= ts - a < R["add_window_s"] for a in adds)
        dec = exit_plan(xprice, tp_level=tp, peak_x=pk, be_x=R["be_x"], leader_sold=sold, adding=adding)
        pk = max(pk or xprice, xprice)
        if not dec: continue
        k2, f2, reason = dec
        if k2 == "defer":
            msg = f"      {r['ts']} x={xprice:.3f} {reason}"
            if not out or not out[-1].endswith(reason): out.append(msg)
            continue
        s = f2 * left
        out.append(f"      {r['ts']} x={xprice:.3f} SELL {s:.2%} of original ({100*f2:.0f}% of holding): {reason}")
        left -= s
        if k2 in ("tp1", "tp2", "tp12"): tp = tp_level_after(reason, tp)
    for o in out: print(o)
    print(f"      -> still held: {left:.2%} of original, last x={xprice:.3f}, tp_level={tp}, peak={pk}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--once", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--exit-on-action", action="store_true", help="old one-shot mode: exit after the first action")
    a = ap.parse_args()
    sys.exit(dry_run(a) if a.dry_run else run(a))
