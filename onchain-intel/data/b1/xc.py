import json,sys,os,time
sys.path.insert(0,"scripts")
os.environ["SCOUT_PUBLIC_FIRST"]="1"; os.environ["SCOUT_HELIUS_BUDGET_FILE"]="/tmp/b1budget.json"
import sol
MOUS="J9WL4zQVCFvLTydjtHoMGcLasjhRMZomnVmp4Y2cpump"; B="9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc"
C="HweKg73ZH6xTLoXBYuDQBHJeeUahwB2gjVY97sSqDKYi 59puf9koHVBEy4abi9xQFr2AGxHaZo45BXomiJAWXtQ8 4CLifH4tdKj45Xa2ixZmQufLdqKnByBx3dDSMsB3GGbR 36izt4q3uYRhLnriBrSPz5E2LTgD8qzsM1hWZkPwgh2Q GdiM7NF9RC6RDMhyLeWEsGv365x9L9vQfRdXSCwHAYSm 7stb5TwRBEHrvGvHy4f61PRUNrdoZSF2JLRrGNWXmgX2 4YUiszKY2fVZFtZgk7XYeta635tWf6rgMYEibxqPPwAe".split()
t0=1792797600; t1=1792799400   # 23:20-23:50Z
for c in C:
    sigs=sol.rpc("getSignaturesForAddress",[c,{"limit":1000}]) or []
    near=[s for s in sigs if t0<=(s.get("blockTime") or 0)<=t1]
    hit=[];link=False
    for s in near[:40]:
        t=sol.tx(s["signature"])
        if not t: continue
        keys=json.dumps(t)
        if MOUS in keys: hit.append(s["signature"][:10])
    for s in sigs[:200]:
        pass
    print(c[:8],"sigs",len(sigs),"oldest",time.strftime('%m-%d %H:%M',time.gmtime(sigs[-1]["blockTime"])) if sigs else "-","in23:20-50",len(near),"moustache_txs",hit, "9PB1_in_recent" , any(B in json.dumps(sol.tx(s["signature"]) or {}) for s in sigs[:15]))
