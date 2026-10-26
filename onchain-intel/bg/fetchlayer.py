"""Scout fetch layer (read-only, free-first). One module for Solana RPC + public HTTP APIs with per-source rate limits,
cooldown on 403/429/5xx, automatic fallback, and a call log. Helius is LAST resort and hard-capped by HELIUS_CAP (default 0).
Usage: from fetchlayer import rpc, get ; rpc('getTransaction',[sig,{...}]) ; get(url)
Log: /workspace/onchain-intel/data/fetchlayer_calls.log (ts source method status)."""
import json,time,os,threading,urllib.request,urllib.error
LOG='/workspace/onchain-intel/data/fetchlayer_calls.log'
HCF='/workspace/onchain-intel/bg/helius_used_fl.json'
HELIUS_CAP=int(os.environ.get('HELIUS_CAP','0'))
def _hkey():
    k=os.environ.get('HELIUS_API_KEY') or os.environ.get('HELIUS_KEY')
    if k: return k
    try:
        for l in open('/home/box/.scout-secrets/helius.env'):
            if '=' in l and 'KEY' in l.split('=')[0].upper(): return l.split('=',1)[1].strip().strip('"\'')
    except Exception: pass
    return None
# fallback order (probed 2026-10-25 ~10:00Z): publicnode, Solana Labs/Triton mainnet-beta, LeoRPC public FREE tier, Helius (capped)
RPCS=[dict(name='publicnode',url='https://solana-rpc.publicnode.com',gap=0.12),
      dict(name='mainnet-beta',url='https://api.mainnet-beta.solana.com',gap=0.45),
      dict(name='leorpc-free',url='https://solana.leorpc.com/?api_key=FREE',gap=1.0)]
for s in RPCS: s.update(next=0.0,cool=0.0,fails=0)
_L=threading.Lock(); _logL=threading.Lock()
def _log(src,meth,st):
    with _logL: open(LOG,'a').write(f"{int(time.time())} {src} {meth} {st}\n")
def _post(url,body,timeout=30):
    req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","User-Agent":"scout-readonly/1.0"})
    return json.loads(urllib.request.urlopen(req,timeout=timeout).read())
def _pick(skip=()):
    while True:
        with _L:
            now=time.time(); ok=[s for s in RPCS if s['cool']<=now and s['name'] not in skip] or [s for s in RPCS if s['cool']<=now]
            if not ok: wait=min(s['cool'] for s in RPCS)-now
            else:
                s=min(ok,key=lambda s:(max(s['next'],now),RPCS.index(s)))
                wait=s['next']-now
                if wait<=0: s['next']=now+s['gap']; return s
        time.sleep(max(0.02,min(wait,5)))
def _hel_take():
    with _L:
        u=json.load(open(HCF))['used'] if os.path.exists(HCF) else 0
        if u>=HELIUS_CAP: return False
        json.dump({'used':u+1},open(HCF,'w')); return True
def helius_used(): return json.load(open(HCF))['used'] if os.path.exists(HCF) else 0
def rpc(method,params,tries=6):
    if method=='getTransaction' and len(params)>1 and isinstance(params[1],dict) and params[1].get('maxSupportedTransactionVersion',1)<1:
        params=[params[0],dict(params[1],maxSupportedTransactionVersion=1)]   # v1 txs exist (busy bots); v0 requests fail with -32015
    body={"jsonrpc":"2.0","id":1,"method":method,"params":params}
    skip=set()
    for a in range(tries):
        s=_pick(skip)
        try:
            r=_post(s['url'],body); 
            if 'result' in r and (r['result'] is not None or method!='getTransaction' or a==tries-1): s['fails']=0; _log(s['name'],method,200); return r['result']
            _log(s['name'],method,'rpcerr:'+str(r.get('error',{}).get('code'))); skip.add(s['name'])  # request-specific error: try next source, no cooldown
        except urllib.error.HTTPError as e:
            _log(s['name'],method,e.code); s['fails']+=1; s['cool']=time.time()+(60 if e.code in (401,402,403) else 8*s['fails'])
        except Exception as e:
            _log(s['name'],method,'exc'); s['fails']+=1; s['cool']=time.time()+5*s['fails']
    if HELIUS_CAP and _hel_take():
        k=_hkey()
        if k:
            try:
                r=_post('https://mainnet.helius-rpc.com/?api-key='+k,body); _log('helius',method,200 if 'result' in r else 'rpcerr')
                return r.get('result')
            except Exception as e: _log('helius',method,getattr(e,'code','exc'))
    return None
# HTTP GET sources with own pacing (GeckoTerminal ~30/min free; DexScreener ~300/min; Jupiter/Raydium lite)
HG={'api.geckoterminal.com':2.1,'api.dexscreener.com':0.25,'lite-api.jup.ag':0.5,'api-v3.raydium.io':0.5,'kolscan.io':2.0}
_hn={}
def get(url,tries=4,cache=None):
    if cache is not None and url in cache: return cache[url]
    host=url.split('/')[2]; gap=HG.get(host,1.0)
    for a in range(tries):
        with _L:
            w=_hn.get(host,0)-time.time(); _hn[host]=max(time.time(),_hn.get(host,0))+gap
        if w>0: time.sleep(w)
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=25))
            _log(host,'GET',200)
            if cache is not None: cache[url]=r
            return r
        except urllib.error.HTTPError as e:
            _log(host,'GET',e.code)
            if e.code in (403,404,401): return None   # blocked/absent: skip, never work around
            time.sleep(6*(a+1))
        except Exception: _log(host,'GET','exc'); time.sleep(3)
    return None
