#!/bin/bash
# per-wallet pipeline: an24 (SNIPE) -> sim -> tmeta -> fsim; concise summary. Read-only.
for W in "$@"; do
SNIPE=1 timeout 400 python3 an24.py $W > /dev/null 2>&1
python3 sim.py tx/$W.jsonl > /dev/null 2>&1
python3 tmeta.py $W > /dev/null 2>&1
python3 fsim.py $W > /dev/null 2>&1
python3 - $W <<'P'
import json,sys,os
w=sys.argv[1]; a=json.load(open(f'an/{w}.json')); s=json.load(open(f'an/{w}.sim.json')) if os.path.exists(f'an/{w}.sim.json') else {}
t=json.load(open(f'an/{w}.tm.json')) if os.path.exists(f'an/{w}.tm.json') else {}; f=json.load(open(f'an/{w}.fsim.json')) if os.path.exists(f'an/{w}.fsim.json') else {}
print(a.get('name'),w[:8],'| last',a.get('last_active'),'idle',a.get('idle_h'),'swaps',a.get('swaps_24h'),'| 1d',a.get('pnl_1d_sol'),'cap',a.get('pnl_1d_capped_sol'),'exb',a.get('ex_best_sol'),'win',a.get('win_rate'),'med%',a.get('med_ret_pct'),'hold',a.get('med_hold_min'),'n',a.get('rounds_closed'),'lt60',a.get('share_hold_lt60s'),'stock',a.get('stock_mints'),'snipe',len(a.get('snipe_early') or []),'ml',a.get('multi_leg_txs'),'clock',a.get('clock_share'))
print('   sim100',{k:s.get(k) for k in ('trigger_buys_24h','copied_closed','copy_win_rate','copy_med_ret_pct','copy_sum_ex_best','copy_med_hold_min','copy_share_lt60s')},'| tm lt10s',t.get('share_entry_lt10s'),'mcap',t.get('med_mcap_now_usd'),'age_h',t.get('med_pair_age_h_at_entry'))
print('   FSIM',f.get('triggers_passing'),f.get('blocked'),f.get('filtered'))
P
done
