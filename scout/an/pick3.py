import json,os,glob
d=json.load(open('an/sig3.json')); done={os.path.basename(f)[:-5] for f in glob.glob('an/wg/*.json')}
q=set(open('an/q3.txt').read().split()) if os.path.exists('an/q3.txt') else set()
r=[(k,v) for k,v in d.items() if v['day_share'] and v['day_share']>=0.55 and 0.2<=v['per_h']<=6 and v['span_h']>=72 and v['n2h']>=2 and v['err']<300 and k not in done and k not in q]
r.sort(key=lambda kv:(-kv[1]['day_share']))
for k,v in r: print(k,v)
