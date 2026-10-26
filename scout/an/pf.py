"""FREE public-RPC deep fetch -> an/wg/<w>.json. No Helius. Logs progress/errors."""
import json,time,os,sys,threading,urllib.request
sys.path.insert(0,'/workspace/scout')
from fetchw import legs
RPC="https://api.mainnet-beta.solana.com"; L=threading.Lock(); last=[0.0]; GAP=float(os.environ.get('GAP','0.3')); ERR=[0]
def rpc(m,p,tries=5):
    for a in range(tries):
        with L:
            w=last[0]+GAP-time.time()
            if w>0: time.sleep(w)
            last[0]=time.time()
        try:
            req=urllib.request.Request(RPC,data=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),headers={"Content-Type":"application/json","User-Agent":"scout-readonly/1.0"})
            r=json.loads(urllib.request.urlopen(req,timeout=20).read())
            if "result" in r: return r["result"]
            ERR[0]+=1
        except Exception as e:
            ERR[0]+=1
        time.sleep(1.5*(a+1))
    return None
from concurrent.futures import ThreadPoolExecutor
MAXTX=int(os.environ.get('MAXTX','500')); DAYS=float(os.environ.get('DAYS','14'))
for w in sys.argv[1:]:
    fn=f'an/wg/{w}.json'
    if os.path.exists(fn): print(w,'cached',flush=True); continue
    t0=time.time(); cut=time.time()-DAYS*86400; S=[]; before=None
    while len(S)<MAXTX:
        p={"limit":1000}
        if before: p["before"]=before
        r=rpc("getSignaturesForAddress",[w,p])
        if not r: break
        S+=[x for x in r if not x.get('err') and (x.get('blockTime') or 0)>=cut]; before=r[-1]['signature']
        if (r[-1].get('blockTime') or 0)<cut or len(r)<1000: break
    trunc=len(S)>MAXTX; S=S[:MAXTX]
    def g(s):
        t=rpc("getTransaction",[s['signature'],{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
        if not t: return None
        d,pp,fp=legs(t,w); return {'sig':s['signature'],'ts':t['blockTime'],'d':d,'pump':pp,'fp':fp}
    with ThreadPoolExecutor(4) as ex: R=list(ex.map(g,S))
    tx=[x for x in R if x]
    json.dump({'n_sigs':len(S),'missing':len(S)-len(tx),'complete_30d':False,'truncated':trunc,'tx':tx,'source':'public-rpc'},open(fn,'w'))
    print(w,len(S),'trunc' if trunc else '','miss',len(S)-len(tx),'errs',ERR[0],round(time.time()-t0),'s',flush=True)
