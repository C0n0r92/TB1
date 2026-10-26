Changed since last update (2026-10-24T09:05:48Z): top heat COIL 70.8,  46.6, PUMP DEV 5.0; rug flags 0; callers with early calls 9; reads left today 932.

# x-intel notes (Pulse, X research, read-only)

Files (written atomically by /workspace/x-pulse/pulse.py merge; do not hand-edit except this NOTES.md body):
- hot.json: per tracked coin (contract_address, ticker, ts, mentions_15m, mentions_60m, distinct_accounts, heat_score 0-100,
  trend rising|flat|fading, confidence low|med|high) + narratives. Mirrors /workspace/x-pulse/latest.json. `stale: true` = no X reads that run.
- rugs.json: coins flagged rug|honeypot|dev_dump|scam by >=2 distinct aged (>=90d), non-promo, non-template accounts, with post URLs.
  Weaker flags (1 account, or only bot/promo accounts) stay out and appear in latest.json coin notes.
- callers.csv: accumulates accounts that mentioned a CA before the coin's first runner-radar signal (or first radar scan if never
  signalled) or before the first Pulse run where that coin spiked (>=8 mentions/15m). Only aged, >=100-follower accounts with no
  promo/template/brag flags. Evidence = real x.com post URLs from saved raw results.
- latest.json: byte copy of hot.json (same schema), for consumers that expect that name.
- midcaps.json: hourly X attention on Solana mid-caps / older coins (mcap $5M-$200M, liq >= $500k, top 20 by 24h volume from
  DexScreener, plus Chunk's oldcoins universe/paper tokens, held tokens, Scout oldcoins-intel candidates): per-coin heat, distinct
  and quality accounts, posts/h, 1h price change, sector rollup, flags (quality_attention_before_move, pre_breakout_momentum),
  alerts. `held` section (refreshed EVERY run): negative attention (rug/exploit/hack/drained/dev dump/honeypot/can't sell...)
  on tokens Chunk holds LIVE, with alert true on >= 2 distinct quality accounts in 15 min or a sudden jump vs the previous run.
- first-mentions.jsonl: append-only, ONE line per (account user_id, token) ever = that "respected" account's FIRST post
  mentioning the token that Pulse has seen (deduped against the whole file; never rewritten). Written by the core merge,
  midcap-merge and held-merge from posts already fetched (0 extra X reads); `pulse.py first-mentions-backfill` replays raw/.
  Fields: token (contract address), ticker, handle, user_id, followers, account_created (ISO UTC), respected_reason,
  first_mention_at (post created_at, ISO UTC), post_url (https://x.com/<handle>/status/<id>), observed_at (ISO UTC, newest
  post time of the run that saw it), token_mcap_at_observation (USD, null unless a runner-radar or saved DexScreener snapshot
  exists within 60 min of observed_at), token_age_h (at observed_at, null if unknown), source_step core|midcap|held;
  extra keys: token_age_h_at_first_mention, token_data_source, token_mcap_snapshot_at, matched_by contract_address|ticker,
  quality_flags (Pulse author flags in that run's sample; [] = passed), backfill true|false.
  respected_reason (";"-joined): "quality_filters+followers>=2000" (no new/low_followers/promo/template/ring/self_template/brag
  flag AND >= 2000 followers), "copy-leads.md" (handle in a ranked lead heading of copy-leads.md, not the rejected/red-flag
  lists), "callers.csv" (handle or user_id in callers.csv, read at merge time).
  Caveats: first mention = earliest post in Pulse's samples (60-min windows, <= 25 posts/page), not necessarily the account's
  true first post. Backfilled lines use today's callers.csv/copy-leads.md (hindsight), so filter on respected_reason. Alert/
  tracker bots are excluded from new lines; older bot lines stay (append-only): drop user_ids in NOTES.md <!-- bot-excluded -->
first-mentions.jsonl bot/tracker exclusions (12 accounts, 25 lines; updated from bot-accounts.txt + handle heuristics). Consumers MUST drop rows whose user_id is in:
excluded_user_ids: 1436526596496629766,1669351608348721154,1918669396274221056,1920193758982705152,1938883544996290561,1946005552603000832,1976597274877673472,1981435433218449408,199800862,2022625677338349568,2033961945922228224,3001310558
- 1436526596496629766 @fourtislisting (denylist, 1 line)
- 1669351608348721154 @popmemecoin (denylist, 5 lines)
- 1918669396274221056 @AiSolanaKols (denylist, 1 line)
- 1920193758982705152 @SolanaMemesScan (denylist, 1 line)
- 1938883544996290561 @AuraTrackerBot (denylist, 2 lines)
- 1946005552603000832 @PeepRadars (denylist, 2 lines)
- 1976597274877673472 @AutorunAlert (denylist, 1 line)
- 1981435433218449408 @BscKOLScanner (denylist, 1 line)
- 199800862 @systemport_br (denylist, 1 line)
- 2022625677338349568 @RaOnChain (denylist, 2 lines)
- 2033961945922228224 @SolTokenScan (denylist, 1 line)
- 3001310558 @dex_kolwatcher (denylist, 7 lines)
<!-- /bot-excluded -->

<!-- reddit-status -->
Reddit side experiment status (2026-10-24T09:06:53Z): BLOCKED/FAILED from this box (https://www.reddit.com/r/all/rising.json?limit=100 HTTP 403). Backing off 6h until 2026-10-24T15:06:53Z. No workaround (no proxies, alternate hosts or logins) by design.
<!-- /reddit-status -->
