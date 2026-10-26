"""Read-only: pull a wallet's last DAYS of txs via public RPC (free), extract swap legs. Caches per wallet."""
import json,time,os,sys
from concurrent.futures import ThreadPoolExecutor
from pub import rpc
DAYS=int(os.environ.get('DAYS','30')); MAXTX=int(os.environ.get('MAXTX','2500'))
SOL="So11111111111111111111111111111111111111112"
USD={"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
PUMP="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
os.makedirs('data/w',exist_ok=True)
def sigs(w):
    cut=time.time()-DAYS*86400; out=[]; before=None
    while len(out)<MAXTX+1000:
        p={"limit":1000}
        if before: p["before"]=before
        r=rpc("getSignaturesForAddress",[w,p])
        if not r: break
        out+=r; before=r[-1]['signature']
        if (r[-1].get('blockTime') or 0)<cut or len(r)<1000: break
    return [x for x in out if not x.get('err') and (x.get('blockTime') or 0)>=cut]
def legs(tx,w):
    m=tx['meta']; keys=[k['pubkey'] if isinstance(k,dict) else k for k in tx['transaction']['message']['accountKeys']]
    keys+= (m.get('loadedAddresses') or {}).get('writable',[])+(m.get('loadedAddresses') or {}).get('readonly',[])
    d={}
    if w in keys:
        i=keys.index(w); d[SOL]=(m['postBalances'][i]-m['preBalances'][i])/1e9
    tb={}
    for s,arr in ((-1,m.get('preTokenBalances') or []),(1,m.get('postTokenBalances') or [])):
        for t in arr:
            if t.get('owner')==w:
                tb[t['mint']]=tb.get(t['mint'],0)+s*float(t['uiTokenAmount']['uiAmount'] or 0)
    for k,v in tb.items(): d[k]=d.get(k,0)+v   # wSOL merges into SOL
    pump=PUMP in keys
    fp=keys[0]==w
    return {k:v for k,v in d.items() if abs(v)>1e-9},pump,fp
def get(w):
    fn=f'data/w/{w}.json'
    if os.path.exists(fn): return json.load(open(fn))
    S=sigs(w)
    if len(S)>MAXTX: json.dump({'too_many':len(S)},open(fn,'w')); return {'too_many':len(S)}
    def g(s):
        t=rpc("getTransaction",[s['signature'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}])
        if not t: return None
        d,p,fp=legs(t,w); return {'sig':s['signature'],'ts':t['blockTime'],'d':d,'pump':p,'fp':fp}
    with ThreadPoolExecutor(2) as ex: R=[x for x in ex.map(g,S)]
    miss=sum(1 for x in R if x is None)
    out={'n_sigs':len(S),'missing':miss,'tx':[x for x in R if x]}
    json.dump(out,open(fn,'w')); return out
if __name__=='__main__':
    for w in sys.argv[1:]:
        t=time.time(); o=get(w); print(w,o.get('too_many'),o.get('n_sigs'),o.get('missing'),round(time.time()-t),flush=True)
