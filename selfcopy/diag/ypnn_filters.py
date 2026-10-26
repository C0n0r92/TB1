"""read-only: last-24h buys of the Ypnn wallet vs selfcopy entry filters (approx: mcap at buy = fill price * supply; liq/age from dexscreener now)"""
import json, urllib.request, time, collections
W="YpnnUu1ZPHpAzy4xggEd5pBTbu1aDayXuARsYsavNs9"; WSOL="So11111111111111111111111111111111111111112"
USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"; USDT="Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
UA={"Content-Type":"application/json","User-Agent":"Mozilla/5.0 selfcopy-diag"}
def post(u,d):
    for a in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,data=json.dumps(d).encode(),headers=UA),timeout=25))
        except Exception as e: time.sleep(1.5*(a+1))
def rpc(m,p):
    for u in ("https://solana-rpc.publicnode.com","https://api.mainnet-beta.solana.com"):
        j=post(u,{"jsonrpc":"2.0","id":1,"method":m,"params":p})
        if j and j.get("result") is not None: return j["result"]
        time.sleep(0.5)
def get(u):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=20))
    except Exception: return None
now=time.time(); sigs=[]; before=None
while True:
    p={"limit":1000}; 
    if before: p["before"]=before
    r=rpc("getSignaturesForAddress",[W,p]) or []
    sigs+= [s for s in r if s.get("blockTime",0)>=now-86400]
    if not r or r[-1].get("blockTime",0)<now-86400: break
    before=r[-1]["signature"]
sigs=[s for s in sigs if not s.get("err")]
print("ok sigs 24h:",len(sigs),flush=True)
solpx=float(get(f"https://lite-api.jup.ag/price/v3?ids={WSOL}")[WSOL]["usdPrice"])
swaps=[]
for i,s in enumerate(reversed(sigs)):
    tx=rpc("getTransaction",[s["signature"],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}]); time.sleep(0.25)
    if not tx or not tx.get("meta"): continue
    m=tx["meta"]; keys=[k["pubkey"] for k in tx["transaction"]["message"]["accountKeys"]]
    tok,pre={},{}
    for side,sg in (("preTokenBalances",-1),("postTokenBalances",1)):
        for b in m.get(side) or []:
            if b.get("owner")!=W: continue
            a=float(b["uiTokenAmount"]["uiAmountString"] or 0); tok[b["mint"]]=tok.get(b["mint"],0)+sg*a
            if sg==-1: pre[b["mint"]]=pre.get(b["mint"],0)+a
    sol=0.0
    if W in keys:
        k=keys.index(W); sol=(m["postBalances"][k]-m["preBalances"][k])/1e9 + (m.get("fee",0)/1e9 if k==0 else 0)
    sol+=tok.pop(WSOL,0); uq=tok.pop(USDC,0)+tok.pop(USDT,0)
    mv={a:b for a,b in tok.items() if abs(b)>1e-12}
    if len(mv)!=1: continue
    mint,d=next(iter(mv.items())); q=sol*solpx+uq
    side="buy" if d>0 and q<0 else "sell" if d<0 and q>0 else None
    if side: swaps.append(dict(t=tx["blockTime"],side=side,mint=mint,usd=abs(q),tokens=abs(d),pre=pre.get(mint,0.0)))
buys=[x for x in swaps if x["side"]=="buy"]
print("swaps",len(swaps),"buys",len(buys),flush=True)
info={}
for mint in {b["mint"] for b in buys}:
    j=get(f"https://api.dexscreener.com/tokens/v1/solana/{mint}") or []; time.sleep(0.3)
    j=[p for p in j if p.get("priceUsd")]
    if not j: info[mint]=None; continue
    p=max(j,key=lambda p:(p.get("liquidity") or {}).get("usd") or 0)
    px=float(p["priceUsd"]); fdv=p.get("marketCap") or p.get("fdv") or 0
    info[mint]=dict(supply=fdv/px if px else None, liq=(p.get("liquidity") or {}).get("usd") or 0, created=(p.get("pairCreatedAt") or 0)/1000, sym=p["baseToken"]["symbol"], mcap_now=fdv)
seen=set(); C=collections.Counter(); rows=[]
for b in buys:
    first = b["pre"]<=0 and b["mint"] not in seen; seen.add(b["mint"])
    i=info.get(b["mint"]); mc=(b["usd"]/b["tokens"])*i["supply"] if i and i["supply"] else None
    age=(b["t"]-i["created"])/60 if i and i["created"] else None
    paper = first and b["usd"]>=50 and mc is not None and mc>=100_000
    v2 = paper and mc>=1_000_000 and i["liq"]>=100_000 and age is not None and age>=60
    C["buys"]+=1; C["first"]+=first; C["first_ge50"]+= first and b["usd"]>=50; C["paper_pass"]+=paper; C["v2_live_pass"]+=v2
    rows.append(dict(t=time.strftime("%H:%M",time.gmtime(b["t"])),sym=i and i["sym"],usd=round(b["usd"]),first=first,mcap=round(mc) if mc else None,liq_now=round(i["liq"]) if i else None,age_min=round(age) if age else None,paper=paper,v2=v2))
json.dump(dict(counts=C,rows=rows),open("/workspace/selfcopy/diag/ypnn_filters.json","w"),indent=1)
print(dict(C)); print("distinct mints bought:",len(seen))
for r in rows[-40:]: print(r)
