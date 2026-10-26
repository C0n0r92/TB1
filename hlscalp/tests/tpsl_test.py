import os,json,time,secrets
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.utils.types import Cloid
A=os.environ["HL_ACCOUNT"].strip(); w=Account.from_key(os.environ.pop("HL_API_KEY").strip())
assert w.address.lower()!=A.lower()
ex=Exchange(w,constants.MAINNET_API_URL,account_address=A); info=Info(constants.MAINNET_API_URL,skip_ws=True)
C="DOGE"
us=info.user_state(A); assert not any(p["position"]["coin"]==C and float(p["position"]["szi"])!=0 for p in us["assetPositions"])
mid=float(info.all_mids()[C]); lim=round(mid*0.80,5); sz=float(int(11.5/lim)+1)
sl=round(lim*0.97,5); tp=round(lim*1.03,5)
cid=lambda k:Cloid.from_str("0x5ca1"+k+secrets.token_hex(13))
c0,c1,c2=cid("e0"),cid("51"),cid("7a")
reqs=[{"coin":C,"is_buy":True,"sz":sz,"limit_px":lim,"order_type":{"limit":{"tif":"Gtc"}},"reduce_only":False,"cloid":c0},
      {"coin":C,"is_buy":False,"sz":sz,"limit_px":round(sl*0.9,5),"order_type":{"trigger":{"triggerPx":sl,"isMarket":True,"tpsl":"sl"}},"reduce_only":True,"cloid":c1},
      {"coin":C,"is_buy":False,"sz":round(sz/2),"limit_px":round(tp*0.9,5),"order_type":{"trigger":{"triggerPx":tp,"isMarket":True,"tpsl":"tp"}},"reduce_only":True,"cloid":c2}]
print("mid",mid,"lim",lim,"sz",sz,"ntl",round(sz*lim,2))
r=ex.bulk_orders(reqs,grouping="normalTpsl"); print("T1 normalTpsl:",json.dumps(r)[:600])
time.sleep(1)
oo=[o for o in info.frontend_open_orders(A) if o["coin"]==C]; print("open:",[(o["oid"],o["orderType"],o.get("cloid"),o["sz"],o.get("triggerPx"),o.get("isPositionTpsl")) for o in oo])
for c in (c1,c2): q=info.query_order_by_cloid(A,c); print("child",c.to_raw()[:8],(q.get("order") or {}).get("status"),q.get("status"))
oid=r["response"]["data"]["statuses"][0].get("resting",{}).get("oid")
print("cancel parent:",ex.cancel(C,oid)); time.sleep(1)
for c in (c0,c1,c2): q=info.query_order_by_cloid(A,c); print("after cancel",c.to_raw()[:8],(q.get("order") or {}).get("status"),q.get("status"))
# T2: positionTpsl SL while flat
c3=cid("51")
r2=ex.bulk_orders([{"coin":C,"is_buy":False,"sz":sz,"limit_px":round(sl*0.9,5),"order_type":{"trigger":{"triggerPx":sl,"isMarket":True,"tpsl":"sl"}},"reduce_only":True,"cloid":c3}],grouping="positionTpsl")
print("T2 positionTpsl flat:",json.dumps(r2)[:400])
time.sleep(1)
oo=[o for o in info.frontend_open_orders(A) if o["coin"]==C]; print("open after T2:",[(o["oid"],o["orderType"],o.get("cloid")) for o in oo])
for o in oo: print("cleanup",ex.cancel(C,o["oid"]))
print("final open DOGE:",[o for o in info.frontend_open_orders(A) if o["coin"]==C])
