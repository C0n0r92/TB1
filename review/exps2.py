exec(open('sim.py').read().split("act=sum")[0])
B=[run(t) for t in T];bn=sum(B)
def show(name,res):
    fil=[r for r in res if r is not None];print(f"{name:45} n{len(fil)} w{sum(r>0.005 for r in fil)} net{sum(fil):+.2f} vs base {sum(fil)-bn:+.2f}")
for e in ('q','h','mid'):
    res=[run(t,entry=e) for t in T]
    print(e,'filled-only effect',round(sum(r-b for r,b in zip(res,B) if r is not None),2),' skipped-trades effect',round(-sum(b for r,b in zip(res,B) if r is None),2))
    show(f'limit {e} + market fallback at bar end',[run(t,entry=e,fb=True) for t in T])
for bot in ('scalper','perp'):
    idx=[i for i,t in enumerate(T) if t['bot']==bot]
    for nm,kw in [('BE0.75',dict(be=0.75)),('BE+TP1@1R',dict(be=0.75,tp1r=1.0))]:
        print(bot,nm,round(sum(run(T[i],**kw)-B[i] for i in idx),2),'base',round(sum(B[i] for i in idx),2))
def ms(t):
    same=sum(1 for u in T if u is not t and u['bot']==t['bot'] and u['side']==t['side'] and u['t_open']<t['t_open']<u['t_close'])
    return 0.5 if same>=2 else 1.0
r=[run(t,size=ms(t)) for t in T];show('3rd+ same-dir 50% (per bot)',r);print('  shrunk',sum(ms(t)<1 for t in T))
for nm,kw in [('PACKAGE A: mkt+BE.75+TP1@1R+fractal stop',dict(be=0.75,tp1r=1.0,struct=True)),('PACKAGE A + per-bot 3rd+ 50%',None),('PACKAGE B: A + mid-limit w/ mkt fallback',dict(entry='mid',fb=True,be=0.75,tp1r=1.0,struct=True))]:
    if kw is None: res=[run(t,be=0.75,tp1r=1.0,struct=True,size=ms(t)) for t in T]
    else: res=[run(t,**kw) for t in T]
    show(nm,res)
    if 'B' in nm: show('PACKAGE B + per-bot 3rd+ 50%',[run(t,entry='mid',fb=True,be=0.75,tp1r=1.0,struct=True,size=ms(t)) for t in T])
# robustness: BE trigger sweep within package A
for be in (0.5,0.75,1.0):
    show(f'  A with BE@{be}',[run(t,be=be,tp1r=1.0,struct=True) for t in T])
