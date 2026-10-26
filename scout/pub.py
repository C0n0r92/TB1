# Delegates to the multi-source fetch layer (fallback publicnode -> mainnet-beta -> leorpc-free -> Helius capped). Old version: pub.py.bak_1005
import sys; sys.path.insert(0,'/workspace/onchain-intel/bg')
import fetchlayer as _fl
RPC="fetchlayer"; GAP=0.0
def rpc(method, params, tries=6): return _fl.rpc(method, params, tries)
