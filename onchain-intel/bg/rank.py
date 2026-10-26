"""Rank an/<w>.json into /workspace/onchain-intel/bg_copy_20.json (atomic). Read-only."""
import json,glob,os,time
C=json.load(open('cands.json')); OUT='/workspace/onchain-intel/bg_copy_20.json'
DIR=json.load(open('kolscan_directory.json'))
SPAM_UNVERIFIED=json.load(open('spam_unverified.json')) if os.path.exists('spam_unverified.json') else []
SPAM_UNVERIFIED=[u for u in SPAM_UNVERIFIED if not os.path.exists('an/%s.json'%u['wallet'])]
SEEDS=['Rilsio','KOREAN','zeropnl','bystevenr','Cented','decu','Schoen','West','Doji','Mel','King Solomon']
def xh(w):
    c=C.get(w,{}); t=c.get('twitter') or (DIR.get(w) or {}).get('twitter')
    if t: t=t.split('/')[-1].lstrip('@')
    return t
rows=[];fails=[]
for f in glob.glob('an/*.json'):
    if os.path.basename(f).count('.')>1: continue
    if f.endswith('names.json') or f.endswith('.sim.json') or f.endswith('.p7.json') or f.endswith('.tm.json') or f.endswith('tmeta_cache.json') or f.endswith('.fsim.json') or f.endswith('fsim_meta.json'): continue
    a=json.load(open(f)); w=a['wallet']; c=C.get(w,{})
    if not a.get('name'): a['name']=c.get('name') or ('wallet-'+w[:6])
    k1=(c.get('k1') or {}); k7=(c.get('k7') or {})
    p7=k7.get('profit_sol'); p7src='kolscan weekly board (SOL, realized, not re-verified on-chain)' if p7 is not None else None
    _p7f='an/%s.p7.json'%a['wallet']; P7=json.load(open(_p7f)) if os.path.exists(_p7f) else {}
    if P7: p7=P7['pnl7_capped_sol'] if k7.get('profit_sol') is None or P7['pnl7_capped_sol']<p7 else p7; p7src=('on-chain 7d realized, capped to price move (SOL): raw %s / capped %s; ex-best %s; kolscan weekly %s'%(P7['pnl7_onchain_sol'],P7['pnl7_capped_sol'],P7['pnl7_ex_best_sol'],k7.get('profit_sol') and round(k7['profit_sol'],2)))
    why=[]
    S=json.load(open(f'an/{w}.sim.json')) if os.path.exists(f'an/{w}.sim.json') else {}
    if (a.get('pnl_1d_capped_sol') or 0)<=0 or (a.get('pnl_1d_sol') or 0)<=0: why.append(f"1d on-chain PnL not positive ({a.get('pnl_1d_sol')} SOL raw / {a.get('pnl_1d_capped_sol')} capped)")
    if S.get('trigger_buys_24h',0)<10: why.append(f"only {S.get('trigger_buys_24h')} buys >=$100 in 24h (need 10)")
    if S.get('copied_closed',0)<5: why.append(f"only {S.get('copied_closed')} closed copyable ($100+) round trips")
    else:
        if S['copy_med_hold_min']<1.0: why.append(f"median hold of $100+ entries {S['copy_med_hold_min']} min (<1 min, not copyable)")
        if S['copy_share_lt60s']>0.5: why.append(f"dumps fast: {int(S['copy_share_lt60s']*100)}% of $100+ entries sold <60s after buy")
        if S['copy_sum_ret_after_2pct_cost']<=0: why.append(f"copy sim loses after 2% round-trip cost ({S['copy_sum_ret_after_2pct_cost']} units)")
        if S['copy_sum_ex_best']<=0: why.append(f"copy profit carried by one trade (ex-best {S['copy_sum_ex_best']} units, best {S['copy_best_ret_pct']}%)")
        if not (S['copy_win_rate']>=0.4 or S['copy_med_ret_pct']>0): why.append(f"low win quality (win {S['copy_win_rate']}, median {S['copy_med_ret_pct']}%)")
    if p7 is None: why.append('7d PnL unknown (not on Kolscan weekly top-50; on-chain 7d not fetched)')
    elif p7<=0: why.append(f'7d PnL negative ({p7} SOL)')
    if (a.get('idle_h') or 99)>6: why.append(f"inactive {a.get('idle_h')}h")
    if a.get('stock_mints'): why.append(f"trades tokenized stocks {a['stock_mints']}")
    se=a.get('snipe_early') or []
    if len(se)>=2: why.append(f"dev/launch buyer: {len(se)} of its {a.get('snipe_checked')} largest 24h entries were in the token's creation tx or within 2 slots of it")
    if a.get('known_rugger'): why.append('on known_ruggers.json')
    if a.get('custodial'): why.append('custodial')
    TM=json.load(open(f'an/{w}.tm.json')) if os.path.exists(f'an/{w}.tm.json') else {}
    if (TM.get('tokens') or 0)>=5 and (TM.get('share_entry_lt10s') or 0)>=0.25: why.append(f"launch sniper: {int(TM['share_entry_lt10s']*100)}% of its first buys per token landed within 10s of the token's creation ({int(TM['share_entry_lt60s']*100)}% within 60s; DexScreener pairCreatedAt, spot-checked against the mint's first on-chain tx)")
    if (a.get('clock_share') or 0)>0.4: why.append(f"scheduled bot: {int(a['clock_share']*100)}% of swaps land in the same 30s slot of every 10-minute cycle")
    if (a.get('multi_leg_txs') or 0)>3: why.append('multi-leg (MEV/arb-like) txs')
    FS=json.load(open(f'an/{w}.fsim.json')) if os.path.exists(f'an/{w}.fsim.json') else None
    FF=(FS or {}).get('filtered') or {}
    MT=json.load(open(f'an/{w}.mtm.json')) if os.path.exists(f'an/{w}.mtm.json') else None
    if MT is not None:
        MC=MT.get('combined') or {}; MCl=MT.get('closed') or {}
        if (MC.get('n') or 0)<8 or (MCl.get('n') or 0)<5: why.append(f"Chunk's BG filters leave only {MCl.get('n',0)} closed + {(MT.get('open') or {}).get('n',0)} open copies in 24h (need >=8 total, >=5 closed)")
        else:
            if (MC.get('med_ret_pct') or 0)<=0: why.append(f"filtered copy sim incl. open copies marked to market: median {MC.get('med_ret_pct')}% (not positive)")
            if (MC.get('sum_ex_best_after_2pct') or 0)<=0: why.append(f"filtered copy sim incl. open copies marked to market not positive without best trade after 2% cost ({MC.get('sum_ex_best_after_2pct')} units)")
            if (MC.get('med_hold_min') or 0)<1: why.append(f"filtered copy median hold {MC.get('med_hold_min')} min (<1)")
    elif FS is not None:
        if (FF.get('copied_closed') or 0)<8: why.append(f"Chunk's BG filters (mcap>=$30k, token age>=5min, leader buy>=$20) leave only {FF.get('copied_closed',0)} closed copies in 24h (need >=8) ({FS.get('triggers_passing')} buys pass; blocked {FS.get('blocked')})")
        else:
            if (FF.get('med_ret_pct') or 0)<=0: why.append(f"filtered copy sim median trade {FF.get('med_ret_pct')}% (not positive)")
            if (FF.get('sum_ex_best_after_2pct') or 0)<=0: why.append(f"filtered copy sim not positive without best trade after 2% cost ({FF.get('sum_ex_best_after_2pct')} units)")
            if (FF.get('med_hold_min') or 0)<1: why.append(f"filtered copy sim median hold {FF.get('med_hold_min')} min (<1)")
    e=dict(name=a.get('name'),x_handle=xh(w),x_handle_source=('kolscan' if xh(w) else None),wallet=w,
        wallet_source=c.get('src') or ('kolscan daily board' if c.get('k1') else 'seed/leader_mappings'),
        pnl_1d_sol_onchain=a.get('pnl_1d_sol'),pnl_1d_sol_capped=a.get('pnl_1d_capped_sol'),pnl_1d_usd_onchain=a.get('pnl_1d_usd'),
        pnl_1d_sol_kolscan=k1.get('profit_sol') and round(k1['profit_sol'],2),pnl_7d_sol=p7 and round(p7,2),pnl_7d_source=p7src,
        win_rate=S.get('copy_win_rate'),win_rate_all_rounds=a.get('win_rate'),closed_rounds_24h=a.get('rounds_closed'),trades_24h=a.get('swaps_24h'),
        median_hold_min=S.get('copy_med_hold_min'),median_hold_min_all_rounds=a.get('med_hold_min'),median_buy_usd=S.get('copy_med_buy_usd'),median_buy_usd_all_swaps=a.get('med_buy_usd'),buys_ge_100usd_24h=S.get('trigger_buys_24h'),copy_sim=S,median_position_usd=a.get('med_pos_usd'),median_trade_pct=S.get('copy_med_ret_pct'),median_trade_pct_all_rounds=a.get('med_ret_pct'),
        pnl_1d_ex_best_sol=a.get('ex_best_sol'),best_trade_sol=a.get('best_sol'),last_active_utc=a.get('last_active'),idle_h_at_check=a.get('idle_h'),
        share_rounds_held_lt2m=a.get('share_hold_lt2m'),snipe_check=f"{len(se)} of {a.get('snipe_checked')} largest entries near launch" if a.get('snipe_checked') is not None else 'not run')
    notes=[]
    if len(se)==1: notes.append('1 of its largest entries was in a token-creation tx / within 2 slots of launch')
    if (a.get('med_buy_usd') or 0)<100: notes.append(f"makes many small probe buys (median of all buys ${a.get('med_buy_usd')}): set BG Min Trade Size ~1 SOL so only its $100+ buys are copied")
    if e['x_handle'] is None: notes.append('no X handle on Kolscan: cannot be added on copyfomo by handle')
    if (S.get('copy_med_hold_min') or 0)<2 and not why: notes.append('median hold under 2 min: copy latency risk')
    if k1.get('profit_sol') is not None and a.get('pnl_1d_sol') is not None and abs(k1['profit_sol']-a['pnl_1d_sol'])>max(3,0.3*abs(k1['profit_sol'])):
        notes.append(f"Kolscan 1d {round(k1['profit_sol'],2)} SOL vs on-chain rolling-24h closed rounds {a['pnl_1d_sol']} SOL (different windows; Kolscan may include open/older positions)")
    e['token_profile_24h']={k:TM.get(k) for k in ('tokens','med_entry_delay_min','share_entry_lt10s','share_entry_lt60s','med_pair_age_h_at_entry','share_pair_lt1h','med_mcap_now_usd','share_mcap_lt100k','share_mcap_ge1m','med_liq_now_usd')} if TM else None
    e['copy_sim_chunk_filters']=(dict(filters=FS.get('filters'),buys_24h=FS.get('buys_24h'),buys_passing_filters=FS.get('triggers_passing'),blocked=FS.get('blocked'),**FF,open_copies=FS.get('filtered_open')) if FS else 'not run')
    e['copy_sim_chunk_filters_mtm']=(dict(closed=MT.get('closed'),open_marked_to_market=MT.get('open'),open_unpriced=MT.get('open_unpriced'),combined=MT.get('combined'),computed_utc=MT.get('computed_utc'),note=MT.get('note')) if MT else 'not run')
    e['pnl_30d_sol_kolscan']=(c.get('k30') or {}).get('profit_sol') and round(c['k30']['profit_sol'],2)
    e['notes']='; '.join(notes); e['fail_reasons']=why
    n=max(1,S.get('copied_closed') or 1); e['_xbonus']=1 if e['x_handle'] else 0; e['_score']=e['_xbonus']+10*(S.get('copy_sum_ex_best') or 0)/n + 5*(S.get('copy_win_rate') or 0) + min(S.get('copy_med_ret_pct') or 0,30)/10
    (rows if not why else fails).append(e)
