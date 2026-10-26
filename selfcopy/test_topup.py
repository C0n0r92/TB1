"""session topup_entry (ypnn-day, 24 Oct day session): top-up buys open one entry per mint per session. No network."""
import os, time, datetime
T0 = time.time()
z = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
os.environ.update(SELFCOPY_SESSION_START=z(T0 - 3600), SELFCOPY_SESSION_END=z(T0 + 4 * 3600), SELFCOPY_SESSION_NO_ENTRY_MIN="30",
                  SELFCOPY_SESSION_MANUAL_LIVE="Y", SELFCOPY_SESSION_TOPUP_ENTRY="Y,X",
                  SELFCOPY_SESSION_MIN_MCAP_USD="1000000", SELFCOPY_SESSION_MIN_AGE_MIN="60", SELFCOPY_SESSION_HALT_LOSS_PCT="20")   # isolate from session.json
import selfcopy as S, live as L
ok = 0
def check(c, msg):
    global ok
    assert c, "FAIL: " + msg; ok += 1; print("  pass:", msg)
sess = L.load_session(S.HERE)
check(sess["topup_entry"] == ["Y"], "topup_entry limited to manual-live wallets (X dropped)")
b = S.Bot.__new__(S.Bot); logs = []
b.state = dict(positions=[], seen={}, skips={}); b.hist = {}; b.pending = []; b.live = None
b.avoid_mints, b.avoid_addr = set(), set(); b.avoid_mtime = os.path.getmtime(os.path.join(S.OI, "avoid.csv"))
b.leaders = {n: dict(wallet=n + "w", confidence="m") for n in ("Y", "N")}
b.log = lambda ev, **k: logs.append((ev, k)); b.save = lambda: None; b.sol_price = lambda: 100.0; b.creator = lambda m: None
INFO = dict(mcap=5e6, liq=3e5, age_s=7200)
b.token_info = lambda m: dict(INFO)
b.quote = lambda a, c, amt, why: (dict(out=amt * 10, impact=0.1, route="r"), None)   # 5$ -> 0.05 SOL -> tokens; price ~ 1e-8*... fixed below
def sw(mint, side="buy", pre=100.0, usd=200.0, bt=None, sig=None):
    bt = bt or time.time()
    return dict(sig=sig or f"s{len(logs)}{mint}{side}", side=side, mint=mint, tokens=10.0, usd=usd, fill_px=None, pre_bal=pre, block_time=bt, decimals=6)
def run(name, s):
    b.pending = []; b.consider_entry(name, s, time.time())
    for pe in b.pending:
        pe["sw"]["fill_px"] = S.CFG["stake_usd"] / (5e7 / 1e6)   # no chase
        b.do_entry(pe)
