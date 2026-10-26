import json,requests,time,datetime
W=json.load(open('wallets.json'))
RPC='https://api.mainnet-beta.solana.com'
out={}
for n,(e,s) in W.items():
    r=requests.post(RPC,json={"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":[s,{"limit":1000}]},timeout=30).json()
    res=r.get('result',[])
    out[n]=res
    ts=[x['blockTime'] for x in res if x.get('blockTime')]
    print(n,len(res), datetime.datetime.utcfromtimestamp(max(ts)) if ts else None, datetime.datetime.utcfromtimestamp(min(ts)) if ts else None, r.get('error'))
    time.sleep(1.5)
json.dump(out,open('sol_sigs.json','w'))
