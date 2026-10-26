"""paper exits use the same v3 rules as LIVE (selfcopy.Bot.apply_exit / mirror_sell / note_add / last_trade). No network."""
import time, selfcopy as S
ok = 0
def check(c, msg):
    global ok
    assert c, "FAIL: " + msg; ok += 1; print("  pass:", msg)
b = S.Bot.__new__(S.Bot); b.state = dict(positions=[]); b.live = None; b.val = {}; logs = []
b.log = lambda ev, **k: logs.append((ev, k)); b.save = lambda: None; b.sol_price = lambda: 100.0
b.quote = lambda mint, out, amt, why: (dict(out=b.val[mint] * amt / 1000 / 100 * 1e9, impact=0.1, route="x"), None)
def mk(i, mint):
    p = dict(id=f"q{i}", leader="L", mint=mint, status="open", tokens_raw=1000, tokens_left=1000, cost_usd=10.0, fees_usd=0.05, proceeds_usd=0.0,
             cf_proceeds_usd=0.0, sells=[], tp_done=False, entry_sol_px=100.0, noroute_since=None, next_q=0)
    b.state["positions"].append(p); return p
def mark(p, x_full):   # x_full = value of 1000 tokens / cost
    b.val[p["mint"]] = x_full * 10.0; q, _ = b.quote(p["mint"], 0, p["tokens_left"], "");  val = q["out"] / 1e9 * 100
    b.apply_exit(p, val, p["cost_usd"] * p["tokens_left"] / p["tokens_raw"], q, 100.0)
R = lambda p: p["sells"][-1]["reason"] if p["sells"] else None
p = mk(1, "A"); mark(p, 1.41); check(R(p) == "tp_+40%_25%" and p["tokens_left"] == 750 and p["tp_level"] == 1, "paper TP1 25% at +40%")
mark(p, 2.05); check(R(p) == "tp_+100%_25%" and p["tokens_left"] == 500, "paper TP2 another 25% of original at +100%")
mark(p, 1.50); check(R(p).startswith("sl_trail_-25%") and p["status"] == "closed", "paper trail 25% below peak after TP")
p = mk(2, "B"); b.note_add("L", dict(mint="B", block_time=time.time()), time.time()); mark(p, 1.6)
check(not p["sells"] and any(e == "tp_deferred" for e, _ in logs), "paper TP deferred while leader adds")
mark(p, 0.84); check(R(p) == "sl_-15%", "paper hard SL not skipped while adding")
p = mk(3, "C"); p["last_add_ts"] = time.time() - 601; mark(p, 1.6); check(R(p) == "tp_+40%_25%", "paper deferred TP fires after 10 min without add")
mark(p, 1.0); check(R(p) == "sl_breakeven" and p["status"] == "closed", "paper breakeven stop after TP")
p = mk(4, "D"); b.val["D"] = 10.0; b.mirror_sell("L", dict(mint="D", tokens=10, pre_bal=100, sig="s"))
check(R(p) == "leader_sold_10%_keep10" and p["tokens_left"] == 100, "paper: leader's first sell (10%) -> keep 10% of original")
b.mirror_sell("L", dict(mint="D", tokens=90, pre_bal=90, sig="t")); check(len(p["sells"]) == 1, "paper: later leader sells ignored")
mark(p, 4.0); check(len(p["sells"]) == 1, "paper leftover: no trail/TP at +300%")
mark(p, 6.0); check(R(p) == "tp_leftover_+500%" and p["status"] == "closed", "paper leftover TP all at +500%")
p = mk(5, "E"); b.val["E"] = 10.0; p["tokens_left"] = 50; p["tp_level"] = 2; b.mirror_sell("L", dict(mint="E", tokens=1, pre_bal=1, sig="u"))
check(not p["sells"] and p["leader_sold"] and p["keep_raw"] == 50, "paper: <10% left -> keep it all")
mark(p, 1.0); check(R(p) == "sl_breakeven", "paper leftover stop is breakeven after a TP")
b.state["last_trade"] = {}; b.state["last_trade_seeded"] = True
check(isinstance(b.last_trade(), dict), "last_trade() available")
print(f"PAPER EXIT TESTS: {ok} passed")
