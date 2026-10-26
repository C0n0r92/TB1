"""Unit tests for the rotating roster (no network, no wallet)."""
import json, os, tempfile, shutil, time
import roster as R, live as L
ok = 0
def check(c, msg):
    global ok
    assert c, "FAIL: " + msg; ok += 1; print("  pass:", msg)
T0 = 1_800_000_000
def tr(nets, t=T0 - 3600): return [dict(t=t + i, net=x, cost=5.0, open=False) for i, x in enumerate(nets)]
def sc(nets): return R.score(tr(nets))

# --- scoring
s = sc([1, -0.5, 2, -1])
check(s["n"] == 4 and abs(s["ev_usd"] - 0.375) < 1e-9 and abs(s["ev_pct"] - 0.075) < 1e-9, "EV per trade = mean net after costs ($ and % of stake)")
check(s["win_rate"] == 0.5 and abs(s["max_dd_usd"] - 1.0) < 1e-9, "win rate 50%, max drawdown $1.00 on the cumulative curve")
check(sc([-1, -1, 3, 0.1])["max_dd_usd"] == 2.0, "drawdown counts from the start (0) too")
check(not sc([1, 1, 1])["eligible"] and sc([1, 1, 1, 1])["eligible"], "4-trade minimum: 3 winners not eligible, 4 are")
check(not sc([1, -1, 1, -1.5])["eligible"] and not sc([0, 0, 0, 0])["eligible"], "score <= 0 not eligible")
# qualifying filter
pos = [dict(leader="a", opened=R.iso_of(T0 - 3600), filters=dict(v2_pass=True), status="closed", cost_usd=5),
       dict(leader="a", opened=R.iso_of(T0 - 73 * 3600), filters=dict(v2_pass=True), status="closed", cost_usd=5),
       dict(leader="a", opened=R.iso_of(T0 - 60), filters=dict(v2_pass=False), status="closed", cost_usd=5),
       dict(leader="a", opened=R.iso_of(T0 - 60), filters=dict(), status="closed", cost_usd=5),
       dict(leader="a", opened=R.iso_of(T0 - 60), filters=dict(v2_pass=True), status="open", last_value=7, cost_usd=5),
       dict(leader="a", opened=R.iso_of(T0 - 60), filters=dict(v2_pass=True), status="closed", cost_usd=5, forced_filter_override="mcap"),
       dict(leader="b", opened=R.iso_of(T0 - 60), filters=dict(v2_pass=True), status="closed", cost_usd=5)]
q = R.qualifying(pos, "a", T0, lambda p, m: m - 5 if p["status"] == "open" else -1)
check(len(q) == 2 and q[1]["open"] and q[1]["net"] == 2, "qualifying = last 72h, v2-pass, not forced, open marked to market")

# --- ranking
S = dict(a=sc([1, 1, 1, 1]), b=sc([2, 2, 2, 2]), c=sc([0.5] * 6), d=sc([3, 3, 3]), e=sc([-1, -1, 1, 0.5]), f=sc([0.2] * 10))
check(R.rank(S) == ["b", "a", "c", "f"], "ranking: best EV first; <4 trades (d) and score<=0 (e) excluded")

# --- rotation
labs = list("abcdef") + ["_benjitrades"]
st = R.new_state(T0)
check(R.live_set(st) == ("_benjitrades",) and st["mode"] == "default", "start: default _benjitrades only")
R.rank_and_rotate(st, dict(x=sc([1, 1])), labs + ["x"], {}, T0)
check(st["live"] == ["_benjitrades"] and st["mode"] == "default", "nobody qualifies -> keep _benjitrades")
st = R.new_state(T0)
R.rank_and_rotate(st, S, labs, {}, T0)
check(st["live"] == ["_benjitrades"] and st["streak"]["b"] == 1, "hysteresis: top 3 once is not enough (still default)")
R.rank_and_rotate(st, S, labs, {}, T0 + 3600)
check(st["mode"] == "rotation" and st["live"] == ["b", "a", "c"], "after 2 consecutive top-3 ranks: b, a, c promoted; default dropped")
check(len(L.entry_gate(L.load_cfg(tempfile.mkdtemp()), leader="f", first_buy=True, leader_usd=80, mcap=2e6, avoid=False, chase=0.01, impact=0.01, n_open=0,
      same_mint_open=False, loc=__import__("datetime").datetime(2026, 10, 24, 2, 0), halted=False, forced=False, liq=2e5, age_s=7200, leader_age_s=10,
      live_set=tuple(st["live"]))) > 0, "4th eligible leader f gets no live entry (slots full)")
