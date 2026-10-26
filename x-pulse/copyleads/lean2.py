"""Read-only. Public Solana RPC (no keys) + DexScreener public API. Position opens in a wallet's last N txs."""
import json, sys, time, urllib.request, concurrent.futures as cf
RPCS=["https://api.mainnet-beta.solana.com","https://solana-rpc.publicnode.com"]
SKIP={"So11111111111111111111111111111111111111112","EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
def rpc(m,p,k=0):
    for a in range(6):
        try:
            r=json.loads(urllib.request.urlopen(urllib.request.Request(RPCS[(a+k)%2],data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"curl/8.5.0"}),timeout=30).read())
            if "result" in r: return r["result"]
        except Exception: pass
        time.sleep(1.5*(a+1))
def get(u):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"curl/8.5.0"}),timeout=30).read())
        except Exception: time.sleep(2)
def opens(w,n):
    out=[]; sigs=[]; before=None
    while len(sigs)<n:
        p={"limit":min(1000,n-len(sigs))}
        if before: p["before"]=before
        s=rpc("getSignaturesForAddress",[w,p]) or []
        if not s: break
        sigs+=s; before=s[-1]["signature"]
    ok=0
    for i,x in enumerate(sigs):
        if x.get("err"): continue
        t=rpc("getTransaction",[x["signature"],{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}],i); time.sleep(0.12)
        if not t: continue
        ok+=1; m=t["meta"]; pre={}; post={}
        for b in m.get("preTokenBalances") or []:
            if b.get("owner")==w: pre[b["mint"]]=float(b["uiTokenAmount"]["uiAmount"] or 0)
        for b in m.get("postTokenBalances") or []:
            if b.get("owner")==w: post[b["mint"]]=float(b["uiTokenAmount"]["uiAmount"] or 0)
        for mint,v in post.items():
            if mint in SKIP: continue
            if v>0 and pre.get(mint,0)==0: out.append({"mint":mint,"ts":t["blockTime"],"sig":x["signature"]})
    span=(sigs[0]["blockTime"]-sigs[-1]["blockTime"])/3600 if sigs else 0
    return out,len(sigs),ok,span
def run(w):
    b,ns,ok,span=opens(w,int(sys.argv[1])); mints=list(dict.fromkeys(x["mint"] for x in sorted(b,key=lambda x:-x["ts"])))[:60]; info={}
    for i in range(0,len(mints),30):
        for p in get("https://api.dexscreener.com/tokens/v1/solana/"+",".join(mints[i:i+30])) or []:
            mt=p["baseToken"]["address"]; liq=(p.get("liquidity") or {}).get("usd") or 0
            c=(p.get("pairCreatedAt") or 0)/1000
            if mt in info:
                if c and (not info[mt]["created"] or c<info[mt]["created"]): info[mt]["created"]=c
                if liq<=(info[mt]["liq"] or 0): continue
            info.setdefault(mt,{"created":c})
            info[mt].update({"sym":p["baseToken"]["symbol"],"mcap":p.get("marketCap") or p.get("fdv"),"liq":liq,"dex":p.get("dexId")})
    rows=[]; seen=set()
    for x in sorted(b,key=lambda x:-x["ts"]):
        if x["mint"] in seen: continue
        seen.add(x["mint"]); i=info.get(x["mint"],{})
        age=(x["ts"]-i["created"])/3600 if i.get("created") else None
        rows.append({**x,**i,"age_h_at_buy":round(age,2) if age is not None else None})
    return w,{"sigs":ns,"tx_ok":ok,"span_h":round(span,1),"opens":rows}
res={}
with cf.ThreadPoolExecutor(3) as ex:
    for w,r in ex.map(run,sys.argv[2:]):
        res[w]=r; rows=r["opens"]; ages=[x["age_h_at_buy"] for x in rows if x["age_h_at_buy"] is not None]
        print(w,"sigs",r["sigs"],"ok",r["tx_ok"],"span_h",r["span_h"],"opens",len(rows),"age_known",len(ages),"older1h",sum(a>1 for a in ages),"older24h",sum(a>24 for a in ages),"mcapNow>=1M",sum((x.get("mcap") or 0)>=1e6 for x in rows),flush=True)
        json.dump(res,open("lean2_out.json","w"),indent=1)
