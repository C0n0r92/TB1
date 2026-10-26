import json,urllib.request,time,sys
M="6bW6xsZxYqcvqabk9rRgQwgjPNwe8SACPusx5o1wpump"
def rpc(m,p,url="https://api.mainnet-beta.solana.com"):
    for a in range(8):
        try:
            b=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
            r=json.loads(urllib.request.urlopen(urllib.request.Request(url,data=b,headers={"Content-Type":"application/json"}),timeout=60).read())
            if "result" in r: return r["result"]
            print(r.get("error"),file=sys.stderr)
        except Exception as e: print(e,file=sys.stderr)
        time.sleep(2+a)
target=1792788600  # 20:50:00
slot=460579644+int((target-1792787448)/0.4)
for _ in range(6):
    bt=rpc("getBlockTime",[slot]); print(slot,bt,file=sys.stderr)
    if bt is None: slot+=1; continue
    if abs(bt-target)<20: break
    slot+=int((target-bt)/0.4)
blk=rpc("getBlock",[slot,{"transactionDetails":"signatures","rewards":False,"maxSupportedTransactionVersion":0}])
before=blk["signatures"][0]
allsig=[]
while True:
    r=rpc("getSignaturesForAddress",[M,{"limit":1000,"before":before}])
    if not r: break
    allsig+=r; before=r[-1]["signature"]; print(len(allsig),time.strftime('%H:%M:%S',time.gmtime(r[-1]["blockTime"])),file=sys.stderr)
    if r[-1]["blockTime"]<1792787700 or len(r)<1000: break
    time.sleep(0.5)
json.dump(allsig,open("data/b1/truth_win_sigs.json","w"))
