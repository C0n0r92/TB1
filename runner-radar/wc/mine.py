import json,sys,time,os,requests
os.environ.setdefault("SCOUT_HELIUS_BUDGET_FILE","/workspace/runner-radar/wc/budget.json")
sys.path.insert(0,'/workspace/onchain-intel/scripts')
import sol
if not os.path.exists(sol.BUDGET_FILE): json.dump({"limit":700,"used":0,"denied":0},open(sol.BUDGET_FILE,'w'))
W=json.load(open('windows.json'))
SEL={'Moustache':None,'MI':None,'McRib':None,'Hercules':None,'Pumptache':None,'mil':None,'SWORDOPE':None,'YAGI':None,'AOP':(1792634400,1792700000)}
WSOL="So11111111111111111111111111111111111111112"
QUOTE={WSOL,"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
key=sol._helius_key()
def gtfa(addr,gte,lte):
    if not sol.budget_take(10,"gtfa"): return []
    cfg={"transactionDetails":"full","sortOrder":"asc","limit":100,"encoding":"jsonParsed","maxSupportedTransactionVersion":1,
         "filters":{"blockTime":{"gte":int(gte),"lte":int(lte)},"status":"succeeded"}}
    try:
        r=requests.post("https://mainnet.helius-rpc.com/?api-key="+key,json={"jsonrpc":"2.0","id":1,"method":"getTransactionsForAddress","params":[addr,cfg]},timeout=60).json()
    except Exception as e: print('err',e); return []
    if 'error' in r: print('rpcerr',r['error']); return []
    return (r.get('result') or {}).get('data') or []
out=json.load(open('buys.json')) if os.path.exists('buys.json') else {}
for s,ov in SEL.items():
    if s in out: continue
    w=W[s]; a,b=ov or (w['win_start'],w['win_end']+900)
    mint=w['mint']; buys=[]
    n=6; step=(b-a)/n
    for k in range(n):
        txs=gtfa(w['pool'],a+k*step,a+(k+1)*step)
        for t in txs:
            ak=t["transaction"]["message"]["accountKeys"]
            keys=[x["pubkey"] if isinstance(x,dict) else x for x in ak]
            signer=keys[0]; m=t["meta"]
            pre=sum(float(x["uiTokenAmount"]["uiAmount"] or 0) for x in m.get("preTokenBalances") or [] if x.get("owner")==signer and x["mint"]==mint)
            post=sum(float(x["uiTokenAmount"]["uiAmount"] or 0) for x in m.get("postTokenBalances") or [] if x.get("owner")==signer and x["mint"]==mint)
            dw=sum(float(x["uiTokenAmount"]["uiAmount"] or 0) for x in m.get("postTokenBalances") or [] if x.get("owner")==signer and x["mint"]==WSOL)-sum(float(x["uiTokenAmount"]["uiAmount"] or 0) for x in m.get("preTokenBalances") or [] if x.get("owner")==signer and x["mint"]==WSOL)
            dsol=(m["postBalances"][0]-m["preBalances"][0])/1e9+dw
            if post-pre>0 and dsol<-0.05:
                buys.append(dict(w=signer,ts=t["blockTime"],sol=round(-dsol,3),tok=post-pre,price_sol=-dsol/(post-pre),sig=t["transaction"]["signatures"][0]))
        print(s,k,len(txs),len(buys),flush=True)
    out[s]=dict(mint=mint,pool=w['pool'],peak=w['peak_mcap'],peak_ts=w['peak_ts'],buys=buys)
    json.dump(out,open('buys.json','w'))
print(json.load(open(sol.BUDGET_FILE)))
