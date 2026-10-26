# Value a wallet's still-open positions (bought within 7d tx file, not fully sold): current balance x DexScreener price vs SOL cost. Read-only, public RPC + DexScreener.
import json,sys,urllib.request,time,collections
sys.path.insert(0,'/workspace/scout'); import analyze as A
w=sys.argv[1]; fn=sys.argv[2] if len(sys.argv)>2 else f'tx7/{w}.jsonl'
L=[json.loads(l) for l in open(fn)]; L=[x for x in L if 'err' not in x]
sw=A.swaps(L)
pos={}
for x in sw:
    m=x['mint']
    if x['side']=='buy':
        p=pos.setdefault(m,dict(b=0,s=0,cin=0,cout=0)); p['b']+=x['tok']; p['cin']+=x['sol']
    elif m in pos:
        p=pos[m]; p['s']+=x['tok']; p['cout']+=x['sol']
        if p['s']>=0.95*p['b']: pos.pop(m)
def post(m,p):
    r=urllib.request.Request('https://api.mainnet-beta.solana.com',json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(r,timeout=30))
bal=collections.defaultdict(float)
for prog in ['TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA','TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb']:
    res=post('getTokenAccountsByOwner',[w,{"programId":prog},{"encoding":"jsonParsed"}])
    for a in res.get('result',{}).get('value',[]):
        i=a['account']['data']['parsed']['info']; bal[i['mint']]+=float(i['tokenAmount']['uiAmount'] or 0)
cost={m:p['cin']-p['cout'] for m,p in pos.items()}
mints=[m for m in cost]
px={}
SOLUSD=float(json.load(urllib.request.urlopen(urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/So11111111111111111111111111111111111111112',headers={'User-Agent':'Mozilla/5.0'}),timeout=30))[0]['priceUsd'])
for i in range(0,len(mints),30):
    d=json.load(urllib.request.urlopen(urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/'+','.join(mints[i:i+30]),headers={'User-Agent':'Mozilla/5.0'}),timeout=30))
    for p in d:
        m=p['baseToken']['address']; liq=(p.get('liquidity') or {}).get('usd') or 0
        if m not in px or liq>px[m][1]: px[m]=(float(p.get('priceUsd') or 0)/SOLUSD,liq,p.get('marketCap'))
tc=tv=0;rows=[]
for m in mints:
    v=bal.get(m,0)*px.get(m,(0,0,0))[0]; tc+=cost[m]; tv+=v; rows.append((m[:6],round(cost[m],2),round(bal.get(m,0)),round(v,3)))
out=dict(wallet=w,open_positions=len(mints),open_cost_sol=round(tc,2),open_value_sol=round(tv,2),unrealized_sol=round(tv-tc,2),src='public RPC getTokenAccountsByOwner + DexScreener tokens API priceUsd / SOL priceUsd (deepest-liquidity pair), '+time.strftime('%H:%MZ',time.gmtime()))
print(rows); print(out); json.dump(out,open(f'an/{w}.open.json','w'))
