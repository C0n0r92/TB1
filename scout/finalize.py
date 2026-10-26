import json,os,sys,csv,time,statistics as st,requests
from analyze import night
sys.argv  # wallets meta passed via data/winners_meta.json
OUT='/workspace/onchain-intel/winners'
B=json.load(open('data/winners_build.json')); RC=json.load(open('data/rc_creators.json')) if os.path.exists('data/rc_creators.json') else {}
META=json.load(open('data/winners_meta.json')); ACT=json.load(open('data/activity.json'))
C='data/gtcache.json'; cache=json.load(open(C))
GT='https://api.geckoterminal.com/api/v2/networks/solana'; H={'Accept':'application/json','User-Agent':'scout-readonly/1.0'}
def gt1m(pool,e,m):
    k=f'oh1:{pool}:{e}'
    if k not in cache:
        for i in range(4):
            time.sleep(2.2)
            try:
                r=requests.get(f'{GT}/pools/{pool}/ohlcv/minute?aggregate=1&before_timestamp={e}&limit=40&currency=usd&token={m}',headers=H,timeout=30)
                if r.status_code==429: time.sleep(15); continue
                cache[k]=r.json() if r.ok else None; break
            except Exception: time.sleep(5)
        json.dump(cache,open(C,'w'))
    return cache.get(k)
def stair(pool,e,m):
    j=gt1m(pool,e,m) if pool else None
    L=sorted([c for c in ((j or {}).get('data') or {}).get('attributes',{}).get('ohlcv_list',[]) if e-1800<=c[0]<e],key=lambda c:c[0])
    if len(L)<20: return None,None,None,len(L)
    up=sum(1 for c in L if c[4]>c[1])/len(L); worst=min(c[4]/c[1]-1 for c in L if c[1]); net=L[-1][4]/L[0][1]-1 if L[0][1] else 0
    v=[c[5] for c in L]; cv=st.pstdev(v)/st.mean(v) if st.mean(v) else None
    flag=int(up>=0.65 and worst>=-0.02 and 0.05<=net<=1.0 and cv is not None and cv<=0.6)
    return flag,round(up,3),round(cv,3) if cv is not None else None,len(L)
rows=[r for r in B['rows'] if r['wallet'] in META]
def gsupply(m):
    if m.endswith('pump'): return 1e9
    for p in ((cache.get('pools:'+m) or {}).get('data') or []):
        a=p['attributes']; base=p['relationships']['base_token']['data']['id']
        if base=='solana_'+m and a.get('fdv_usd') and a.get('base_token_price_usd') and float(a['base_token_price_usd'])>0:
            return float(a['fdv_usd'])/float(a['base_token_price_usd'])
    return None
for r in rows:
    rc=RC.get(r['mint'],{})
    if not r.get('supply_now'):
        sp=gsupply(r['mint']); r['supply_now']=round(sp) if sp else None; r['mcap_at_entry_usd_approx']=round(r['entry_price_usd']*sp) if sp else None
    r['max_single_holder_pct']=None; r['top_holders_linked_pct']=None; r['fresh_holder_pct_top50']=None
    r['max_single_holder_pct_now']=rc.get('max_holder_pct_now'); r['max_holder_gt5_now']=(int(rc['max_holder_pct_now']>5) if rc.get('max_holder_pct_now') is not None else None)
    r['insider_top20_pct_now_rugcheck']=rc.get('insider_top20_pct_now'); r['top10_pct_now_incl_lp']=rc.get('top10_pct_now'); r['holders_now']=rc.get('holders_now'); r['liquidity_now_usd']=round(rc['liq_now_usd']) if rc.get('liq_now_usd') else None
    r['creator']=rc.get('creator'); r['wallet_is_creator']=(int(rc.get('creator')==r['wallet']) if rc.get('creator') else None)
    r['vol24h_mcap']=round(r['vol_24h_usd']/r['mcap_at_entry_usd_approx'],3) if r.get('vol_24h_usd') and r.get('mcap_at_entry_usd_approx') else None
    e=int(time.mktime(time.strptime(r['entry_time'],'%Y-%m-%dT%H:%M:%SZ'))-time.timezone)
    f,up,cv,n=stair(r.get('context_pool'),e,r['mint']); r.update(stair_step=f,up_share_1m_30m=up,vol_cv_1m_30m=cv,n_1m_candles_30m=n)
    r['style']=META[r['wallet']]['style']; r['source']=META[r['wallet']]['source']