last = lambda: logs[-1]
def lastskip(): return [k for e, k in logs if e == "skip"][-1]["reason"]
run("N", sw("M1")); check(lastskip() == "not_first_buy", "other wallets: top-up still skipped not_first_buy")
run("Y", sw("M1")); e = last()
check(e[0] == "entry" and e[1].get("topup") and e[1]["leader_usd"] == 200.0 and e[1]["leader_pre_bal"] == 100.0, "ypnn top-up emits an entry event (topup, leader_usd, leader_pre_bal)")
p = b.state["positions"][-1]; check(p["topup"] == sess["key"] and p["opened_ts"] > 0, "position tagged topup + opened_ts")
check("M1" in b.state["topup_entries"][sess["key"]], "mint recorded for this session")
run("Y", sw("M1")); check(lastskip() == "not_first_buy" and [k for e, k in logs if e == "skip"][-1].get("topup_skip") == "topup_already_entered_this_session", "second top-up same mint: no entry")
# exits: sells/adds before our entry ignored, after count
b.mirror_sell("Y", sw("M1", "sell", bt=p["opened_ts"] - 30)); check(not p.get("leader_sold") and last()[0] == "leader_sell_before_entry_ignored", "leader trim BEFORE our entry ignored")
check(p.get("last_add_ts"), "a later top-up after our entry counts as leader adding"); p["last_add_ts"] = None
b.note_add("Y", sw("M1", bt=p["opened_ts"] - 30), time.time()); check(not p.get("last_add_ts"), "leader add BEFORE our entry ignored")
b.note_add("Y", sw("M1", bt=p["opened_ts"] + 5), time.time()); check(p.get("last_add_ts") == p["opened_ts"] + 5, "leader add AFTER our entry counts")
b.mirror_sell("Y", sw("M1", "sell", bt=p["opened_ts"] + 60)); check(p.get("leader_sold") and p["sells"][-1]["reason"].startswith("leader_sold"), "leader sell a minute AFTER entry triggers first-sell exit")
b.state["positions"][-1]["status"] = "closed"
run("Y", sw("M1")); check(lastskip() == "not_first_buy", "after exit: still one entry per coin per session")
# filters still apply
INFO.update(mcap=8e5); run("Y", sw("M2")); check(lastskip() == "topup_v2_fail" and "M2" not in b.state["topup_entries"][sess["key"]], "mcap < $1M -> skip, not recorded")
INFO.update(mcap=5e6, liq=5e4); run("Y", sw("M2")); check(lastskip() == "topup_v2_fail", "liq < $100k -> skip")
INFO.update(liq=3e5, age_s=1800); run("Y", sw("M2")); check(lastskip() == "topup_v2_fail", "age < 60 min -> skip")
INFO.update(age_s=7200); run("Y", sw("M2", usd=40)); check(lastskip() == "leader_buy_lt_50", "leader top-up < $50 -> skip")
run("Y", sw("M2", bt=time.time() - 300)); check(lastskip() == "topup_v2_fail", "stale (>2 min old) top-up -> skip")
b.state["positions"].append(dict(mint="M3", status="open", leader="N")); run("Y", sw("M3")); check(lastskip() == "not_first_buy", "never while we hold the mint (any leader)")
run("Y", sw("M2")); check(last()[0] == "entry", "different mint passes -> entry")
# non-topup position unaffected: early sells still mirror
q = dict(id="q", leader="N", mint="M9", status="open", tokens_raw=1000, tokens_left=1000, cost_usd=5, fees_usd=0, proceeds_usd=0, cf_proceeds_usd=0, sells=[], entry_sol_px=100)
b.state["positions"].append(q); b.mirror_sell("N", sw("M9", "sell", bt=1)); check(q.get("leader_sold"), "non-topup positions: mirror unchanged")
# cutoff: entry blocked inside last 30 min
os.environ["SELFCOPY_SESSION_END"] = z(time.time() + 600); run("Y", sw("M5")); check(lastskip() == "not_first_buy" and [k for e, k in logs if e == "skip"][-1].get("topup_skip") == "topup_session_blocked", "after the entry cutoff -> no top-up entry")
os.environ["SELFCOPY_SESSION_END"] = z(T0 + 4 * 3600)
# --- 09:56Z rules: all_live top-ups + session thresholds ---
os.environ.update(SELFCOPY_SESSION_TOPUP_ENTRY="all_live", SELFCOPY_SESSION_MIN_MCAP_USD="300000", SELFCOPY_SESSION_MIN_AGE_MIN="15")
b.state["rotation"] = dict(live=["N"])
run("N", sw("M6")); check(last()[0] == "entry" and last()[1].get("topup"), "all_live: a LIVE-rotation leader's top-up emits an entry")
b.leaders["Z"] = dict(wallet="Zw", confidence="m"); run("Z", sw("M7")); check(lastskip() == "not_first_buy", "all_live: non-live leader top-up still skipped")
INFO.update(mcap=4e5, age_s=20 * 60); run("N", sw("M8")); check(last()[0] == "entry", "session: mcap $400k + age 20 min pass")
INFO.update(mcap=2.5e5); run("N", sw("M10")); check(lastskip() == "topup_v2_fail", "session: mcap $250k < $300k -> skip")
INFO.update(mcap=4e5, age_s=10 * 60); run("N", sw("M10")); check(lastskip() == "topup_v2_fail", "session: age 10 min < 15 -> skip")
INFO.update(age_s=20 * 60, liq=9e4); run("N", sw("M10")); check(lastskip() == "topup_v2_fail", "session: liq $90k < $100k still skip")
os.environ["SELFCOPY_SESSION_MIN_MCAP_USD"] = "1000"; os.environ["SELFCOPY_SESSION_MIN_AGE_MIN"] = "1"
s2 = L.load_session(S.HERE); check(s2["min_mcap_usd"] == 300000 and s2["min_age_s"] == 900, "session cannot loosen below $300k / 15 min floors")
os.environ["SELFCOPY_SESSION_HALT_LOSS_PCT"] = "50"; check(L.load_session(S.HERE)["halt_loss_frac"] == 0.2, "halt pct can only tighten (50 -> 20)")
os.environ["SELFCOPY_SESSION_HALT_LOSS_PCT"] = "10"; s3 = L.load_session(S.HERE)
check(L.loss_limit_hit(0.90, 1.0, L.session_halt_frac(time.time(), s3)) and not L.loss_limit_hit(0.91, 1.0, L.session_halt_frac(time.time(), s3)), "session halt at -10%")
check(not L.loss_limit_hit(0.85, 1.0) and L.loss_limit_hit(0.80, 1.0), "outside a session: -20% unchanged")
check(L.HARD["sl_frac"] == 0.85 and L.exit_plan(0.849, tp_level=0, peak_x=1.0, be_x=1.01, leader_sold=False, adding=False)[0] == "sl", "per-position hard stop -15%")
check(L.v2_filters(mcap=4e5, liq=2e5, age_s=1200, leader_age_s=0, chase=0) == ["mcap_lt_1m", "age_lt_60m"], "LIVE entry_gate v2 stays HARD ($1M / 60 min)")
for k in ("SELFCOPY_SESSION_MIN_MCAP_USD", "SELFCOPY_SESSION_MIN_AGE_MIN", "SELFCOPY_SESSION_HALT_LOSS_PCT", "SELFCOPY_SESSION_TOPUP_ENTRY"): os.environ.pop(k, None)
print(f"TOPUP TESTS: {ok} passed")
