import json,time,sys
from concurrent.futures import ThreadPoolExecutor
from pub import rpc
L=json.load(open('data/shortlist_known.json'))[:int(sys.argv[1])]
NOW=time.time(); out={}
try: out=json.load(open('data/screen_known.json'))
except: pass
def f(w):
    if w in out: return
    r=rpc("getSignaturesForAddress",[w,{"limit":1000}])
    if r is None: return
    ts=[x['blockTime'] for x in r if x.get('blockTime')]
    oldest=min(ts) if ts else NOW
    span_d=(NOW-oldest)/86400
    n30=sum(1 for t in ts if t>=NOW-30*86400); err=sum(1 for x in r if x.get('err'))
    out[w]={'n':len(r),'span_d':round(span_d,2),'n30':n30,'err':err,'est30':round(len(r)/max(span_d,0.01)*30) if len(r)==1000 else n30}
import threading
def saver():
    while True:
        time.sleep(20); json.dump(dict(out),open("data/screen_known.json","w"))
threading.Thread(target=saver,daemon=True).start()
with ThreadPoolExecutor(3) as ex: list(ex.map(f,L))
json.dump(out,open('data/screen_known.json','w'))
print(len(out))