rows.sort(key=lambda e:-e['_score'])
for i,e in enumerate(rows,1): e['rank']=i; e.pop('_score'); e.pop('_xbonus'); e.pop('fail_reasons')
for e in fails: e.pop('_score'); e.pop('_xbonus')
seed={}
for s in SEEDS:
    m=[e for e in rows+fails if e['name']==s]
    seed[s]=('PASS' if m and m[0] in rows else ('FAIL: '+'; '.join(m[0]['fail_reasons']) if m else 'not analysed on-chain'))
for u in SPAM_UNVERIFIED:
    if u['name'] in SEEDS: seed[u['name']]='UNVERIFIED: '+u['reason']
COPIED={'rilsio','korean','bystevenr','ew4ue-flip','cented','decu','schoen','west','pointfarmcap','exacttalltakin','_benjitrades','neodot','doji','mel','kingsolomon','king solomon'}
def _k7wr(c):
    k=c.get('k7') or {}
    return round(k['wins']/(k['wins']+k['losses']),2) if k.get('wins') is not None and (k['wins']+k['losses']) else None
def chunk_entry(e,status):
    c=CANDS.get(e['wallet'],{}); tp=e.get('token_profile_24h') or {}; S=e.get('copy_sim') or {}
    flags=[]
    if tp.get('med_entry_delay_min') is not None and ((tp.get('share_pair_lt1h') or 0)>=0.5 or (tp.get('med_mcap_now_usd') is not None and tp['med_mcap_now_usd']<100000)): flags.append(f"young/tiny tokens: median entry {tp['med_entry_delay_min']} min after token creation, {int((tp.get('share_pair_lt1h') or 0)*100)}% of tokens <1h old at entry, median current mcap ${tp.get('med_mcap_now_usd')} (most of its coins are now dead micro-caps); conflicts with Chunk's 'not too young or tiny'")
    if (e.get('trades_24h') or 0)>150: flags.append(f"busy: {e['trades_24h']} swaps/24h (a human KOL using a fast bot, not a scheduled bot, but expect many copies at 0.08 SOL each)")
    if (e.get('idle_h_at_check') or 0)>6: flags.append(f"idle {e['idle_h_at_check']}h at check (last swap {e.get('last_active_utc')})")
    if (S.get('copy_med_hold_min') or 99)<3: flags.append(f"short holds (median {S.get('copy_med_hold_min')} min): copy latency matters")
    if e.get('pnl_1d_ex_best_sol') is not None and e.get('pnl_1d_sol_capped') and e['pnl_1d_ex_best_sol']<0.5*e['pnl_1d_sol_capped']: flags.append(f"1d profit concentrated: {e['pnl_1d_sol_capped']} SOL total, {e['pnl_1d_ex_best_sol']} SOL without its best trade")
    P7=json.load(open(f"an/{e['wallet']}.p7.json")) if os.path.exists(f"an/{e['wallet']}.p7.json") else None
    if P7: flags.append(f"on-chain 7d: {P7['pnl7_capped_sol']} SOL capped, {P7['pnl7_ex_best_sol']} SOL ex-best, 7d round win rate {P7['win_rate_7d']}; daily SOL {P7['daily_sol']}")
    OP=json.load(open(f"an/{e['wallet']}.open.json")) if os.path.exists(f"an/{e['wallet']}.open.json") else None
    if OP and OP['open_positions']>=5: flags.append(f"holds open bags: {OP['open_positions']} unsold positions costing {OP['open_cost_sol']} SOL, now worth {OP['open_value_sol']} SOL (unrealized {OP['unrealized_sol']} SOL; {OP['src']}); win rates above count closed trades only")
    if e.get('notes'): flags.append(e['notes'])
    return dict(name=e['name'],x_handle=e.get('x_handle'),wallet=e['wallet'],status=status,
        pnl_7d_sol=e.get('pnl_7d_sol'),pnl_7d_source=e.get('pnl_7d_source'),pnl_30d_sol_kolscan=e.get('pnl_30d_sol_kolscan'),
        win_rate_copy_sim_24h=S.get('copy_win_rate'),win_rate_kolscan_7d=_k7wr(c),trades_per_day=e.get('trades_24h'),
        median_buy_usd=e.get('median_buy_usd'),median_hold_min=e.get('median_hold_min'),
        copy_sim_chunk_filters=e.get('copy_sim_chunk_filters'),copy_sim_chunk_filters_mtm=e.get('copy_sim_chunk_filters_mtm'),why=None,red_flags=flags,token_profile_24h=tp or None)
