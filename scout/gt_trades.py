import requests, json, time, collections
P=json.load(open('data/pools.json')); out={}
for a,v in P.items():
    for i in range(4):
        r=requests.get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{a}/trades?trade_volume_in_usd_greater_than=50',timeout=30)
        if r.status_code==429: time.sleep(20); continue
        break
    time.sleep(2.1)
    if not r.ok: print('fail',v['sym'],r.status_code); continue
    out[a]=[x['attributes'] for x in r.json().get('data',[])]
json.dump(out,open('data/gt_trades.json','w')); print(len(out), sum(len(x) for x in out.values()))
