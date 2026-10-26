import json,urllib.request,time
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=30))
pools={}
for dur in ["24h","6h","1h"]:
  for page in [1,2,3]:
    try:
      j=get(f"https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?duration={dur}&page={page}&include=base_token")
    except Exception as e: print(dur,page,e); continue
    toks={t['id']:t['attributes'] for t in j.get('included',[])}
    for p in j['data']:
      a=p['attributes']; bt=p['relationships']['base_token']['data']['id']
      pools[p['attributes']['address']]=dict(pool=a['address'],name=a['name'],mint=bt.replace('solana_',''),fdv=float(a.get('fdv_usd') or 0),mcap=float(a.get('market_cap_usd') or 0),chg24=float((a.get('price_change_percentage') or {}).get('h24') or 0),chg6=float((a.get('price_change_percentage') or {}).get('h6') or 0),vol24=float((a.get('volume_usd') or {}).get('h24') or 0),created=a.get('pool_created_at'),liq=float(a.get('reserve_in_usd') or 0))
    time.sleep(2.2)
for u in ["https://api.dexscreener.com/token-boosts/top/v1","https://api.dexscreener.com/token-boosts/latest/v1"]:
  try:
    j=get(u); print(u,len(j))
    sol=[x['tokenAddress'] for x in j if x.get('chainId')=='solana']
    for i in range(0,len(sol),30):
      d=get("https://api.dexscreener.com/tokens/v1/solana/"+",".join(sol[i:i+30]))
      best={}
      for p in d:
        m=p['baseToken']['address']
        if m not in best or (p.get('liquidity') or {}).get('usd',0)>(best[m].get('liquidity') or {}).get('usd',0): best[m]=p
      for m,p in best.items():
        pools.setdefault(p['pairAddress'],dict(pool=p['pairAddress'],name=p['baseToken']['symbol'],mint=m,fdv=p.get('fdv') or 0,mcap=p.get('marketCap') or 0,chg24=(p.get('priceChange') or {}).get('h24') or 0,chg6=(p.get('priceChange') or {}).get('h6') or 0,vol24=(p.get('volume') or {}).get('h24') or 0,created=p.get('pairCreatedAt'),liq=(p.get('liquidity') or {}).get('usd') or 0,src='dexboost'))
  except Exception as e: print(u,e)
json.dump(list(pools.values()),open('pools.json','w'),indent=1)
R=[p for p in pools.values() if p['vol24']>300000 and max(p['mcap'],p['fdv'])>=300000 and p['chg24']>=100]
R.sort(key=lambda p:-p['chg24'])
for p in R: print(p['name'][:30],p['mint'],int(max(p['mcap'],p['fdv'])),p['chg24'],int(p['vol24']),p['created'])
