import pickle,itertools,json
T=pickle.load(open('T.pkl','rb'))
TK,MK=0.00045,0.00015
# per-trade stop slippage: use observed avg
SLIP=0.0004
def fractal_stop(t):
    b=t['m15'];E=t['entry'];s=t['sgn']
    for i in range(len(b)-3,1,-1):
        if s>0:
            if all(b[i]['l']<b[j]['l'] for j in (i-2,i-1,i+1,i+2)) and b[i]['l']<E: px=b[i]['l']*(1-0.001);break
        else:
            if all(b[i]['h']>b[j]['h'] for j in (i-2,i-1,i+1,i+2)) and b[i]['h']>E: px=b[i]['h']*(1+0.001);break
    else: px=None
    d=abs(E-px) if px else 0
    return max(d,0.008*E)
def run(t,entry='mkt',be=None,tp1r=None,trail=None,size=1.0,struct=False,fb=False):
    scal=t['bot']=='scalper';s=t['sgn'];risk=t['risk']
    E0=t['entry'];t0=t['t_open'];feeE=TK
    if entry!='mkt':
        tr=t['trig'];bar=900e3 if scal else 3600e3
        C=tr['c']; X={'q':0.25*t['atr'],'h':0.5*t['atr'],'mid':abs(C-(tr['h']+tr['l'])/2)}[entry]
        L=C-s*X
        end=tr['t']+2*bar
        f=[b for b in t['m1'] if b['t']>=t0-60e3 and b['t']<end and ((b['l']<L) if s>0 else (b['h']>L))]
        # also: if limit is better than actual market entry price it must trade through; if worse (L beyond E0 in our favour?) cap
        if s*(L-E0)>0: L=E0  # never worse than what we actually got
        if not f:
            if not fb: return None
            lastb=[b for b in t['m1'] if b['t']<end][-1]; E=lastb['c'];t0=lastb['t'];feeE=TK
            if t0>=t['force_t']-60e3: return None
        else: E=L;t0=f[0]['t'];feeE=MK
    else: E=E0
    dist=fractal_stop(t) if (struct and scal) else t['dist0']
    sz=risk/dist*size
    stop=E-s*dist
    base_tp_r=(t['tp1_R'] or 1.5) if scal else 6.0
    tpr=tp1r if tp1r else base_tp_r
    tp1=E+s*tpr*dist; frac=0.5 if (scal or tp1r) else 1.0
    if not scal and not tp1r: frac=1.0
    trail_k = trail if trail is not None else (1.0 if scal else None)
    a15=t['atr'] if scal else None
    rem=sz;pnl=-E*sz*feeE;best=E;done=False;exitr='end'
    bars=[b for b in t['m1'] if b['t']>=t0+60e3-(t0%60e3) and b['t']<t['force_t']]
    for b in bars:
        hi,lo=b['h'],b['l']
        adv=lo if s>0 else hi; fav=hi if s>0 else lo
        if s*(adv-stop)<=0:
            px=stop*(1-s*SLIP); pnl+=s*(px-E)*rem-px*rem*TK; rem=0; exitr='stop' if not done else 'trail/BE'; break
        if not done and s*(fav-tp1*(1+s*0.0005))>0:
            q=rem*frac if frac<1 else rem; pnl+=s*(tp1-E)*q-tp1*q*TK; rem-=q; done=True
            if rem<=1e-12: exitr='TP';break
            stop=E*(1+s*0.001) if s*(E*(1+s*0.001)-stop)>0 else stop
        best=max(best,fav) if s>0 else min(best,fav)
        if be and s*(best-E)>=be*dist:
            bp=E*(1+s*0.001)
            if s*(bp-stop)>0: stop=bp
        if done and trail_k:
            k=trail_k*(a15 if scal else dist)
            tp_=best-s*k
            if s*(tp_-stop)>0: stop=tp_
    if rem>0:
        px=t['force_px'] if t['force_px'] else bars[-1]['c']
        pnl+=s*(px-E)*rem-px*rem*TK
    return pnl
def total(f):
    res=[f(t) for t in T]
    fil=[r for r in res if r is not None]
    return len(fil),sum(r>0.005 for r in fil),sum(fil),res
act=sum(t['net'] for t in T);aw=sum(t['net']>0 for t in T)
print(f"ACTUAL n25 w{aw} net{act:+.2f}")
n,w,p,_=total(lambda t:run(t));print(f"SIM BASELINE n{n} w{w} net{p:+.2f}")
for t,r in zip(T,_): 
    if abs(r-t['net'])>0.15: print('  mismatch',t['coin'],t['side'],round(t['net'],3),round(r,3))
pickle.dump(T,open('T.pkl','wb'))
