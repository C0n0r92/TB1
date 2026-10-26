import os,json,time
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
A=os.environ["HL_ACCOUNT"].strip(); w=Account.from_key(os.environ.pop("HL_API_KEY").strip()); assert w.address.lower()!=A.lower()
ex=Exchange(w,constants.MAINNET_API_URL,account_address=A); info=Info(constants.MAINNET_API_URL,skip_ws=True)
C="DOGE"; mid=float(info.all_mids()[C]); sl=round(mid*0.78,5); sz=187.0
r=ex.order(C,False,sz,round(sl*0.9,5),{"trigger":{"triggerPx":sl,"isMarket":True,"tpsl":"sl"}},reduce_only=True)
print("T3 na reduce-only SL flat:",json.dumps(r)[:300])
oid=r["response"]["data"]["statuses"][0].get("resting",{}).get("oid")
try:
  for t in (2,20,45):
    time.sleep(t-(0 if t==2 else (2 if t==20 else 20)))
    oo=[o for o in info.frontend_open_orders(A) if o["coin"]==C]; print(t,"s open:",[(o["oid"],o["orderType"],o["sz"],o.get("reduceOnly"),o.get("isPositionTpsl")) for o in oo])
finally:
  for o in [o for o in info.frontend_open_orders(A) if o["coin"]==C]: print("cleanup",ex.cancel(C,o["oid"]))
  print("final:",[o for o in info.frontend_open_orders(A) if o["coin"]==C])
