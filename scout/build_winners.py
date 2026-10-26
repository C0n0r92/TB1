"""Build winners/trades.csv + wallets.csv from cached swap legs. Free sources only (GeckoTerminal, DexScreener, public RPC). Read-only."""
import json,os,sys,time,csv,statistics as st,requests
from analyze import swaps,rounds,stats,iso,night
W=sys.argv[1:]
OUT='/workspace/onchain-intel/winners'; os.makedirs(OUT,exist_ok=True)
GT='https://api.geckoterminal.com/api/v2/networks/solana'
H={'Accept':'application/json','User-Agent':'scout-readonly/1.0'}
C='data/gtcache.json'; cache=json.load(open(C)) if os.path.exists(C) else {}
def gt(path,key):
    if key in cache: return cache[key]
    for i in range(4):
        time.sleep(2.2)
        try:
            r=requests.get(GT+path,headers=H,timeout=30)
            if r.status_code==429: time.sleep(15); continue
            cache[key]=r.json() if r.ok else None; json.dump(cache,open(C,'w')); return cache[key]
        except Exception: time.sleep(5)
    return None
def supply(m):
    k='supply:'+m
    if k in cache: return cache[k]
    try:
        r=requests.post('https://solana-rpc.publicnode.com',json={'jsonrpc':'2.0','id':1,'method':'getTokenSupply','params':[m]},headers=H,timeout=20).json()
        v=(r.get('result') or {}).get('value',{}).get('uiAmount')
    except Exception: v=None
    cache[k]=v; return v
# tracked buy events for co-buys
SW=json.load(open('/workspace/onchain-intel/smart_wallets.json'))
from datetime import datetime
P=lambda s: int(datetime.strptime(s,'%Y-%m-%dT%H:%M:%SZ').timestamp()+0) if isinstance(s,str) else int(s)
import calendar
P=lambda s: calendar.timegm(time.strptime(s,'%Y-%m-%dT%H:%M:%SZ')) if isinstance(s,str) else int(s)
ev={}  # mint -> list of (ts,wallet,cls)
for cls in ('smart','early_buyer','avoid'):
    for a,v in SW.get(cls,{}).items():
        for b in v.get('buys',[]) or []:
            if b.get('ts'): ev.setdefault(b['mint'],[]).append((P(b['ts']),a,cls))
known=set(SW.get('smart',{}))|set(SW.get('early_buyer',{}))
for row in csv.DictReader(open('/workspace/onchain-intel/wallets.csv')): known.add(row['address'])
for a in known|set(W):
    fn=f'data/w/{a}.json'
    if os.path.exists(fn) and 'tx' in json.load(open(fn)):
        for s in swaps(json.load(open(fn))['tx']):
            if s['side']=='buy': ev.setdefault(s['mint'],[]).append((s['ts'],a,'winner' if a in W else 'wallets_csv'))
def co(mint,ts,me,classes):
    return len({a for t,a,c in ev.get(mint,[]) if a!=me and c in classes and abs(t-ts)<=1800}) 
AV=set(l.split(',')[0].strip() for l in open('/workspace/onchain-intel/avoid.csv') if l.strip()) if os.path.exists('/workspace/onchain-intel/avoid.csv') else set()
rows=[];wst={}
for w in W:
    o=json.load(open(f'data/w/{w}.json')); R,op=rounds(swaps(o['tx'])); s=stats(R,30); s['open']=op; wst[w]=(s,R,o)
    for r in R:
        m=r['mint']; tp=gt(f'/tokens/{m}/pools?page=1','pools:'+m); pools=(tp or {}).get('data') or []
        sym=None; pool=None; created=None
        if pools:
            pool=pools[0]['attributes']['address']; nm=pools[0]['attributes'].get('name','')
            sym=nm.split(' / ')[0] if ' / ' in nm else nm
            cs=[p['attributes'].get('pool_created_at') for p in pools if p['attributes'].get('pool_created_at')]
            if cs: created=min(P(c[:19]+'Z') for c in cs)
        e=r['entry_ts']; d=dict(wallet=w,mint=m,symbol=sym,entry_time=iso(e),exit_time=iso(r['exit_ts']),
            size_in_sol=round(r['size_in_sol'],4),size_out_sol=round(r['size_out_sol'],4),size_in_usd=round(r['size_in_usd'],2),size_out_usd=round(r['size_out_usd'],2),
            entry_price_usd=r['entry_price_usd'],exit_price_usd=r['exit_price_usd'],n_buys=r['n_buys'],n_sells=r['n_sells'])
        g=r['size_out_sol']/r['size_in_sol']-1
        for c in (0,3,5):
            sfx='gross' if c==0 else f'net{c}'
            d[f'pnl_pct_{sfx}']=round((g-c/100)*100,2); d[f'pnl_sol_{sfx}']=round(r['size_out_sol']-r['size_in_sol']*(1+c/100),4)
        d['hold_min']=round((r['exit_ts']-e)/60,1)
        d['age_at_entry_h']=round((e-created)/3600,2) if created else None
        sp=supply(m); d['supply_now']=sp; d['mcap_at_entry_usd_approx']=round(r['entry_price_usd']*sp) if sp else None
        d['context_pool']=pool
        for k in ('vol_1h_usd','vol_6h_usd','vol_24h_usd','chg_5m_pct','chg_1h_pct','chg_24h_pct'): d[k]=None
        if pool:
            oh=gt(f'/pools/{pool}/ohlcv/minute?aggregate=5&before_timestamp={e}&limit=288&currency=usd&token={m}',f'oh:{pool}:{e}')
            L=sorted(((c[0],c[1],c[4],c[5]) for c in ((oh or {}).get('data') or {}).get('attributes',{}).get('ohlcv_list',[]) ),key=lambda x:x[0])
            if L:
                last=L[-1]
                def vol(h): return round(sum(c[3] for c in L if c[0]>=e-h*3600),0)
                def chg(sec):
                    base=[c for c in L if c[0]<=e-sec]
                    if not base or e-sec< L[0][0]-1: return None
                    b=base[-1][2]; return round((last[2]/b-1)*100,2) if b else None
                if last[0]>=e-900:
                    d.update(vol_1h_usd=vol(1),vol_6h_usd=vol(6),vol_24h_usd=vol(24) if L[0][0]<=e-86400+300 else None,
                        chg_5m_pct=chg(300),chg_1h_pct=chg(3600),chg_24h_pct=chg(86400-300))
        d['smart_co_buys_30m']=co(m,e,w,{'smart','early_buyer','winner','wallets_csv'})
        d['avoid_co_buys_30m']=co(m,e,w,{'avoid'})
        for k in ('liquidity_at_entry_usd','holders_at_entry','holder_growth','top10_share_at_entry'): d[k]=None
        d['entry_via_pumpfun']=r['entry_via_pumpfun']; d['entry_sig']=r['entry_sig']; d['exit_sig']=r['exit_sig']
        rows.append(d); print(w[:6],sym,d['entry_time'],d['pnl_pct_net5'],d['chg_1h_pct'],flush=True)
json.dump(cache,open(C,'w'))
json.dump({'rows':rows,'stats':{w:v[0] for w,v in wst.items()}},open('data/winners_build.json','w'),default=str)
