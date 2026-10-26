"""Helius enhanced SWAP history -> data/w/<wallet>.json (same format as fetchw). Credits logged to rpc_calls.log (100/call).
Hard cap via data/credits_batch.json. Never prints the key."""
import json,os,sys,time,requests
sys.path.insert(0,'/workspace/onchain-intel/scripts')
from sol import _helius_key
import trader_trades as TT
LOG='/workspace/onchain-intel/data/rpc_calls.log'; CAP=int(os.environ.get('CAP','8000'))
CF='data/credits_batch.json'
def used(): return json.load(open(CF))['used'] if os.path.exists(CF) else 0
def add(n): json.dump({'used':used()+n},open(CF,'w'))
def day_total():
    day=time.strftime('%Y-%m-%d',time.gmtime()); tot=0
    for l in open(LOG):
        p=l.split()
        if len(p)!=3: continue
        try: d=p[0] if '-' in p[0] else time.strftime('%Y-%m-%d',time.gmtime(int(p[0])))
        except: continue
        if d==day: tot+=int(p[2])*(100 if p[1]=='helius-enhanced' else 1)
    return tot
def conv(raw,w):
    out=[]
    for x in raw:
        d=TT.legs(x,w)
        out.append({'sig':x['signature'],'ts':x['timestamp'],'d':d,'pump':x.get('source')=='PUMP_FUN','fp':x.get('feePayer')==w,'src':x.get('source')})
    return out
def fetch(w,days=30,maxpages=10):
    fn=f'data/w/{w}.json'; rawfn=f'data/raw/{w}.json'; os.makedirs('data/raw',exist_ok=True)
    raw=json.load(open(rawfn)) if os.path.exists(rawfn) else []
    have={x['signature'] for x in raw}; before=raw[-1]['signature'] if raw else None
    cut=time.time()-days*86400; done=bool(raw) and raw[-1]['timestamp']<cut
    pages=0
    while not done and pages<maxpages:
        if used()+100>CAP or day_total()+100>25000: print('budget stop',w,flush=True); break
        p={'api-key':_helius_key(),'type':'SWAP','limit':100}
        if before: p['before']=before
        r=requests.get(f'https://api.helius.xyz/v0/addresses/{w}/transactions',params=p,timeout=60)
        open(LOG,'a').write(f"{int(time.time())} helius-enhanced 1\n"); add(100); pages+=1; time.sleep(0.25)
        d=r.json() if r.ok else []
        if isinstance(d,dict):
            msg=str(d.get('error','')); before=msg.split('before` parameter set to ')[-1].split('.')[0].strip() if 'before' in msg else None
            if not before: done=True
            continue
        if not d: done=True; break
        raw+=[x for x in d if x['signature'] not in have]; before=d[-1]['signature']
        if d[-1]['timestamp']<cut: done=True
    raw.sort(key=lambda x:-x['timestamp']); json.dump(raw,open(rawfn,'w'))
    o={'n_sigs':len(raw),'missing':0,'complete_30d':done,'pages':pages,'tx':conv([x for x in raw if x['timestamp']>=cut],w),'source':'helius-enhanced'}
    json.dump(o,open(fn,'w')); return o
if __name__=='__main__':
    mp=int(os.environ.get('MAXP','10'))
    for w in sys.argv[1:]:
        o=fetch(w,maxpages=mp); print(w,len(o['tx']),'complete' if o['complete_30d'] else 'partial',o['pages'],'used',used(),flush=True)
