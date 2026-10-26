exec(open('sim.py').read().split("act=sum")[0])
import statistics as st
act=sum(t['net'] for t in T);aw=sum(t['net']>0 for t in T)
B=[run(t) for t in T];bn=sum(B);bw=sum(r>0.005 for r in B)
def line(name,res):
    fil=[r for r in res if r is not None]
    print(f"{name:42} n{len(fil):2} w{sum(r>0.005 for r in fil):2} net{sum(fil):+7.2f}  vs sim-base {sum(fil)-bn:+6.2f}")
print(f"actual n25 w{aw} net{act:+.2f}; sim-base n25 w{bw} net{bn:+.2f}")
print("== 1 limit entry")
for e in ('q','h','mid'):
    res=[run(t,entry=e) for t in T]; line('limit '+e,res)
    imp=[];impR=[];fl=[0,0];tot=[0,0]
    for t,r,b in zip(T,res,B):
        win=t['net']>0;tot[win]+=1
        if r is None: continue
        fl[win]+=1
        tr=t['trig'];C=tr['c'];X={'q':0.25*t['atr'],'h':0.5*t['atr'],'mid':abs(C-(tr['h']+tr['l'])/2)}[e]
        L=C-t['sgn']*X
        if t['sgn']*(L-t['entry'])>0: L=t['entry']
        imp.append(t['sgn']*(t['entry']-L)/t['entry']*100); impR.append(t['sgn']*(t['entry']-L)/t['dist0'])
    fees=sum((TK-MK)*t['entry']*t['sz'] for t,r in zip(T,res) if r is not None)
    print(f"   fills {len(imp)}/25, losers filled {fl[0]}/{tot[0]}, winners filled {fl[1]}/{tot[1]}, avg improvement {st.mean(imp):.3f}% = {st.mean(impR):.2f}R, entry fee saving ${fees:.2f}")
    print('   unfilled:',[ (t['coin'],t['side'],round(t['net'],2)) for t,r in zip(T,res) if r is None])
print("== 2 profit mgmt")
for name,kw in [('BE@0.75R',dict(be=0.75)),('TP1@1R 50%',dict(tp1r=1.0)),('trail 0.5ATR after TP1',dict(trail=0.5)),('BE+TP1@1R',dict(be=0.75,tp1r=1.0)),('TP1@1R+trail0.5',dict(tp1r=1.0,trail=0.5)),('BE+TP1@1R+trail0.5',dict(be=0.75,tp1r=1.0,trail=0.5)),('BE@0.5R',dict(be=0.5)),('BE@1R',dict(be=1.0))]:
    line(name,[run(t,**kw) for t in T])
print("== 3 shrink")
def mults(t):
    same=sum(1 for u in T if u is not t and u['side']==t['side'] and u['t_open']<t['t_open']<u['t_close'])
    m1=0.5 if same>=2 else 1.0
    m2=0.5 if t['btc_hull']!=t['sgn'] else 1.0
    return m1,m2,same
for name,f in [('3rd+ same-dir 50%',lambda t:mults(t)[0]),('vs BTC Hull 50%',lambda t:mults(t)[1]),('both (stack, min .25)',lambda t:mults(t)[0]*mults(t)[1]),('both (max cut 50%)',lambda t:min(mults(t)[0],mults(t)[1]))]:
    res=[run(t,size=f(t)) for t in T];line(name,res)
    print('    actual-P&L scaled:', round(sum(t['net']*f(t) for t in T),2),' shrunk trades:',sum(f(t)<1 for t in T))
print('   detail',[(t['coin'],t['side'][0],mults(t)[2],t['btc_hull']) for t in T])
print("== 4 struct stops (scalper)")
res=[run(t,struct=True) for t in T];line('fractal stop',res)
sc=[(t,b,r) for t,b,r in zip(T,B,res) if t['bot']=='scalper']
surv=[(t['coin'],round(b,2),round(r,2),round(fractal_stop(t)/t['entry']*100,2),round(t['dist0']/t['entry']*100,2)) for t,b,r in sc if t['exit_reason']=='SL']
print('   SL trades (coin, base, struct, new stop%, old stop%):',surv)
print('   survived (no longer lose >=0.9R):',sum(1 for t,b,r in sc if t['exit_reason']=='SL' and r>-0.9*t['risk']))
print("== 5 grid")
rows=[]
import itertools
for e,mg,sz,stc in itertools.product(['mkt','q','h','mid'],[{},dict(be=0.75),dict(tp1r=1.0),dict(be=0.75,tp1r=1.0),dict(be=0.75,tp1r=1.0,trail=0.5),dict(tp1r=1.0,trail=0.5)],['1','min'],[False,True]):
    res=[run(t,entry=e,struct=stc,size=(1 if sz=='1' else min(mults(t)[:2])),**mg) for t in T]
    fil=[r for r in res if r is not None]
    rows.append((sum(fil),len(fil),sum(r>0.005 for r in fil),e,mg,sz,stc))
rows.sort(key=lambda x:-x[0])
for r in rows[:12]: print('  ',f"{r[0]:+.2f} n{r[1]} w{r[2]}",r[3:])
print('  market-entry best:',[f"{r[0]:+.2f} n{r[1]} w{r[2]} {r[3:]}" for r in rows if r[3]=='mkt'][:4])
print("== wake delay (scalper)")
d=[];c=[];cR=[];cd=[]
for t in T:
    if t['bot']!='scalper':continue
    bc=t['trig']['t']+900e3; dl=(t['t_open']-bc)/1000; C=t['trig']['c']
    d.append(dl); c.append(t['sgn']*(t['entry']-C)/C*100); cR.append(t['sgn']*(t['entry']-C)/t['dist0']); cd.append(t['sgn']*(t['entry']-C)*t['sz'])
print(f"  delay s: mean {st.mean(d):.0f} median {st.median(d):.0f} max {max(d):.0f}; >120s: {sum(x>120 for x in d)}; cost vs bar close: mean {st.mean(c):+.3f}% = {st.mean(cR):+.2f}R, total ${sum(cd):+.2f}")
print('  ',[(t['coin'],int(x),round(y,3)) for t,x,y in zip([t for t in T if t['bot']=='scalper'],d,c)])
