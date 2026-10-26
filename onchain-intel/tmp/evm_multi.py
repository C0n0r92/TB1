import json,urllib.request,time,sys
TF="0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CH={"base":"https://base-rpc.publicnode.com","bsc":"https://bsc-rpc.publicnode.com","monad":"https://rpc.monad.xyz"}
def rpc(R,m,p):
    for a in range(5):
        try:
            q=urllib.request.Request(R,json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{"content-type":"application/json","User-Agent":"Mozilla/5.0"})
            r=json.load(urllib.request.urlopen(q,timeout=40))
            if 'error' in r: return r
            return r['result']
        except Exception as e: time.sleep(3*(a+1))
    return {'error':'fail'}
W={"ETT":"6434454a2f00b3dbbf714de40c71c86857f881a3","PFC":"fd87eda88be6c372453b721da63d58ad1a5b2d94"}
HRS=float(sys.argv[1])
for c,R in CH.items():
    L=rpc(R,"eth_blockNumber",[])
    if isinstance(L,dict): print(c,'rpc fail',L); continue
    L=int(L,16); t1=int(rpc(R,"eth_getBlockByNumber",[hex(L),False])['timestamp'],16); t0=int(rpc(R,"eth_getBlockByNumber",[hex(L-10000),False])['timestamp'],16)
    bps=10000/max(1,t1-t0); start=L-int(HRS*3600*bps); step=int(sys.argv[2]) if len(sys.argv)>2 else 5000
    print(c,'latest',L,'bps',round(bps,2),flush=True)
    for n,ad in W.items():
        pad='0x'+'0'*24+ad; ev=[]; s=step
        for side in (1,2):
            b=start
            while b<=L:
                e=min(b+s-1,L); top=[TF,None,None]; top[side]=pad
                r=rpc(R,"eth_getLogs",[{"fromBlock":hex(b),"toBlock":hex(e),"topics":top}])
                if isinstance(r,dict):
                    if s>200: s//=2; continue
                    print(c,n,'err',str(r)[:150]); break
                ev+=[(int(l['blockNumber'],16),'OUT' if side==1 else 'IN',l['address'][:10],l['transactionHash'][:12]) for l in r]; b=e+1
        print(' ',c,n,'events',len(ev),'OUT',sum(1 for x in ev if x[1]=='OUT'),sorted(ev)[-6:],flush=True)
