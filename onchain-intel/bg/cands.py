import json
K=json.load(open('kolscan_daily.json')); D=json.load(open('kolscan_directory.json'))
d1={x['wallet']:x for x in K if x['timeframe']==1}; d7={x['wallet']:x for x in K if x['timeframe']==7}; d30={x['wallet']:x for x in K if x['timeframe']==30}
seeds=['Rilsio','KOREAN','zeropnl','bystevenr','Cented','decu','Schoen','West']
name2w={v['name']:w for w,v in D.items()}
for x in K: name2w.setdefault(x['name'],x['wallet'])
C={}
for s in seeds:
    w=name2w.get(s)
    if s=='bystevenr': w='AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx'
    C[w]=dict(name=s,seed=True)
for w,x in d1.items():
    if x['profit_sol']>0 and x['wins']+x['losses']>=10: C.setdefault(w,dict(name=x['name'],seed=False))
for w,c in C.items():
    tw=(D.get(w) or {}).get('twitter') or (d1.get(w) or d7.get(w) or {}).get('twitter')
    c.update(twitter=tw,k1=d1.get(w),k7=d7.get(w),k30=d30.get(w))
json.dump(C,open('cands.json','w'),indent=1)
print(len(C)); [print(c['name'],w,c['twitter'],bool(c['k1']),bool(c['k7'])) for w,c in C.items()]
