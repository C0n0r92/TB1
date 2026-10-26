"""Helius enhanced SWAP history, incremental, hard credit cap (bg/helius_used.json, 100/call). Never prints the key.
Usage: CAP=7500 HOURS=24 MAXP=3 python3 hx.py w1 w2 ..."""
import json,os,sys,time,requests
sys.path.insert(0,'/workspace/onchain-intel/scripts'); sys.path.insert(0,'/workspace/scout')
from sol import _helius_key
import trader_trades as TT
LOG='/workspace/onchain-intel/data/rpc_calls.log'; CF='helius_used.json'; CAP=int(os.environ.get('CAP','7500'))
HOURS=float(os.environ.get('HOURS','24')); MAXP=int(os.environ.get('MAXP','3'))
os.makedirs('raw',exist_ok=True)
def used(): return json.load(open(CF))['used'] if os.path.exists(CF) else 0
def add(n): json.dump({'used':used()+n},open(CF,'w'))
def fetch(w):
    fn=f'raw/{w}.json'; st=json.load(open(fn)) if os.path.exists(fn) else {'raw':[],'end':False}
    raw=st['raw']; have={x['signature'] for x in raw}
    cut=time.time()-HOURS*3600; pages=0
    # newest first: if cached, first refresh head (new txs) with one page
    if raw:
        p={'api-key':_helius_key(),'type':'SWAP','limit':100}
        if used()+100<=CAP:
            r=requests.get(f'https://api.helius.xyz/v0/addresses/{w}/transactions',params=p,timeout=60); add(100); pages+=1
            open(LOG,'a').write(f"{int(time.time())} helius-enhanced 1\n")
            d=r.json() if r.ok else []
            if isinstance(d,list): raw+=[x for x in d if x['signature'] not in have]; have|={x['signature'] for x in d}
    raw.sort(key=lambda x:-x['timestamp'])
    before=raw[-1]['signature'] if raw else None
    while not st['end'] and pages<MAXP and not (raw and raw[-1]['timestamp']<cut):
        if used()+100>CAP: print('CAP stop',w,flush=True); break
        p={'api-key':_helius_key(),'type':'SWAP','limit':100}
        if before: p['before']=before
        r=requests.get(f'https://api.helius.xyz/v0/addresses/{w}/transactions',params=p,timeout=60)
        add(100); pages+=1; open(LOG,'a').write(f"{int(time.time())} helius-enhanced 1\n"); time.sleep(0.2)
        try: d=r.json()
        except Exception: d=None
        if d is None or (not r.ok and not isinstance(d,dict)): print('http',r.status_code,w,str(r.text)[:160],flush=True); break
        if isinstance(d,dict):
            msg=str(d.get('error',''))
            if 'before` parameter set to ' in msg: before=msg.split('before` parameter set to ')[-1].split('.')[0].strip(); continue
            print('dict',r.status_code,w,msg[:160],flush=True); st['end']=True; break
        if not d: st['end']=True; break
        raw+=[x for x in d if x['signature'] not in have]; have|={x['signature'] for x in d}; before=d[-1]['signature']
    raw.sort(key=lambda x:-x['timestamp']); st['raw']=raw; json.dump(st,open(fn,'w'))
    span=(time.time()-raw[-1]['timestamp'])/3600 if raw else 0
    print(w[:6],'swaps',len(raw),'span_h',round(span,1),'pages',pages,'used',used(),flush=True)
if __name__=='__main__':
    for w in sys.argv[1:]: fetch(w)
