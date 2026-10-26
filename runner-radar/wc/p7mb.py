import json,sys,os,time,threading
sys.argv=['x','8zkgFGVZrDLieViwqiXFCydSX6WL5hsxmUu55yBdsNsZ']
exec(open('p7pub.py').read().split("w=sys.argv[1]")[0])
w=sys.argv[1]; fn=f'tx7/{w}.jsonl'; have={json.loads(l)['sig'] for l in open(fn)}
need=[x['s'] for x in json.load(open('sig7_8zkg.json')) if x['s'] not in have]; print('need',len(need),flush=True)
out=open(fn,'a'); lock=threading.Lock(); done=[0]; miss=[0]; NT=int(os.environ.get('NT','2')); GAP=float(os.environ.get('GAP','0.6'))
def worker(k):
    for s in need[k::NT]:
        time.sleep(GAP)
        r=post("https://api.mainnet-beta.solana.com",{"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[s,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]})
        t=(r or {}).get('result')
        with lock:
            if t: out.write(json.dumps(parse(t,w,s))+'\n'); out.flush(); done[0]+=1
            else: miss[0]+=1
            if (done[0]+miss[0])%250==0: print('done',done[0],'miss',miss[0],time.strftime('%H:%M'),flush=True)
th=[threading.Thread(target=worker,args=(k,)) for k in range(NT)]; [t.start() for t in th]; [t.join() for t in th]
print('fetched',done[0],'miss',miss[0],flush=True)
