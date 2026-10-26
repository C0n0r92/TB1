import json,collections,datetime as dt
D=json.load(open('hl.json'))
def ts(ms): return dt.datetime.utcfromtimestamp(ms/1000).strftime('%m-%d %H:%M:%S')
F=[f for f in D['fills'] if not f['coin'].startswith('@') and '/' not in f['coin']]
F.sort(key=lambda f:(f['time'],f['tid']))
pos=collections.defaultdict(float);cur={};trips=[]
for f in F:
    c=f['coin'];sz=float(f['sz'])*(1 if f['side']=='B' else -1)
    if c not in cur: cur[c]={'coin':c,'fills':[]}
    cur[c]['fills'].append(f);pos[c]+=sz
    if abs(pos[c])<1e-9:
        trips.append(cur.pop(c));pos[c]=0
open_=[(c,pos[c]) for c in cur]
print('open',open_)
for t in trips:
    fs=t['fills'];op=[f for f in fs if f['dir'].startswith('Open')];cl=[f for f in fs if f['dir'].startswith('Close')]
    t['side']='long' if 'Long' in op[0]['dir'] else 'short'
    q=lambda L:sum(float(f['sz'])*float(f['px']) for f in L)/sum(float(f['sz']) for f in L)
    t['entry']=q(op);t['exit']=q(cl);t['sz']=sum(float(f['sz']) for f in op)
    t['t_open']=op[0]['time'];t['t_close']=cl[-1]['time']
    t['gross']=sum(float(f['closedPnl']) for f in fs);t['fees']=sum(float(f['fee']) for f in fs)
    t['fund']=sum(float(x['delta']['usdc']) for x in D['funding'] if x['delta']['coin']==t['coin'] and t['t_open']<=x['time']<=t['t_close']+1000)
    t['open_cloids']=[f.get('cloid') for f in op];t['close_cloids']=[(f.get('cloid'),f['sz'],f['px'],ts(f['time'])) for f in cl]
    t['crossed']=[f['crossed'] for f in fs]
    print(f"{t['coin']:6}{t['side']:6}{ts(t['t_open'])} -> {ts(t['t_close'])} {t['entry']:.6g}->{t['exit']:.6g} g{t['gross']:+.3f} fee{t['fees']:.3f} fu{t['fund']:+.3f} oc{set(str(x)[:6] for x in t['open_cloids'])} cc{[(str(a)[:6],b) for a,b,c,d in t['close_cloids']]}")
json.dump(trips,open('trips.json','w'))
