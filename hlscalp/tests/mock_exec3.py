import sys, os, json, time
sys.argv=["scalper.py","--dry-run"]; sys.path.insert(0,"/workspace/hlscalp")
import scalper as S
S.STATE="/tmp/mock/state.json"; S.P=lambda f:"/tmp/mock/"+f; S.KILL="/tmp/mock/KILL"
S.ACCOUNT="0xmock"; S.SZD={"DOGE":0}; S.time.sleep=lambda s:None
C="DOGE"
class X: pass
W={"pos":0.0,"entry":0.1,"mid":0.1,"status":{},"orders":[],"calls":[],"fills":[],"hl":(0.1,0.1),"ioc_fill":True}
def mkorder(cl,typ,sz,trig=None): return {"coin":C,"oid":abs(hash(cl))%10**9,"cloid":cl,"orderType":typ,"sz":str(sz),"isTrigger":typ!="Limit","triggerPx":str(trig)}
info=X(); ex=X()
info.query_order_by_cloid=lambda a,c: {"status":"order","order":{"status":W["status"].get(c.to_raw(),"open"),"order":{}}} if c.to_raw() in W["status"] or any(o["cloid"]==c.to_raw() for o in W["orders"]) else {"status":"unknownOid"}
info.user_state=lambda a: {"assetPositions":[{"position":{"coin":C,"szi":str(W["pos"]),"entryPx":str(W["entry"]),"unrealizedPnl":"0","marginUsed":"1","leverage":{"value":5},"liquidationPx":None}}] if W["pos"] else []}
info.frontend_open_orders=lambda a: list(W["orders"])
info.user_fills_by_time=lambda a,t: W["fills"]
info.candles_snapshot=lambda c,iv,s,e: [{"h":W["hl"][0],"l":W["hl"][1]}]
info.all_mids=lambda: {C:str(W["mid"])}
info.spot_user_state=lambda a: {"balances":[{"coin":"USDC","total":"500","hold":"0"}]}
def order(coin,b,sz,px,ot,reduce_only=False,cloid=None):
    W["calls"].append(("order",b,sz,px,ot,reduce_only,cloid.to_raw()[:8]))
    if "trigger" in ot: W["orders"].append(mkorder(cloid.to_raw(),"Stop Market" if ot["trigger"]["tpsl"]=="sl" else "Take Profit Market",sz,ot["trigger"]["triggerPx"])); return {"status":"ok","response":{"data":{"statuses":[{"resting":{"oid":W["orders"][-1]["oid"]}}]}}}
    if W["ioc_fill"]: W["pos"]+=sz if b else -sz; W["fills"].append({"coin":C,"cloid":cloid.to_raw(),"time":S.nms()})
    return {"status":"ok","response":{"data":{"statuses":[{"filled":{"totalSz":str(sz)}}]}}}
def bulk(reqs,grouping="na"):
    W["calls"].append(("bulk",grouping,[(r["is_buy"],r["sz"],r["limit_px"],list(r["order_type"])[0],r["reduce_only"],r["cloid"].to_raw()[:8]) for r in reqs]))
    for r in reqs:
        typ="Limit" if "limit" in r["order_type"] else ("Stop Market" if r["order_type"]["trigger"]["tpsl"]=="sl" else "Take Profit Market")
        W["orders"].append(mkorder(r["cloid"].to_raw(),typ,r["sz"],r["order_type"].get("trigger",{}).get("triggerPx")))
    return {"status":"ok","response":{"data":{"statuses":[{"resting":{"oid":W["orders"][-len(reqs)]["oid"]}},"waitingForFill","waitingForFill"]}}}
def cancel(coin,oid):
    W["calls"].append(("cancel",oid)); W["orders"]=[o for o in W["orders"] if o["oid"]!=oid]; return {"status":"ok"}
