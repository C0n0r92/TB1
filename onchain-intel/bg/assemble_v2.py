import json,os,glob,time
B='/workspace/onchain-intel/bg/'
names={'5YRgrP3mjGzrzirYYN5HAQH19cTYREYwGxW6XRJQUzij':('slingoor','slingoorio','kolscan daily'),'dmuXAmcXJcdNuK264vsJQNBpVBPAx4JLujBzBMahJ6C':('dmuXAm',None,'active'),
'AHXvezMkJhyrXodVeTtbq53p6AZ8PPsCarF8RDy5KeeT':('AHXvez',None,'active'),'GM8C8B5Ybx5eUthFDAQhQnW4A4R3jEgnhwS81goQ1h7d':('GM8C8B',None,'active')}
k=json.load(open(B+'kolscan_daily_1005.json'))['board']
for a in k:
    if a['timeframe']==1 and a['wallet'] not in names: names[a['wallet']]=(a['name'],(a['twitter'] or '').replace('https://x.com/','') or None,f"kolscan daily (+{round(a['profit'])} SOL, {a['wins']}W/{a['losses']}L; self-reported X, unverified)")
for w in ['kEFiAX3jo5NmemysQov342TZ9mGh6yp92GDRjhA8XDf']: names[w]=(w[:6],None,'GT runner-pool repeat buyer (4 runners)')
res={}
for f in glob.glob(B+'an/*.v2.json'):
    if os.path.getmtime(f)<time.time()-3600: continue
    o=json.load(open(f)); w=o['wallet']; n=names.get(w,(w[:6],None,'?'))
    o2={k:v for k,v in o.items() if k!='copies'}; o2.update(name=n[0],x=n[1],route=n[2]); res[w]=o2
fl=[l.split() for l in open('/workspace/onchain-intel/data/fetchlayer_calls.log') if int(l.split()[0])>=1792922280]
from collections import Counter
calls=Counter((x[1],x[3]) for x in fl)
out=dict(generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'),job='Scout data+scoring upgrade (user via Zero 09:57Z), single ~30-min pass',
 sources=json.load(open(B+'sources_v2.json')),fetch_calls_this_job={f"{a} {b}":c for (a,b),c in calls.items()},helius_credits_used=0,
 scorer='scorer_v2.py (see docstring)',results=res,
 passes=sorted([v for v in res.values() if v.get('pass_')],key=lambda v:-v['score']),
 discovery=dict(gt_runner_hits=json.load(open(B+'disc_v2.json'))['hits'][:40],funders=json.load(open(B+'funders_v2.json'))))
json.dump(out,open('/workspace/onchain-intel/bg_search_v2_2026-10-25.json.tmp','w'),indent=1); os.replace('/workspace/onchain-intel/bg_search_v2_2026-10-25.json.tmp','/workspace/onchain-intel/bg_search_v2_2026-10-25.json')
for v in sorted(res.values(),key=lambda v:-(v.get('score') or -999)): print(v['name'],v.get('score'),v.get('median_pct'),v.get('copies_scored'),v.get('fails'))
