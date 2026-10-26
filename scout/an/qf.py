"""Quick-flip strict copy-cost model (Zero 11:54 UTC). Read-only, free sources (public RPC, GeckoTerminal).
Per 7d closed round: copy_ret = (exitLow/entryHigh) / ((1+ib)(1+is)) - 1 - 0.04
  entryHigh = 1-min candle HIGH (USD) of the entry minute, exitLow = 1-min candle LOW of the exit (final sell) minute,
  pool = the GT pool whose address appears in the wallet's own entry/exit tx (static or ALT-loaded keys).
  ib, is = constant-product impact of a 0.09 SOL buy and a 0.09 SOL sell: dx/R_sol, with R_sol = pool token-vault balance
  (post-tx, from the wallet's own tx meta) x spot price in SOL (x*y=k => R_sol = R_tok*p).
"""
import json,sys,os,time,statistics as st,urllib.request
sys.path.insert(0,'/workspace/scout'); import analyze as A; from pub import rpc
GT='https://api.geckoterminal.com/api/v2/networks/solana/'; CO=0.09; RT=0.04; MAXGAP=30
C=os.environ.get('QFC','an/qf/cache.json'); cache=json.load(open(C)) if os.path.exists(C) else {}
_last=[0]
def gt(path):
    if path in cache: return cache[path]
    for a in range(6):
        w=_last[0]+2.3-time.time()
        if w>0: time.sleep(w)
        _last[0]=time.time()
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(GT+path,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=30))
            cache[path]=r; json.dump(cache,open(C,'w')); return r
        except urllib.error.HTTPError as e:
            if e.code==404: cache[path]=None; return None
            time.sleep(10*(a+1))
        except Exception: time.sleep(5)
    return None
