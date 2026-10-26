import json, time
from hyperliquid.info import Info
from hyperliquid.utils import constants
I=Info(constants.MAINNET_API_URL, skip_ws=True)
S=[t for t in json.load(open("trips2.json")) if t['bot']=='scalper']
def cand(coin,a,b):
    for k in range(4):
        try: return I.candles_snapshot(coin,"1m",a,b)
        except Exception as x: time.sleep(3*(k+1))
    return []
out=[]
now=int(time.time()*1000)
for t in S:
    r=t.get('rec') or {}; stop=r.get('stop'); tp=r.get('tp1')
    if not stop or not tp: continue
    sh=t['side']=='short'; e=t['entry']; d=abs(e-stop)
    end=min(t['t_open']+6*3600000, now)
    C=cand(t['coin'],t['t_open'],end); time.sleep(1.1)
    held=[c for c in C if c['t']<=t['t_close']]; after=[c for c in C if c['t']>t['t_close']]
    fav=lambda c:(e-float(c['l'])) if sh else (float(c['h'])-e)
    mfe=max([fav(c) for c in held] or [0])/d
    # first event after close: tp1 or original stop
    post=None
    for c in after:
        hit_tp = float(c['l'])<=tp if sh else float(c['h'])>=tp
        hit_sl = float(c['h'])>=stop if sh else float(c['l'])<=stop
        if hit_tp and hit_sl: post='both-same-min'; break
        if hit_tp: post='TP1'; break
        if hit_sl: post='orig-stop'; break
    tpR=abs(tp-e)/d
    out.append(dict(coin=t['coin'],open=t['t_open'],x=t['xtype'],net=t['net'],R=t['R'],risk=t['risk'],mfeR=round(mfe,2),tpR=round(tpR,2),post=post,ver=t['ver']))
    print(out[-1],flush=True)
json.dump(out,open("mfe.json","w"))
