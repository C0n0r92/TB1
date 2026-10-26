#!/usr/bin/env python3
"""Unit tests for LIVE hard caps (fake prices, no network) + one real build/sign/simulate (no send)."""
import sys, os, json, time, datetime, types, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live as L
from zoneinfo import ZoneInfo
DUB = ZoneInfo("Europe/Dublin")
ok = 0
def check(c, msg):
    global ok
    assert c, "FAIL: " + msg; ok += 1; print("  pass:", msg)

def dt(h, m): return datetime.datetime(2026, 10, 24, h, m, tzinfo=DUB)
tmp = tempfile.mkdtemp()
# --- config cannot loosen caps
json.dump(dict(size_usd=50, priority_fee_sol=0.01, max_open=10, max_impact=0.5, max_chase=0.9), open(os.path.join(tmp, "live-config.json"), "w"))
c = L.load_cfg(tmp)
check(c["size_usd"] == 10 and c["priority_fee_sol"] == 0.0001 and c["max_open"] == 3 and c["max_impact"] == 0.03 and c["max_chase"] == 0.08, f"config loosening clamped {c}")
json.dump(dict(size_usd=3, priority_fee_sol=0.00005), open(os.path.join(tmp, "live-config.json"), "w"))
c2 = L.load_cfg(tmp); check(c2["size_usd"] == 3 and c2["priority_fee_sol"] == 0.00005, "config may tighten")
try: L.HARD["max_usd"] = 100; check(False, "HARD mutable")
except TypeError: check(True, "HARD caps are read-only")
cfg = L.load_cfg("/nonexistent")
# --- sizing
check(L.live_size_usd(cfg, 1000) == 10, "size capped at $10 on big wallet")
check(abs(L.live_size_usd(cfg, 85) - 10) < 1e-9 and abs(L.live_size_usd(cfg, 50) - 7.5) < 1e-9, "$85 wallet -> $10; $50 wallet -> $7.50")
check(abs(L.live_size_usd(cfg, 20) - 3.0) < 1e-9, "size = 15% of $20 wallet = $3")
check(L.funded_check(0.0, 6, 100)[1] == "unfunded", "0 SOL -> unfunded")
check(L.funded_check(0.12, 10, 100) == (False, "unfunded"), "0.12 SOL < 0.10+0.02+overhead -> unfunded")
check(L.funded_check(0.13, 10, 100) == (True, None), "0.13 SOL funds $10 buy and keeps 0.02 reserve")
check(L.funded_check(1.0, 0.5, 100)[1] == "unfunded", "size < $1 -> unfunded")
# --- entry gate
base = dict(leader="_benjitrades", first_buy=True, leader_usd=80, mcap=2_500_000, avoid=False, chase=0.05, impact=0.01,
            n_open=0, same_mint_open=False, loc=dt(2, 0), halted=False, forced=False, liq=150_000, age_s=4000, leader_age_s=30)
check(L.entry_gate(cfg, **base) is None, "qualifying benji buy passes")
for k, v, r in [("leader", "bystevenr", "leader_not_live"), ("forced", True, "forced_override_never_live"), ("halted", True, "night_loss_limit_halt"),
                ("first_buy", False, "not_first_buy"), ("leader_usd", 49.9, "leader_buy_lt_50"), ("mcap", 999_999, "mcap_lt_1m"), ("mcap", None, "mcap_lt_1m"), ("liq", 99_999, "liq_lt_100k"), ("liq", None, "liq_lt_100k"),
                ("age_s", 3599, "age_lt_60m"), ("age_s", None, "age_lt_60m"), ("leader_age_s", 121, "leader_buy_gt_2m_old"), ("leader_age_s", None, "leader_buy_gt_2m_old"),
                ("avoid", True, "avoid"), ("loc", dt(7, 45), "no_entry_0745_0800"), ("loc", dt(7, 59), "no_entry_0745_0800"),
                ("n_open", 3, "max_open_3"), ("same_mint_open", True, "already_open_same_mint"), ("chase", 0.081, "chase_gt_8pct"),
                ("chase", None, "chase_gt_8pct"), ("impact", 0.031, "impact_gt_3pct")]:
    check(L.entry_gate(cfg, **{**base, k: v}) == r, f"{k}={v} -> {r}")
