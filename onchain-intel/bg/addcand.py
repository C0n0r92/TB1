"""Add wallets to cands.json (atomic) with name GT2-<prefix> and source string. Read-only wrt chain."""
import json,sys,os
C=json.load(open('cands.json')); src=os.environ.get('SRC','GeckoTerminal trades API 22:29Z: $100+ trades in established Solana pools (pool age>=1d, mcap>=$1M), bought 2+ pools or bought+sold >=60s later; public-RPC triage')
for w in sys.argv[1:]:
    if w not in C: C[w]=dict(name='GT2-'+w[:6],seed=False,twitter=None,k1=None,k7=None,k30=None,src=src)
json.dump(C,open('cands.json.tmp','w'),indent=1); os.replace('cands.json.tmp','cands.json')
