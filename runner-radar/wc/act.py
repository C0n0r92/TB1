import json,requests,time,statistics,sys
U="https://api.mainnet-beta.solana.com"
def rpc(m,p):
    for u in [U,"https://solana-rpc.publicnode.com"]:
        try:
            r=requests.post(u,json={"jsonrpc":"2.0","id":1,"method":m,"params":p},timeout=30).json()
            if 'result' in r: return r['result']
        except Exception: pass
        time.sleep(1)
now=time.time()
for w in sys.argv[1:]:
    S=rpc("getSignaturesForAddress",[w,{"limit":1000}]) or []
    ts=[s['blockTime'] for s in S if s.get('blockTime')]
    if not ts: print(w,'none');continue
    span=(max(ts)-min(ts))/3600
    n24=sum(1 for t in ts if now-t<86400)
    print(w[:8],'n',len(ts),'last_h_ago',round((now-max(ts))/3600,2),'span_h',round(span,1),'tx24h(cap1000)',n24,'err',sum(1 for s in S if s.get('err')))
    time.sleep(1.5)
