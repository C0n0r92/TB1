import json,urllib.request,time,sys
R="https://api.mainnet-beta.solana.com"; WS={'So11111111111111111111111111111111111111112'}
def rpc(m,p):
    for i in range(4):
        try:
            q=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
            return json.load(urllib.request.urlopen(urllib.request.Request(R,q,{"Content-Type":"application/json"}),timeout=30)).get('result')
        except Exception: time.sleep(2)
now=time.time()
for w in sys.argv[1:]:
    sig=rpc('getSignaturesForAddress',[w,{"limit":40}]) or []; found=None
    for s in [x for x in sig if not x['err'] and x['blockTime']>now-7200][:12]:
        t=rpc('getTransaction',[s['signature'],{"maxSupportedTransactionVersion":0,"encoding":"json"}]); time.sleep(0.6)
        if not t: continue
        pre={(b['mint']):float(b['uiTokenAmount']['uiAmount'] or 0) for b in t['meta']['preTokenBalances'] if b.get('owner')==w and b['mint'] not in WS}
        post={(b['mint']):float(b['uiTokenAmount']['uiAmount'] or 0) for b in t['meta']['postTokenBalances'] if b.get('owner')==w and b['mint'] not in WS}
        ch={m:post.get(m,0)-pre.get(m,0) for m in set(pre)|set(post) if abs(post.get(m,0)-pre.get(m,0))>0}
        if ch: found=(time.strftime('%H:%M:%SZ',time.gmtime(s['blockTime'])),round((now-s['blockTime'])/60),list(ch.items())[:1],s['signature'][:16]); break
    print(w, 'LAST_SWAP' , found)
