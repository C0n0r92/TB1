import requests,json,sys
W=json.load(open('wallets.json'))
T='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
CH={'base':'https://base-rpc.publicnode.com','bsc':'https://bsc-rpc.publicnode.com'}
def rpc(u,m,p): return requests.post(u,json={"jsonrpc":"2.0","id":1,"method":m,"params":p},timeout=20).json()
for ch,u in CH.items():
    bn=int(rpc(u,'eth_blockNumber',[])['result'],16)
    for n,(e,s) in W.items():
        pad='0x'+'0'*24+e[2:]
        tot=0;err=None
        for rng in [(bn-4999,bn)]:
            a=rpc(u,'eth_getLogs',[{"fromBlock":hex(rng[0]),"toBlock":hex(rng[1]),"topics":[T,None,pad]}])
            b=rpc(u,'eth_getLogs',[{"fromBlock":hex(rng[0]),"toBlock":hex(rng[1]),"topics":[T,pad]}])
            if 'result' in a and 'result' in b: tot=(len(a['result']),len(b['result']))
            else: err=(a.get('error'),b.get('error'))
        print(ch,n,'in/out transfers last 5k blocks',tot,err,flush=True)
