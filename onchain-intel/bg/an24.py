import os
"""24h on-chain stats per wallet from tx/<w>.jsonl (ftb.py) or raw/<w>.json (Helius enhanced). Read-only.
Output an/<w>.json. Usage: python3 an24.py w1 w2 ... [SNIPE=1 for mint-launch gap check via public RPC]"""
import json,sys,os,time,statistics as st,collections,urllib.request
sys.path.insert(0,'/workspace/scout')
import analyze as A
from pub import rpc
NOW=time.time(); D=86400
KR=set(json.load(open('/workspace/onchain-intel/known_ruggers.json'))['wallets'])
CU={x['address'] for x in json.load(open('/workspace/onchain-intel/custodial_ignore.json'))['wallets']}
C=json.load(open('cands.json'))
NC='an/names.json'; names=json.load(open(NC)) if os.path.exists(NC) else {}
def tnames(mints):
    need=[m for m in mints if m not in names]
    for i in range(0,len(need),30):
        ch=need[i:i+30]
        try:
            r=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/'+','.join(ch),headers={'User-Agent':'scout-readonly/1.0'}),timeout=30).read())
            for p in r:
                b=p.get('baseToken',{}); 
                if b.get('address') in ch: names[b['address']]=[b.get('symbol'),b.get('name')]
        except Exception as e: pass
        for m in ch: names.setdefault(m,None)
        time.sleep(1.1)
    json.dump(names,open(NC,'w'))
def stocky(m):
    n=names.get(m) or ['','']
    s=(' '.join(x or '' for x in n)).lower()
    return m.startswith('Xs') or any(k in s for k in ('xstock','securities','ondo global','tokenized equity','prestock')) or (n[0] or '') in ('TTWO','TTWOx')
def load(w):
    fn=f'tx/{w}.jsonl'
    if os.path.exists(fn):
        L=[];seen=set()
        for l in open(fn):
            x=json.loads(l)
            if 'err' in x or x['sig'] in seen: continue
            seen.add(x['sig']); L.append(x)
        return L,'rpc-getTransaction (all 24h sigs)'
    return None,None
def run(w,snipe):
    txs,src=load(w)
    if os.path.exists('helius_wallets.txt') and w in open('helius_wallets.txt').read().split(): src='helius getTransactionsForAddress (24h, status=succeeded, tokenTransfer filter, jsonParsed)'
    if txs is None: return None
    sw=[s for s in A.swaps(txs) if s['ts']>NOW-D]
    R,openn=A.rounds(sw)
    res=dict(wallet=w,name=C.get(w,{}).get('name'),src=src,n_tx=len(txs),swaps_24h=len(sw),buys_24h=sum(s['side']=='buy' for s in sw),
             rounds_closed=len(R),open_positions=openn)
    if not sw: return res
    tnames(sorted({s['mint'] for s in sw}))
    _sb={}
    for s in sw:
        if stocky(s['mint']) and s['side']=='buy': _sb[s['mint']]=_sb.get(s['mint'],0)+s['usd']
    res['stock_mints']=[names.get(m) for m,u in _sb.items() if u>=5]
    res['stock_sold_only_or_dust']=[names.get(m) for m in {s['mint'] for s in sw} if stocky(m) and _sb.get(m,0)<5]
    res['last_active']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(max(s['ts'] for s in sw)))
    res['idle_h']=round((NOW-max(s['ts'] for s in sw))/3600,2)
    bu=[s['usd'] for s in sw if s['side']=='buy']; res['med_buy_usd']=round(st.median(bu)) if bu else None
    _cb=collections.Counter(x['ts']%600//30 for x in sw); res['clock_share']=round(_cb.most_common(1)[0][1]/len(sw),2) if len(sw)>=50 else None
    res['payers']=collections.Counter(x['payer']==w for x in txs).most_common()
    if R:
        net=[x['size_out_sol']-x['size_in_sol'] for x in R]
        cap=[]
        for x in R:
            rs=x['size_out_sol']/x['size_in_sol']-1; rp=x['exit_price_usd']/x['entry_price_usd']-1 if x['entry_price_usd'] else rs
            cap.append(x['size_in_sol']*min(rs,rp))
        pct=[(x['size_out_sol']/x['size_in_sol']-1)*100 for x in R]
        holds=[(x['exit_ts']-x['entry_ts'])/60 for x in R]
        res.update(pnl_1d_sol=round(sum(net),2),pnl_1d_capped_sol=round(sum(cap),2),ex_best_sol=round(sum(net)-max(net),2),best_sol=round(max(net),2),
                   win_rate=round(sum(p>0 for p in net)/len(R),2),med_ret_pct=round(st.median(pct),1),med_hold_min=round(st.median(holds),1),
                   share_hold_lt60s=round(sum(h<1 for h in holds)/len(R),2),share_hold_lt2m=round(sum(h<2 for h in holds)/len(R),2),
                   med_size_sol=round(st.median(x['size_in_sol'] for x in R),2),pnl_1d_usd=round(sum(x['size_out_usd']-x['size_in_usd'] for x in R)))
        # same-tx multi-mint / buy+sell same sig (MEV/arb pattern)
        bysig=collections.defaultdict(list)
        for s in sw: bysig[s['sig']].append(s)
        res['multi_leg_txs']=sum(len(v)>1 for v in bysig.values())
        res['med_pos_usd']=round(st.median(x['size_in_usd'] for x in R))
        old=json.load(open(f'an/{w}.json')) if os.path.exists(f'an/{w}.json') else {}
        if old.get('snipe_checked') is not None and old.get('rounds_closed')==len(R): res['snipe_checked']=old['snipe_checked']; res['snipe_early']=old['snipe_early']
        elif snipe:
            early=[];chk=0
            for x in sorted(R,key=lambda r:-r['size_in_sol'])[:15]:
                es=[t for t in txs if t['sig']==x['entry_sig']]
                if not es: continue
                prior=rpc('getSignaturesForAddress',[x['mint'],{"before":x['entry_sig'],"limit":1000}])
                if prior is None: continue
                chk+=1
                if len(prior)<1000:
                    gap=es[0]['slot']-prior[-1]['slot'] if prior else 0
                    if gap<=2: early.append([x['mint'],gap,len(prior)])
            res['snipe_checked']=chk; res['snipe_early']=early
    res['known_rugger']=w in KR; res['custodial']=w in CU
    os.makedirs('an',exist_ok=True); json.dump(res,open(f'an/{w}.json','w'),indent=1)
    return res
if __name__=='__main__':
    sn=os.environ.get('SNIPE')=='1'
    for w in sys.argv[1:]:
        r=run(w,sn)
        if r: print(json.dumps({k:v for k,v in r.items() if k not in('src',)}),flush=True)