# cap on live slots: 6 eligible all in a row
S6 = {k: sc([1 + i] * 4) for i, k in enumerate("abcdef")}
st2 = R.new_state(T0)
for h in range(4): R.rank_and_rotate(st2, S6, labs, {}, T0 + h * 3600)
check(len(st2["live"]) == 3 and set(st2["live"]) == {"f", "e", "d"}, "live slots capped at 3 (top 3 of 6 eligible)")
st2["live"] += ["a", "b"]
check(len(R.live_set(st2)) == 3 and len(L.entry_gate(L.load_cfg(tempfile.mkdtemp()), leader="b", first_buy=True, leader_usd=80, mcap=2e6, avoid=False, chase=0.01,
      impact=0.01, n_open=0, same_mint_open=False, loc=__import__("datetime").datetime(2026, 10, 24, 2, 0), halted=False, forced=False, liq=2e5, age_s=7200,
      leader_age_s=10, live_set=tuple(st2["live"]))) > 0, "even a corrupted 5-name live list is cut to 3 (hard cap in live.py)")
st2["live"] = st2["live"][:3]
# hysteresis on swaps: newcomer g beats c once -> no swap; twice -> swap
S2 = dict(S); S2["g"] = sc([3] * 4)
R.rank_and_rotate(st, S2, labs + ["g"], {}, T0 + 7200)
check(st["live"] == ["b", "a", "c"] and st["streak"]["g"] == 1 and st["streak"]["c"] == 0, "newcomer in top 3 for 1 rank: no swap yet")
R.rank_and_rotate(st, S, labs + ["g"], {}, T0 + 3 * 3600)
check(st["streak"]["g"] == 0 and st["live"] == ["b", "a", "c"], "newcomer drops out again: streak resets, no swap")
R.rank_and_rotate(st, S2, labs + ["g"], {}, T0 + 4 * 3600); R.rank_and_rotate(st, S2, labs + ["g"], {}, T0 + 5 * 3600)
check(st["live"] == ["b", "a", "g"] and any(e["action"] == "demoted" and e["leader"] == "c" and "swapped out for g" in e["why"] for e in st["log"]),
      "newcomer top 3 for 2 ranks: replaces c (fell out of top 3)")
# demotion on score
S3 = dict(S2); S3["a"] = sc([-1, -1, -1, 0.5])
R.rank_and_rotate(st, S3, labs + ["g"], {}, T0 + 6 * 3600)
check("a" not in st["live"] and st["log"][-1]["why"].startswith("score") or any(e["leader"] == "a" and e["why"] == "score <= 0" for e in st["log"]), "score drops <= 0 -> demoted")
check(st["live"][:2] == ["b", "g"] and len(st["live"]) <= 3, f"after demotion live = {st['live']}")
S4 = dict(S3); S4["b"] = sc([1, 1, 1])
R.rank_and_rotate(st, S4, labs + ["g"], {}, T0 + 7 * 3600)
check("b" not in st["live"], "fewer than 4 qualifying trades in window -> demoted")
# demotion after 2 live losses in a row (+ cooldown, + only losses since promotion count)
lv = {"g": [(T0 + 5 * 3600 + 100, -0.001)]}
check(not R.check_loss_demotions(st, lv, T0 + 7 * 3600), "1 live loss: keeps slot")
lv["g"].append((T0 + 5 * 3600 + 200, 0.002)); lv["g"].append((T0 + 5 * 3600 + 300, -0.002))
check(not R.check_loss_demotions(st, lv, T0 + 7 * 3600), "loss, win, loss: not 2 in a row")
lv["g"].append((T0 + 5 * 3600 + 400, -0.003))
check(R.check_loss_demotions(st, lv, T0 + 7 * 3600) and "g" not in st["live"] and st["cooldown_until"]["g"] > T0 + 7 * 3600, "2 live losses in a row -> demoted with 24h cooldown")
R.rank_and_rotate(st, S2, labs + ["g"], lv, T0 + 8 * 3600); R.rank_and_rotate(st, S2, labs + ["g"], lv, T0 + 9 * 3600)
check("g" not in st["live"], "cooldown: top-ranked g not re-promoted within 24h")
check(R.consecutive_losses([(10, -1), (20, -1)], since_ts=15) == 1, "losses before promotion don't count")
# default leader: 2 live losses -> no live leader until someone qualifies
st3 = R.new_state(T0)
check(R.check_loss_demotions(st3, {"_benjitrades": [(T0 + 10, -0.01), (T0 + 20, -0.01)]}, T0 + 30) and R.live_set(st3) == (), "default _benjitrades after 2 live losses -> no live leader")
# all rotation leaders lose their slot -> back to default
st4 = R.new_state(T0); Sx = dict(a=sc([1] * 4))
R.rank_and_rotate(st4, Sx, ["a", "_benjitrades"], {}, T0); R.rank_and_rotate(st4, Sx, ["a", "_benjitrades"], {}, T0 + 3600)
check(st4["live"] == ["a"], "single qualifier takes over from default")
R.rank_and_rotate(st4, dict(a=sc([-1] * 4)), ["a", "_benjitrades"], {}, T0 + 7200)
check(st4["live"] == ["_benjitrades"] and st4["mode"] == "default", "everyone demoted -> back to default _benjitrades")
# demotion only blocks new entries: live mirror ignores slots
class FB:  # minimal bot for Live.live_set
    state = dict(rotation=dict(live=["a"]))
