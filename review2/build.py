import json, collections, datetime as dt, calendar
D=json.load(open("hl.json"))
def ms(s): return calendar.timegm(time_.strptime(s[:19],"%Y-%m-%dT%H:%M:%S"))*1000
import time as time_
def ts(m): return dt.datetime.utcfromtimestamp(m/1000).strftime('%m-%d %H:%M')
F=[f for f in D['fills'] if not f['coin'].startswith('@')]; F.sort(key=lambda f:(f['time'],f['tid']))
pos=collections.defaultdict(float); cur={}; trips=[]
for f in F:
    c=f['coin']; sz=float(f['sz'])*(1 if f['side']=='B' else -1)
    cur.setdefault(c,{'coin':c,'fills':[]})['fills'].append(f); pos[c]+=sz
    if abs(pos[c])<1e-9: trips.append(cur.pop(c)); pos[c]=0
print("still open:",[(c,pos[c]) for c in cur])
fund=D['funding']
for t in trips:
    fs=t['fills']; op=[f for f in fs if f['dir'].startswith('Open')]; cl=[f for f in fs if f['dir'].startswith('Close')]
    q=lambda L:sum(float(f['sz'])*float(f['px']) for f in L)/sum(float(f['sz']) for f in L)
    t.update(side='long' if 'Long' in op[0]['dir'] else 'short', entry=q(op), exit=q(cl), sz=sum(float(f['sz']) for f in op),
             t_open=op[0]['time'], t_close=cl[-1]['time'], gross=sum(float(f['closedPnl']) for f in fs), fees=sum(float(f['fee']) for f in fs))
    t['fund']=sum(float(x['delta']['usdc']) for x in fund if x['delta']['coin']==t['coin'] and t['t_open']<=x['time']<=t['t_close']+1000)
    t['net']=t['gross']-t['fees']+t['fund']
    oc=[str(f.get('cloid') or '') for f in op]; t['bot']='scalper' if any(c.startswith('0x5ca1') for c in oc) else 'perp'
    t['open_tags']=sorted(set(c[6:8] if c.startswith('0x5ca1') else 'none' for c in oc))
    t['close_tags']=[(str(f.get('cloid') or '')[6:8] if str(f.get('cloid') or '').startswith('0x5ca1') else 'none', float(f['sz']), float(f['px']), f['time'], float(f['closedPnl']), f['oid']) for f in cl]
    t['open_fills']=[(float(f['sz']),float(f['px']),f['time'],f['crossed']) for f in op]
    del t['fills']
# --- scalper records
TR=[json.loads(l) for l in open("/workspace/hlscalp/trades.jsonl")]
for e in TR: e['_ms']=ms(e['ts'])
for t in [t for t in trips if t['bot']=='scalper']:
    cand=[e for e in TR if e['coin']==t['coin'] and e['event'] in('open','adopted') and abs(e['_ms']-t['t_open'])<20*60000]
    o=min(cand,key=lambda e:abs(e['_ms']-t['t_open'])) if cand else None; t['rec']=o
    t['lp']=next((e for e in TR if e['coin']==t['coin'] and e['event']=='limit_placed' and 0<=t['t_open']-e['_ms']<20*60000),None)
    t['be']=any(e['coin']==t['coin'] and e['event']=='be_armed' and t['t_open']-1000<=e['_ms']<=t['t_close']+60000 for e in TR)
    t['tp1']=any(e['coin']==t['coin'] and e['event']=='tp1' and t['t_open']<=e['_ms']<=t['t_close']+60000 for e in TR)
    t['closeord']=[e['reason'] for e in TR if e['coin']==t['coin'] and e['event']=='close_order' and t['t_open']<=e['_ms']<=t['t_close']+60000]
    t['crec']=next((e for e in TR if e['coin']==t['coin'] and e['event']=='closed' and t['t_close']-5000<=e['_ms']<=t['t_close']+30*60000),None)
# --- perp records
P=[json.loads(l) for l in open("/workspace/perpbot/fills.jsonl")]
for t in [t for t in trips if t['bot']=='perp']:
    c=[e for e in P if e['event']=='trade_closed' and e['coin']==t['coin'] and abs(ms(e['ts'])-t['t_close'])<10*60000]
    t['prec']=c[0] if c else None
    en=[e for e in P if e['event']=='entry' and e['coin']==t['coin'] and abs(ms(e['ts'])-t['t_open'])<10*60000]; t['pent']=en[0] if en else None
json.dump(trips,open("trips.json","w"),default=str)
for t in trips: print(t['bot'][:5],t['coin'],t['side'],ts(t['t_open']),ts(t['t_close']),round(t['net'],3),t['open_tags'],[c[0] for c in t['close_tags']], 'REC' if t.get('rec') or t.get('prec') else 'norec')
