import json,sys,time,os
sys.path.insert(0,"scripts")
os.environ["SCOUT_PUBLIC_FIRST"]="1"; os.environ["SCOUT_HELIUS_BUDGET_FILE"]="/tmp/b1budget.json"
json.dump({"limit":0,"used":0,"denied":0},open("/tmp/b1budget.json","w"))   # public only, 0 Helius
import sol
M="6bW6xsZxYqcvqabk9rRgQwgjPNwe8SACPusx5o1wpump"
USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
d=json.load(open(sys.argv[3] if len(sys.argv)>3 else "data/b1/fomo_truth_window.json"))
which=sys.argv[1]; lim=int(sys.argv[2]) if len(sys.argv)>2 else 100000
rows=[]
for s in [x for k,v in d.items() if k.startswith(which) for x in v][:lim]:
    t=sol.tx(s["signature"])
    if not t: rows.append({"sig":s["signature"],"err":"fetch"}); continue
    tok,sold,wsol,signers,acct=sol.deltas(t,M)
    usdc={}
    for side,sg in (("preTokenBalances",-1),("postTokenBalances",1)):
        for b in t["meta"].get(side) or []:
            if b["mint"]==USDC: usdc[b.get("owner")]=usdc.get(b.get("owner"),0)+sg*float(b["uiTokenAmount"]["uiAmount"] or 0)
    for o,dt in tok.items():
        if abs(dt)<1e-6: continue
        rows.append({"sig":s["signature"],"ts":s["blockTime"],"owner":o,"truth":round(dt,2),"sol":round(sold.get(o,0)+wsol.get(o,0),4),"usdc":round(usdc.get(o,0),2),"signers":signers[:3]})
json.dump(rows,open(f"data/b1/parsed_{which}.json","w"),indent=0)
for r in rows:
    if r.get("truth",0)>0: print(time.strftime('%H:%M:%S',time.gmtime(r["ts"])),r["owner"],r["truth"],"sol",r["sol"],"usdc",r["usdc"],r["signers"][0][:6])
