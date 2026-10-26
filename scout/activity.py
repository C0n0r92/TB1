"""30d activity from getSignaturesForAddress (mainnet-beta, free). Counts successful sigs as activity proxy."""
import json,sys,time,datetime
from zoneinfo import ZoneInfo
from pub import rpc
DUB=ZoneInfo('Europe/Dublin'); out=json.load(open('data/activity.json')) if __import__('os').path.exists('data/activity.json') else {}
cut=time.time()-30*86400
for w in sys.argv[1:]:
    ts=[];before=None;calls=0;trunc=False
    while True:
        p={'limit':1000}
        if before:p['before']=before
        r=rpc('getSignaturesForAddress',[w,p]); calls+=1
        if not r: break
        ts+=[x['blockTime'] for x in r if x.get('blockTime') and not x.get('err')]
        before=r[-1]['signature']
        if r[-1].get('blockTime',0)<cut or len(r)<1000: break
        if calls>=60: trunc=True;break
    ts=[t for t in ts if t>=cut]
    span=(time.time()-min(ts))/3600 if ts else 0
    hours=set(t//3600 for t in ts)
    # night hours Dublin 21-08 in the covered span
    nh=0;nh_act=0;h=int((time.time()-span*3600)//3600)+1
    while h<int(time.time()//3600):
        hr=datetime.datetime.fromtimestamp(h*3600,DUB).hour
        if hr>=21 or hr<8:
            nh+=1; nh_act+= h in hours
        h+=1
    nights=max(span/24,1e-9)
    out[w]={'sigs_30d':len(ts),'span_h':round(span,1),'truncated':trunc,'sigs_per_h':round(len(ts)/max(span,1),2),
        'night_sigs_per_night':round(sum(1 for t in ts if (lambda hr: hr>=21 or hr<8)(datetime.datetime.fromtimestamp(t,DUB).hour))/nights,1),
        'night_hours_active_share':round(nh_act/nh,3) if nh else None,'all_hours_active_share':round(len(hours)/max(span,1),3)}
    json.dump(out,open('data/activity.json','w'),indent=0); print(w,out[w],flush=True)
