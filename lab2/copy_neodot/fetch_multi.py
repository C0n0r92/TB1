"""Parallel tx fetch across two keyless public RPCs (mainnet-beta + publicnode), one throttled worker each. Same cache as rpc.py."""
import json, sys, os, time, threading, queue, urllib.request
sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc
EPS = [("https://api.mainnet-beta.solana.com", 0.25), ("https://solana-rpc.publicnode.com", 0.12), ("https://solana-rpc.publicnode.com", 0.12)]
def get(u, sig):
    req = urllib.request.Request(u, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getTransaction",
          "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}]}).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=40))
def worker(u, gap, q, stats):
    back = 1
    while True:
        try: sig = q.get_nowait()
        except queue.Empty: return
        f = os.path.join(rpc.D, "tx", sig + ".json")
        if os.path.exists(f): continue
        time.sleep(gap)
        try:
            r = get(u, sig); res = r.get("result")
            if res is None: raise RuntimeError(str(r)[:100])
            json.dump(res, open(f + ".tmp", "w")); os.replace(f + ".tmp", f); stats[u] = stats.get(u, 0) + 1; back = 1
        except Exception as e:
            q.put(sig); time.sleep(min(30, back)); back *= 2; stats["err"] = stats.get("err", 0) + 1
if __name__ == "__main__":
    sigs = [s.strip() for s in open(sys.argv[1]) if s.strip()]
    q = queue.Queue(); [q.put(s) for s in sigs]; stats = {}
    th = [threading.Thread(target=worker, args=(u, g, q, stats), daemon=True) for u, g in EPS]; [t.start() for t in th]
    t0 = time.time()
    while any(t.is_alive() for t in th):
        time.sleep(30); print(int(time.time() - t0), "s", stats, "left", q.qsize(), flush=True)
    print("DONE", stats, flush=True)