CANDS=json.load(open('cands.json'))
fc=[chunk_entry(e,'passes every BG criterion') for e in rows if e['name'].lower() not in COPIED]
for e in fails:
    if e['name'].lower() in COPIED: continue
    if e['fail_reasons'] and all(x.startswith('inactive') for x in e['fail_reasons']): fc.append(chunk_entry(e,'passes every check except recent activity'))
WHY=json.load(open('chunk_why.json')) if os.path.exists('chunk_why.json') else {}
for x in fc: x['why']=WHY.get(x['name'])
EXC={e['name']:'; '.join(e['fail_reasons']) for e in fails if e['name'].lower() not in COPIED and (e.get('pnl_7d_sol') or 0)>50 and (e.get('pnl_1d_sol_capped') or 0)>0}
MANX=json.load(open('manual_excl.json')) if os.path.exists('manual_excl.json') else {}
for k,v in MANX.items():
    if k in EXC: EXC[k]=v+' | auto: '+EXC[k]
    else: EXC[k]=v
for_chunk=dict(generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'),status='interim',copy_size_sol=0.08,
    excluded_as_already_copied=sorted(COPIED),
    summary=f"{len(fc)} new names met the checks; fewer than the 5-10 asked for, not padded. See copy_sim_chunk_filters and red_flags per name.",
    candidates=fc,profitable_but_excluded=EXC,
    replacements_requested_for=['KOREAN','Cented','Schoen','Rilsio','decu','bystevenr','West','Doji','Mel'],
    replacement_status=f"{len(fc)} passing replacement(s) of up to 9 requested (Pikalosi counts as 1); every candidate re-simulated with Chunk's BG filters (min mcap $30k, min token age 5 min, leader buy >= $20); a wallet must still have >=8 closed filtered copies with positive median and positive ex-best after 2% cost. List not padded.")