ex.order=order; ex.bulk_orders=bulk; ex.cancel=cancel; ex.update_leverage=lambda *a,**k:{"status":"ok"}
S.info=info; S.ex=ex
def fresh():
    W.update(pos=0.0,orders=[],calls=[],fills=[],status={},hl=(0.1,0.1),mid=0.1,ioc_fill=True)
    st=S.load_state(); st.update(trades={},cooldown={}); S._ST.clear(); S._ST.update(st); return S._ST
e=dict(coin=C,signal=1,atr=0.001,stop_dist=0.0015,risk_mult=1.0,bar_high=0.1010,bar_low=0.0990,bar_close=S.nms()//900000*900000,tp_r=1.5,votes={},primary="SWING_BRK",strategies=["SWING_BRK"],trend=1,setups={},confirm={},confirmers=[])
uni={"coin":C,"maxlev":10}
def ent(st):
    us=info.user_state(0); pos=S.own_positions(us)
    return S.enter(st,e,200.0,pos,[],us,info.all_mids(),uni)
print("=== 1 placement"); st=fresh(); W["mid"]=0.1008
r=ent(st); print(r); [print(c) for c in W["calls"]]; t=st["trades"][C]; print({k:t[k] for k in ("pending","lim","stop","tp1","sz0","deadline_ms")})
print("open_risk", S.open_risk(st,{}), "samedir", S.samedir_count(st,"long"))
print("=== 2 partial fill + deadline -> fallback"); W["calls"]=[]
W["pos"]=100.0; W["entry"]=t["lim"]; W["fills"].append({"coin":C,"cloid":t["cloid"],"time":S.nms()}); t["deadline_ms"]=S.nms()-1000; W["hl"]=(0.1009,0.0995)
pos=S.own_positions(info.user_state(0)); S.manage_pending(st,pos,info.all_mids()); [print(c) for c in W["calls"]]
t=st["trades"][C]; print("pending" in t, t.get("entry_type"), t["sz0"], t["stop"], t["tp1_ok"]); print("orders left:",[(o["orderType"],o["sz"],o["cloid"][:8]) for o in W["orders"]])
oo=S.own_orders(); W["calls"]=[]; S.manage(st,S.own_positions(info.user_state(0)),oo,info.all_mids()); print("manage:",W["calls"]); print("orders:",[(o["orderType"],o["sz"]) for o in W["orders"]])
print("=== 3 full fill"); st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["calls"]=[]
W["status"][t["cloid"]]="filled"; W["orders"]=[o for o in W["orders"] if o["cloid"]!=t["cloid"]]; W["pos"]=t["sz0"]; W["entry"]=t["lim"]
S.manage_pending(st,S.own_positions(info.user_state(0)),info.all_mids()); print(W["calls"]); print("orders:",[(o["orderType"],o["sz"],o["cloid"][:6]) for o in W["orders"]], st["trades"][C].get("entry_type"))
print("=== 4 TP hit before fill -> drop"); st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["calls"]=[]; W["mid"]=t["tp1"]*1.001
S.manage_pending(st,{},info.all_mids()); print(W["calls"]); print("trades:",st["trades"],"orders:",W["orders"])
print("=== 5 deadline, no fill, valid -> market fallback full"); st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["calls"]=[]; t["deadline_ms"]=S.nms()-1000; W["hl"]=(0.1009,0.0995)
S.manage_pending(st,{},info.all_mids()); print(W["calls"]); print(st["trades"][C].get("entry_type"), st["trades"][C]["sz0"])
print("=== 6 too late (paused) -> just cancel"); st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["calls"]=[]; t["deadline_ms"]=S.nms()-700_000
S.manage_pending(st,{},info.all_mids()); print(W["calls"], st["trades"])
print("=== 7 BE arm"); st=fresh(); W.update(pos=100.0,entry=0.1,mid=0.10076)
st["trades"][C]=dict(side="long",entry=0.1,sz0=100.0,stop=0.099,tp1=0.1015,tp1_ok=True,tp1_done=False,atr=0.0005,best=0.1,risk_usd=0.1,lev=5,opened_ms=S.nms()-600000,votes={},realized=0.0)
W["orders"]=[mkorder("0x5ca151"+"a"*26,"Stop Market",100.0,0.099)]
S.manage(st,S.own_positions(info.user_state(0)),S.own_orders(),info.all_mids()); print(W["calls"], st["trades"][C]["stop"], st["trades"][C].get("be_armed"))
print("=== 8 samedir: 2 longs open -> half"); st=fresh(); W["mid"]=0.1008
st["trades"]["X1"]={"side":"long","stop":1,"entry":1}; st["trades"]["X2"]={"side":"long","stop":1,"entry":1}; ent(st); print(st["trades"][C]["samedir_mult"], st["trades"][C]["sz0"])
print("=== 9 CHIP race: limit filled, step-start pos snapshot is stale (empty) -> must track, not drop")
st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["calls"]=[]
W["status"][t["cloid"]]="filled"; W["orders"]=[o for o in W["orders"] if o["cloid"]!=t["cloid"]]; W["pos"]=t["sz0"]; W["entry"]=t["lim"]
S.manage_pending(st,{},info.all_mids())   # stale snapshot: no position
tt=st["trades"].get(C); print("calls",W["calls"]); print("tracked:",bool(tt) and not tt.get("pending"), tt and (tt["stop"],tt["tp1"],tt["tp1_ok"],tt["risk_mult"],tt["primary"],tt["entry_type"]))
print("orders:",[(o["orderType"],o["sz"]) for o in W["orders"]])
assert tt and not tt.get("pending") and tt["tp1_ok"] and any("Stop" in o["orderType"] for o in W["orders"]) and any("Take" in o["orderType"] for o in W["orders"])
print("=== 10 filled, no position, no closing fill -> wait (orders kept); later closing fill -> drop")
st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["calls"]=[]
W["status"][t["cloid"]]="filled"; W["orders"]=[o for o in W["orders"] if o["cloid"]!=t["cloid"]]
S.manage_pending(st,{},info.all_mids()); print("after 1st:", C in st["trades"], [c[0] for c in W["calls"] if c[0]=="cancel"])
assert C in st["trades"] and not any(c[0]=="cancel" for c in W["calls"])
W["fills"].append({"coin":C,"dir":"Close Long","time":S.nms(),"cloid":"x"}); S.manage_pending(st,{},info.all_mids()); print("after closing fill:", C in st["trades"])
assert C not in st["trades"]
print("=== 11 drop guard: any drop path with a live position finalizes instead")
st=fresh(); W["mid"]=0.1008; ent(st); t=st["trades"][C]; W["pos"]=t["sz0"]; W["entry"]=t["lim"]; W["calls"]=[]
S._pending_drop(st,C,t,"test"); print(st["trades"][C].get("entry_type"), [c[0] for c in W["calls"]]); assert not st["trades"][C].get("pending")
print("=== 12 TP1 self-heal in manage (adopted/stripped TP)")
st=fresh(); W.update(pos=-1326.0,entry=0.043923,mid=0.04385)
st["trades"][C]=dict(side="short",entry=0.043923,sz0=1326.0,stop=0.044292,tp1=0.042718,tp1_ok=True,tp1_done=False,atr=0.00037,best=0.043923,risk_usd=1,lev=3,opened_ms=S.nms()-600000,votes={},realized=0.0,dist0=0.000804,peak=0.043796,hl_ms=S.nms())
W["orders"]=[mkorder("0x5ca151"+"b"*26,"Stop Market",1326.0,0.044292)]
S.manage(st,S.own_positions(info.user_state(0)),S.own_orders(),info.all_mids()); print(W["calls"])
assert any(c[0]=="order" and c[4]["trigger"]["tpsl"]=="tp" and c[2]==663.0 for c in W["calls"])
print("ALL CHIPFIX TESTS PASSED")
exec(open("/workspace/hlscalp/tests/focus_tests.py").read())