lvobj = L.Live.__new__(L.Live); lvobj.bot = FB()
check(lvobj.live_set() == ("a",), "Live.live_set() reads the rotation state")
check("live_set" not in open("live.py").read().split("    def mirror(self")[1].split("def flatten")[0], "mirror() of open live positions doesn't check the live slot")

# --- roster.json
tmp = tempfile.mkdtemp(); fn = os.path.join(tmp, "roster.json")
W = "9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc"
ents = [dict(label=f"w{i}", wallet=W[:-2] + "%02d" % i if False else W[:40] + "%04d" % i, source="scout") for i in range(22)]
ents = [dict(e, wallet=e["wallet"].replace("0", "a")) for e in ents]
ents += [dict(label="bad", wallet="not-a-wallet"), dict(label="w1", wallet=W), dict(label="off", wallet=W, active=False)]
json.dump(dict(leaders=ents), open(fn, "w"))
got, warn = R.load_roster(fn)
check(len(got) == 20 and any("over 20" in w for w in warn) and any("invalid" in w for w in warn) and any("duplicate" in w for w in warn),
      "roster: max 20 wallets, invalid / duplicate / inactive skipped")
shutil.rmtree(tmp)

# --- inactivity rotation (every minute)
S2 = dict(a=sc([1, 1, 1, 1]), b=sc([2, 2, 2, 2]), c=sc([0.5] * 6), f=sc([0.2] * 10), d=sc([3, 3, 3]), e=sc([-1, -1, 1, 0.5]))
labs2 = list("abcdef") + ["_benjitrades"]
def rot(live, scores=S2):
    st = R.new_state(T0); st["live"] = list(live); st["mode"] = "rotation"; st["scores"] = scores; st["_roster"] = labs2; return st
