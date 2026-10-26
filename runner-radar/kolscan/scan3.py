import json,time,urllib.request
RPCS=["https://solana-rpc.publicnode.com","https://api.mainnet-beta.solana.com"]
def rpc(m,p):
    for k in range(8):
        u=RPCS[k%2]
        try:
            req=urllib.request.Request(u,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"scan"})
            j=json.load(urllib.request.urlopen(req,timeout=25))
            if "result" in j: return j["result"]
        except Exception: time.sleep(1.5+k)
    return None
Q={"So11111111111111111111111111111111111111112","EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
now=time.time()
import sys
W=sys.argv[1].split(',')
rows=[r for r in json.load(open('scan1.json')) if r['name'] in W]
res={}
for r in rows:
    w=r['wallet']; s=rpc("getSignaturesForAddress",[w,{"limit":60}]) or []
    s=[x for x in s if not x.get('err') and x.get('blockTime') and now-x['blockTime']<7200][:18]
    swaps=[]
    for x in s:
        tx=rpc("getTransaction",[x['signature'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}])
        if not tx or not tx.get('meta'):
            print('  miss',flush=True); continue
        m=tx['meta']; keys=[k['pubkey'] if isinstance(k,dict) else k for k in tx['transaction']['message']['accountKeys']]
        signer = keys[0]==w
        def bal(lst):
            d={}
            for b in lst or []:
                if b.get('owner')==w: d[b['mint']]=d.get(b['mint'],0)+float(b['uiTokenAmount']['uiAmount'] or 0)
            return d
        pre,post=bal(m.get('preTokenBalances')),bal(m.get('postTokenBalances'))
        i=keys.index(w) if w in keys else None
        dsol=(m['postBalances'][i]-m['preBalances'][i])/1e9 if i is not None else 0
        for mint in set(pre)|set(post):
            if mint in Q: continue
            d=post.get(mint,0)-pre.get(mint,0)
            if abs(d)<=0: continue
            q=dsol+sum(post.get(qm,0)-pre.get(qm,0) for qm in Q if qm!="So11111111111111111111111111111111111111112")/190
            side='buy' if d>0 and q<0 else ('sell' if d<0 and q>0 else None)
            if side: swaps.append(dict(ts=x['blockTime'],side=side,mint=mint,sol=round(abs(q),3),pre=pre.get(mint,0),signer=signer))
        time.sleep(0.6)
    res[r['name']]=dict(wallet=w,swaps=swaps); 
    b=[z for z in swaps if z['side']=='buy']
    print(r['name'],len(s),'tx',len(b),'buys',len([z for z in b if not z['pre']]),'first',len(swaps)-len(b),'sells',flush=True)
json.dump(res,open('scan3.json','w'),indent=1)
