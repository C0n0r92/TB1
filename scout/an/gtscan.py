import requests,json,time,collections,sys
H={"Accept":"application/json"}
def get(u):
    for i in range(5):
        try: r=requests.get(u,headers=H,timeout=30)
        except Exception: time.sleep(5); continue
        if r.status_code==429: time.sleep(20); continue
        time.sleep(2.1); return r.json() if r.ok else None
    return None
pools={}
for path in ['pools?sort=h24_volume_usd_desc&page=%d'%p for p in range(1,6)]+['trending_pools?duration=1h&page=1','trending_pools?duration=1h&page=2','trending_pools?page=1']:
    j=get('https://api.geckoterminal.com/api/v2/networks/solana/'+path)
    for x in (j or {}).get('data',[]):
        a=x['attributes']; fd=float(a.get('market_cap_usd') or a.get('fdv_usd') or 0); lq=float(a.get('reserve_in_usd') or 0)
        mint=x['relationships']['base_token']['data']['id'].replace('solana_','')
        if mint in ('So11111111111111111111111111111111111111112','EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v','Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'): continue
        if fd>=1e5 and lq>=3e4 and fd<5e9:
            pools.setdefault(a['address'],{'sym':a['name'],'mint':mint,'mcap':fd,'liq':lq,'h1vol':float(a['volume_usd'].get('h1') or 0),'created':a.get('pool_created_at')})
print('pools',len(pools),flush=True)
json.dump(pools,open('an/pools.json','w'))
# prioritise by 1h volume, cap 45
P=sorted(pools.items(),key=lambda x:-x[1]['h1vol'])[:45]
now=time.time(); W=collections.defaultdict(list)
for a,v in P:
    j=get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{a}/trades?trade_volume_in_usd_greater_than=100')
    for t in (j or {}).get('data',[]):
        x=t['attributes']; ts=time.mktime(time.strptime(x['block_timestamp'][:19],'%Y-%m-%dT%H:%M:%S'))-time.timezone
        W[x['tx_from_address']].append({'ts':ts,'pool':a,'sym':v['sym'],'mint':v['mint'],'mcap':v['mcap'],'kind':x['kind'],'usd':float(x['volume_in_usd'] or 0)})
json.dump(W,open('an/gt_wallet_trades.json','w'))
rows=[]
for w,L in W.items():
    n1=sum(1 for x in L if now-x['ts']<=3600); n2=sum(1 for x in L if now-x['ts']<=7200)
    if n2>=2: rows.append((n2,n1,len({x['mint'] for x in L}),w,max(x['ts'] for x in L)))
rows.sort(reverse=True)
for r in rows[:60]: print(r[0],r[1],r[2],r[3],time.strftime('%H:%M',time.gmtime(r[4])))
print('wallets',len(W),'active2+',len(rows))
