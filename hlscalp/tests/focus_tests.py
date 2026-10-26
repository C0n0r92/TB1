# 2026-10-26 focus tests (run from mock_exec3.py, shares its mocks)
def _mc(coin, slippage=0.01, cloid=None):
    W["calls"].append(("market_close", coin)); W["pos"] = 0.0; return {"status":"ok","response":{"data":{"statuses":[{"filled":{}}]}}}
ex.market_close = _mc
print("=== 13 config: triggers / tiers / stacking")
assert S.cfg["trigger_strats"] == ["SQZMOM","BBKC_BRK","VWAP_RSI","ABSORB","FAIL_BRK","VWAP_BAND"], S.cfg["trigger_strats"]
assert S.cfg["confirm_half_risk_mult"] == 1.0 and S.cfg["samedir_risk_mult"] == 0.25 and S.cfg["samedir_max_risk_r"] == 3
assert S.cfg["risk_per_trade"] == 0.03 and S.cfg["max_open_risk_pct"] == 30.0
print("=== 14 3rd same-direction -> x0.25"); st=fresh(); W["mid"]=0.1008
st["trades"]["X1"]={"side":"long","stop":1,"entry":1}; st["trades"]["X2"]={"side":"long","stop":1,"entry":1}
r14=ent(st); t=st["trades"][C]; print(r14, t["samedir_mult"], t["risk_usd"]); assert t["samedir_mult"]==0.25 and abs(t["risk_usd"]-0.25*0.03*200)<0.05
print("=== 15 same-direction 3R cap: sizes into the room, short-side risk ignored")
st=fresh(); W["mid"]=0.1008
st["trades"]["X1"]=dict(side="long",pending=True,sz0=1000,lim=1.0,stop=0.99,lev=1000)   # $10 long risk
st["trades"]["X2"]=dict(side="long",pending=True,sz0=700,lim=1.0,stop=0.99,lev=1000)    # $7 long risk -> 17 of 18 used
st["trades"]["X3"]=dict(side="short",pending=True,sz0=500,lim=1.0,stop=1.01,lev=1000)  # $5 short risk: other side
print("long risk", S.open_risk(st,{},"long"), "short", S.open_risk(st,{},"short"))
r15=ent(st); t=st["trades"][C]; print(r15, t["risk_usd"], t["sz0"]); assert r15=="limit_placed" and t["risk_usd"]<=1.0+1e-6
st=fresh(); W["mid"]=0.1008; st["trades"]["X1"]=dict(side="long",pending=True,sz0=1800,lim=1.0,stop=0.99,lev=1000)   # $18 = 3R used
r15b=ent(st); print(r15b); assert r15b=="skip_size" and C not in st["trades"]
st=fresh(); W["mid"]=0.1008; e["signal"]=-1; e["bar_high"],e["bar_low"]=0.1000,0.0998
st["trades"]["X1"]=dict(side="long",pending=True,sz0=1800,lim=1.0,stop=0.99,lev=1000)
W["mid"]=0.0999; r15c=ent(st); print("short with longs full:", r15c); assert r15c=="limit_placed"
e["signal"]=1; e["bar_high"],e["bar_low"]=0.1010,0.0990
print("=== 16 fallback deadline = placed + 300s, sized off the live price")
st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]
assert abs((t["deadline_ms"]-t["placed_ms"]) - 300_000) < 5, t["deadline_ms"]-t["placed_ms"]
plan = t["planned_sz"]*(abs(t["lim"]-t["stop"])+0.0015*t["lim"]); W["calls"]=[]; t["deadline_ms"]=S.nms()-1000; W["hl"]=(0.1009,0.0995); W["mid"]=0.1012
S._SNAP[0]=S.nms(); S.manage_pending(st,{},info.all_mids())
ioc=[c for c in W["calls"] if c[0]=="order" and "limit" in c[4]][0]; sz=ioc[2]
risk_now = sz*(abs(0.1012-t["stop"])+0.0015*0.1012); print("planned sz",t["planned_sz"],"fallback sz",sz,"plan risk",round(plan,4),"risk at fill",round(risk_now,4))
assert sz < t["planned_sz"] and abs(risk_now-plan)/plan < 0.02 and st["trades"][C].get("entry_type")=="market_fallback"
print("=== 16b not late yet (< 300s) -> limit keeps resting"); st=fresh(); W["mid"]=0.1008; ent(st); W["calls"]=[]
S.manage_pending(st,{},info.all_mids()); assert st["trades"][C].get("pending") and not W["calls"]
print("=== 17 instant (marketable) limit fill -> stop/TP re-based on the fill with the planned distance")
st=fresh(); W["mid"]=0.0992; e["bar_high"],e["bar_low"]=0.1010,0.0990
r17=ent(st); t=st["trades"][C]; d=abs(t["lim"]-t["stop"]); W["calls"]=[]
W["status"][t["cloid"]]="filled"; W["orders"]=[o for o in W["orders"] if o["cloid"]!=t["cloid"]]; W["pos"]=t["sz0"]; W["entry"]=0.0992
S.manage_pending(st,S.own_positions(info.user_state(0)),info.all_mids()); tt=st["trades"][C]
print("lim",t["lim"],"fill",tt["entry"],"stop",tt["stop"],"tp1",tt["tp1"],"dist0",tt["dist0"])
sls=[o for o in W["orders"] if "Stop" in o["orderType"]]; tps=[o for o in W["orders"] if "Take" in o["orderType"]]
print("orders:",[(o["orderType"],o["sz"],o["triggerPx"]) for o in W["orders"]])
assert abs(tt["stop"]-(0.0992-d))<1e-6 and abs(tt["tp1"]-(0.0992+1.5*d))<1e-6 and len(sls)==1 and float(sls[0]["triggerPx"])==tt["stop"]
assert len(tps)==1 and float(tps[0]["triggerPx"])==tt["tp1"] and abs(tt["dist0"]-d)<1e-9
print("=== 17b normal limit fill at the limit -> stop/TP untouched"); st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; s0,tp0=t["stop"],t["tp1"]
W["status"][t["cloid"]]="filled"; W["orders"]=[o for o in W["orders"] if o["cloid"]!=t["cloid"]]; W["pos"]=t["sz0"]; W["entry"]=t["lim"]
S.manage_pending(st,S.own_positions(info.user_state(0)),info.all_mids()); assert st["trades"][C]["stop"]==s0 and st["trades"][C]["tp1"]==tp0
def be_trade():
    st=fresh(); W.update(pos=100.0,entry=0.1)
    st["trades"][C]=dict(side="long",entry=0.1,sz0=100.0,stop=0.099,tp1=0.1015,tp1_ok=True,tp1_done=False,atr=0.0005,best=0.1,risk_usd=0.1,lev=5,
                         opened_ms=S.nms()-600000,votes={},realized=0.0,dist0=0.001,peak=0.1008,hl_ms=S.nms(),be_armed=True)
    W["orders"]=[mkorder("0x5ca151"+"c"*26,"Stop Market",100.0,0.099),mkorder("0x5ca151"+"d"*26,"Take Profit Market",50.0,0.1015)]; return st
