
## Root causes, ranked by $ lost (they overlap, so don't add them up)
1. **The PULLBACK trigger: −$5.35, 0/8, −9.7R.**
   - It was the primary trigger on every S1/S2 loss except SUI, plus LIT.
   - 6 of the 8 were shorts taken right after BTC's 10:00 low, while the old EMA20/50 1h trend still read −1.
   - The lagging 1h filter let them through.
2. **Correlated same-direction entries: −$5.12 from 8 shorts.**
   - 11:30:45–11:31:09: five shorts in 24 s (WLD, DOGE, AAVE, ONDO, TAO), plus SUI from 11:00. All six were stopped between 11:45 and 11:53, for −$3.18. That is one bet on "alts down" with 6× the risk.
   - 12:15: PUMP and kPEPE shorts together, −$1.94.
   - The perp bot's 6 shorts were also one directional bet (BTC/ETH/SOL/HYPE/XRP/ZEC), −$3.82.
3. **Perp bot trend entries in a chop: −$3.82, 0/6.**
   - All 6 entered in the 24 Oct "join" pass, i.e. joining signals that already existed. That is late, after the move.
   - MFE was only 0.1–0.87R against a 6R TP. XRP stopped at −1.04R.
   - The 18:04 restart (a rule change) triggered the startup signal_faded rule and market-closed BTC, HYPE and ZEC for −$2.19. They were all losing at the time. BTC drifted 80.78k→80.55k afterwards, so holding would have helped only slightly.
   - The 5% risk_per_trade did **not** apply to any of today's trades (they were 2%). It is live now, though: 3 stops at 5% would cost 15% of the perp bot's equity.
4. **Stops too tight for the noise in S1/S2, plus slippage beyond 1R.**
   - All 8 S1/S2 trades used 0.4% stops and were all stopped within 7–36 min.
   - Realized stop losses were −1.13 to −1.39R, not −1R, because of fees and taker slippage. That excess cost ≈2.2R (≈$1.1).
   - After the S3 changes (min 0.8% / 1 ATR plus slip buffer), stops came in at about −0.94 to −1.13R.
5. **Fees on small notional: $1.55, ≈15% of the total loss.**
   - Average scalper notional was ~$73. A taker round trip costs ≈0.09%, which is ≈0.23R on a 0.4% stop.
6. **Giving back open profit: 12 trades reached ≥0.5R MFE and still lost.**
   - That includes all 6 perp trades. The PUMP short got 1.54R vs TP1 at 1.49R and missed TP1 by about a tick, then lost −$0.94.
   - The 2 trades that did hit TP1 (TIA, INIT) made +$1.29.
7. **Bugs and outages: small direct $ cost, high trust cost.**
   - LIT was lost from tracking (watchdog SIGTERM mid-entry) but its stop worked: −$0.77, with no extra cost from the bug.
   - BNB double entry (stale snapshot): 2× intended size, ≈−$0.08 extra.
   - kPEPE and UNI were adopted after being lost from tracking. No harm (+$0.19, +$0.25).
   - HYPE perp P&L misrecorded (+0.005 vs −0.941), so the perp bot's own day-loss accounting is wrong by about $0.95.
   - The perp bot halted falsely at 09:34 (equity 52.09, "−37%"), a capital-accounting bug fixed at 10:39.
   - Also: the 'p' crash at 20:02, a watchdog stale-heartbeat kill at 13:33, and HL 502s at 09:33.
8. **Frequent rule changes.**
   - Scalper: 17 starts and 5 rule versions in 9.5 h. Perp bot: 7 restarts.
   - No version ran long enough to judge it. Most of the bugs above came from restarts or box pauses, and one restart forced 3 market closes.
9. **Minor or not supported by today's data:**
   - Late entries: most entries were 18–137 s after the bar. The 6–7 min ones were kPEPE and BNB, both reconcile cases.
   - Time stop cutting winners: one case, kPEPE +0.19 at 0.59R MFE.
   - Your manual close: 5 positions, net −$0.22.

**Encouraging sign:** S3 (trigger + confirmers) ran 11 trades for 5W/6L and −$1.19 (−0.94R), close to flat. CORE was 3/5 and +$0.49. That is far too few trades to call an edge.

## Suggestions (analysis only, nothing changed)
**Top 3:**
1. **Fewer, stronger setups.**
   - Keep PULLBACK off (it already is, since 19:46). Make VPROFILE paper-only. Trade live only CORE and ABSORB with full confirmers.
   - Evidence: PULLBACK 0/8 −$5.35 and VPROFILE 1/5 −$1.79, vs CORE+ABSORB 4/6 +$0.83.
   - Expected effect: about −70% of today's scalper loss came from triggers you'd remove, and you'd take fewer trades and pay less in fees.
   - Risk: 6 trades is a tiny sample, and you may miss trend days.
2. **Correlated-exposure cap plus a BTC regime check, across both bots (they share one account).**
   - Caps: at most 2 new same-direction entries per bar, and at most 3 same-direction positions open account-wide.
   - Alts trade only when BTC's 1h Hull slope agrees with the direction.
   - Evidence: the 11:30 cluster (−$3.18 in 23 min), the 12:15 pair (−$1.94), and the perp bot's 6 shorts all in one direction (−$3.82).
   - Expected effect: today's worst cluster drops from 6R to ≤2–3R.
   - Risk: you under-participate in genuine broad moves.
3. **Freeze the rules, cut risk, and paper-test changes first.**
   - Run S3/Hull unchanged for ≥30–50 trades at 0.5% risk on the scalper.
   - Set the perp bot back from 5% to 1–2% risk until it has a positive record.
   - Any rule change goes to paper (hlscalp/paper_v0 exists) and must not be a live restart mid-position.
   - Evidence: 5 versions plus 24 restarts across the two bots, the restart-caused bugs, and the 18:04 forced closes.
   - Expected effect: halves the dollar damage while you learn, and gives you a clean sample to judge.
   - Risk: slower iteration, and smaller wins.

**Also worth doing:**
- A break-even or partial-profit move at ~+0.75R, paper-tested first. 12 of today's trades reached ≥0.5R and still lost; TP1 at 1.26–1.5R was hit only twice. Risk: more scratch trades.
- Keep wider stops with smaller size (S3 already does this). Losses moved from −1.27R to ~−1.0R.
- An always-on VPS (~€4–5/mo). It needs your signup and card. It removes the box-pause and watchdog class of bugs.
- A proper backtest on HL candles before re-enabling any trigger. Suggestion only; I ran none.
- Pause the perp bot until risk is reduced and the HYPE/close-fill accounting is fixed. It went 0/6 today, and its 5% risk is live.

## Full trade tables