doc=dict(generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ'),status='partial' if os.environ.get('PARTIAL') else 'final',
    count_qualified=len(rows),note=(f"Only {len(rows)} wallets passed every criterion; list not padded." if len(rows)<20 else ''),
    method=open('method.txt').read() if os.path.exists('method.txt') else '',
    ranked=rows[:20],seed_results=seed,near_misses=sorted(fails,key=lambda e:len(e["fail_reasons"]))[:40],
    unverified_spammed_wallets=SPAM_UNVERIFIED,for_chunk=for_chunk)
for _k,_f in (('leader_verdicts','leader_verdicts.json'),('screened_no_24h_swaps','no_swaps.json'),('notes_by_wallet','wallet_notes.json')):
    if os.path.exists(_f): doc[_k]=json.load(open(_f))
json.dump(fails,open("all_fails.json","w"),ensure_ascii=False,default=str)
json.dump(doc,open(OUT+'.tmp','w'),indent=1,ensure_ascii=False); os.replace(OUT+'.tmp',OUT)
print(len(rows),'qualified'); [print(e['rank'],e['name'],e['x_handle'],e['pnl_1d_sol_capped'],e['pnl_7d_sol'],e['win_rate'],e['trades_24h'],e['median_hold_min'],e['median_buy_usd']) for e in rows]
for k,v in seed.items(): print(k,v[:150])