t = T0 + 10_000
st = rot(["b", "a"]); lt = dict(b=t - 3599, a=t - 3601, c=t - 1700, f=t - 60, d=t - 10, e=t - 10)
check(R.check_inactivity(st, lt, t) and "a" not in st["live"] and "b" in st["live"], "live leader with no buy/sell in 60 min loses its slot (59:59 keeps it)")
check(st["live"] == ["b", "c"] and st["promoted_at"]["c"] == t, "slot goes straight to best eligible leader active in last 30 min (c, streak 0: hysteresis skipped)")
ev = [e for e in st["log"] if e["ts"] == R.iso_of(t)]
check(any(e["action"] == "demoted" and "inactive" in e["why"] for e in ev) and any(e["action"] == "promoted" and "replaces inactive a" in e["why"] for e in ev), "swap logged with reason")
check(not R.check_inactivity(st, lt, t + 1), "no change -> nothing logged next minute")
st = rot(["b"]); lt = dict(b=t - 4000, a=t - 1801, c=t - 1801, d=t - 5, e=t - 5, f=t - 1800)
R.check_inactivity(st, lt, t)
check(st["live"] == ["f"], "replacement must have traded within 30 min (a, c at 30:01 skipped); d (<4 trades) and e (score<=0) never picked")
st = rot(["b"]); lt = dict(b=t - 4000, d=t - 5, e=t - 5, _benjitrades=t - 3700)
R.check_inactivity(st, lt, t)
check(st["live"] == [] and any(e["action"] == "slot_empty" for e in st["log"]), "no eligible active replacement and benji inactive -> slot left empty")
R.check_inactivity(st, dict(lt, _benjitrades=t + 30), t + 60)
check(st["live"] == ["_benjitrades"] and st["mode"] == "default", "benji returns as default once he trades again")
st = rot(["b"]); R.check_inactivity(st, dict(b=t - 4000, _benjitrades=t - 100), t)
check(st["live"] == ["_benjitrades"], "no eligible active replacement but benji active -> benji default")
st = R.new_state(T0); st["scores"] = {}; st["_roster"] = labs2
R.check_inactivity(st, dict(_benjitrades=t - 3601), t)
check(st["live"] == [] , "default mode: benji holds the default slot only while active")
st = R.new_state(T0); st["scores"] = S2; st["_roster"] = labs2
R.check_inactivity(st, dict(_benjitrades=t - 3601, c=t - 100), t)
check(st["live"] == ["c"] and st["mode"] == "rotation", "inactive default benji replaced by an eligible active leader (hysteresis skipped)")
st = rot(["b", "a"]); st["cooldown_until"]["c"] = t + 999; R.check_inactivity(st, dict(b=t, a=t - 4000, c=t - 10, f=t - 10), t)
check(st["live"] == ["b", "f"], "replacement skips leaders in loss cooldown")
check(st["cooldown_until"].get("a", 0) <= t, "no cooldown for inactivity")
# inactive leader earns the slot back normally (hysteresis) once it trades again
st = rot(["b"]); st["streak"] = {}
lt = dict(b=t, a=t - 4000)
R.rank_and_rotate(st, S2, labs2, {}, t, lt); R.rank_and_rotate(st, S2, labs2, {}, t + 3600, lt)
check("a" not in st["live"], "inactive leader not promoted by the hourly rank even with a 2-rank streak")
lt["a"] = t + 7000; R.rank_and_rotate(st, S2, labs2, {}, t + 7200, lt)
check("a" in st["live"], "once it trades again it earns the slot back normally (streak, no cooldown)")
src = open("selfcopy.py").read()
check("R.check_inactivity(st, self.last_trade(), now()" in src and 'lt[name] = max(' in src, "bot runs the inactivity check every minute and records every leader buy/sell")

