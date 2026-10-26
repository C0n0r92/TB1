import json,urllib.request,time,sys
def rpc(m,p,url="https://api.mainnet-beta.solana.com"):
    for a in range(8):
        try:
            b=json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode()
            r=json.loads(urllib.request.urlopen(urllib.request.Request(url,data=b,headers={"Content-Type":"application/json"}),timeout=60).read())
            if "result" in r: return r["result"]
        except Exception as e: print(e,file=sys.stderr)
        time.sleep(2+a)
S=json.load(open("data/b1/truth_win_sigs.json"))
hi,lo=1792788300,1792787880   # 20:45:00 .. 20:38:00
anchor=min((s for s in S if (s.get("blockTime") or 0)>=hi), key=lambda s:s["blockTime"])["signature"]
truth={s["signature"]:s for s in S if lo<=(s.get("blockTime") or 0)<=hi and s.get("err") is None}
print("truth sigs in window",len(truth),file=sys.stderr)
res={}
for addr in ("R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX","AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51"):
    before=anchor; got=[]
    while True:
        r=rpc("getSignaturesForAddress",[addr,{"limit":1000,"before":before}])
        if not r: break
        got+=r; before=r[-1]["signature"]; print(addr[:5],len(got),time.strftime('%H:%M:%S',time.gmtime(r[-1]["blockTime"])),file=sys.stderr)
        if r[-1]["blockTime"]<lo or len(r)<1000: break
        time.sleep(0.5)
    res[addr]=[g["signature"] for g in got if g["signature"] in truth]
    print(addr[:5],"total",len(got),"intersect TRUTH",len(res[addr]),file=sys.stderr)
json.dump({k:[truth[s] for s in v] for k,v in res.items()},open("data/b1/fomo_truth_window.json","w"))
