import json,sys,time
from concurrent.futures import ThreadPoolExecutor
import fetchw
d=json.load(open('data/screen.json'))
L=json.load(open('data/free_list.json'))
pass
def f(w):
    t=time.time()
    try: o=fetchw.get(w); print(w,o.get('too_many'),o.get('n_sigs'),o.get('missing'),round(time.time()-t),flush=True)
    except Exception as e: print(w,'ERR',e,flush=True)
with ThreadPoolExecutor(1) as ex: list(ex.map(f,L))
