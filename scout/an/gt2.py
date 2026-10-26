"""Free: GT top-volume Solana pools mcap 100k-50M -> recent trades; accumulate per-wallet across rounds. Read-only."""
import requests,json,time,os,collections
H={"Accept":"application/json"}
def get(u):
    for i in range(5):
        try: r=requests.get(u,headers=H,timeout=30)
        except Exception: time.sleep(5); continue
        if r.status_code==429: time.sleep(20); continue
        time.sleep(2.1); return r.json() if r.ok else None
STABLE={'So11111111111111111111111111111111111111112','EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v','Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'}
pools={}
for path in ['pools?sort=h24_volume_usd_desc&page=%d'%p for p in range(1,9)]+['trending_pools?duration=1h&page=%d'%p for p in (1,2,3)]+['trending_pools?duration=6h&page=1']:
    j=get('https://api.geckoterminal.com/api/v2/networks/solana/'+path)
    for x in (j or {}).get('data',[]):
        a=x['attributes']; fd=float(a.get('market_cap_usd') or a.get('fdv_usd') or 0); lq=float(a.get('reserve_in_usd') or 0)
        mint=x['relationships']['base_token']['data']['id'].replace('solana_','')
        if mint in STABLE: continue
        if 1e5<=fd<=5e7 and lq>=2e4:
            pools.setdefault(a['address'],{'sym':a['name'],'mint':mint,'mcap':fd,'liq':lq,'h1vol':float(a['volume_usd'].get('h1') or 0)})
print('pools',len(pools),flush=True)
fn='an/gt2_trades.json'; W=json.load(open(fn)) if os.path.exists(fn) else {}
seen={(t['tx'],w) for w,L in W.items() for t in L}
P=sorted(pools.items(),key=lambda x:-x[1]['h1vol'])[:50]; new=0
for a,v in P:
    j=get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{a}/trades?trade_volume_in_usd_greater_than=50')
    for t in (j or {}).get('data',[]):
        x=t['attributes']; w=x['tx_from_address']
        ts=time.mktime(time.strptime(x['block_timestamp'][:19],'%Y-%m-%dT%H:%M:%S'))-time.timezone
        k=(x['tx_hash'],w)
        if k in seen: 
            # same tx seen twice (both sides) -> mark
            continue
        seen.add(k); new+=1
        W.setdefault(w,[]).append({'ts':ts,'tx':x['tx_hash'],'blk':x.get('block_number'),'pool':a,'mint':v['mint'],'mcap':v['mcap'],'kind':x['kind'],'usd':float(x['volume_in_usd'] or 0)})
json.dump(W,open(fn,'w')); json.dump(pools,open('an/gt2_pools.json','w'))
print('round done new',new,'wallets',len(W),time.strftime('%H:%M',time.gmtime()),flush=True)
