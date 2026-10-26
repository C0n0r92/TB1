import json,os,collections,statistics as st,datetime
S=json.load(open('sol_sigs.json'));W=json.load(open('wallets.json'))
SOLUSD=103.61
WSOL='So11111111111111111111111111111111111111112'
USD={'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v','Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB','USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB','2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo'}
def irish_h(t): return ((t//3600)+1)%24
def inwin(t): h=irish_h(t); return h>=21 or h<8
def parse(tx,owner):
    m=tx['meta']; keys=[k['pubkey'] if isinstance(k,dict) else k for k in tx['transaction']['message']['accountKeys']]
    sol=0
    if owner in keys:
        i=keys.index(owner); sol=(m['postBalances'][i]-m['preBalances'][i]+ (m['fee'] if i==0 else 0))/1e9
    d=collections.defaultdict(float)
    for side,sg in (('preTokenBalances',-1),('postTokenBalances',1)):
        for b in m.get(side) or []:
            if b.get('owner')==owner:
                d[b['mint']]+=sg*float(b['uiTokenAmount']['uiAmount'] or 0)
    q=sol*SOLUSD + d.pop(WSOL,0)*SOLUSD
    for u in list(d):
        if u in USD: q+=d.pop(u)
    toks={k:v for k,v in d.items() if abs(v)>0}
    return q,toks
res={}
for n,(e,s) in W.items():
    ev=[]
    for x in S[n]:
        fn=f"tx/{x['signature']}.json"
        if x['err'] is None and os.path.exists(fn):
            tx=json.load(open(fn)); q,toks=parse(tx,s)
            if len(toks)==1:
                mint,amt=list(toks.items())[0]
                if amt>0 and q<-0.5: ev.append(('B',x['blockTime'],mint,amt,-q))
                elif amt<0 and q>0.05: ev.append(('S',x['blockTime'],mint,-amt,q))
                elif amt<0 and q<=0.05: ev.append(('X',x['blockTime'],mint,-amt,0))  # token out w/o proceeds (transfer)
    ev.sort(key=lambda e:e[1]); res[n]=ev
json.dump(res,open('events.json','w'))
# round trips
rows=[]
for n,ev in res.items():
    pos={}
    for k,t,mint,amt,usd in ev:
        p=pos.setdefault(mint,{'first':t,'bq':0,'bu':0,'sq':0,'su':0,'xq':0,'last':t,'buys':0,'sells':0,'fbp':None,'sp':[]})
        if k=='B': p['bq']+=amt;p['bu']+=usd;p['buys']+=1; p['fbp']=p['fbp'] or usd/amt
        elif k=='S': p['sq']+=amt;p['su']+=usd;p['sells']+=1;p['last']=t;p['sp'].append((t,usd/amt))
        else: p['xq']+=amt;p['last']=t
    trips=[p for p in pos.values() if p['bq']>0]
    closed=[p for p in trips if p['sq']>=0.9*p['bq']]
    wins=[p for p in closed if p['su']>p['bu']]
    holds=[(p['last']-p['first'])/60 for p in closed]
    buys=[e[4] for e in ev if e[0]=='B']; sells=[e for e in ev if e[0]=='S']; xs=[e for e in ev if e[0]=='X']
    # copier sim: first buy only, in window, $14
    pnl=0;cnt=0;cw=0;openn=0
    for p in trips:
        if not inwin(p['first']): continue
        if not p['sp']: openn+=1; continue
        entry=p['fbp']*1.03; stake=14*0.98; qty=stake/entry; proceeds=0; left=qty; tp=False
        for t,px in p['sp']:
            exit=px*0.97
            if exit<=entry*0.75: proceeds+=left*entry*0.75*0.98*0.97/0.97; left=0; break  # SL (optimistic: fills at -25%)
            if not tp and exit>=2*entry: proceeds+=left/2*exit*0.98; left/=2; tp=True
        if left>0:
            frac=min(1,p['sq']/p['bq']); avgx=p['su']/p['sq']*0.97
            proceeds+=left*frac*avgx*0.98  # unsold fraction treated as 0
        r=proceeds-14; pnl+=r;cnt+=1;cw+=r>0
    last=datetime.datetime.utcfromtimestamp(ev[-1][1]).strftime('%m-%d %H:%M') if ev else '-'
    span=(ev[-1][1]-ev[0][1])/86400 if ev else 0
    rows.append((n,len(ev),len(buys),len(sells),len(xs),len(trips),len(closed),len(wins)/len(closed)*100 if closed else None,st.median(holds) if holds else None,st.median(buys) if buys else None,sum(p['su']-p['bu'] for p in closed),cnt,cw,pnl,openn,span,last))
print("name evts buys sells xfer tokens closed win% medHoldMin medBuy$ traderRealized$ simN simWins simPnL$ openNoSell spanDays last")
for r in rows: print(*[f"{v:.1f}" if isinstance(v,float) else v for v in r])
