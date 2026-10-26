import json,sys,glob,os,time
from analyze import swaps,rounds,stats
res={}
for fn in sys.argv[1:]:
    o=json.load(open(fn)); w=os.path.basename(fn)[:-5]; tx=o['tx']
    if not tx: print(w,'no tx');continue
    span=(time.time()-min(x['ts'] for x in tx))/86400
    R,op=rounds(swaps(tx)); s=stats(R,span); s['open']=op; s['span_d']=round(span,1); res[w]=s
    print(w[:6],{k:s.get(k) for k in ('span_d','n_closed','open','win_3','win_5','med_pct_3','med_pct_5','avg_pct_5','sum_sol_3','sum_sol_5','maxdd_sol_5','med_hold_min','win_hold_lt2m','night_trades_per_night','pump_entry_share','med_size_sol','n_mints')})
json.dump(res,open('data/stats_wg.json','w'),indent=0)
