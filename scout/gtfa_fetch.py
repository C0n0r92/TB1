"""Helius getTransactionsForAddress (full, jsonParsed, 100 tx/call, 10 credits/call) -> data/wg/<w>.json in data/w format. Read-only. Never prints key."""
import json,os,sys,time,requests
sys.path.insert(0,'/workspace/onchain-intel/scripts')
from sol import _helius_key
from fetchw import legs
from henh import used,add,day_total,LOG
CAP=int(os.environ.get('CAP','8000')); MAXP=int(os.environ.get('MAXP','30')); os.makedirs('data/wg',exist_ok=True)
cut=int(time.time()-30*86400)
for w in sys.argv[1:]:
    out=[];tok=None;pages=0;done=False;prev=0
    fn=f'data/wg/{w}.json'
    if os.environ.get('RESUME') and os.path.exists(fn):
        o0=json.load(open(fn))
        if o0.get('complete_30d'): print(w,'already complete',flush=True); continue
        if o0.get('next_token'): out=o0['tx'];tok=o0['next_token'];prev=o0.get('pages',0)
    while pages<MAXP:
        if used()+10>CAP or day_total()+10>int(os.environ.get('DAYSTOP','25000')): print('budget stop',flush=True);break
        cfg={"transactionDetails":"full","sortOrder":"desc","limit":100,"encoding":"jsonParsed","maxSupportedTransactionVersion":1,
             "filters":{"blockTime":{"gte":cut},"status":"succeeded","tokenAccounts":"balanceChanged"}}
        if tok:cfg["paginationToken"]=tok
        try: r=requests.post("https://mainnet.helius-rpc.com/?api-key="+_helius_key(),json={"jsonrpc":"2.0","id":1,"method":"getTransactionsForAddress","params":[w,cfg]},timeout=90).json()
        except Exception as e: print('err',type(e).__name__);break
        open(LOG,'a').write(f"{int(time.time())} helius-gtfa 10\n"); add(10); pages+=1
        if 'error' in r: print('rpc error',str(r['error'])[:200]);break
        res=r.get('result') or {}; data=res.get('data') or []
        for t in data:
            d,p,fp=legs(t,w); out.append({'sig':t['transaction']['signatures'][0],'ts':t['blockTime'],'d':d,'pump':p,'fp':fp})
        tok=res.get('paginationToken')
        if not tok or not data: done=True;break
        time.sleep(0.2)
    o={'n_sigs':len(out),'missing':0,'complete_30d':done,'pages':pages+prev,'next_token':None if done else tok,'tx':out,'source':'helius-gtfa(balanceChanged)'}
    json.dump(o,open(f'data/wg/{w}.json','w'))
    span=(time.time()-min(x['ts'] for x in out))/86400 if out else 0
    print(w,len(out),'complete' if done else 'partial',pages,'span_d',round(span,1),'used',used(),flush=True)
