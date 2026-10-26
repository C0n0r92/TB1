import sys,json,time,requests
sys.path.insert(0,'/workspace/onchain-intel/scripts'); sys.path.insert(0,'/workspace/scout')
from sol import _helius_key
import henh
LOG='/workspace/onchain-intel/data/rpc_calls.log'; CAP=1500; used=0
RELAY="AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51"; FEE="R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX"
now=time.time(); res={}
for h,w in [a.split('=') for a in sys.argv[1:]]:
    before=None; got=[]
    for page in range(2):
        if used+100>CAP or henh.day_total()+100>20000: print('budget stop'); break
        p={'api-key':_helius_key(),'type':'SWAP','limit':100}
        if before: p['before']=before
        r=requests.get(f'https://api.helius.xyz/v0/addresses/{w}/transactions',params=p,timeout=60)
        open(LOG,'a').write(f"{int(time.time())} helius-enhanced 1\n"); used+=100
        d=r.json() if r.ok else {'error':'http %s'%r.status_code}
        if isinstance(d,dict):
            msg=str(d.get('error',''))
            before=msg.split('before` parameter set to ')[-1].split('.')[0].strip() if 'before` parameter' in msg else None
            if not before: break
            continue
        got=d; break
    json.dump(got,open(f'/workspace/onchain-intel/tmp/enh_{h}.json','w'))
    ts=[x['timestamp'] for x in got]
    rel=sum(1 for x in got if x.get('feePayer')==RELAY or any(n.get('toUserAccount')==FEE for n in (x.get('nativeTransfers') or [])+(x.get('tokenTransfers') or [])))
    res[h]=dict(wallet=w,swaps=len(got),relayed=rel,
      last_swap_utc=time.strftime('%m-%d %H:%MZ',time.gmtime(ts[0])) if ts else None,
      idle_min=round((now-ts[0])/60) if ts else None,
      oldest_in_page=time.strftime('%m-%d %H:%MZ',time.gmtime(ts[-1])) if ts else None,
      n_1h=sum(now-t<3600 for t in ts),n_6h=sum(now-t<21600 for t in ts),n_24h=sum(now-t<86400 for t in ts))
    print(h,json.dumps(res[h]),flush=True)
print('credits used',used,'day_total',henh.day_total())
json.dump(res,open('/workspace/onchain-intel/tmp/enh_recent_summary.json','w'),indent=1)
