"""Helius getTransactionsForAddress with tokenTransfer filter (isolates wallet's own token movements from spam). Read-only.
Usage: DET=signatures|full HOURS=24 HCAP=8000 python3 hgt.py w1 ..."""
import json,sys,os,time,urllib.request,math
sys.path.insert(0,'/workspace/scout'); sys.path.insert(0,'/workspace/onchain-intel/scripts')
from fetchw import legs
from sol import _helius_key
HOURS=float(os.environ.get('HOURS','24')); HCAP=int(os.environ.get('HCAP','8000')); DET=os.environ.get('DET','signatures')
LOG='/workspace/onchain-intel/data/rpc_calls.log'; CF='helius_used.json'
def hused(): return json.load(open(CF))['used']
def hadd(n):
    json.dump({'used':hused()+n},open(CF+'.tmp','w')); os.replace(CF+'.tmp',CF); open(LOG,'a').write(f"{int(time.time())} helius-gtfa {n}\n")
URL="https://mainnet.helius-rpc.com/?api-key="+_helius_key()
def post(body):
    for a in range(4):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(URL,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","User-Agent":"scout-readonly/1.0"}),timeout=90).read())
        except Exception as e: print('httperr',getattr(e,'code',None),flush=True); time.sleep(4*(a+1))
for w in sys.argv[1:]:
    cut=int(time.time()-HOURS*3600); tok=None; rows=[]; n=0
    while True:
        if hused()+10>HCAP: print('HCAP stop'); break
        cfg={"transactionDetails":DET,"limit":100 if DET=='full' else 1000,"filters":{"status":"succeeded","blockTime":{"gte":cut},"tokenTransfer":{}}}
        if DET=='full': cfg.update(encoding='jsonParsed',maxSupportedTransactionVersion=1)
        if tok: cfg['paginationToken']=tok
        r=post({"jsonrpc":"2.0","id":1,"method":"getTransactionsForAddress","params":[w,cfg]})
        if not r or 'error' in r: print(w[:6],'err',str(r)[:200]); break
        d=r['result']['data']; hadd(10 if DET=='signatures' else max(10,10*math.ceil(len(d)/100))); n+=1
        rows+=d; tok=r['result'].get('paginationToken')
        if not tok or not d: break
        time.sleep(0.5)
    if DET=='signatures':
        print(w[:6],'calls',n,'sigs',len(rows),'oldest',min((x['blockTime'] for x in rows),default=None)); continue
    out=open(os.environ.get('TXDIR','tx')+f'/{w}.jsonl','w'); bad=0
    for t in rows:
        sig=t['transaction']['signatures'][0]
        try:
            dd,p,fp=legs(t,w); ks=[k['pubkey'] if isinstance(k,dict) else k for k in t['transaction']['message']['accountKeys']]
            out.write(json.dumps({'sig':sig,'ts':t['blockTime'],'slot':t['slot'],'d':dd,'pump':p,'fp':fp,'payer':ks[0],'nix':len(t['transaction']['message']['instructions'])})+'\n')
        except Exception as e: bad+=1; out.write(json.dumps({'sig':sig,'ts':t.get('blockTime'),'slot':t.get('slot'),'err':str(e)[:80]})+'\n')
    out.close(); print(w[:6],'need',len(rows),'bad',bad,'calls',n,'hel_used',hused(),flush=True)