check(L.entry_gate(cfg, **{**base, "loc": dt(8, 0)}) is None and L.entry_gate(cfg, **{**base, "loc": dt(7, 44)}) is None, "07:44 and 08:00 allowed")
# --- exits v3 (pure exit_plan)
E = lambda x, lvl=0, pk=None, be=1.002, ls=False, add=False: L.exit_plan(x, tp_level=lvl, peak_x=pk, be_x=be, leader_sold=ls, adding=add)
check(E(1.39) is None and E(1.40)[:2] == ("tp1", 0.25), "TP1: 25% at +40%")
check(E(1.99, 1, 1.99) is None and E(2.0, 1, 2.0)[:2] == ("tp2", 1 / 3), "TP2: another 25% of original (1/3 of the 75% left) at +100%")
check(E(2.3)[:2] == ("tp12", 0.5), "jump straight past +100%: both TPs at once (50%)")
check(E(1.6, add=True)[0] == "defer" and E(2.5, 1, 2.5, add=True)[0] == "defer", "leader adding (<10 min): TP1 and TP2 deferred")
check(E(1.6, add=False)[0] == "tp1", "deferred TP fires on the next check once 10 min pass without an add (still above level)")
check(E(1.3, add=False) is None, "...but not if price fell back below the level")
check(E(0.85)[:3] == ("sl", 1.0, "sl_-15%") and E(0.86) is None, "SL −15% before first TP")
check(E(0.85, add=True)[0] == "sl", "hard SL never skipped while leader adds")
check(E(1.0, 1, 1.5)[2] == "sl_breakeven" and E(1.002, 1, 1.3)[2] == "sl_breakeven" and E(1.01, 1, 1.3) is None, "after TP1 the stop is breakeven (entry + costs)")
check(E(1.0, 1, 1.5, add=True)[2] == "sl_breakeven", "breakeven stop never skipped while leader adds")
check(E(1.3, 0, 2.0) is None, "trail not active before TP1 (−35% from a 2.0x peak, no sell)")
check(E(1.49, 1, 2.0)[0] == "trail" and E(1.51, 1, 2.0) is None, "after TP1: trail 25% below peak since entry")
check(E(1.49, 1, 2.0, add=True) is None and E(1.29, 1, 2.0, add=True)[0] == "trail", "trail widens to 35% while leader adds")
check(E(3.0, 2, 4.0)[0] == "trail" and E(3.1, 2, 4.0) is None, "trail keeps running on the 50% after TP2")
check(L.mirror_keep(1000, 1000) == (0.9, 100), "leader's first sell: sell all but 10% of ORIGINAL")
check(L.mirror_keep(500, 1000) == (0.8, 100) and L.mirror_keep(60, 1000) == (0.0, 60), "after TPs keep 10% of original; if <10% left keep it all")
check(E(5.99, 0, 5.99, ls=True) is None and E(6.0, 0, 6.0, ls=True)[:2] == ("moon", 1.0), "leftover: sells all at +500%")
check(E(0.85, 0, 3.0, ls=True)[2] == "sl_-15%" and E(1.0, 1, 3.0, ls=True)[2] == "sl_breakeven", "leftover stop: −15% if no TP fired, breakeven if one did")
check(E(1.2, 1, 5.0, ls=True) is None and E(1.2, 1, 5.0, ls=True, add=True) is None, "no trailing stop on the leftover after the leader sold")
check(E(1.5, 0, 1.5, ls=True) is None, "no TP1/TP2 on the leftover")
check(L.loss_limit_hit(0.08, 0.1) and not L.loss_limit_hit(0.0801, 0.1), "night loss limit at -20%")
check(L.night_key(dt(7, 59)) == "2026-10-23" and L.night_key(dt(8, 0)) == "2026-10-24", "night rolls at 08:00 Dublin")

# --- stateful flow with fake bot + fake prices (no network, no signing)
class FakeBot:
    def __init__(s): s.state = {}; s.px = 100.0; s.val = {}
    def save(s): pass
    def sol_price(s): return s.px
    def quote(s, inp, out, amt, purpose): return dict(out=int(s.val[inp] * 1e9 / s.px), impact=0.01, route="fake"), None
