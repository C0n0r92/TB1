# Copy simulation: copier triggers only on target buys >= MIN usd (BG "Min Trade Size"), fixed size per trigger,
# copies sells proportionally; entry/exit at the target's own fill prices (no slippage/fees -> optimistic; 1% BG fee each side noted).
import json,sys,glob,os,statistics as st,time
sys.path.insert(0,'/workspace/scout'); import analyze as A
MIN=float(os.environ.get('MIN','100'))
def sim(sw,now):
    pos={}; out=[]
    for s in sw:
        m=s['mint']; p=pos.get(m)
        if s['side']=='buy':
            if p is None: p=pos[m]=dict(tb=0,ts=0,copy=None,c=[] )
            p['tb']+=s['tok']
            if s['usd']>=MIN and s['tok']>0: p['c'].append(dict(t=s['ts'],px=s['usd']/s['tok'],usd=s['usd'],sold=0.0,proc=0.0,sig=s['sig']))
        elif p:
            frac=min(1.0,s['tok']/max(p['tb']-p['ts'],1e-12)); px=s['usd']/s['tok'] if s['tok'] else 0
            p['ts']+=s['tok']
            for c in p['c']:
                q=(1-c['sold'])*frac; c['sold']+=q; c['proc']+=q*px; c['t1']=s['ts']
            if p['ts']>=0.95*p['tb']:
                for c in p['c']:
                    rem=1-c['sold']; c['proc']+=rem*px; c['sold']=1
                    out.append(dict(mint=m,ret=c['proc']/c['px']-1,hold=(c['t1']-c['t'])/60,usd=c['usd'],t=c['t'],sig=c['sig']))
                pos.pop(m)
    openc=sum(len(p['c']) for p in pos.values())
    return out,openc
if __name__=='__main__':
    now=time.time()
    for fn in sys.argv[1:] or glob.glob('tx/*.jsonl'):
        w=os.path.basename(fn)[:-6]
        L=[json.loads(l) for l in open(fn)]; L=[x for x in L if 'err' not in x and x['ts']>=now-86400]
        L.sort(key=lambda x:(x['slot'],x['ts']))
        sw=A.swaps(L); C,openc=sim(sw,now)
        trig=[s for s in sw if s['side']=='buy' and s['usd']>=MIN]
        r={'min_trigger_usd':MIN,'trigger_buys_24h':len(trig),'copied_closed':len(C),'copied_open':openc}
        if C:
            rets=[c['ret'] for c in C]; holds=[c['hold'] for c in C]
            r.update(copy_win_rate=round(sum(x>0 for x in rets)/len(rets),2),copy_med_ret_pct=round(st.median(rets)*100,1),
              copy_sum_ret_units=round(sum(rets),2),copy_sum_ex_best=round(sum(rets)-max(rets),2),copy_best_ret_pct=round(max(rets)*100,1),
              copy_med_hold_min=round(st.median(holds),1),copy_share_lt60s=round(sum(h<1 for h in holds)/len(holds),2),
              copy_share_lt2m=round(sum(h<2 for h in holds)/len(holds),2),copy_med_buy_usd=round(st.median(c['usd'] for c in C)),
              copy_sum_ret_after_2pct_cost=round(sum(x-0.02 for x in rets),2))
        json.dump(r,open(f'an/{w}.sim.json','w'))
        print(w[:6],r)
