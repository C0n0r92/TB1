import json,collections,datetime as dt
T=json.load(open('trips_full.json'))
D=json.load(open('hl.json'))
def agg(key):
    g=collections.defaultdict(lambda:[0,0,0.0,0.0,0.0,0.0,0.0])
    for t in T:
        k=key(t);a=g[k];a[0]+=1;a[1]+=t['net']>0;a[2]+=t['net'];a[3]+=t['gross'];a[4]+=t['fees'];a[5]+=t['fund'];a[6]+=t['R']
    return g
for name,f in [('bot',lambda t:t['bot']),('bot/strat',lambda t:(t['bot'],t['strat'] if t['bot']=='scalper' else 'perp-vote')),('bot/side',lambda t:(t['bot'],t['side'])),('bot/exit',lambda t:(t['bot'],t['exit_reason'])),('scalper ver',lambda t:(t['bot'],t['ver'][:2])),('ALL',lambda t:'all')]:
    print('==',name)
    for k,a in sorted(agg(f).items(),key=lambda x:x[1][2]):
        print(f"  {str(k):45} n{a[0]:2} w{a[1]:2} net{a[2]:+7.3f} gross{a[3]:+7.3f} fees{a[4]:6.3f} fund{a[5]:+6.3f} sumR{a[6]:+6.2f}")
allf=sum(float(x['delta']['usdc']) for x in D['funding'] if x['time']>=1792886400000)
print('funding on 25 Oct total',allf)
p=dict(D['portfolio'])
for k in ('day','perpDay'):
    print(k,[(dt.datetime.utcfromtimestamp(a/1000).strftime('%d %H:%M'),b) for a,b in p[k]['accountValueHistory']])
    print(k,'pnl',[(dt.datetime.utcfromtimestamp(a/1000).strftime('%d %H:%M'),b) for a,b in p[k]['pnlHistory']])
# MFE stats
sc=[t for t in T if t['bot']=='scalper']
print('MFE>=1R',[(t['coin'],round(t['mfe'],2),round(t['net'],2)) for t in sc if t['mfe']>=1])
print('MFE>=0.5R & net<0',[(t['coin'],round(t['mfe'],2),round(t['net'],2)) for t in T if t['mfe']>=0.5 and t['net']<0])
print('stop losses R',[round(t['R'],2) for t in sc if t['exit_reason']=='SL'])
print('fees/|gross| scalper',sum(t['fees'] for t in sc),sum(t['gross'] for t in sc), 'avg notional',sum(t['notional'] for t in sc)/len(sc))
