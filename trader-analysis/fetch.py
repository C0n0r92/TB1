import json,requests,time,os,threading,sys
from concurrent.futures import ThreadPoolExecutor
S=json.load(open('sol_sigs.json'))
RPCS=['https://solana-rpc.publicnode.com','https://solana-rpc.publicnode.com']
CAP=int(sys.argv[1]) if len(sys.argv)>1 else 300
os.makedirs('tx',exist_ok=True)
lock=threading.Lock()
def get(sig,i):
    fn=f'tx/{sig}.json'
    if os.path.exists(fn): return
    for attempt in range(8):
        url=RPCS[(i+attempt)%2]
        try:
            r=requests.post(url,json={"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":0}]},timeout=20).json()
            if 'result' in r and r['result']:
                json.dump(r['result'],open(fn,'w'));return
        except Exception as e: pass
        time.sleep(0.5)
jobs=[]
L=[[x['signature'] for x in res if x['err'] is None][:CAP] for res in S.values()]
import itertools
for t in itertools.zip_longest(*L):
    jobs+=[x for x in t if x]
print(len(jobs),flush=True)
done=0
with ThreadPoolExecutor(8) as ex:
    for k,_ in enumerate(ex.map(lambda a:get(*a),[(s,i) for i,s in enumerate(jobs)])):
        if k%100==0: print(k,time.strftime('%X'),flush=True)
print('DONE')