# --- daytime session fill (session.json roster_fill)
NOSC = dict(_benjitrades=R.score([]), neo=R.score([]), ext=R.score([]), pfc=R.score([]), los=R.score([]))
labsS = list(NOSC)
CONF = dict(_benjitrades="low", neo="medium", ext="medium", pfc="medium-low", los="medium")
SESS = dict(conf=CONF, record=dict(los=dict(n=3, net_usd=-2.5), neo=dict(n=1, net_usd=-0.4)))
t = T0
st = R.new_state(t); st["live"] = []; st["_roster"] = labsS
lt = dict(neo=t - 600, ext=t - 4000, pfc=t - 60, los=t - 30, _benjitrades=t - 9000)
R.rank_and_rotate(st, NOSC, labsS, {}, t, lt)
check(st["live"] == [], "no session: nobody qualifies (0 trades) -> no live leader (old behaviour unchanged)")
R.rank_and_rotate(st, NOSC, labsS, {}, t, lt, session=SESS)
check(st["live"] == ["neo"], "session fill: active medium wallet with a neutral record (1 small loss) takes the empty slot")
check("ext" not in st["live"], "session fill: medium wallet idle > 60 min not promoted")
check("pfc" not in st["live"], "session fill: medium-low wallet not promoted even when active")
check("los" not in st["live"], "session fill: clearly negative wallet (3 trades, net < 0) not promoted")
check(st["session_fill"] == ["neo"] and "session fill" in st["log"][-1]["why"], "session fill logged and tracked")
R.rank_and_rotate(st, NOSC, labsS, {}, t + 3600, dict(lt, neo=t + 3000), session=SESS)
check(st["live"] == ["neo"], "hourly rank keeps a session-filled leader despite < 4 qualifying trades")
lt2 = dict(lt, neo=t + 3000, ext=t + 3500)
R.check_inactivity(st, lt2, t + 3600, session=SESS)
check(st["live"] == ["neo", "ext"], "an idle wallet that trades again gets an empty slot within a minute")
R.check_inactivity(st, dict(lt2, neo=t + 3000 - 4000), t + 3600 + 3700, session=SESS)
check("neo" not in st["live"], "60-min idle demotion still applies to session-filled leaders")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsS
R.rank_and_rotate(st, NOSC, labsS, {}, t, lt, session=SESS)
R.check_loss_demotions(st, dict(neo=[(t + 10, -0.01), (t + 20, -0.02)]), t + 30)
check("neo" not in st["live"] and st["cooldown_until"]["neo"] > t + 30, "2-loss demotion + 24h cooldown still apply")
R.check_inactivity(st, dict(lt, neo=t + 25), t + 60, session=SESS)
check("neo" not in st["live"], "session fill respects the loss cooldown")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsS
R.rank_and_rotate(st, NOSC, labsS, {}, t, lt, session=SESS)
neg = dict(SESS, record=dict(SESS["record"], neo=dict(n=2, net_usd=-1.0)))
R.rank_and_rotate(st, NOSC, labsS, {}, t + 3600, dict(lt, neo=t + 3500), session=neg)
check("neo" not in st["live"] and "negative" in st["log"][-1]["why"], "session-filled leader loses the slot once its record turns clearly negative")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsS
R.rank_and_rotate(st, NOSC, labsS, {}, t, lt, session=SESS)
R.rank_and_rotate(st, NOSC, labsS, {}, t + 3600, dict(lt, neo=t + 3500))
check("neo" not in st["live"] and not st.get("session_fill"), "after the session closes for entries the session-fill slot ends at the next hourly rank")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsS
R.rank_and_rotate(st, NOSC, labsS, {}, t, lt, session=SESS)
R.check_inactivity(st, dict(lt, neo=t + 50), t + 60)
check(st["live"] == [] and "session closed" in st["log"][-1]["why"], "...and the per-minute check ends it as soon as the session stops entries")
# hysteresis 1 during the session for eligible leaders
st = R.new_state(t); st["streak"] = {}
R.rank_and_rotate(st, S2, labs2, {}, t, None, session=dict(conf={}, record={}))
check(st["mode"] == "rotation" and len(st["live"]) > 0, "session: an eligible top-3 leader is promoted after one hourly rank")
st = R.new_state(t); st["streak"] = {}
R.rank_and_rotate(st, S2, labs2, {}, t, None)
check(st["mode"] == "default", "no session: 2-rank hysteresis unchanged")
# config switch
tmpd = tempfile.mkdtemp()
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z"), open(os.path.join(tmpd, "session.json"), "w"))
check(L.load_session(tmpd)["roster_fill"] is True, "roster_fill defaults on while a session file exists")
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", roster_fill=False), open(os.path.join(tmpd, "session.json"), "w"))
check(L.load_session(tmpd)["roster_fill"] is False, "roster_fill can be switched off in session.json")
os.environ["SELFCOPY_SESSION_ROSTER_FILL"] = "1"; check(L.load_session(tmpd)["roster_fill"] is True, "env SELFCOPY_SESSION_ROSTER_FILL overrides"); del os.environ["SELFCOPY_SESSION_ROSTER_FILL"]
shutil.rmtree(tmpd)
# manual_live (session-scoped)
CONFM = dict(CONF, ypd="medium-low"); labsM = labsS + ["ypd"]
NOSCM = dict(NOSC, ypd=R.score([]))
SESSM = dict(conf=CONFM, record=SESS["record"], manual=["ypd"])
st = R.new_state(t); st["live"] = []; st["_roster"] = labsM
ltm = dict(lt, ypd=t - 120)
R.rank_and_rotate(st, NOSCM, labsM, {}, t, ltm, session=dict(SESSM, manual=[]))
check("ypd" not in st["live"], "medium-low wallet without manual_live is not promoted")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsM
R.rank_and_rotate(st, NOSCM, labsM, {}, t, ltm, session=SESSM)
check(st["live"][0] == "ypd" and "neo" in st["live"] and "manual_live" in [e for e in st["log"] if e["leader"] == "ypd"][-1]["why"], "manual_live wallet gets a slot first (and neo still fills another)")
R.check_inactivity(st, dict(ltm, ypd=t - 3700, neo=t), t + 60, session=SESSM)
check("ypd" not in st["live"], "manual_live wallet still loses its slot after 60 min idle")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsM
R.rank_and_rotate(st, NOSCM, labsM, {}, t, ltm, session=SESSM)
R.check_loss_demotions(st, dict(ypd=[(t + 10, -0.01), (t + 20, -0.02)]), t + 30)
R.check_inactivity(st, dict(ltm, ypd=t + 25), t + 60, session=SESSM)
check("ypd" not in st["live"], "manual_live wallet: 2 live losses -> demoted and kept out (cooldown)")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsM
R.rank_and_rotate(st, NOSCM, labsM, {}, t, ltm, session=SESSM)
R.check_inactivity(st, dict(ltm, ypd=t + 50), t + 60)
check("ypd" not in st["live"], "manual_live slot ends when the session stops entries")
st = R.new_state(t); st["live"] = []; st["_roster"] = labsS          # rank ran before the wallet was added to roster.json
R.check_inactivity(st, ltm, t + 60, session=SESSM)
check(st["live"][0] == "ypd", "a wallet added to roster.json mid-hour can take its manual slot before the next hourly rank")
tmpd = tempfile.mkdtemp()
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", manual_live=["ypnn-day"]), open(os.path.join(tmpd, "session.json"), "w"))
check(L.load_session(tmpd)["manual_live"] == ["ypnn-day"], "manual_live read from session.json")
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z"), open(os.path.join(tmpd, "session.json"), "w"))
check(L.load_session(tmpd)["manual_live"] == [], "no manual_live by default"); shutil.rmtree(tmpd)
check("session=self.session_roster()" in src and "session=self.session_roster(t)" in src, "bot passes the session context to the hourly rank and the per-minute check")

