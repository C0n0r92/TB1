"""Free: GT Solana pools mcap $300k-$1B, liq>=$100k, age>=1d -> recent trades -> candidate wallets. Read-only."""
import requests,json,time,os,collections,statistics as st,glob
H={"Accept":"application/json"}
def get(u):
    for i in range(5):
        try: r=requests.get(u,headers=H,timeout=30)
        except Exception: time.sleep(5); continue
        if r.status_code==429: time.sleep(20); continue
        time.sleep(2.2); return r.json() if r.ok else None
STABLE={'So11111111111111111111111111111111111111112','EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v','Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB'}
now=time.time(); pools={}
paths=['pools?sort=h24_volume_usd_desc&page=%d'%p for p in range(1,11)]+['pools?sort=h24_tx_count_desc&page=%d'%p for p in range(1,4)]+['trending_pools?duration=24h&page=%d'%p for p in (1,2,3)]+['trending_pools?duration=6h&page=%d'%p for p in (1,2)]
for path in paths:
    j=get('https://api.geckoterminal.com/api/v2/networks/solana/'+path)
    for x in (j or {}).get('data',[]):
        a=x['attributes']; fd=float(a.get('market_cap_usd') or a.get('fdv_usd') or 0); lq=float(a.get('reserve_in_usd') or 0)
        mint=x['relationships']['base_token']['data']['id'].replace('solana_','')
        if mint in STABLE: continue
        try: age=(now-time.mktime(time.strptime(a['pool_created_at'][:19],'%Y-%m-%dT%H:%M:%S'))+time.timezone)/86400
        except Exception: age=None
        if 3e5<=fd<=1e9 and lq>=1e5 and (age or 0)>=1:
            pools.setdefault(a['address'],{'sym':a['name'],'mint':mint,'mcap':fd,'liq':lq,'age_d':round(age,1),'h24vol':float(a['volume_usd'].get('h24') or 0)})
print('pools',len(pools),flush=True)
json.dump(pools,open('an/gt3_pools.json','w'))
fn='an/gt3_trades.json'; W=json.load(open(fn)) if os.path.exists(fn) else {}
seen={(t['tx'],w) for w,L in W.items() for t in L}
# one pool per mint, prefer biggest liq
bym={}
for a,v in pools.items():
    if v['mint'] not in bym or v['liq']>pools[bym[v['mint']]]['liq']: bym[v['mint']]=a
P=sorted(bym.values(),key=lambda a:-pools[a]['h24vol'])[:90]
for i,a in enumerate(P):
    v=pools[a]
    j=get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{a}/trades?trade_volume_in_usd_greater_than=150')
    for t in (j or {}).get('data',[]):
        x=t['attributes']; w=x['tx_from_address']
        ts=time.mktime(time.strptime(x['block_timestamp'][:19],'%Y-%m-%dT%H:%M:%S'))-time.timezone
        k=(x['tx_hash'],w)
        if k in seen: continue
        seen.add(k)
        W.setdefault(w,[]).append({'ts':ts,'tx':x['tx_hash'],'blk':x.get('block_number'),'pool':a,'mint':v['mint'],'mcap':v['mcap'],'kind':x['kind'],'usd':float(x['volume_in_usd'] or 0)})
    if i%15==0: json.dump(W,open(fn,'w')); print(i,len(W),flush=True)
json.dump(W,open(fn,'w'))
OI='/workspace/onchain-intel/'; txt=''.join(open(OI+f).read() for f in ['known_funders.csv','avoid.csv','known_ruggers.json','custodial_ignore.json'])
done={os.path.basename(f)[:-5] for f in glob.glob('an/wg/*.json')}|set(json.load(open('an/sig3.json')))
C=[]
for w,L in W.items():
    if w in txt or w in done: continue
    bytx=collections.defaultdict(set); byblk=collections.Counter()
    for t in L: bytx[t['tx']].add(t['kind']); byblk[t['blk']]+=1
    if any(len(k)>1 for k in bytx.values()) or max(byblk.values())>2: continue
    buys=[t for t in L if t['kind']=='buy']
    if not buys or max(t['usd'] for t in buys)<300: continue
    if len(L)>25: continue   # high-rate in sample
    Ls=sorted(L,key=lambda t:t['ts'])
    if any(b['kind']=='sell' and b['mint']==a['mint'] and 0<b['ts']-a['ts']<1800 for i,a in enumerate(Ls) if a['kind']=='buy' for b in Ls[i+1:]): continue
    npool=len({t['mint'] for t in L})
    C.append((npool,len(L),w))
C.sort(reverse=True); print('cands',len(C),'multi-pool',sum(1 for c in C if c[0]>=2))
json.dump([w for _,_,w in C],open('an/gt3_cands.json','w'))