fb = FakeBot()
lv = L.Live.__new__(L.Live)
lv.bot = fb; lv.here = tmp; lv.enabled_flag = True; lv.fn = os.path.join(tmp, "lt.jsonl"); lv.night_fn = os.path.join(tmp, "night.json")
lv.cfg = cfg; lv.pub = "BOT"; lv.s = dict(positions=[], halted_nights=[], closed_days=[]); fb.state["live"] = lv.s
lv.last_unfunded_log = lv.last_val_t = lv.last_close_try = 0; lv.sol_bal = 0.5
sold = []
def fake_sell(pos, frac, reason):
    sold.append((pos["id"], frac, reason)); pos["tokens_left"] = int(pos["tokens_left"] * (1 - frac))
    if frac >= 0.999 or pos["tokens_left"] == 0: pos["status"] = "closed"
    return True
lv.sell = fake_sell
lv.get_sol = lambda: lv.sol_bal
lv.usdc_bal = 0.0; lv.get_usdc = lambda: lv.usdc_bal; lv.last_gas_log = 0
def mk(i, mint): return dict(id=f"p{i}", leader="_benjitrades", mint=mint, status="open", tokens_raw=1000, tokens_left=1000, usd_in=6.0,
                             tp_done=False, next_q=0, last_value_usd=6.0, sol_out=0, usd_out=0, sol_in=0.06, sells=[])
p = mk(1, "M1"); lv.s["positions"].append(p)
fb.val["M1"] = 8.5; lv.tick(dt(2, 0), 100)                                 # 1.417x
check(sold[-1] == ("p1", 0.25, "tp_+40%_25%") and p["tp_level"] == 1, "live tick: TP1 sells 25% at +40%")
p["next_q"] = 0; fb.val["M1"] = 9.3; lv.tick(dt(2, 1), 100)               # 750 tokens, basis 4.5 -> 2.07x
check(sold[-1][:2] == ("p1", 1 / 3) and p["tp_level"] == 2 and p["tokens_left"] == 500, "live tick: TP2 another 25% of original at +100%")
lv.note_add("_benjitrades", "M1", time.time())
p["next_q"] = 0; fb.val["M1"] = 4.2; lv.tick(dt(2, 2), 100)               # basis 3 -> 1.40x; peak 2.07 -> -32%
check(len(sold) == 2, "leader adding: -32% from peak holds (trail widened to 35%)")
p["last_add_ts"] = time.time() - 601
p["next_q"] = 0; lv.tick(dt(2, 3), 100)
check(sold[-1][0] == "p1" and sold[-1][2].startswith("sl_trail_-25%"), f"add >10 min old: trail back to 25% -> sells rest ({sold[-1][2]})")
pS = mk(9, "M9"); lv.s["positions"].append(pS); fb.val["M9"] = 5.05; lv.tick(dt(2, 4), 100)
check(sold[-1] == ("p9", 1.0, "sl_-15%"), "live tick: SL -15% before TP")
pD = mk(5, "M5"); lv.s["positions"].append(pD); lv.note_add("_benjitrades", "M5", time.time()); n0 = len(sold)
fb.val["M5"] = 9.0; lv.tick(dt(2, 5), 100)
check(len(sold) == n0 and pD["deferred"] and '"tp_deferred"' in open(lv.fn).read(), "live tick: TP deferred while leader adds (logged once)")
pD["last_add_ts"] = time.time() - 601; pD["next_q"] = 0; lv.tick(dt(2, 6), 100)
check(sold[-1] == ("p5", 0.25, "tp_+40%_25%"), "deferred TP fires once 10 min pass with no new add")
pD["next_q"] = 0; fb.val["M5"] = 0.75 * 6.0; lv.tick(dt(2, 7), 100)   # 4500 tokens? value of 750 left = 4.5 vs basis 4.5 -> 1.0x
check(sold[-1] == ("p5", 1.0, "sl_breakeven"), "after TP1 a drop to entry sells at breakeven")
pM = mk(6, "M6"); lv.s["positions"].append(pM); sold.clear()
lv.mirror("_benjitrades", dict(mint="M6", sig="x"), 0.3, 0.3)
check(sold[-1] == ("p6", 0.9, "leader_sold_30%_keep10") and pM["leader_sold"] and pM["keep_raw"] == 100, "leader's first sell (even 30%) -> sell all but 10% of original")
lv.mirror("_benjitrades", dict(mint="M6", sig="y"), 1.0, 1.0)
check(len(sold) == 1, "later leader sells ignored for the leftover")
pM["next_q"] = 0; fb.val["M6"] = 0.6 * 4.0; lv.tick(dt(2, 8), 100)    # 100 tokens, basis 0.6 -> 4.0x
check(len(sold) == 1, "leftover at +300%: holds (no trail, no TP)")
pM["next_q"] = 0; fb.val["M6"] = 0.6 * 6.1; lv.tick(dt(2, 9), 100)
check(sold[-1] == ("p6", 1.0, "tp_leftover_+500%"), "leftover sells all at +500%")
pM2 = mk(7, "M7"); lv.s["positions"].append(pM2); lv.mirror("_benjitrades", dict(mint="M7", sig="z"), 1.0, 1.0)
pM2["next_q"] = 0; fb.val["M7"] = 0.6 * 0.84; lv.tick(dt(2, 10), 100)
check(sold[-1] == ("p7", 1.0, "sl_-15%"), "leftover keeps its −15% stop when no TP fired")
p2 = mk(2, "M2"); lv.s["positions"].append(p2); fb.val["M2"] = 6.0
p2.update(leader_sold=True, keep_raw=100, tokens_left=100, tp_level=1)      # a 10% leftover
lv.tick(dt(8, 0), 100)
check(sold[-1] == ("p2", 1.0, "close_0800_dublin"), "08:00 Dublin close-out sells everything, the 10% leftover too")
# night loss limit
lv.s["positions"] = []; lv.last_val_t = 0; sold.clear()
json.dump(dict(night="2026-10-23", start_sol=0.5), open(lv.night_fn, "w"))
p3 = mk(3, "M3"); lv.s["positions"].append(p3); fb.val["M3"] = 6.0; p3["next_q"] = time.time() + 99
p3.update(leader_sold=True, keep_raw=100)                                   # leftover (value kept so the wallet maths holds)
lv.sol_bal = 0.33   # 0.33 + 0.06 tokens = 0.39 < 0.4
lv.tick(dt(3, 0), 100)
check(("p3", 1.0, "loss_limit") in sold and "2026-10-23" in lv.s["halted_nights"], "night loss -20% -> sell all (leftover too) + halt")
check(lv.halted(dt(4, 0)) and not lv.halted(dt(9, 0)), "halt lasts until 08:00")
# mirror
p4 = mk(4, "M4"); lv.s["positions"].append(p4); sold.clear()
lv.mirror("_benjitrades", dict(mint="M4", sig="x"), 0.4, 0.4); check(sold[-1] == ("p4", 0.9, "leader_sold_40%_keep10"), "mirror: first leader sell keeps 10%")
lv.mirror("bystevenr", dict(mint="M4", sig="x"), 1.0, 1.0); check(len(sold) == 1, "other leaders never touch live positions")
check(all(r.startswith(L.URGENT) for r in ("sl_-15%", "sl_breakeven", "sl_trail_-25%_from_peak_2.00x", "close_0800_dublin", "loss_limit", "stop_flatten")) and not "tp_+100%_half".startswith(L.URGENT),
      "urgent exits escalate slippage 5%->10%->15%")
