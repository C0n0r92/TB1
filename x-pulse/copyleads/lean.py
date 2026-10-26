"""Read-only: sample a wallet's recent buys via PUBLIC Solana RPC (no keys), then DexScreener for token age/mcap."""
import json, sys, time, urllib.request
RPCS=["https://solana-rpc.publicnode.com","https://api.mainnet-beta.solana.com"]
WSOL="So11111111111111111111111111111111111111112"
STABLE={"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",WSOL}
def rpc(m,p):
    for a in range(6):
        try:
            r=json.loads(urllib.request.urlopen(urllib.request.Request(RPCS[a%2],data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"curl/8.5.0"}),timeout=30).read())
            if "result" in r: return r["result"]
            if "error" in r and r["error"].get("code") not in (429,-32429): return None
        except Exception: pass
        time.sleep(1+a)
def get(u):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=30).read())
        except Exception: time.sleep(2)
def buys(w,n=80):
    out=[]; s=rpc("getSignaturesForAddress",[w,{"limit":n}]) or []
    for x in s:
        if x.get("err"): continue
        t=rpc("getTransaction",[x["signature"],{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]); time.sleep(0.25)
        if not t: continue
        m=t["meta"]; d={}
        for side,sg in (("preTokenBalances",-1),("postTokenBalances",1)):
            for b in m.get(side) or []:
                if b.get("owner")!=w: continue
                d[b["mint"]]=d.get(b["mint"],0)+sg*float(b["uiTokenAmount"]["uiAmount"] or 0)
        for mint,v in d.items():
            if v>0 and mint not in STABLE: out.append({"mint":mint,"ts":t["blockTime"],"sig":x["signature"]})
    return out
res={}
for w in sys.argv[1:]:
    b=buys(w); mints=list({x["mint"] for x in b})[:30]; info={}
    for i in range(0,len(mints),30):
        r=get("https://api.dexscreener.com/tokens/v1/solana/"+",".join(mints[i:i+30])) or []
        for p in r:
            mt=p["baseToken"]["address"]; 
            if mt in info and (info[mt].get("liq") or 0)>=((p.get("liquidity") or {}).get("usd") or 0): continue
            info[mt]={"sym":p["baseToken"]["symbol"],"created":(p.get("pairCreatedAt") or 0)/1000,"mcap":p.get("marketCap") or p.get("fdv"),"liq":(p.get("liquidity") or {}).get("usd"),"dex":p.get("dexId")}
    seen=set(); rows=[]
    for x in sorted(b,key=lambda x:x["ts"]):
        if x["mint"] in seen: continue
        seen.add(x["mint"]); i=info.get(x["mint"],{})
        age=(x["ts"]-i["created"])/3600 if i.get("created") else None
        rows.append({**x,**i,"age_h_at_buy":round(age,2) if age is not None else None})
    res[w]=rows
    ages=[r["age_h_at_buy"] for r in rows if r["age_h_at_buy"] is not None]
    old=sum(1 for a in ages if a>1); mc=sum(1 for r in rows if (r.get("mcap") or 0)>=1e6)
    print(w,"sigs_buys",len(b),"distinct",len(rows),"known_age",len(ages),"older1h",old,"mcap_now>=1M",mc,flush=True)
json.dump(res,open("lean_%d.json"%int(time.time()),"w"),indent=1)