# --- 10:27Z: session slots up to 5, any-confidence fill, roster_inbox.json
labs5 = ["l1", "l2", "l3", "l4", "l5", "l6", "neg"]
conf5 = dict(l1="low", l2="low", l3="medium-low", l4="?", l5="medium", l6="low", neg="medium")
lt5 = dict(l1=t - 60, l2=t - 120, l3=t - 180, l4=t - 240, l5=t - 300, l6=t - 3700, neg=t - 30)
rec5 = dict(neg=dict(n=2, net_usd=-1.0))
S5 = dict(conf=conf5, record=rec5, manual=[], max_slots=5, any_conf=True)
noS5 = {k: R.score([]) for k in labs5}
st = R.new_state(t); st["live"] = []; st["_roster"] = labs5
R.rank_and_rotate(st, noS5, labs5, {}, t, lt5, session=S5)
check(st["live"] == ["l1", "l2", "l3", "l4", "l5"], "session: 5 slots, ANY confidence, most recent activity first")
check("l6" not in st["live"] and "neg" not in st["live"], "idle >60 min (l6) and clearly negative (neg: 2 trades net<0) still excluded")
st = R.new_state(t); st["live"] = []; st["_roster"] = labs5
R.rank_and_rotate(st, noS5, labs5, {}, t, lt5, session=dict(S5, any_conf=False))
check(st["live"] == ["l5"], "without any_conf only medium+ wallets fill")
st = R.new_state(t); st["live"] = []; st["_roster"] = labs5; st["cooldown_until"]["l1"] = t + 999
R.rank_and_rotate(st, noS5, labs5, {}, t, lt5, session=S5)
check("l1" not in st["live"], "loss cooldown still blocks the fill")
tie = dict(lt5, l2=t - 60); scs = dict(noS5, l2=sc([1, 1, 1, 1]))
st = R.new_state(t); st["live"] = []; st["_roster"] = labs5
R.session_fill(st, scs, dict(S5, max_slots=1), t, tie)
check(st["live"] == ["l2"], "activity tie -> higher score first")
check(R.slots(None) == 3 and R.slots(dict(max_slots=9)) == 5 and R.slots(dict(max_slots=4)) == 4, "slots: 3 by default, session max 5")
st = R.new_state(t); st["live"] = []; st["_roster"] = labs5
R.rank_and_rotate(st, noS5, labs5, {}, t, lt5, session=S5); R.check_inactivity(st, lt5, t + 30)
check(len(st["live"]) <= 3, "session ends -> back to at most 3 slots")
tmpd = tempfile.mkdtemp()
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z", max_live_leaders=8, roster_fill_any_conf=True), open(os.path.join(tmpd, "session.json"), "w"))
ss = L.load_session(tmpd)
check(ss["max_live_slots"] == 5 and ss["roster_fill_any_conf"] is True, "session.json max_live_leaders capped at 5; any_conf read")
check(L.HARD["max_live_leaders"] == 3, "HARD max_live_leaders unchanged (own live wallet stays at 3)")
json.dump(dict(start="2026-10-24T08:31:00Z", end="2026-10-24T20:00:00Z"), open(os.path.join(tmpd, "session.json"), "w"))
check(L.load_session(tmpd)["max_live_slots"] is None and not L.load_session(tmpd)["roster_fill_any_conf"], "defaults: no extra slots, confidence rule on")
W = lambda i: "1" * 31 + "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijk"[i]
rf, inf = os.path.join(tmpd, "roster.json"), os.path.join(tmpd, "inbox.json")
json.dump(dict(leaders=[dict(label=f"r{i}", wallet=W(i), confidence=("low" if i < 3 else "medium"), source="t") for i in range(19)]), open(rf, "w"))
json.dump([dict(label="new1", wallet="2" * 40, confidence="medium", source="scout"), dict(label="new2", wallet="3" * 40, confidence="bogus"),
           dict(label="bad", wallet="0OIl"), dict(label="r0", wallet="4" * 40)], open(inf, "w"))