check(L.HARD["urgent_exit_slip_steps"] == (500, 1000, 1500) and L.HARD["sell_tries"] == 3, "3 sell tries, max 15%")
# --- USDC handling
check(L.usdc_convert_amount(85, 0.03) == 84.0, "$85 USDC + 0.03 SOL -> swap $84, keep $1")
check(L.usdc_convert_amount(4.99, 0.03) == 0 and L.usdc_convert_amount(85, 0.0099) == 0, "no swap under $5 USDC or under 0.01 SOL")
check(L.gas_ok(0.01) and not L.gas_ok(0.0099), "gas threshold 0.01 SOL")
lv.s["positions"] = []; lv.sol_bal = 0.03; lv.usdc_bal = 85.0
v, s_ = lv.wallet_value_sol(100); check(abs(v - (0.03 + 0.85)) < 1e-9, f"wallet value counts USDC at face: {v} SOL")
calls = []
def fake_swap(inp, out, amt, slip, dyn, purpose):
    calls.append((inp, out, amt, slip, dyn, purpose)); lv.usdc_bal = 1.0; lv.sol_bal = 0.03 + 0.8395
    return dict(sig="S", ok=True, err=None, slip_bps=40, fill=dict(lamports=int(0.8395e9), token_raw=-84_000_000, fee=5000)), None
