import sys,json,time
sys.path.insert(0,'/workspace/onchain-intel/scripts')
import leader_activity as la
la.RPCS=["https://api.mainnet-beta.solana.com","https://solana-rpc.publicnode.com"]
RELAY="AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51"; FEE="R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX"
now=time.time(); out={}
for h,w in [a.split('=') for a in sys.argv[1:]]:
    sigs=[]; before=None
    while len(sigs)<int(__import__('os').environ.get('NS','300')):
        p={"limit":1000};
        if before: p["before"]=before
        r=la.rpc("getSignaturesForAddress",[w,p]) or []
        if not r: break
        sigs+=r; before=r[-1]["signature"]
        if len(r)<1000: break
    ok=[s for s in sigs if s.get("err") is None]
    swaps=[];relay=0;n=0
    for s in ok[:40]:
        tx=la.rpc("getTransaction",[s["signature"],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}]); n+=1
        if la.classify(tx,w):
            keys=[k["pubkey"] for k in tx["transaction"]["message"]["accountKeys"]]
            rl=keys[0]==RELAY or FEE in keys
            relay+=rl; swaps.append((s["blockTime"],s["signature"][:20],rl))
        time.sleep(0.25)
    out[h]=dict(wallet=w,n_sigs=len(sigs),newest_sig_min=round((now-sigs[0]["blockTime"])/60) if sigs else None,
       oldest_sig_utc=time.strftime('%m-%d %H:%MZ',time.gmtime(sigs[-1]["blockTime"])) if sigs else None,
       checked=n,swaps=len(swaps),relayed=relay,
       last_swap_utc=time.strftime('%m-%d %H:%MZ',time.gmtime(swaps[0][0])) if swaps else None,
       last_swap_min=round((now-swaps[0][0])/60) if swaps else None,
       swaps_6h=sum(1 for t,_,_ in swaps if now-t<6*3600), swaps_24h=sum(1 for t,_,_ in swaps if now-t<86400),
       sample=swaps[:3])
    print(json.dumps({h:out[h]}),flush=True)
json.dump(out,open('/workspace/onchain-intel/tmp/verify_top_%d.json'%int(now),'w'),indent=1)
