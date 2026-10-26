"""GeckoTerminal public API: trending/top pools on Solana (pool age>=6h, fdv 200k-50M), then last trades >=$100 per pool; count distinct pools bought per wallet. Read-only."""
import json,urllib.request,time,collections
def get(u):
    for i in range(3):
        try:
            r=urllib.request.Request(u,headers={'Accept':'application/json','User-Agent':'scout-readonly/1.0'}); return json.load(urllib.request.urlopen(r,timeout=25))
        except Exception as e: print('err',u[-60:],e); time.sleep(4)
pools={}
for path in ['trending_pools?duration=24h&page=1','trending_pools?duration=24h&page=2','trending_pools?duration=6h&page=1','pools?page=1&sort=h24_volume_usd_desc','pools?page=2&sort=h24_volume_usd_desc']:
    d=get('https://api.geckoterminal.com/api/v2/networks/solana/'+path); time.sleep(2.2)
    for p in (d or {}).get('data',[]):
        a=p['attributes']; age=(time.time()-time.mktime(time.strptime(a['pool_created_at'][:19],'%Y-%m-%dT%H:%M:%S')))/3600
        fdv=float(a.get('fdv_usd') or 0)
        if age>=6 and 2e5<=fdv<=5e7: pools[a['address']]=dict(name=a['name'],fdv=fdv,age_h=round(age,1))
print('pools',len(pools))
W=collections.defaultdict(lambda:{'pools':set(),'buy_usd':0,'n':0})
for pa in list(pools)[:30]:
    d=get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{pa}/trades?trade_volume_in_usd_greater_than=100'); time.sleep(2.2)
    for t in (d or {}).get('data',[]):
        a=t['attributes']
        if a['kind']=='buy': x=W[a['tx_from_address']]; x['pools'].add(pa); x['buy_usd']+=float(a['volume_in_usd']); x['n']+=1
out={w:dict(pools=len(v['pools']),buys=v['n'],buy_usd=round(v['buy_usd'])) for w,v in W.items() if len(v['pools'])>=2}
json.dump(dict(pools=pools,wallets=out),open('gt/mine_2155.json','w'),indent=0)
print('wallets>=2 pools',len(out))
