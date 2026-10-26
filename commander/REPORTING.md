# Team reporting structure (set by Zero, commander)

Team:
- Zero: commander. Doesn't trade. Owns efficiency, the scoreboard, and team changes.
- Copycat: copyfomo copy-trading wallet (started ~$94 USDC on 23 Oct 2026).
- Chunk: Banana Gun runner-radar wallet (started 0.928 SOL on 23 Oct 2026).
- Scout: Solana on-chain research (read-only), feeding the other bots.
- Lab: paper trading and backtesting only. Proposes proven rules to Zero (/workspace/lab/).
- Pulse: X (Twitter) research (read-only). It tracks which coins, narratives and callers are moving, and feeds Chunk's radar and Copycat's X checks.

## Nightly report (every trading bot, after its morning close)
Write /workspace/commander/reports/<bot>-<YYYY-MM-DD>.md (the date the night started), then send Zero a short message pointing to it.

Use these exact headings:
- Start value / end value (USD, plus SOL where relevant), % change
- Trades, wins, losses, fees if known
- Biggest win, biggest loss (with links)
- What went wrong / what broke
- Rule ideas (proposals only)

## Scout daily report
Write /workspace/commander/reports/scout-<YYYY-MM-DD>.md and put a "changed since last update" line at the top of /workspace/onchain-intel/NOTES.md.

Cover:
- New smart wallets and avoid-list entries
- Hits: smart wallets that were early in coins our bots traded, and avoid-list wallets in our losers
- Proposed rule or trader changes

## Pulse daily report
Write /workspace/commander/reports/pulse-<YYYY-MM-DD>.md. Keep /workspace/x-intel/ updated, including callers.csv (reliable early callers, with evidence), hot.json (coins and narratives trending right now, as contract addresses with a timestamp, readable by the radar) and NOTES.md.

Cover:
- callers who were early on our winners
- coins flagged as rugs or shills
- proposed changes

## Alerts (any time)
Message Zero right away with priority if any of these happen:
- A wallet hits its loss limit
- Something fails twice
- A rule seems to be causing harm

Message the user only as your own instructions say.

## Authority
Zero can change bots' jobs and rules within the user's risk caps:
- Size at most 15% per trade
- Stop loss on every position
- 20% nightly loss limit
- Copyfomo safety pause below $30
- Everything flat by 8am

Never deposit, withdraw, transfer, import wallets, or touch keys.

## Guard (safety watchdog, added 2026-10-23, agent 0efd06e0-11fc-4bba-a5c0-e84cc44ddf7a)
- Read-only. Every 15 min, 21:00-08:15 Dublin: wallet balances, bot freshness, loss limits, Telegram heartbeat, and a flat-by-07:55 check.
- Logs to /workspace/commander/guard-log.md. Alerts Zero with priority, and the user directly for limit breaches, open positions after 07:55, or silence over 45 min.
- Copycat writes a heartbeat line to x-watch-log.md each watch run: time, telegram ok or signed-out, balance, open positions.

## Team communication rule (user, 2026-10-23)
- Bots may message each other directly (SendToAgent) and read each other's files to cross-check and bounce ideas around.
- Any new idea or rule change goes to Zero for final review, with evidence attached, before it changes how a bot trades. Lab tests it first when it's a trading rule.
- Allowed without Zero: sharing data, asking a teammate to check something, and flagging a risk. Guard alerts go straight to Zero, or to the user if serious.
- Not allowed: one bot telling another to change trading settings, sizes or traders. Those come only from Zero.
- Use priority true only when the other bot must act now.

## Team board (2026-10-23)
All bots read and append findings to /workspace/commander/TEAM-BOARD.md each run (format and feed map inside). The 10% nightly goal never overrides caps.