print("=== 18 paused computer: stale snapshot -> refreshed before BE (no wrong close)")
st=be_trade(); W["mid"]=0.1009; stale={C:"0.1000"}; S._SNAP[0]=S.nms()-900_000; W["calls"]=[]
S.manage(st,S.own_positions(info.user_state(0)),S.own_orders(),stale); print(W["calls"])
assert not any(c[0]=="market_close" for c in W["calls"]) and abs(st["trades"][C]["stop"]-0.10012)<1e-6
print("=== 18b fresh snapshot but cached mid stale -> fresh-price re-check before BE close")
st=be_trade(); W["mid"]=0.1009; S._SNAP[0]=S.nms(); W["calls"]=[]
S.manage(st,S.own_positions(info.user_state(0)),S.own_orders(),stale); print(W["calls"])
assert not any(c[0]=="market_close" for c in W["calls"]) and abs(st["trades"][C]["stop"]-0.10012)<1e-6
print("=== 18c genuine: fresh price really back at BE -> BE close still happens")
st=be_trade(); W["mid"]=0.1000; S._SNAP[0]=S.nms(); W["calls"]=[]
S.manage(st,S.own_positions(info.user_state(0)),S.own_orders(),info.all_mids()); print(W["calls"])
assert any(c[0]=="market_close" for c in W["calls"])
print("ALL FOCUS TESTS PASSED")
print("=== 19 FAIL_BRK / VWAP_BAND detectors")
import pandas as pd, numpy as np
def mkdf(rows, t0=None):
    t0 = t0 if t0 is not None else (S.nms()//86_400_000)*86_400_000
    d = pd.DataFrame(rows, columns=["o","h","l","c","v"]); d["t"] = [t0 + k*900_000 for k in range(len(d))]; d["T"] = d["t"] + 899_999; return d
base = [(100,100.5,99.5,100,10)]*20
# swing high at 103 (bar 10), flat after; prev bar pokes 103.6, last bar closes back at 102.5 -> short
r = [(100,100.0+0.01*k,99.5-0.01*k,100,10) for k in range(10)] + [(100,103,99.5,100,10)] + [(100,101-0.05*k,99.5+0.01*k,100,10) for k in range(9)]
r += [(102,103.6,101.8,103.2,10),(103.2,103.3,102.2,102.5,10)]
f = S.setup_failbrk(mkdf(r), 1.0); print(f); assert f and f["side"]==-1 and abs(f["stop"]-103.6*1.001)<1e-9
r2 = list(r); r2[-1] = (103.2,103.8,103.0,103.4,10); assert S.setup_failbrk(mkdf(r2),1.0) is None   # still beyond -> no fade
# mirror: swing low 97, poke 96.4, close back 97.5 -> long
r3 = [(100,100.5+0.01*k,99.9-0.01*k,100,10) for k in range(10)] + [(100,100.5,97,100,10)] + [(100,100.5-0.01*k,99+0.05*k,100,10) for k in range(9)]
r3 += [(98,98.2,96.4,96.8,10),(96.8,97.8,96.7,97.5,10)]
f3 = S.setup_failbrk(mkdf(r3),1.0); print(f3); assert f3 and f3["side"]==1 and abs(f3["stop"]-96.4*0.999)<1e-9
# VWAP band: 12 quiet bars around 100 (+-0.2 noise), prev bar closes far below lower band, last closes back inside
rng = np.random.default_rng(1); q = [(100, 100.3, 99.7, 100+rng.uniform(-0.2,0.2), 10) for _ in range(12)]
vb = q + [(100,100,98.6,98.7,10),(98.7,99.9,98.65,99.85,10)]
d = mkdf(vb); vw, sd, _ = S.session_vwap(d); print("lower band prev", vw.iloc[-2]-2*sd.iloc[-2], "last", vw.iloc[-1]-2*sd.iloc[-1])
g = S.setup_vwapband(d, 0.5); print(g); assert g and g["side"]==1 and abs(g["stop"]-98.6*0.999)<1e-9
vb2 = q + [(100,101.4,100,101.3,10),(101.3,101.35,100.1,100.15,10)]; g2 = S.setup_vwapband(mkdf(vb2),0.5); print(g2); assert g2 and g2["side"]==-1
assert S.setup_vwapband(mkdf(q + [(100,100,98.6,98.7,10),(98.7,98.8,98.5,98.6,10)]),0.5) is None   # still outside
assert S.setup_vwapband(mkdf(vb, t0=(S.nms()//86_400_000)*86_400_000 - 12*900_000),0.5) is None  # prev bar in another session
assert "FAIL_BRK" in S.cfg["trigger_strats"] and "VWAP_BAND" in S.cfg["trigger_strats"] and "SWING_BRK" not in S.cfg["trigger_strats"]
print("ALL NEW-TRIGGER TESTS PASSED")