seen = {}
res = R.merge_inbox(rf, inf, seen, dict(r0=t - 10, r1=t - 5000, r2=t - 100), {"r1"}, t)
ents, _ = R.load_roster(rf); labsr = [e["label"] for e in ents]
check(res["added"][:2] == ["new1", "new2"] and len(ents) == 20, "inbox merged, roster capped at 20 active")
check("r2" in res["dropped"] and "r2" not in labsr and "r1" in labsr, "full -> idlest low-confidence wallet dropped (protected live/open r1 kept)")
check(any(e["label"] == "new2" and e["confidence"] == "low" for e in ents), "unknown confidence -> low")
check(("bad", "invalid wallet") in res["skipped"], "invalid wallet rejected")
check(any(e["label"] == "r0-444444" for e in ents), "label clash renamed (r0 -> r0-444444)")
res2 = R.merge_inbox(rf, inf, seen, {}, set(), t + 60)
check(not res2["added"] and not res2["dropped"], "each inbox wallet merged once")
shutil.rmtree(tmpd)
check("merge_inbox()" in src and "INBOX_FN" in src, "bot merges roster_inbox.json every minute")

# --- 10:29Z: session prune rules
def cp(net, opened, held=3600, stop=False, src="paper", mint="m"):
    return dict(opened_ts=opened, closed_ts=opened + held, net_frac=net, stop_hit=stop, src=src, mint=mint)
st = R.new_state(t); st["live"] = ["a", "b", "c"]
ev = R.prune_check(st, dict(a=[cp(0.1, t - 9000), cp(-0.05, t - 8000), cp(-0.05, t - 7000), cp(-0.02, t - 6000)],
                            b=[cp(0.3, t - 9000), cp(-0.05, t - 8000), cp(-0.05, t - 7000), cp(-0.02, t - 6000)],
                            c=[cp(0.2, t - 3000, held=1000), cp(-0.16, t - 900, held=600, stop=True)]), t, since_ts=t - 20000)
