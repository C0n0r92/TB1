import json,time,math,itertools,datetime as dt,pickle,os
from hyperliquid.info import Info
from hyperliquid.utils import constants
info=Info(constants.MAINNET_API_URL,skip_ws=True)
T=json.load(open('trips_full.json'))
END=1792959758000  # 20:22:38 manual close-all
TK,MK,SLIP=0.00045,0.00015,0.0004
cache='cndl.pkl'
C=pickle.load(open(cache,'rb')) if os.path.exists(cache) else {}
def cs(coin,iv,a,b):
    k=(coin,iv,int(a),int(b))
    if k not in C:
        for i in range(8):
            try: r=info.candles_snapshot(coin,iv,int(a),int(b));break
            except Exception as e: time.sleep(5*(i+1))
        C[k]=[{'t':x['t'],'o':float(x['o']),'h':float(x['h']),'l':float(x['l']),'c':float(x['c'])} for x in r];time.sleep(1.0)
        pickle.dump(C,open(cache,'wb'))
    return C[k]
def atr(b,n=14):
    tr=[max(b[i]['h']-b[i]['l'],abs(b[i]['h']-b[i-1]['c']),abs(b[i]['l']-b[i-1]['c'])) for i in range(1,len(b))]
    return sum(tr[-n:])/n
def wma(x,n):
    w=list(range(1,n+1));return sum(a*b for a,b in zip(x[-n:],w))/sum(w)
def hull_slope(closes,n=21):
    def h(xs): 
        m=int(math.sqrt(n)); ser=[2*wma(xs[:i],n//2)-wma(xs[:i],n) for i in range(len(xs)-m+1,len(xs)+1)]; return wma(ser,m)
    return 1 if h(closes)>h(closes[:-1]) else -1
btc1h=cs('BTC','1h',1792800000000,END)
for t in T:
    scal=t['bot']=='scalper'; bar=900e3 if scal else 3600e3
    t['sgn']=1 if t['side']=='long' else -1
    t['dist0']=abs(t['entry']-t['stop0']); 
    # forced exit
    discretionary=t['exit_reason'] not in('SL','stop') and 'TP1' not in t['exit_reason']
    t['force_t']=t['t_close'] if discretionary else (min(t['t_open']+6*3600e3,END) if scal else END)
    t['force_px']=t['exit'] if discretionary else None
    t['m1']=cs(t['coin'],'1m',t['t_open']-60e3,t['force_t']+60e3)
    iv='15m' if scal else '1h'
    hb=cs(t['coin'],iv,t['t_open']-80*bar,t['t_open'])
    hb=[b for b in hb if b['t']+bar<=t['t_open']]  # closed bars
    t['trig']=hb[-1]; t['atr']=atr(hb); t['hb']=hb
    t['m15']=cs(t['coin'],'15m',t['t_open']-60*900e3,t['t_open'])
    t['m15']=[b for b in t['m15'] if b['t']+900e3<=t['t_open']]
    bb=[b['c'] for b in btc1h if b['t']+3600e3<=t['t_open']]
    t['btc_hull']=hull_slope(bb)
pickle.dump(C,open(cache,'wb'))
pickle.dump(T,open('T.pkl','wb'))
print('ok',len(T))