lv.swap = fake_swap; lv.get_sol = lambda: lv.sol_bal; lv.get_usdc = lambda: lv.usdc_bal
check(lv.maybe_convert_usdc(100) is True and calls[-1][:4] == (L.USDC, L.WSOL, 84_000_000, 100), "USDC->SOL swap $84 via Jupiter, 1% slippage cap")
check(lv.maybe_convert_usdc(100) is None and len(calls) == 1, "only once (USDC left $1)")
v2, _ = lv.wallet_value_sol(100); check(abs(v2 - (0.8695 + 0.01)) < 1e-6, "value preserved after conversion")
lv.sol_bal = 0.005; lv.usdc_bal = 85.0; lv.s["usdc_last_try"] = 0
check(lv.maybe_convert_usdc(100) is None and len(calls) == 1, "no conversion when SOL < 0.01")
logs0 = open(lv.fn).read().count("needs gas SOL")
lv.on_paper_entry("_benjitrades", dict(mint="M9", usd=80, fill_px=1.0, decimals=6, sig="z"), dict(mcap=2e6, liq=2e5, age_s=7200, leader_age_s=20), avoid=False, first_buy=True,
                  forced=False, loc=dt(2, 0), solpx=100)
check(open(lv.fn).read().count("needs gas SOL") == logs0 + 1 and len(calls) == 1, "SOL < 0.01 -> logs 'needs gas SOL', stays idle")
# v2 pre-check: a young/illiquid token never reaches the wallet or Jupiter
lv.get_sol = lambda: (_ for _ in ()).throw(AssertionError("wallet touched"))
lv.on_paper_entry("_benjitrades", dict(mint="MY", usd=80, fill_px=1.0, decimals=6, sig="y"), dict(mcap=5e6, liq=5e5, age_s=600, leader_age_s=20),
                  avoid=False, first_buy=True, forced=False, loc=dt(2, 0), solpx=100)
check('"reason": "age_lt_60m"' in open(lv.fn).read().splitlines()[-1], "token 10 min old -> skip age_lt_60m before any wallet call")
lv.on_paper_entry("_benjitrades", dict(mint="MO", usd=80, fill_px=1.0, decimals=6, sig="o"), dict(mcap=5e6, liq=5e5, age_s=7200, leader_age_s=300),
                  avoid=False, first_buy=True, forced=False, loc=dt(2, 0), solpx=100)
