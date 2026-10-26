"""GeckoTerminal public API (free): established Solana pools (pool age>=1d, FDV/mcap>=$1M), last $100+ trades per pool.
Keeps wallets that BOTH bought and sold (swing-like) or bought in 2+ pools. Read-only. Writes gt/mine2_<HHMM>.json"""
import json,urllib.request,time,collections,calendar
def get(u):
    for i in range(3):
        try:
            r=urllib.request.Request(u,headers={'Accept':'application/json','User-Agent':'scout-readonly/1.0'}); return json.load(urllib.request.urlopen(r,timeout=25))
        except Exception as e: print('err',u[-70:],e,flush=True); time.sleep(6)
pools={}
paths=['trending_pools?duration=24h&page=%d'%p for p in (1,2,3)]+['trending_pools?duration=6h&page=1','trending_pools?duration=1h&page=1']+['pools?page=%d&sort=h24_volume_usd_desc'%p for p in (1,2,3,4)]+['pools?page=%d&sort=h24_tx_count_desc'%p for p in (1,2)]
for path in paths:
    d=get('https://api.geckoterminal.com/api/v2/networks/solana/'+path); time.sleep(2.2)
    for p in (d or {}).get('data',[]):
        a=p['attributes']; age=(time.time()-calendar.timegm(time.strptime(a['pool_created_at'][:19],'%Y-%m-%dT%H:%M:%S')))/3600
        mc=float(a.get('market_cap_usd') or a.get('fdv_usd') or 0); fdv=float(a.get('fdv_usd') or 0)
        if age>=24 and mc>=1e6 and fdv<=5e9: pools[a['address']]=dict(name=a['name'],mcap=mc,age_h=round(age,1),liq=float(a.get('reserve_in_usd') or 0))
print('pools',len(pools),flush=True)
W=collections.defaultdict(lambda:{'bpools':set(),'spools':set(),'buy_usd':0,'nb':0,'ns':0,'bt':{},'st':{}})
for pa in list(pools)[:45]:
    d=get(f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{pa}/trades?trade_volume_in_usd_greater_than=100'); time.sleep(2.2)
    for t in (d or {}).get('data',[]):
        a=t['attributes']; x=W[a['tx_from_address']]; ts=calendar.timegm(time.strptime(a['block_timestamp'][:19],'%Y-%m-%dT%H:%M:%S'))
        if a['kind']=='buy': x['bpools'].add(pa); x['buy_usd']+=float(a['volume_in_usd']); x['nb']+=1; x['bt'].setdefault(pa,[]).append(ts)
        else: x['spools'].add(pa); x['ns']+=1; x['st'].setdefault(pa,[]).append(ts)
out={}
for w,v in W.items():
    # round-trip-like: buy then sell in same pool >=60s later
    rt=[(min(s for s in v['st'][p] if s>=min(v['bt'][p]))-min(v['bt'][p])) for p in v['bt'] if p in v['st'] and any(s>=min(v['bt'][p]) for s in v['st'][p])]
    if len(v['bpools'])>=2 or any(h>=60 for h in rt):
        out[w]=dict(bpools=len(v['bpools']),spools=len(v['spools']),buys=v['nb'],sells=v['ns'],buy_usd=round(v['buy_usd']),rt_holds_s=sorted(rt))
fn='gt/mine2_%s.json'%time.strftime('%H%M',time.gmtime())
json.dump(dict(pools=pools,wallets=out),open(fn,'w'),indent=0)
print(fn,'wallets kept',len(out),flush=True)
