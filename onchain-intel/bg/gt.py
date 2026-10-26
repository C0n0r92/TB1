import json,urllib.request,time,collections
H={'User-Agent':'scout-readonly/1.0','Accept':'application/json'}
def get(u):
    for i in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=30).read())
        except Exception as e: print('err',u[-60:],e); time.sleep(5)
B='https://api.geckoterminal.com/api/v2/networks/solana'
pools={}
for path in ['trending_pools?duration=24h&page=1','trending_pools?duration=24h&page=2','trending_pools?duration=6h&page=1','trending_pools?duration=1h&page=1','pools?sort=h24_volume_usd_desc&page=1','pools?sort=h24_tx_count_desc&page=1','new_pools?page=1']:
    d=get(f'{B}/{path}'); time.sleep(2.2)
    for p in (d or {}).get('data',[]):
        a=p['attributes']; pools[p['attributes']['address']]=dict(name=a['name'],vol=float(a['volume_usd']['h24'] or 0),created=a.get('pool_created_at'))
print(len(pools),'pools')
W=collections.defaultdict(lambda: dict(buys=0,sells=0,pools=set(),usd=0.0))
for addr,p in pools.items():
    d=get(f'{B}/pools/{addr}/trades?trade_volume_in_usd_greater_than=100'); time.sleep(2.2)
    for t in (d or {}).get('data',[]):
        a=t['attributes']; w=a['tx_from_address']; x=W[w]
        x['buys' if a['kind']=='buy' else 'sells']+=1; x['pools'].add(addr); x['usd']+=float(a['volume_in_usd'] or 0)
out={w:dict(v,pools=sorted(v['pools'])) for w,v in W.items()}
json.dump(dict(pools=pools,wallets=out),open('gt/gt_wallets.json','w'))
top=sorted(out.items(),key=lambda kv:(-len(kv[1]['pools']),-(kv[1]['buys']+kv[1]['sells'])))
for w,v in top[:60]: print(w,len(v['pools']),v['buys'],v['sells'],round(v['usd']))