cols=['wallet','style','source','mint','symbol','entry_time','exit_time','size_in_sol','size_out_sol','size_in_usd','size_out_usd','entry_price_usd','exit_price_usd','n_buys','n_sells',
 'pnl_pct_gross','pnl_sol_gross','pnl_pct_net3','pnl_sol_net3','pnl_pct_net5','pnl_sol_net5','hold_min','age_at_entry_h','mcap_at_entry_usd_approx','supply_now',
 'liquidity_at_entry_usd','vol_1h_usd','vol_6h_usd','vol_24h_usd','holders_at_entry','holder_growth','top10_share_at_entry','chg_5m_pct','chg_1h_pct','chg_24h_pct','smart_co_buys_30m','avoid_co_buys_30m',
 'max_single_holder_pct','top_holders_linked_pct','fresh_holder_pct_top50','vol24h_mcap','stair_step','up_share_1m_30m','vol_cv_1m_30m','n_1m_candles_30m',
 'max_single_holder_pct_now','max_holder_gt5_now','insider_top20_pct_now_rugcheck','top10_pct_now_incl_lp','holders_now','liquidity_now_usd','creator','wallet_is_creator','entry_via_pumpfun','context_pool','entry_sig','exit_sig']
with open(f'{OUT}/trades.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader()
    for r in sorted(rows,key=lambda r:(r['wallet'],r['entry_time'])): w.writerow({k:('' if r.get(k) is None else r.get(k)) for k in cols})
wc=['address','label','source','style','n_trades','win_rate_net3','win_rate_net5','median_pnl_pct_net3','median_pnl_pct_net5','avg_pnl_pct_net3','avg_pnl_pct_net5','sum_pnl_sol_net3','sum_pnl_sol_net5','trades_per_night','median_hold_min','sigs_per_hour_30d','night_hours_active_share_30d','window_days','confidence','evidence']
with open(f'{OUT}/wallets.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=wc); w.writeheader()
    for a,m in META.items():
        R=[r for r in rows if r['wallet']==a]
        if not R: continue
        n3=[r['pnl_pct_net3'] for r in R]; n5=[r['pnl_pct_net5'] for r in R]
        ts=[time.mktime(time.strptime(r['entry_time'],'%Y-%m-%dT%H:%M:%SZ')) for r in R]; span=max((max(ts)-min(ts))/86400,1)
        A=ACT.get(a,{})
        w.writerow(dict(address=a,label=m.get('label',''),source=m['source'],style=m['style'],n_trades=len(R),win_rate_net3=round(sum(x>0 for x in n3)/len(R),3),win_rate_net5=round(sum(x>0 for x in n5)/len(R),3),
            median_pnl_pct_net3=round(st.median(n3),2),median_pnl_pct_net5=round(st.median(n5),2),avg_pnl_pct_net3=round(st.mean(n3),2),avg_pnl_pct_net5=round(st.mean(n5),2),
            sum_pnl_sol_net3=round(sum(r['pnl_sol_net3'] for r in R),2),sum_pnl_sol_net5=round(sum(r['pnl_sol_net5'] for r in R),2),
            trades_per_night=round(sum(1 for r,t in zip(R,ts) if night(t))/span,2),median_hold_min=round(st.median(r['hold_min'] for r in R),1),
            sigs_per_hour_30d=A.get('sigs_per_h',''),night_hours_active_share_30d=A.get('night_hours_active_share',''),window_days=round(span,1),confidence=m['confidence'],evidence=m['evidence']))
print('rows',len(rows))
