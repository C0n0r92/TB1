import json,time
from hyperliquid.info import Info
from hyperliquid.utils import constants
A="0x8bf46912296ecE936D446f3448e383054100c482"
info=Info(constants.MAINNET_API_URL,skip_ws=True)
t0=int(time.mktime(time.strptime("2026-10-24 18:00","%Y-%m-%d %H:%M"))*1000)
import calendar
t0=calendar.timegm(time.strptime("2026-10-24 18:00","%Y-%m-%d %H:%M"))*1000
now=int(time.time()*1000)
fills=[];s=t0
while True:
    b=info.user_fills_by_time(A,s,now)
    fills+=b
    if len(b)<2000: break
    s=max(f["time"] for f in b)+1
fund=info.user_funding_history(A,t0,now)
port=info.post("/info",{"type":"portfolio","user":A})
json.dump({"fills":fills,"funding":fund,"portfolio":port},open("/workspace/review2/hl.json","w"))
print(len(fills),len(fund))
