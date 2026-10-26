#!/usr/bin/env python3
"""Hits check (free: GeckoTerminal). For each mint our bots traded, pull recent pool trades and
flag smart / early_buyer / avoid / known_rugger / funder wallets present, with first buy time vs our entry."""
import json,csv,sys,time,urllib.request
B='/workspace/onchain-intel/'
def get(u):
    for i in range(4):
        try:
            r=urllib.request.Request(u,headers={'accept':'application/json','user-agent':'scout/1'})
            return json.load(urllib.request.urlopen(r,timeout=25))
        except Exception as e:
            time.sleep(3+5*i)
    return None
tags={}
def tag(a,t):
    if a: tags.setdefault(a,set()).add(t)
sw=json.load(open(B+'smart_wallets.json'))
for k in ('smart','early_buyer','avoid'):
    for a in sw.get(k,{}): tag(a,'sw_'+k)
for r in csv.DictReader(open(B+'wallets.csv')): tag(r['address'],'wallets.csv:'+(r.get('confidence') or ''))
for r in csv.DictReader(open(B+'avoid.csv')): tag(r['address'],'avoid.csv')
kr=json.load(open(B+'known_ruggers.json'))
it=kr.items() if isinstance(kr,dict) else [(x.get('address'),x) for x in kr]
for a,v in it:
    if isinstance(v,dict) and 'address' in v: a=v['address']
    if a and len(a)>30: tag(a,'known_rugger')
for r in csv.DictReader(open(B+'known_funders.csv')):
    a=r.get('address') or r.get('funder') or list(r.values())[0]; tag(a,'known_funder')
mints=json.load(open(sys.argv[1]))  # [{sym,mint,our_entry,outcome}]
out=[]
for m in mints:
    p=get(f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{m['mint']}/pools?page=1")
    time.sleep(2.2)
    pools=[x['attributes']['address'] for x in (p or {}).get('data',[])][:2]
    seen={}
    ntr=0
    for pool in pools:
        t=get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/trades")
        time.sleep(2.2)
        for tr in (t or {}).get('data',[]):
            a=tr['attributes']; ntr+=1
            w=a.get('tx_from_address')
            if w in tags:
                s=seen.setdefault(w,{'tags':sorted(tags[w]),'buys':0,'sells':0,'first':a['block_timestamp'],'vol_usd':0.0,'tx':a.get('tx_hash')})
                s['buys' if a['kind']=='buy' else 'sells']+=1
                s['vol_usd']+=float(a.get('volume_in_usd') or 0)
                if a['block_timestamp']<s['first']: s['first']=a['block_timestamp']; s['tx']=a.get('tx_hash')
    out.append({**m,'pools':pools,'trades_scanned':ntr,'hits':seen})
    print(m['sym'],ntr,len(seen),file=sys.stderr)
json.dump(out,open(sys.argv[2],'w'),indent=1)
