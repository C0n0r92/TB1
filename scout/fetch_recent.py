"""Last N successful txs of a wallet via public RPC getTransaction (free) -> data/wp/<w>.json (same format as data/w)."""
import json,os,sys
from concurrent.futures import ThreadPoolExecutor
from pub import rpc
from fetchw import legs
N=int(os.environ.get('N','450')); os.makedirs('data/wp',exist_ok=True)
for w in sys.argv[1:]:
    S=[];before=None
    while len(S)<N:
        p={'limit':1000}
        if before:p['before']=before
        r=rpc('getSignaturesForAddress',[w,p])
        if not r:break
        S+=[x for x in r if not x.get('err')];before=r[-1]['signature']
        if len(r)<1000:break
    S=S[:N]
    def g(s):
        t=rpc('getTransaction',[s['signature'],{'encoding':'jsonParsed','maxSupportedTransactionVersion':0}])
        if not t:return None
        d,p,fp=legs(t,w);return {'sig':s['signature'],'ts':t['blockTime'],'d':d,'pump':p,'fp':fp}
    with ThreadPoolExecutor(2) as ex:R=list(ex.map(g,S))
    o={'n_sigs':len(S),'missing':sum(x is None for x in R),'tx':[x for x in R if x],'source':'public-rpc last %d'%N}
    json.dump(o,open(f'data/wp/{w}.json','w'));print(w,len(S),o['missing'],flush=True)
