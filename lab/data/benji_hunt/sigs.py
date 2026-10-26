import json, time, urllib.request, os, sys
RPC = "https://api.mainnet-beta.solana.com"; ADDR = sys.argv[1]; STOP = int(sys.argv[2]); OUT = sys.argv[3]
def rpc(m, p):
    for k in range(6):
        try:
            r = urllib.request.Request(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(), {"Content-Type": "application/json"})
            j = json.load(urllib.request.urlopen(r, timeout=30))
            if "result" in j: return j["result"]
            print("err", j.get("error"), flush=True)
        except Exception as e: print("exc", e, flush=True)
        time.sleep(5 * (k + 1))
    raise SystemExit("rpc failed")
allr = json.load(open(OUT)) if os.path.exists(OUT) else []
before = allr[-1]["signature"] if allr else None
while True:
    p = {"limit": 1000}
    if before: p["before"] = before
    res = rpc("getSignaturesForAddress", [ADDR, p])
    if not res: break
    allr += res; before = res[-1]["signature"]
    json.dump(allr, open(OUT + ".tmp", "w")); os.replace(OUT + ".tmp", OUT)
    bt = res[-1].get("blockTime"); print(len(allr), time.strftime("%H:%M:%S", time.gmtime(bt)) if bt else None, flush=True)
    if bt and bt < STOP: break
    time.sleep(1.5)