check([e["leader"] for e in ev] == ["a", "c"] and st["live"] == ["b"], "prune: last 4 net<0 (a) and -15% stop within 15 min (c) demoted; b (net>0) kept")
check(st["cooldown_until"]["a"] == t + 12 * 3600 and st["cooldown_until"]["c"] == t + 12 * 3600, "12h cooldown for both rules")
check(ev[0]["rule"] == "last4_negative" and ev[1]["rule"] == "quick_stop" and "cooldown" in ev[1]["why"], "prune events carry rule and reason")
st = R.new_state(t); st["live"] = ["d"]
check(not R.prune_check(st, dict(d=[cp(-0.16, t - 4000, held=1200, stop=True)]), t, since_ts=0), "stop after 20 min is not a quick stop")
check(not R.prune_check(st, dict(d=[cp(-0.1, t - 9000), cp(-0.1, t - 8000), cp(-0.1, t - 7000)]), t), "fewer than 4 copies: rule (a) waits")
st = R.new_state(t); st["live"] = ["e"]
old = [cp(-0.1, t - 9000), cp(-0.1, t - 8000), cp(-0.1, t - 7000), cp(-0.1, t - 6000)]
check(not R.prune_check(st, dict(e=old), t, since_ts=t) and st["live"] == ["e"], "only copies closed this session trigger a prune")
st = R.new_state(t); st["live"] = []
ev = R.prune_check(st, dict(f=[cp(-0.15, t - 1000, held=300, stop=True)]), t)
check(ev and not ev[0]["was_live"] and st["cooldown_until"]["f"] > t, "quick stop on a non-live leader -> cooldown, kept out")
check(not R.prune_check(st, dict(f=[cp(-0.15, t - 1000, held=300, stop=True)]), t + 60), "same copy judged once")
dd = R.dedupe_copies([cp(-0.1, t, src="chunk", mint="X")], [cp(0.2, t + 30, mint="X"), cp(0.1, t, mint="Y")])
check([c["src"] for c in dd] == ["chunk", "paper"] and dd[1]["mint"] == "Y", "live copy wins over the paper copy of the same trade")
check("run_prune()" in src and "prune-log.jsonl" in src, "bot runs the prune every minute and logs prune-log.jsonl")

# --- 10:35Z: manual_live is exempt from the paper "clearly negative" rule; real-copy rules and idle demotion stay
labsN = ["ypd", "oth"]; confN = dict(ypd="medium-low", oth="medium")
recN = dict(ypd=dict(n=4, net_usd=-0.13), oth=dict(n=2, net_usd=-0.5))
SN = dict(conf=confN, record=recN, manual=["ypd"], max_slots=5, any_conf=True)
ltN = dict(ypd=t - 30, oth=t - 30)
st = R.new_state(t); st["live"] = []; st["_roster"] = labsN
R.rank_and_rotate(st, {k: R.score([]) for k in labsN}, labsN, {}, t, ltN, session=SN)
check(st["live"] == ["ypd"], "manual_live keeps/gets its slot despite a negative paper record; non-manual negative wallet stays out")
R.rank_and_rotate(st, {k: R.score([]) for k in labsN}, labsN, {}, t + 3600, dict(ltN, ypd=t + 3500), session=SN)
R.check_inactivity(st, dict(ltN, ypd=t + 3500), t + 3560, session=SN)
check(st["live"] == ["ypd"], "manual_live not demoted by the paper rule at the hourly rank or the per-minute check")
R.check_inactivity(st, dict(ltN, ypd=t + 3500), t + 3500 + 3700, session=SN)
check("ypd" not in st["live"], "manual_live still loses the slot after 60 min idle")
R.check_inactivity(st, dict(ltN, ypd=t + 3500 + 3750), t + 3500 + 3760, session=SN)
check(st["live"] == ["ypd"], "live hysteresis: idle-demoted wallet regains a free slot on the next per-minute check after it trades")
st = R.new_state(t); st["live"] = ["ypd"]; st["promoted_at"]["ypd"] = t - 100
check(R.check_loss_demotions(st, dict(ypd=[(t - 50, -0.01), (t - 20, -0.02)]), t) and "ypd" not in st["live"], "manual_live: 2 real losses in a row -> demoted")
st = R.new_state(t); st["live"] = ["ypd"]
paper4 = [dict(opened_ts=t - 9000 + i * 1000, closed_ts=t - 8000 + i * 1000, net_frac=-0.1, stop_hit=False, src="paper", mint=str(i)) for i in range(4)]
check(not R.prune_check(st, dict(ypd=paper4), t, real_only={"ypd"}) and st["live"] == ["ypd"], "manual_live: paper copies ignored by the prune rules")
real4 = [dict(c, src="chunk") for c in paper4]
check(R.prune_check(st, dict(ypd=real4), t, real_only={"ypd"}) and "ypd" not in st["live"], "manual_live: last 4 REAL copies net < 0 -> pruned")
check("real_closed_by_leader()" in src and "real_only=" in src, "bot feeds Chunk's real copies to the 2-loss rule and real_only to the prune")
print(f"ROSTER TESTS: {ok} passed")
