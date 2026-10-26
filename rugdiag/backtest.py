import json, re, sys, glob, os, datetime as dt
sys.path.insert(0, '/workspace/runner-radar')
import rugguard
now = json.load(open('/workspace/rugdiag/now.json'))
rows = [json.loads(l) for l in open('/workspace/runner-radar/scanned.jsonl')]
by = {}
for r in rows: by.setdefault(r['token'], []).append(r)
def scout(a):
    for fn in (f'/workspace/rugdiag/sc_{a}.json', f'/workspace/onchain-intel/data/rugcheck/{a}.json'):
        try:
            j = json.load(open(fn))
            if j: return j
        except Exception: pass
    return None
res = []
for a, rs in by.items():
    o = now.get(a)
    if not o or o['ret'] is None: continue
    rep = json.load(open(f'/workspace/rugdiag/rc_{a}.json'))
    lab = 'RUG' if o['ret'] < -0.8 else ('dead?' if o['liq_now'] < 1000 else 'surv')
    # evaluate the first scan where it would have been a candidate (old score >= 55 & no old rejects), else first scan
    cand = [r for r in rs if r['score'] >= 55 and not r['rejects']]
    r = (cand or rs)[0]; idx = rs.index(r)
    x = rugguard.rc_extract(rep, r['pair'])
    x['danger'] = [d for d in x['danger'] if d != 'Low Liquidity']   # post-rug artefact, not knowable at signal time
    b = re.search(r'\((\d+) buyers/5m\)', ' '.join(r['reasons'])); b5 = int(b.group(1)) if b else None
    rej, pen, why = rugguard.guard(r, x, rs[:idx], b5)
    srej, spen, swhy = rugguard.scout_verdict(scout(a))
    noage = [z for z in rej if not z.startswith('too young')]
    res.append(dict(sym=r['symbol'], tok=a[:6], lab=lab, old_sig=bool(cand), old=r['score'], new=max(0, r['score']-pen-spen),
                    rej=rej, srej=srej, noage=noage, sv=(scout(a) or {}).get('verdict'), ret=o['ret']))
for z in sorted(res, key=lambda z: z['lab']):
    print(f"{z['lab']:5} {z['sym'][:9]:9} {z['tok']} oldsig={int(z['old_sig'])} {z['old']:5.1f}->{z['new']:5.1f} ret {z['ret']*100:+6.0f}% scout={z['sv']}  rej={z['rej'] + z['srej']}")
def tally(name, f):
    R = [z for z in res if z['lab'] == 'RUG']; S = [z for z in res if z['lab'] == 'surv']
    print(f"{name:45} rugs rejected {sum(map(f,R))}/{len(R)}  survivors rejected {sum(map(f,S))}/{len(S)}")
print()
tally('age>=45min only', lambda z: any(s.startswith('too young') for s in z['rej']))
tally('holders/mcap-per-holder/wash only', lambda z: any(('holders' in s or 'per holder' in s or 'wash' in s) for s in z['rej']))
tally('Scout launch forensics only', lambda z: bool(z['srej']))
tally('m5 crash/spike + liq drop', lambda z: any(s.startswith(('crashing','extreme','liquidity fell')) for s in z['rej']))
tally('rugcheck danger + LP lock + creator', lambda z: any(s.startswith(('rugcheck danger','LP only','creator')) for s in z['rej']))
tally('ALL except age', lambda z: bool(z['noage'] or z['srej']))
tally('ALL incl age', lambda z: bool(z['rej'] or z['srej']))
sig = [z for z in res if z['old_sig']]
print('\nold live signals:', len(sig), ' rugs among them:', sum(z['lab']=='RUG' for z in sig))
print('would still signal (no reject, new score>=55):', [(z['sym'], z['lab']) for z in sig if not (z['rej'] or z['srej']) and z['new'] >= 55])
print('would still signal ignoring age gate:', [(z['sym'], z['lab']) for z in sig if not (z['noage'] or z['srej']) and z['new'] >= 55])
