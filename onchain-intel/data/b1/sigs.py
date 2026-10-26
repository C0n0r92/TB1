import json,urllib.request,time,sys
M="6bW6xsZxYqcvqabk9rRgQwgjPNwe8SACPusx5o1wpump"
def rpc(m,p,url="https://api.mainnet-beta.solana.com"):
    for a in range(5):
        try:
            b=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
            r=json.loads(urllib.request.urlopen(urllib.request.Request(url,data=b,headers={"Content-Type":"application/json"}),timeout=40).read())
            if "result" in r: return r["result"]
            print(r.get("error"),file=sys.stderr)
        except Exception as e: print(e,file=sys.stderr)
        time.sleep(1+a)
allsig=[]; before=None
while True:
    p={"limit":1000}; 
    if before: p["before"]=before
    r=rpc("getSignaturesForAddress",[M,p])
    if not r: break
    allsig+=r; before=r[-1]["signature"]
    print(len(allsig), time.strftime('%H:%M',time.gmtime(r[-1]["blockTime"])), file=sys.stderr)
    if r[-1]["blockTime"]<1792787400 or len(r)<1000: break
json.dump(allsig,open("data/b1/truth_sigs.json","w"))
