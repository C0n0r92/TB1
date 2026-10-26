"""7d tx fetch via free public RPC (no Helius). Writes wc/tx7/<w>.jsonl in ftb format. Read-only."""
import json,sys,os,time,urllib.request,threading
sys.path.insert(0,'/workspace/scout'); sys.path.insert(0,'/workspace/onchain-intel/scripts')
from fetchw import legs
URLS=["https://solana-rpc.publicnode.com","https://api.mainnet-beta.solana.com"]
def post(url,body):
    for a in range(6):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","User-Agent":"scout-readonly/1.0"}),timeout=60).read())
        except Exception as e: time.sleep(3*(a+1))
    return None
def parse(t,w,sig):
    try:
        ks=[k['pubkey'] if isinstance(k,dict) else k for k in t['transaction']['message']['accountKeys']]
        d,p,fp=legs(t,w)
        return {'sig':sig,'ts':t['blockTime'],'slot':t['slot'],'d':d,'pump':p,'fp':fp,'payer':ks[0],'nix':len(t['transaction']['message']['instructions'])}
    except Exception as e: return {'sig':sig,'ts':t.get('blockTime'),'slot':t.get('slot'),'err':str(e)[:80]}
w=sys.argv[1]; cut=time.time()-7*86400; sigs=[]; before=None
for page in range(30):
    p={"limit":1000}
    if before: p["before"]=before
    r=post(URLS[0],{"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":[w,p]})
    r=(r or {}).get('result') or []
    sigs+=[x['signature'] for x in r if x.get('err') is None and (x.get('blockTime') or 0)>=cut]
    if len(r)<1000 or (r[-1].get('blockTime') or 0)<cut: break
    before=r[-1]['signature']; time.sleep(0.4)
print('sigs7d',len(sigs),flush=True)
fn=f'/workspace/runner-radar/wc/tx7/{w}.jsonl'; have=set()
if os.path.exists(fn): have={json.loads(l)['sig'] for l in open(fn)}
need=[s for s in sigs if s not in have]; lock=threading.Lock(); out=open(fn,'a'); done=[0]
def worker(k,url,gap):
    for s in need[k::NT]:
        time.sleep(gap)
        r=post(url,{"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[s,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]})
        t=(r or {}).get('result')
        if t:
            with lock: out.write(json.dumps(parse(t,w,s))+'\n'); done[0]+=1
            if done[0]%500==0: print('done',done[0],flush=True)
NT=4; th=[threading.Thread(target=worker,args=(k,URLS[0],0.35)) for k in range(NT)]
[t.start() for t in th]; [t.join() for t in th]; out.close(); print('fetched',done[0],'of',len(need),flush=True)
