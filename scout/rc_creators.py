import json,os,sys,time,requests
from analyze import swaps,rounds
C='data/rc_creators.json'
AMM={'5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1','GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL','WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh','39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg'}; c=json.load(open(C)) if os.path.exists(C) else {}
for w in sys.argv[1:]:
    R,_=rounds(swaps(json.load(open(f'data/w/{w}.json'))['tx']))
    for m in {r['mint'] for r in R}:
        if m in c and 'liq_now_usd' in c[m]: continue
        try:
            r=requests.get(f'https://api.rugcheck.xyz/v1/tokens/{m}/report',timeout=30,headers={'User-Agent':'scout-readonly/1.0'})
            j=r.json() if r.ok else {}
        except Exception: j={}
        th=j.get('topHolders') or []
        EX=AMM|{x.get('pubkey') for x in (j.get('markets') or [])}|{x.get(k) for x in (j.get('markets') or []) for k in ('liquidityA','liquidityB')}|set((j.get('knownAccounts') or {}).keys())
        hs=[h for h in th if h.get('owner') not in EX and h.get('address') not in EX]
        c[m]={'max_holder_pct_now':round(max([h.get('pct',0) for h in hs] or [0]),2) if th else None,'insider_top20_pct_now':round(sum(h.get('pct',0) for h in th[:20] if h.get('insider')),2) if th else None,'graph_insiders':j.get('graphInsidersDetected'),'liq_now_usd':j.get('totalMarketLiquidity'),'n_insider_networks':len(j.get('insiderNetworks') or []),'creator':j.get('creator'),'top10_pct_now':round(sum(h.get('pct',0) for h in th[:10]),2) if th else None,'holders_now':j.get('totalHolders'),'ok':bool(j)}
        json.dump(c,open(C,'w')); time.sleep(1.5)
    cr=[m for m in {r['mint'] for r in R} if c.get(m,{}).get('creator')==w]
    print(w,'mints',len({r['mint'] for r in R}),'self-created',cr,'unknown',sum(1 for m in {r['mint'] for r in R} if not c.get(m,{}).get('ok')))
