"""Fetch + parse wallet txs for a time window (public RPC free; optional Helius RPC with hard credit cap). Read-only.
Usage: HOURS=24 HCAP=3000 python3 ftx.py w1 w2 ...   -> tx/<w>.jsonl (one parsed tx per line, cached, incremental)"""
import json,sys,os,time,threading,queue,urllib.request
sys.path.insert(0,'/workspace/scout'); sys.path.insert(0,'/workspace/onchain-intel/scripts')
from fetchw import legs
from sol import _helius_key
HOURS=float(os.environ.get('HOURS','24')); HCAP=int(os.environ.get('HCAP','0')); PUBT=int(os.environ.get('PUBT','2'))
LOG='/workspace/onchain-intel/data/rpc_calls.log'; CF='helius_used.json'
os.makedirs('tx',exist_ok=True)
lock=threading.Lock()
def hused(): return json.load(open(CF))['used'] if os.path.exists(CF) else 0
PUB="https://api.mainnet-beta.solana.com"
HEL="https://mainnet.helius-rpc.com/?api-key="+(_helius_key() or '') if HCAP else None
def call(url,sig):
    if url==PUB:
        import fetchlayer; return fetchlayer.rpc('getTransaction',[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
    req=urllib.request.Request(url,data=json.dumps({"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]}).encode(),headers={"Content-Type":"application/json","User-Agent":"scout-readonly/1.0"})
    r=json.loads(urllib.request.urlopen(req,timeout=40).read()); return r.get('result')
def parse(t,w,sig):
    d,p,fp=legs(t,w)
    ks=[k['pubkey'] if isinstance(k,dict) else k for k in t['transaction']['message']['accountKeys']]
    return {'sig':sig,'ts':t['blockTime'],'slot':t['slot'],'d':d,'pump':p,'fp':fp,'payer':ks[0],'nix':len(t['transaction']['message']['instructions'])}
def worker(kind,q,out,w):
    gap=0.0 if kind=='pub' else 0.35; last=0
    while True:
        try: sig=q.get_nowait()
        except queue.Empty: return
        if kind=='hel':
            with lock:
                if hused()>=HCAP: q.put(sig); return
                json.dump({'used':hused()+1},open(CF,'w')); open(LOG,'a').write(f"{int(time.time())} helius-rpc 1\n")
        for a in range(6):
            wt=last+gap-time.time()
            if wt>0: time.sleep(wt)
            last=time.time()
            try:
                t=call(PUB if kind=='pub' else HEL,sig)
                if t:
                    with lock: out.write(json.dumps(parse(t,w,sig))+'\n'); out.flush()
                    break
            except Exception as e: time.sleep(3*(a+1))
        q.task_done() if False else None
for w in sys.argv[1:]:
    S=json.load(open(f'sig/{w}.json')); cut=time.time()-HOURS*3600
    fn=f'tx/{w}.jsonl'; have=set()
    if os.path.exists(fn):
        for l in open(fn):
            try: have.add(json.loads(l)['sig'])
            except: pass
    need=[x['s'] for x in S['sigs'] if x['t']>=cut and x['s'] not in have]
    q=queue.Queue(); [q.put(s) for s in need]
    t0=time.time()
    with open(fn,'a') as out:
        th=[threading.Thread(target=worker,args=('pub',q,out,w)) for _ in range(PUBT)]
        if HCAP: th+=[threading.Thread(target=worker,args=('hel',q,out,w)) for _ in range(3)]
        [x.start() for x in th]; [x.join() for x in th]
    print(w[:6],'need',len(need),'left',q.qsize(),'secs',round(time.time()-t0),'hel_used',hused(),flush=True)
