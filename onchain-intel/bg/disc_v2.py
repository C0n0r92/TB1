"""Creative discovery (a): wallets repeatedly buying (>= $100) tokens that ran 24h, from GeckoTerminal trending/top pools + per-pool trade lists. Read-only."""
import json,sys,time,collections
sys.path.insert(0,'/workspace/onchain-intel/bg'); from fetchlayer import get
GT='https://api.geckoterminal.com/api/v2/networks/solana/'
pools={}
for path in ['trending_pools?duration=24h&page=1','trending_pools?duration=24h&page=2','trending_pools?duration=6h&page=1','pools?sort=h24_volume_usd_desc&page=1']:
    r=get(GT+path) or {}
    for p in r.get('data',[]):
        a=p['attributes']; ch=float((a.get('price_change_percentage') or {}).get('h24') or 0)
        fdv=float(a.get('fdv_usd') or 0); age=a.get('pool_created_at')
        if ch>=50 and fdv>=30000: pools[a['address']]=dict(name=a['name'],ch24=ch,fdv=fdv,created=age)
print('runner pools',len(pools),flush=True)
hits=collections.defaultdict(lambda: dict(pools=set(),buy_usd=0.0,sell_usd=0.0,nb=0,first_ts={}))
for addr in list(pools)[:22]:
    r=get(GT+f'pools/{addr}/trades?trade_volume_in_usd_greater_than=100') or {}
    for t in r.get('data',[]):
        a=t['attributes']; w=a['tx_from_address']; v=float(a.get('volume_in_usd') or 0)
        h=hits[w]
        if a['kind']=='buy': h['pools'].add(addr); h['buy_usd']+=v; h['nb']+=1
        else: h['sell_usd']+=v
out=[]
for w,h in hits.items():
    if len(h['pools'])>=2: out.append(dict(wallet=w,runners=len(h['pools']),buy_usd=round(h['buy_usd']),sell_usd=round(h['sell_usd']),buys=h['nb'],pool_names=[pools[p]['name'] for p in h['pools']]))
out.sort(key=lambda x:(-x['runners'],-x['sell_usd']))
json.dump(dict(generated=time.strftime('%Y-%m-%dT%H:%M:%SZ'),runner_pools=pools,hits=out),open('disc_v2.json','w'),indent=1)
for x in out[:25]: print(x['wallet'],x['runners'],x['buy_usd'],x['sell_usd'],x['pool_names'][:4])