TXC='an/qf/tx'; os.makedirs(TXC,exist_ok=True)
def gettx(sig):
    f=f'{TXC}/{sig}.json'
    if os.path.exists(f): return json.load(open(f))
    t=rpc('getTransaction',[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
    if t: json.dump(t,open(f,'w'))
    return t
def keys(t):
    k=[a['pubkey'] if isinstance(a,dict) else a for a in t['transaction']['message']['accountKeys']]
    la=t['meta'].get('loadedAddresses') or {}
    return set(k)|set(la.get('writable',[]))|set(la.get('readonly',[]))
def vault(t,mint,wallet):
    pre={b['accountIndex']:float(b['uiTokenAmount']['uiAmount'] or 0) for b in t['meta']['preTokenBalances'] if b['mint']==mint and b.get('owner')!=wallet}
    post={b['accountIndex']:float(b['uiTokenAmount']['uiAmount'] or 0) for b in t['meta']['postTokenBalances'] if b['mint']==mint and b.get('owner')!=wallet}
    best=None
    for i in set(pre)|set(post):
        ch=abs(post.get(i,0)-pre.get(i,0))
        if best is None or ch>best[0]: best=(ch,post.get(i,0),pre.get(i,0))
    return best

SOLM=A.SOL; WS=set(A.USD)
def tx_price(t,m,pool):
    """SOL per token of a pool trade, from the pool's own balance changes in that tx. None if not parseable."""
    if not t or t['meta'].get('err'): return None
    ks=[a['pubkey'] if isinstance(a,dict) else a for a in t['transaction']['message']['accountKeys']]
    la=t['meta'].get('loadedAddresses') or {}; ks=ks+la.get('writable',[])+la.get('readonly',[])
    def ch(mint):
        pre={b['accountIndex']:(b.get('owner'),float(b['uiTokenAmount']['uiAmount'] or 0)) for b in t['meta']['preTokenBalances'] if b['mint']==mint}
        post={b['accountIndex']:(b.get('owner'),float(b['uiTokenAmount']['uiAmount'] or 0)) for b in t['meta']['postTokenBalances'] if b['mint']==mint}
        return {i:(post.get(i,pre.get(i))[0],post.get(i,(0,0))[1]-pre.get(i,(0,0))[1]) for i in set(pre)|set(post)}
    tok=[(o,d) for o,d in ch(m).values() if o==pool]
    signer=ks[0]
    if not tok or not [1 for o,d in ch(SOLM).values() if o==pool and d]:
        # USD-quoted pool (USDC/USDT): pool-owned (or authority-owned) USD change, converted to SOL at that time
        for U in WS:
            uq=[(o,d) for o,d in ch(U).values() if d and o!=signer]
            if not uq: continue
            own=pool if any(o==pool for o,_ in uq) else max(uq,key=lambda z:abs(z[1]))[0]
            tq=[(o,d) for o,d in ch(m).values() if o==own and d]
            if not tq: continue
            dt=sum(d for _,d in tq); dq=sum(d for o,d in uq if o==own)
            if dt and dq and (dt>0)!=(dq>0): return abs(dq)/abs(dt)/A.solpx(t['blockTime'])

    if not tok:   # vault owned by an AMM authority (e.g. Raydium): largest non-signer change of the mint, and opposite WSOL change of same owner
        c=[(o,d) for o,d in ch(m).values() if o!=signer and d]
        if not c: return None
        own,dt0=max(c,key=lambda z:abs(z[1])); tok=[(own,dt0)]
        q=[(o,d) for o,d in ch(SOLM).values() if o==own and d]
        if not q: return None
        dt=dt0; dq=sum(d for _,d in q)
        return abs(dq)/abs(dt) if (dt>0)!=(dq>0) else None
    dt=sum(d for _,d in tok)
    q=[(o,d) for o,d in ch(SOLM).values() if o==pool]
    if q: dq=sum(d for _,d in q)
    elif pool in ks:
        i=ks.index(pool); dq=(t['meta']['postBalances'][i]-t['meta']['preBalances'][i])/1e9
    else: return None
    if dt==0 or dq==0 or (dt>0)==(dq>0): return None
    return abs(dq)/abs(dt)
def anchor_sig(o,T):
    later=sorted((x['ts'],x['sig']) for x in o['tx'] if x['ts']>=T+20)
    return later[0] if later and later[0][0]<=T+3600 else None
def delayed_price(o,pool,m,fill_ts,fill_sig,T_off=5):
    """First successful pool trade with blockTime >= fill_ts+5 (public RPC sigs of the pool, between fill_sig and a later wallet sig)."""
    T=fill_ts+T_off; a=anchor_sig(o,T)
    if not a: return None,'no later anchor'
    before=a[1]; cand=[]
    for page in range(4):
        ck=f'sigs/{pool}/{before}/{fill_sig}'
        if ck in cache: r=cache[ck]
        else:
            r=rpc('getSignaturesForAddress',[pool,{"before":before,"until":fill_sig,"limit":1000}])
            if r is not None: cache[ck]=[{k:c.get(k) for k in ('signature','blockTime','err')} for c in r]; r=cache[ck]
        if r is None: return None,'rpc fail'
        cand+=r
        if len(r)<1000 or (r and r[-1].get('blockTime',0)<T): break
        before=r[-1]['signature']
    ok=[c for c in cand if c.get('err') is None and c.get('blockTime') and c['blockTime']>=T]
    if not ok: return None,'no pool trade in window'
    tmin=min(c['blockTime'] for c in ok)
    seq=list(reversed(ok))   # oldest first
    for c in seq[:25]:
        p=tx_price(gettx(c['signature']),m,pool)
        if p: return (p,c['blockTime']-fill_ts),'ok'
    return None,'unparsed'
def pools(mint):
    r=gt(f'tokens/{mint}/pools?page=1'); out={}
    for p in (r or {}).get('data',[]):
        a=p['attributes']['address']; base=p['relationships']['base_token']['data']['id'].split('_',1)[1]
        out[a]='base' if base==mint else 'quote'
    return out
def candles(pool,side,t0,t1):
    m0=int(t0//60*60); m1=int(t1//60*60); out={}
    end=m1+180
    while True:
        lim=min(1000,(end-m0)//60+2)
        r=gt(f'pools/{pool}/ohlcv/minute?aggregate=1&before_timestamp={end}&limit={lim}&currency=usd&token={side}')
        L=((r or {}).get('data') or {}).get('attributes',{}).get('ohlcv_list',[])
        for c in L: out[int(c[0])]=c
        if not L or min(int(c[0]) for c in L)<=m0 or lim<1000: break
        end=min(int(c[0]) for c in L)
    return out
def pick(cd,m,col,agg):
    for d in (0,60,120):   # candle of that minute, else the next 1-2 minutes (stricter direction via agg)
        if m+d in cd: return cd[m+d][col],d
    return None,None
LEGLOG=[]
def run(w):
    o=json.load(open(f'an/wg/{w}.json')); sw=A.swaps(o['tx']); now=time.time()
    R=[x for x in A.rounds(sw)[0] if x['exit_ts']>now-7*86400]
    sup=json.load(open('an/supply.json')) if os.path.exists('an/supply.json') else {}
    rows=[]
    for x in R:
        m=x['mint']; P=pools(m); te=gettx(x['entry_sig']); tx_=gettx(x['exit_sig'])
        row=dict(mint=m,entry=A.iso(x['entry_ts']),hold_m=round((x['exit_ts']-x['entry_ts'])/60,1),size_sol=round(x['size_in_sol'],3),
                 wallet_ret=round(x['size_out_sol']/x['size_in_sol']-1,4))
        pool=None
        for t in (te,tx_):
            if t and not pool:
                hit=[a for a in P if a in keys(t)]
                if hit: pool=hit[0]
        row['pool']=pool
        if not pool or not te or not tx_: row['err']='no pool/tx'; rows.append(row); continue
        legs=[l for l in sw if l['mint']==m and x['entry_ts']<=l['ts']<=x['exit_ts']]
        cd=candles(pool,P[pool],x['entry_ts'],x['exit_ts'])
        def at(ts,col):
            mm=int(ts//60*60)
            for d in (0,60,120,-60):
                if mm+d in cd: return cd[mm+d][col]/A.solpx(ts)
            return None
        bs=[];ss=[];nreal=nfb=0;gaps=[];why=[]
        for l in legs:
            lt=gettx(l['sig']); lp=[a for a in P if lt and a in keys(lt)]
            dp,st_=delayed_price(o,lp[0] if lp else pool,m,l['ts'],l['sig'])
            lpx=l['sol']/l['tok']
            if dp and dp[1]>MAXGAP: st_=f'gap {dp[1]}s>{MAXGAP}'; dp=None
            if dp: p=dp[0]; nreal+=1; gaps.append(dp[1])
            else:
                p=at(l['ts'],2 if l['side']=='buy' else 3); why.append(st_)
                if p and abs(p/lpx-1)>0.5: why.append(f'candle off {p/lpx-1:+.0%}'); p=None
                if p: nfb+=1
            LEGLOG.append(dict(w=w[:6],mint=m[:6],side=l['side'],ts=l['ts'],leader_px=lpx,used_px=p,d5_px=dp[0] if dp else None,gap=dp[1] if dp else None,why=st_))
            (bs if l['side']=='buy' else ss).append((l['sol'] if l['side']=='buy' else l['tok'],p))
        miss=sum(1 for b in bs+ss if b[1] is None)
        if not bs or not ss or miss: row['err']=f'no price ({miss} legs)'; rows.append(row); continue
        H=sum(b[0] for b in bs)/sum(b[0]/b[1] for b in bs)   # copy avg entry, SOL/token, each buy leg at first pool trade >= fill+5s
        Lo=sum(q[0]*q[1] for q in ss)/sum(q[0] for q in ss)   # copy avg exit, each sell leg likewise
        dh=dl=None; row.update(legs_real5s=nreal,legs_fallback=nfb,fallback_why=why,max_gap_s=max(gaps) if gaps else None)
        sp_e=x['entry_price_usd']/A.solpx(x['entry_ts']); sp_x=x['exit_price_usd']/A.solpx(x['exit_ts'])
        ve=vault(te,m,w); vx=vault(tx_,m,w)
        Re=ve[1]*sp_e if ve else None; Rx=vx[1]*sp_x if vx else None
        if not Re or not Rx: row['err']='no vault'; rows.append(row); continue
        ib=CO/Re; is_=CO/Rx
        r=(Lo/H)/((1+ib)*(1+is_))-1-RT
        s=sup.get(m) or (rpc('getTokenSupply',[m]) or {}).get('value',{}).get('uiAmount')
        row.update(entry_high=H,exit_low=Lo,cdl_shift=(dh,dl),wallet_entry_px=x['entry_price_usd'],wallet_exit_px=x['exit_price_usd'],
                   R_sol_entry=round(Re,1),R_sol_exit=round(Rx,1),impact_buy=round(ib,4),impact_sell=round(is_,4),copy_ret=round(r,4),
                   liq_usd_entry=round(2*Re*A.solpx(x['entry_ts'])),mcap_entry=round(x['entry_price_usd']*float(s)) if s else None)
        rows.append(row); json.dump(cache,open(C,'w'))
    ok=[r for r in rows if 'copy_ret' in r]; cr=[r['copy_ret'] for r in ok]
    def pct10(v): v=sorted(v); return v[max(0,int(0.1*len(v)+0.5)-1)] if v else None
    res=dict(wallet=w,closed7=len(R),modelled=len(ok),legs_real5s=sum(r.get('legs_real5s',0) for r in rows),legs_fallback=sum(r.get('legs_fallback',0) for r in rows),trades_all_real=sum(1 for r in ok if r.get('legs_fallback')==0),errors=[(r['mint'][:6],r['err']) for r in rows if 'err' in r])
    if cr:
        ws=[r['size_sol']*r['copy_ret'] for r in ok]; ew=[CO*c for c in cr]
        res.update(med_copy_ret_pct=round(st.median(cr)*100,2),win=round(sum(c>0 for c in cr)/len(cr),2),
            eq_net_sol=round(sum(ew),4),eq_exbest_sol=round(sum(ew)-max(ew),4),
            wsize_net_sol=round(sum(ws),3),wsize_exbest_sol=round(sum(ws)-max(ws),3),
            med_impact_rt_pct=round(st.median(r['impact_buy']+r['impact_sell'] for r in ok)*100,2),
            min_mcap_usd=pct10([r['mcap_entry'] for r in ok if r['mcap_entry']]),min_liq_usd=pct10([r['liq_usd_entry'] for r in ok]),
            med_liq_usd=round(st.median(r['liq_usd_entry'] for r in ok)))
    json.dump(cache,open(C,'w'))
    json.dump(dict(res=res,rows=rows,legs=[g for g in LEGLOG if g['w']==w[:6]]),open(f'an/qf/{w[:6]}.json','w'),indent=1)
    return res
if __name__=='__main__':
    for w in sys.argv[1:]: print(json.dumps(run(w)),flush=True)
