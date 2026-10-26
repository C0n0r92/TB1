import requests, json, time, sys
H={"Accept":"application/json"}
def get(u):
    for i in range(4):
        r=requests.get(u,headers=H,timeout=30)
        if r.status_code==429: time.sleep(15); continue
        time.sleep(2.2); return r.json() if r.ok else None
    return None
pools={}
# oldcoins main pairs
d=json.load(open('/workspace/onchain-intel/oldcoins-intel.json'))
for t in d['tokens']:
    pools[t['main_pair']]={'sym':t['symbol'],'mint':t['mint'],'src':'oldcoins','mcap':t['mcap_usd'],'liq':t['liq_usd']}
# GT top pools by volume (several pages) + trending
for path in ['pools?sort=h24_volume_usd_desc&page=%d'%p for p in range(1,8)]+['trending_pools?page=1','trending_pools?page=2']:
    j=get('https://api.geckoterminal.com/api/v2/networks/solana/'+path)
    for x in (j or {}).get('data',[]):
        a=x['attributes']; fd=float(a.get('market_cap_usd') or a.get('fdv_usd') or 0); lq=float(a.get('reserve_in_usd') or 0)
        cr=a.get('pool_created_at') or ''
        mint=x['relationships']['base_token']['data']['id'].replace('solana_','')
        if 1e6<=fd<=2e8 and lq>=1e5:
            pools.setdefault(a['address'],{'sym':a['name'],'mint':mint,'src':path.split('?')[0],'mcap':fd,'liq':lq,'created':cr,'vol24':a['volume_usd']['h24']})
json.dump(pools,open('data/pools.json','w'),indent=0); print(len(pools))
