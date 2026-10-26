import json,collections,statistics as st,glob,os
W=json.load(open('an/gt2_trades.json'))
OI='/workspace/onchain-intel/'; txt=''.join(open(OI+f).read() for f in ['known_funders.csv','avoid.csv','known_ruggers.json','custodial_ignore.json'])
done={os.path.basename(f)[:-5] for f in glob.glob('an/wg/*.json')}|set(json.load(open('an/sigscreen.json')))|set(json.load(open('an/sigscreen2.json')))
if os.path.exists('an/sig3.json'): done|=set(json.load(open('an/sig3.json')))
C=[]
for w,L in W.items():
    if w in txt or w in done or not (1<=len(L)<=30): continue
    bytx=collections.defaultdict(set); byblk=collections.Counter()
    for t in L: bytx[t['tx']].add(t['kind']); byblk[t['blk']]+=1
    if any(len(k)>1 for k in bytx.values()) or max(byblk.values())>2: continue
    if not any(t['kind']=='buy' for t in L): continue
    if st.median(t['usd'] for t in L)<100 or max(t['usd'] for t in L if t['kind']=='buy')<300: continue
    Ls=sorted(L,key=lambda t:t['ts'])
    if any(b['kind']=='sell' and b['mint']==a['mint'] and 0<b['ts']-a['ts']<1800 for i,a in enumerate(Ls) if a['kind']=='buy' for b in Ls[i+1:]): continue
    C.append((len(L),w))
C.sort(reverse=True); print(len(C)); json.dump([w for _,w in C],open('an/cand3.json','w'))
