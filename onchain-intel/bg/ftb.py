"""Batch tx fetch. MODE=hel (Helius JSON-RPC batch of 25, 1 credit/tx, hard cap HCAP on helius_used.json) or MODE=pub (public, serial).
Parse errors are recorded, never retried. Read-only. Usage: MODE=hel HOURS=24 HCAP=6500 python3 ftb.py w1 w2 ..."""
import json,sys,os,time,urllib.request
sys.path.insert(0,'/workspace/scout'); sys.path.insert(0,'/workspace/onchain-intel/scripts')
from fetchw import legs
from sol import _helius_key
MODE=os.environ.get('MODE','hel'); HOURS=float(os.environ.get('HOURS','24')); HCAP=int(os.environ.get('HCAP','0'))
LOG='/workspace/onchain-intel/data/rpc_calls.log'; CF='helius_used.json'
def hused(): return json.load(open(CF))['used']
def hadd(n):
    json.dump({'used':hused()+n},open(CF+'.tmp','w')); os.replace(CF+'.tmp',CF); open(LOG,'a').write(f"{int(time.time())} helius-rpc {n}\n")
URL="https://mainnet.helius-rpc.com/?api-key="+_helius_key() if MODE=='hel' else os.environ.get("URL","https://api.mainnet-beta.solana.com")
def post(body):
    for a in range(5):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(URL,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","User-Agent":"scout-readonly/1.0"}),timeout=60).read())
        except Exception as e:
            print('httperr',getattr(e,'code',None),flush=True); time.sleep(3*(a+1))
    return None
def parse(t,w,sig):
    try:
        d,p,fp=legs(t,w)
        ks=[k['pubkey'] if isinstance(k,dict) else k for k in t['transaction']['message']['accountKeys']]
        return {'sig':sig,'ts':t['blockTime'],'slot':t['slot'],'d':d,'pump':p,'fp':fp,'payer':ks[0],'nix':len(t['transaction']['message']['instructions'])}
    except Exception as e: return {'sig':sig,'ts':t.get('blockTime'),'slot':t.get('slot'),'err':str(e)[:80]}
B=int(os.environ.get('B','10')) if MODE=='hel' else 1
for w in sys.argv[1:]:
    S=json.load(open(f'sig/{w}.json')); cut=time.time()-HOURS*3600
    fn=f'tx/{w}.jsonl'; have=set()
    if os.path.exists(fn):
        for l in open(fn):
            try: have.add(json.loads(l)['sig'])
            except: pass
    need=[x['s'] for x in S['sigs'] if x['t']>=cut and x['s'] not in have]; t0=time.time(); stop=False
    with open(fn,'a') as out:
        for i in range(0,len(need),B):
            ch=need[i:i+B]
            if MODE=='hel':
                if hused()+len(ch)>HCAP: stop=True; break
                hadd(len(ch)); time.sleep(float(os.environ.get('GAP','1.0')))
            else: time.sleep(float(os.environ.get('GAP','0.6')))
            r=post([{"jsonrpc":"2.0","id":j,"method":"getTransaction","params":[s,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]} for j,s in enumerate(ch)])
            if not isinstance(r,list): print("bad",str(r)[:150],flush=True); continue
            for x in r:
                t=x.get('result')
                if x.get("error"): print("rpcerr",str(x["error"])[:120],flush=True)
                if t: out.write(json.dumps(parse(t,w,ch[x['id']]))+'\n')
            out.flush()
    print(w[:6],'need',len(need),'secs',round(time.time()-t0),'hel_used',hused(),'STOP' if stop else '',flush=True)
    if stop: break
