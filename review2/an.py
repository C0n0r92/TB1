import json, collections, calendar, time
T=json.load(open("trips.json"))
def ms(s): return calendar.timegm(time.strptime(s,"%Y-%m-%d %H:%M"))*1000
V=[("pre-v3",0),("v3",ms("2026-10-25 12:16")),("exec3",ms("2026-10-25 20:54")),("3%risk",ms("2026-10-25 23:26"))]
def ver(m): return [n for n,b in V if m>=b][-1]
S=[t for t in T if t['bot']=='scalper']; Pp=[t for t in T if t['bot']=='perp']
for t in S:
    r=t.get('rec') or {}; lp=t.get('lp')
    t['ver']=ver(t['t_open']); t['risk']=r.get('risk_usd') or None
    t['R']=t['net']/t['risk'] if t['risk'] else None
    t['prim']=r.get('primary') or '?'; t['strats']=r.get('strategies') or []
    t['trig']=t['prim'] if t['prim'] not in('CORE',None) else '+'.join(t['strats']) or '?'
    t['nconf']=len(r['confirmers']) if r.get('confirmers') is not None else None
    tags=t['open_tags']
    if tags==['e1']:
        inst = lp and "'filled'" in lp['result'][:40]
        t['etype']='limit instant-fill (bug)' if inst else 'limit filled'
    elif 'e1' in tags: t['etype']='limit+market'
    else: t['etype']='market fallback' if lp else 'market (pre-exec3)'
    ct=[c[0] for c in t['close_tags']]
    if '7a' in ct: t['xtype']='TP1+trail'
    elif 'none' in ct: t['xtype']='manual close (you)'
    elif 'c1' in ct: t['xtype']='bot close: '+','.join(sorted(set(x.split(':')[0] for x in t['closeord']))) if t['closeord'] else 'bot close'
    elif t['be'] and t['R'] is not None and abs(t['R'])<0.3: t['xtype']='BE scratch'
    elif t['R'] is not None and t['R']<-0.5: t['xtype']='stop loss'
    else: t['xtype']='stop (other)'
    t['stack']=sum(1 for u in S if u is not t and u['side']==t['side'] and u['t_open']<t['t_open']<u['t_close'])
    t['hour']=time.gmtime(t['t_open']/1000).tm_hour
    if lp and t['etype'].startswith('limit instant'):
        st=lp['stop']; t['plan_stop_pct']=abs(lp['limit_px']-st)/lp['limit_px']*100; t['real_stop_pct']=abs(t['entry']-st)/t['entry']*100
def agg(L,key):
    g=collections.defaultdict(list)
    for t in L: g[key(t)].append(t)
    out=[]
    for k,v in sorted(g.items(),key=lambda kv:sum(t['net'] for t in kv[1])):
        rs=[t['R'] for t in v if t.get('R') is not None]
        out.append(f"  {str(k):34} n={len(v):2} W={sum(t['net']>0 for t in v):2} net=${sum(t['net'] for t in v):+7.2f} avgR={sum(rs)/len(rs) if rs else float('nan'):+.2f}")
    return "\n".join(out)
def summ(L,name):
    w=[t for t in L if t['net']>0]; l=[t for t in L if t['net']<=0]
    rw=[t['R'] for t in w if t.get('R') is not None]; rl=[t['R'] for t in l if t.get('R') is not None]
    print(f"{name}: n={len(L)} net=${sum(t['net'] for t in L):+.2f} gross=${sum(t['gross'] for t in L):+.2f} fees=${sum(t['fees'] for t in L):.2f} funding=${sum(t['fund'] for t in L):+.2f}  win%={len(w)/len(L)*100:.0f}  avgWin=${sum(t['net'] for t in w)/max(1,len(w)):.3f} avgLoss=${sum(t['net'] for t in l)/max(1,len(l)):.3f}  avgWinR={sum(rw)/max(1,len(rw)):+.2f} avgLossR={sum(rl)/max(1,len(rl)):+.2f} expR={(sum(rw)+sum(rl))/max(1,len(rw)+len(rl)):+.3f} exp$={sum(t['net'] for t in L)/len(L):+.3f}")
summ(S,"SCALPER"); summ(Pp,"PERP")
for t in Pp: print("  perp",t['coin'],t['side'],round(t['net'],3),(t.get('prec') or {}).get('exit_reason'),(t.get('prec') or {}).get('pnl_usd'))
for nm,k in [("version",lambda t:t['ver']),("trigger/primary",lambda t:t['trig']),("confirmers (v3+)",lambda t:t['nconf']),("side",lambda t:t['side']),
             ("coin",lambda t:t['coin']),("hour UTC",lambda t:t['hour']),("same-dir already open",lambda t:'0-1 (1st/2nd)' if t['stack']<2 else '2+ (3rd+)'),
             ("half-size flag",lambda t:(t.get('rec') or {}).get('samedir_mult')),("entry type",lambda t:t['etype']),("exit type",lambda t:t['xtype']),
             ("risk_mult",lambda t:(t.get('rec') or {}).get('risk_mult'))]:
    print(f"-- by {nm}"); print(agg(S,k))
print("-- version x side"); print(agg(S,lambda t:(t['ver'],t['side'])))
print("-- 3%risk era by exit"); print(agg([t for t in S if t['ver']=='3%risk'],lambda t:t['xtype']))
print("-- instant-fill limits:"); 
for t in S:
    if 'plan_stop_pct' in t: print(f"  {t['coin']} {t['side']} plan stop {t['plan_stop_pct']:.2f}% real {t['real_stop_pct']:.2f}% net {t['net']:+.3f} R {t['R']}")
print("-- detail");
for t in sorted(S,key=lambda t:t['t_open']): print(f"  {time.strftime('%d %H:%M',time.gmtime(t['t_open']/1000))} {t['ver']:6} {t['coin']:8} {t['side']:5} {t['trig']:22} c{t['nconf']} {t['etype'][:18]:18} {t['xtype'][:22]:22} stk{t['stack']} net{t['net']:+.3f} R{(t['R'] or 0):+.2f} risk{t['risk']} be{int(t['be'])}")
json.dump(S+Pp,open("trips2.json","w"),default=str)
