import json,sys,time,urllib.request
R="https://rpc.mainnet.chain.robinhood.com"
def rpc(m,p):
    for a in range(5):
        try:
            q=urllib.request.Request(R,json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{"content-type":"application/json","User-Agent":"Mozilla/5.0"})
            r=json.load(urllib.request.urlopen(q,timeout=40))
            return r.get('result',r)
        except Exception as e: err=e; time.sleep(2*(a+1))
    return {'error':str(err)}
TF="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
def bts(n): return int(rpc("eth_getBlockByNumber",[hex(n),False])['timestamp'],16)
latest=int(rpc("eth_blockNumber",[]),16); tl=bts(latest); t2=bts(latest-200000)
bps=200000/(tl-t2); print('latest',latest,time.strftime('%H:%MZ',time.gmtime(tl)),'blocks/s',round(bps,2))
hours=float(sys.argv[1]); start=int(latest-hours*3600*bps)
CH=int(sys.argv[2]) if len(sys.argv)>2 else 50000
for a in sys.argv[3:]:
    n,ad=a.split('='); pad='0x'+'0'*24+ad[2:].lower(); ev=[]
    for side in (1,2):
        b=start
        while b<=latest:
            e=min(b+CH-1,latest); top=[TF,None,None]; top[side]=pad
            r=rpc("eth_getLogs",[{"fromBlock":hex(b),"toBlock":hex(e),"topics":top}])
            if isinstance(r,dict): print(n,'err',str(r)[:200]); CH//=2; continue
            for l in r: ev.append((int(l['blockNumber'],16),'IN' if side==2 else 'OUT',l['address'],l['transactionHash']))
            b=e+1
    ev.sort(); txs={}
    for bn,d,tok,h in ev: txs.setdefault(h,(bn,[]))[1].append((d,tok[:10]))
    print(n,ad,'transfer events',len(ev),'txs',len(txs))
    for h,(bn,l) in sorted(txs.items(),key=lambda x:x[1][0])[-12:]:
        print('  ',time.strftime('%m-%d %H:%MZ',time.gmtime(bts(bn))),h[:14],l)
