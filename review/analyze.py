import json,datetime as dt,time,collections
from hyperliquid.info import Info
from hyperliquid.utils import constants
info=Info(constants.MAINNET_API_URL,skip_ws=True)
T=json.load(open('trips.json'))
iso=lambda s:dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000
S=[json.loads(l) for l in open('/workspace/hlscalp/trades.jsonl')]
P=[json.loads(l) for l in open('/workspace/perpbot/fills.jsonl')]
plog=open('/workspace/perpbot/bot.log').read().splitlines()
slog=open('/workspace/hlscalp/bot.log').read().splitlines()
def ver(ms):
    h=dt.datetime.utcfromtimestamp(ms/1000).strftime('%H:%M')
    for cut,v in [('11:52','S1 5-strat vote'),('12:16','S2 +exhaustion rules 4/5'),('19:46','S3 trigger+confirmers'),('20:11','S4 S3 minus PULLBACK'),('99:99','S5 Hull 1h')]:
        if h<cut: return v
out=[]
for t in T:
    scal=any(str(c).startswith('0x5ca1') for c in t['open_cloids'])
    t['bot']='scalper' if scal else 'perp'
    t['net']=t['gross']-t['fees']+t['fund']
    if scal:
        recs=[r for r in S if r['coin']==t['coin'] and r['event'] in('open','adopted') and abs(iso(r.get('opened',r['ts']))-t['t_open'])<15*60e3]
        r=recs[0] if recs else {}
        if not r:
            u=[x for x in S if x['coin']==t['coin'] and x.get('untracked') and abs(iso(x['opened'])-t['t_open'])<15*60e3]
            if u: r=dict(u[0]); r['risk_usd']=round(abs(r['pnl_usd']/r['R']),3); r['stop']=r['last_stop']; r['event']='untracked'
        cl=[x for x in S if x['coin']==t['coin'] and x['event']=='closed' and 0<=iso(x['ts'])-t['t_close']<10*60e3]
        rs=[x for x in S if x['coin']==t['coin'] and x['event']=='resized_record']
        t['rec_pnl']=cl[0]['pnl_usd'] if cl else None
        t['risk']=rs[0]['risk_usd'] if (rs and t['coin']=='BNB') else r.get('risk_usd')
        t['strat']=r.get('primary','?'); t['strats']=r.get('strategies'); t['rm']=r.get('risk_mult'); t['tr1']=r.get('trend1h')
        t['stop0']=r.get('stop'); t['tp1']=r.get('tp1'); t['lev']=r.get('lev'); t['notional']=r.get('notional') or t['entry']*t['sz']
        t['tracked']=bool(r) and r['event']=='open'
        t['ver']=ver(t['t_open'])
        tags=[str(c)[6:8] if c else 'ext' for c,_,_,_ in t['close_cloids']]
        reason=[]
        for c,sz,px,when in t['close_cloids']:
            k=str(c)[6:8] if c else None
            reason.append({'51':'SL','7a':'TP1','c1':'close','e0':'?'}.get(k,'manual/ext'))
        rs_=[]; [rs_.append(x) for x in reason if x not in rs_]
        if 'close' in rs_:
            co=[x for x in S if x['coin']==t['coin'] and x['event']=='close_order' and abs(iso(x['ts'])-t['t_close'])<120e3]
            reasn=co[0]['reason'] if co else None
            if not reasn:
                ll=[l for l in slog if f"CLOSE {t['coin']} (" in l and dt.datetime.utcfromtimestamp(t['t_close']/1000).strftime('%H:%M') [:4] in l]
                reasn=ll[0].split('(')[1].split(')')[0] if ll else 'close'
            rs_=[reasn if x=='close' else x for x in rs_]
        if 'SL' in rs_ and 'TP1' in rs_: rs_=['TP1','then stop(BE/trail)']
        t['exit_reason']='+'.join(rs_)
    else:
        e=[x for x in P if x.get('event')=='entry' and x['coin']==t['coin']][0]
        t['risk']=e['risk_usd'];t['strat']='+'.join(e['strategies_behind']);t['stop0']=e['stop'];t['tp1']=e.get('tp');t['ver']='perp v(24 Oct 20:41 join pass, 2% risk)'
        t['entry_type']=e.get('entry_type');t['notional']=t['entry']*t['sz']
        ll=[l for l in plog if f"CLOSED {t['coin']} " in l and l.startswith('2026-10-25')]
        t['exit_reason']=ll[0].split('reason ')[1].split(' ')[0] if ll else '?'
        t['rec_pnl']=float(ll[0].split('pnl $')[1].split(' ')[0]) if ll else None
        t['tracked']=True
    t['R']=t['net']/t['risk'] if t['risk'] else None
    # MFE/MAE from 1m candles
    a=t['t_open']-60e3;b=t['t_close']+60e3
    cs=info.candles_snapshot(t['coin'],'1m',int(a),int(b))
    cs=[c for c in cs if c['t']+60e3>t['t_open'] and c['t']<=t['t_close']]
    hi=max(float(c['h']) for c in cs);lo=min(float(c['l']) for c in cs)
    sgn=1 if t['side']=='long' else -1
    fav=(hi-t['entry']) if sgn>0 else (t['entry']-lo); adv=(t['entry']-lo) if sgn>0 else (hi-t['entry'])
    t['mfe']=fav*t['sz']/t['risk'] if t['risk'] else None; t['mae']=-adv*t['sz']/t['risk'] if t['risk'] else None
    t['mfe_pct']=fav/t['entry']*100; t['mae_pct']=-adv/t['entry']*100
    t['stop_pct']=abs(t['entry']-t['stop0'])/t['entry']*100 if t['stop0'] else None
    t['tp1_R']=abs(t['tp1']-t['entry'])*t['sz']/t['risk'] if (t.get('tp1') and t['risk']) else None
    # pre-entry move: 1h before entry, in trade direction, in %
    pc=info.candles_snapshot(t['coin'],'15m',int(t['t_open']-4*3600e3),int(t['t_open']))
    if len(pc)>=5:
        p0=float(pc[-5]['o']);t['pre1h_pct']=sgn*(t['entry']-p0)/p0*100
        p4=float(pc[0]['o']);t['pre4h_pct']=sgn*(t['entry']-p4)/p4*100
    t['hold_h']=(t['t_close']-t['t_open'])/3600e3
    t['sec_after_bar']=(t['t_open']/1000)%900 if scal else (t['t_open']/1000)%3600
    out.append(t);time.sleep(0.15)
json.dump(out,open('trips_full.json','w'),default=str)
for t in out:
    print(t['bot'][:5],t['coin'],t['side'],t['strat'],t['exit_reason'],round(t['net'],3),t['rec_pnl'],round(t['R'],2),round(t['mfe'],2),round(t['mae'],2),t.get('tp1_R') and round(t['tp1_R'],2),round(t['stop_pct'] or 0,2),round(t.get('pre1h_pct',0),2),t['tracked'],int(t['sec_after_bar']))
