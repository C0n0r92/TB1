exec(open('exps2.py').read().split("for e in")[0])
def ms(t):
    same=sum(1 for u in T if u is not t and u['bot']==t['bot'] and u['side']==t['side'] and u['t_open']<t['t_open']<u['t_close'])
    return 0.5 if same>=2 else 1.0
for nm,f in [('BE.75',lambda t:run(t,be=0.75)),('BE.75+per-bot shrink',lambda t:run(t,be=0.75,size=ms(t))),('BE.75+fractal',lambda t:run(t,be=0.75,struct=True)),('BE.75+fractal+shrink',lambda t:run(t,be=0.75,struct=True,size=ms(t))),('BE.75+mid-limit fb+shrink',lambda t:run(t,be=0.75,entry='mid',fb=True,size=ms(t))),('BE.75+mid-limit fb',lambda t:run(t,be=0.75,entry='mid',fb=True))]:
    show(nm,[f(t) for t in T])
