import json,time,sys,urllib.request
exec(open('scan3.py').read().split("now=time.time()")[0])
out={}
for name,w in [a.split('=') for a in sys.argv[1:]]:
    s=rpc("getSignaturesForAddress",[w,{"limit":25}]) or []
    got=[]
    for x in s:
        if len(got)>=4: break
        if x.get('err'): continue
        tx=rpc("getTransaction",[x['signature'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}]); time.sleep(2)
        if not tx: continue
        m=tx['meta'];keys=[k['pubkey'] for k in tx['transaction']['message']['accountKeys']]
        if keys[0]!=w: continue
        i=keys.index(w); ds=(m['postBalances'][i]-m['preBalances'][i])/1e9
        tb={}
        for side,lst in (('pre',m['preTokenBalances']),('post',m['postTokenBalances'])):
            for b in lst:
                if b.get('owner')==w and b['mint'] not in Q: tb.setdefault(b['mint'],{})[side]=float(b['uiTokenAmount']['uiAmount'] or 0)
        for mint,v in tb.items():
            d=v.get('post',0)-v.get('pre',0)
            if d: got.append((time.strftime('%H:%M',time.gmtime(x['blockTime'])),'buy' if d>0 else 'sell',mint,round(ds,3),v.get('pre',0)==0))
    out[name]=got; print(name,got,flush=True)
json.dump(out,open('probe.json','w'))
