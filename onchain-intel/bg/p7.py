"""7d realized on-chain PnL from tx7/<w>.jsonl (Helius gTFA 168h). Writes an/<w>.p7.json. Read-only."""
import json,sys,time,os
sys.path.insert(0,'/workspace/scout'); import analyze as A
NOW=time.time()
for w in sys.argv[1:]:
    L=[];seen=set()
    for l in open(f'tx7/{w}.jsonl'):
        x=json.loads(l)
        if 'err' in x or x['sig'] in seen: continue
        seen.add(x['sig']); L.append(x)
    sw=[s for s in A.swaps(L) if s['ts']>NOW-7*86400]
    R,op=A.rounds(sw)
    net=[r['size_out_sol']-r['size_in_sol'] for r in R]
    cap=[r['size_in_sol']*min(r['size_out_sol']/r['size_in_sol']-1,(r['exit_price_usd']/r['entry_price_usd']-1) if r['entry_price_usd'] else 9e9) for r in R]
    days={}
    for r,n in zip(R,net): d=time.strftime('%m-%d',time.gmtime(r['exit_ts'])); days[d]=round(days.get(d,0)+n,2)
    o=dict(wallet=w,n_tx=len(L),swaps_7d=len(sw),rounds_closed_7d=len(R),open_7d=op,pnl7_onchain_sol=round(sum(net),2),pnl7_capped_sol=round(sum(cap),2),
           pnl7_ex_best_sol=round(sum(net)-max(net),2) if net else None,win_rate_7d=round(sum(n>0 for n in net)/len(R),2) if R else None,daily_sol=days,
           src=os.environ.get('SRC','helius getTransactionsForAddress 168h, tokenTransfer filter; realized closed rounds only'))
    json.dump(o,open(f'an/{w}.p7.json','w')); print(w[:6],{k:v for k,v in o.items() if k not in('wallet','src')})
