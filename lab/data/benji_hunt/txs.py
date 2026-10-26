import json, time, urllib.request, os
RPC="https://api.mainnet-beta.solana.com"; MINT="6bW6xsZxYqcvqabk9rRgQwgjPNwe8SACPusx5o1wpump"
w=json.load(open('fomo_window.json')); w=[x for x in w if x['blockTime']<1792788130]; w.sort(key=lambda x:-x['blockTime'])   # pre-wave, latest first
cache=json.load(open('tx_cache.json')) if os.path.exists('tx_cache.json') else {}
def post(body):
    r=urllib.request.Request(RPC,json.dumps(body).encode(),{"Content-Type":"application/json"}); return json.load(urllib.request.urlopen(r,timeout=40))
todo=[x['signature'] for x in w if x['signature'] not in cache]; B=10; i=0
while i<len(todo):
    chunk=todo[i:i+B]
    body=[{"jsonrpc":"2.0","id":k,"method":"getTransaction","params":[sg,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]} for k,sg in enumerate(chunk)]
    try: res=post(body)
    except Exception as e: print("exc",e,flush=True); time.sleep(10); continue
    if isinstance(res,dict): print("err",str(res)[:200],flush=True); time.sleep(10); continue
    bad=0
    for r in res:
        sg=chunk[r['id']]
        if 'result' not in r or r['result'] is None: bad+=1; continue
        t=r['result']; m=t.get('meta') or {}
        pre={(b['owner'],b['mint']):float(b['uiTokenAmount']['uiAmount'] or 0) for b in m.get('preTokenBalances') or []}
        post_={(b['owner'],b['mint']):float(b['uiTokenAmount']['uiAmount'] or 0) for b in m.get('postTokenBalances') or []}
        d={o:post_.get((o,mn),0)-pre.get((o,mn),0) for (o,mn) in set(pre)|set(post_) if mn==MINT}
        keys=[a['pubkey'] if isinstance(a,dict) else a for a in t['transaction']['message']['accountKeys']]
        # stablecoin/SOL deltas per owner
        usdc="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        du={o:post_.get((o,mn),0)-pre.get((o,mn),0) for (o,mn) in set(pre)|set(post_) if mn==usdc}
        sol={keys[k]:(m['postBalances'][k]-m['preBalances'][k])/1e9 for k in range(len(keys))}
        cache[sg]={"bt":t.get('blockTime'),"truth":d,"usdc":du,"sol":{k:v for k,v in sol.items() if abs(v)>0.001},"signers":[a['pubkey'] for a in t['transaction']['message']['accountKeys'] if isinstance(a,dict) and a.get('signer')]}
    if bad==len(chunk): print("all null, backoff",flush=True); time.sleep(15); continue
    i+=B; json.dump(cache,open('tx_cache.json.tmp','w')); os.replace('tx_cache.json.tmp','tx_cache.json')
    print(i,len(todo),sum(1 for v in cache.values() if any(x>0 for x in v['truth'].values())),flush=True); time.sleep(2.5)