check('"reason": "leader_buy_gt_2m_old"' in open(lv.fn).read().splitlines()[-1], "leader buy seen 5 min late -> skip")
check(L.v2_filters(mcap=2e6, liq=2e5, age_s=4000, leader_age_s=10, chase=0.02) == [], "paper v2 tag: pass")
check(L.v2_filters(mcap=5e5, liq=5e4, age_s=100, leader_age_s=200, chase=0.1) == ["mcap_lt_1m", "liq_lt_100k", "age_lt_60m", "leader_buy_gt_2m_old", "chase_gt_8pct"], "paper v2 tag lists every failing filter")
# --- v5 daytime session override (session.json in lv.here; additive only)
U = lambda h, m: datetime.datetime(2026, 10, 24, h, m, tzinfo=datetime.timezone.utc).astimezone(DUB)
for e in ("SELFCOPY_SESSION_START", "SELFCOPY_SESSION_END", "SELFCOPY_SESSION_NO_ENTRY_MIN"): os.environ.pop(e, None)
check(L.load_session(tmp) is None and L.period_key(dt(9, 0), None) == "2026-10-24", "no session.json -> normal nightly rules")
sfn = os.path.join(tmp, "session.json")
json.dump(dict(key="day-T", start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", no_entry_min=30), open(sfn, "w"))
S_ = L.load_session(tmp)
check(S_["key"] == "day-T" and S_["no_entry_s"] == 1800, "session loads from session.json")
check(L.session_entry_block(U(8, 40), S_) is None and L.session_entry_block(U(19, 29), S_) is None, "session: entries 08:40 and 19:29 UTC allowed")
check(L.session_entry_block(U(19, 30), S_) == "no_entry_before_session_end" and L.session_entry_block(U(20, 30), S_) == "session_ended", "session: no entries from 19:30 UTC; none after end")
check(L.entry_gate(cfg, **{**base, "loc": U(19, 31), "session": S_}) == "no_entry_before_session_end" and L.entry_gate(cfg, **{**base, "loc": U(12, 0), "session": S_}) is None, "entry_gate honours the session cutoff")
check(L.entry_gate(cfg, **{**base, "loc": dt(7, 50), "session": S_}) == "no_entry_0745_0800", "session never removes the 07:45-08:00 rule")
check(not L.session_must_close(U(19, 59), S_) and L.session_must_close(U(20, 0), S_), "session: flat at 20:00 UTC")
check(L.period_key(U(12, 0), S_) == "day-T" and L.period_key(U(8, 0), S_) == "2026-10-24", "loss-limit period = session key during the session")
os.environ["SELFCOPY_SESSION_END"] = "2026-10-24T18:00:00Z"; check(L.load_session(tmp)["end_ts"] == L._parse_utc("2026-10-24T18:00:00Z"), "env SELFCOPY_SESSION_END overrides"); os.environ.pop("SELFCOPY_SESSION_END")
json.dump(dict(start="2026-10-24T08:00:00Z", end="2026-10-25T20:00:00Z"), open(sfn, "w")); check(L.load_session(tmp) is None, "session > 24h rejected")
json.dump(dict(key="day-T", start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", no_entry_min=30, resume="2026-10-24T22:00:00Z"), open(sfn, "w"))
S2 = L.load_session(tmp); check(L.session_entry_block(U(21, 0), S2) == "session_ended" and L.session_entry_block(U(22, 1), S2) is None, "resume time re-opens normal rules")
json.dump(dict(key="day-T", start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", no_entry_min=30), open(sfn, "w"))
# live tick: close-out at session end (leftover too), and -20% halt from the session-start balance
lv.s["positions"] = []; lv.s["halted_nights"] = []; sold.clear(); lv.last_close_try = 0; lv.get_sol = lambda: lv.sol_bal
pS = mk(20, "MS"); pS.update(leader_sold=True, keep_raw=100, tokens_left=100, tp_level=1); lv.s["positions"].append(pS); fb.val["MS"] = 0.6; pS["next_q"] = time.time() + 999
lv.tick(U(19, 59), 100); check(not any(r == "close_session_end" for _, _, r in sold), "no session close-out before 20:00 UTC")
lv.last_close_try = 0; lv.tick(U(20, 0), 100); check(sold and sold[-1] == ("p20", 1.0, "close_session_end"), "20:00 UTC session close-out sells everything, leftover too")
check("close_session_end".startswith(L.URGENT), "session close-out is an urgent exit")
lv.s["positions"] = []; sold.clear(); lv.last_val_t = 0
json.dump(dict(night="2026-10-24", start_sol=5.0), open(lv.night_fn, "w")); lv.sol_bal = 0.5; lv.usdc_bal = 0.0
lv.tick(U(9, 0), 100); d = json.load(open(lv.night_fn))
check(d["night"] == "day-T" and abs(d["start_sol"] - 0.5) < 1e-9, "session start balance recorded fresh (old night baseline ignored)")
lv.last_val_t = 0; lv.sol_bal = 0.41; lv.tick(U(10, 0), 100); check(not lv.halted(U(10, 1)), "-18% in session: no halt")
lv.last_val_t = 0; lv.sol_bal = 0.39; lv.tick(U(11, 0), 100)
check("day-T" in lv.s["halted_nights"] and lv.halted(U(11, 1)), "-22% vs session start -> session halted")
os.remove(sfn); check(not lv.halted(datetime.datetime(2026, 10, 25, 9, 0, tzinfo=DUB)), "session halt does not leak into a later night")
shutil.rmtree(tmp)
# topup_entry (24 Oct): only manual-live wallets, live gate refuses non-first buys
_d = tempfile.mkdtemp(); json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", manual_live=["ypnn-day"], topup_entry=["ypnn-day", "other"]), open(os.path.join(_d, "session.json"), "w"))
_s = L.load_session(_d); check(_s["topup_entry"] == ["ypnn-day"], "session topup_entry parsed, limited to manual_live")
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z"), open(os.path.join(_d, "session.json"), "w"))
check(L.load_session(_d)["topup_entry"] == [], "no topup_entry by default"); shutil.rmtree(_d)
print(f"UNIT TESTS: {ok} passed")
