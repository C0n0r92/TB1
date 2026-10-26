import json,urllib.request,time
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=30))
P={p['name'].split(' / ')[0]:p for p in json.load(open('pools.json'))}
R=json.load(open('/workspace/onchain-intel/data/runners_100x.json'))
want={}
for s in ['Hercules','Moustache','REMUS','SWORDOPE','MI','swordtrump','HOOKED','swordcat']:
    if s in P: want[s]=(P[s]['mint'],P[s]['pool'])
for r in R:
    if r['sym'] in ['McRib','YAGI','AOP','DacityCoin','mil','Pumptache','PRIVACY','ELIZABETH','DOPE'] and r['sym'] not in want:
        want[r['sym']]=(r['mint'],r['pool'])
out={}
for s,(mint,pool) in want.items():
    try:
        j=get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=15&limit=1000&currency=usd")
    except Exception as e: print(s,e); time.sleep(3); continue
    c=sorted(j['data']['attributes']['ohlcv_list'])  # ts,o,h,l,c,v
    if not c: continue
    sup=1e9
    pk=max(c,key=lambda x:x[2]); peak=pk[2]*sup
    first=c[0]
    # window: from first candle, until first candle whose close > 40% of peak (and before peak)
    end=None
    for x in c:
        if x[4]*sup>0.4*peak or x[0]>=pk[0]: end=x[0];break
    start=None
    for x in c:
        if x[4]*sup>=50000: start=x[0];break
    out[s]=dict(mint=mint,pool=pool,peak_mcap=round(peak),peak_ts=pk[0],first_ts=first[0],first_mcap=round(first[4]*sup),win_start=start,win_end=end,now_mcap=round(c[-1][4]*sup))
    print(s,out[s],flush=True); time.sleep(2.3)
json.dump(out,open('windows.json','w'),indent=1)
