import json,time,urllib.request
RPCS=["https://solana-rpc.publicnode.com","https://api.mainnet-beta.solana.com"]
def rpc(m,p):
    for u in RPCS*2:
        try:
            req=urllib.request.Request(u,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"scan"})
            j=json.load(urllib.request.urlopen(req,timeout=20))
            if "result" in j: return j["result"]
        except Exception as e: time.sleep(1)
    return None
if __name__!="__main__": raise SystemExit
now=time.time(); out=[]
for r in json.load(open('kol.json')):
    s=rpc("getSignaturesForAddress",[r['wallet'],{"limit":200}]) or []
    ok=[x for x in s if not x.get('err') and x.get('blockTime')]
    n1=sum(1 for x in ok if now-x['blockTime']<3600); n2=sum(1 for x in ok if now-x['blockTime']<7200)
    last=max((x['blockTime'] for x in ok),default=0)
    r.update(sigs_1h=n1,sigs_2h=n2,idle_min=round((now-last)/60) if last else None)
    out.append(r); print(r['name'],n1,n2,r['idle_min'],flush=True); time.sleep(0.3)
json.dump(out,open('scan1.json','w'),indent=1)
