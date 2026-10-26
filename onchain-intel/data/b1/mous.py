import json,sys,os,time
sys.path.insert(0,"scripts")
os.environ["SCOUT_PUBLIC_FIRST"]="1"; os.environ["SCOUT_HELIUS_BUDGET_FILE"]="/tmp/b1budget.json"
import sol
M="J9WL4zQVCFvLTydjtHoMGcLasjhRMZomnVmp4Y2cpump"; USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
lead="2T3vXhE6rCpKvC1MdEtNYjiPJ2T9Ad4eejP5GHw119mh8S8HdMCb6q3naVTGuVamYnyWWrYJBzFVSR8VqMUtoLAL"
# page backwards from just after the leader buy
before=None; allS=[]
lt=sol.tx(lead); T=lt["blockTime"]; print("leader $2k buy at",time.strftime('%H:%M:%S',time.gmtime(T)))
s0=sol.rpc("getSignaturesForAddress",[M,{"limit":1000}]) or []
# find page containing T
while s0 and s0[-1]["blockTime"]>T+60:
    s0=sol.rpc("getSignaturesForAddress",[M,{"limit":1000,"before":s0[-1]["signature"]}]) or []
allS+=s0
for _ in range(15):
    if not allS or allS[-1]["blockTime"]<T-2400: break
    allS+=sol.rpc("getSignaturesForAddress",[M,{"limit":1000,"before":allS[-1]["signature"]}]) or []
w=[s for s in allS if T-2400<=s["blockTime"]<=T+60 and not s.get("err")]
print("sigs in window",len(w))
out=[]
for s in w:
    t=sol.tx(s["signature"])
    if not t: continue
    tok,sold,wsol,signers,acct=sol.deltas(t,M)
    usdc={}
    for side,sg in (("preTokenBalances",-1),("postTokenBalances",1)):
        for b in t["meta"].get(side) or []:
            if b["mint"]==USDC: usdc[b.get("owner")]=usdc.get(b.get("owner"),0)+sg*float(b["uiTokenAmount"]["uiAmount"] or 0)
    for o,dt in tok.items():
        if dt>0:
            usd=-usdc.get(o,0) if usdc.get(o,0)<0 else -(sold.get(o,0)+wsol.get(o,0))*102.4
            if 400<=usd<=2600: out.append((s["blockTime"],o,round(usd,2),round(usd/dt*1e6,1),s["signature"][:12]))
for r in sorted(out): print(time.strftime('%H:%M:%S',time.gmtime(r[0])),*r[1:])
