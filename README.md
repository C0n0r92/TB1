# hl-trading-bots

Code for a small crypto trading bot team. The two live bots trade perpetual futures on
Hyperliquid from one shared account; everything else is research, copy-trading experiments and
scanners that were used to decide what the live bots do.

This repo is **code only**. Logs, trade histories, runtime state, backups and data dumps are not
committed (see `.gitignore`).

## Secrets

Secrets live in `.env` files (for example `perpbot/.env`, chmod 600), which are **not committed**.
Never put a key in code, config or this repo. The bots read them from the environment:

| Variable | Used by | What it is |
|---|---|---|
| `HL_ACCOUNT` | perpbot, hlscalp | Public Hyperliquid account address (0x + 40 hex) |
| `HL_API_KEY` | perpbot, hlscalp | Hyperliquid **trade-only API wallet** key (cannot withdraw) |
| `HELIUS_API_KEY` | scout, onchain-intel, selfcopy | Solana RPC key (free tier) |

Example `perpbot/.env`:

```
export HL_ACCOUNT=0xYourPublicAccountAddress
export HL_API_KEY=<trade-only API wallet key>
```

## Setup

```
cd perpbot
python3 -m venv .venv
.venv/bin/pip install hyperliquid-python-sdk eth-account requests pandas numpy
```

`hlscalp` reuses `perpbot/.venv` and `perpbot/.env`.

## The bots

### Live (Hyperliquid)

- **perpbot/** - the 1-hour perp bot. Each hour it looks for trend changes across a list of coins,
  enters on the change, risks a fixed % of its bank per trade, takes partial profit early, and keeps
  a resting stop and take-profit on the exchange. Settings are in `config.json`; strategy code in
  `strategies.py`; `scorecard.py` prints a daily scorecard; `research/` holds the backtest and
  testnet tools used to tune it.
  - Run: `./run.sh` (restart loop, logs to `runner.log`/`bot.log`). Stop: `./stop.sh`.
    Keep-alive: `./watchdog.sh` (e.g. from cron).
- **hlscalp/** - the 15-minute scalper on the same account. Entry triggers (VWAP reclaim, failed
  breakout fade, VWAP band reclaim, squeeze, etc.) must agree with a 1-hour trend gate and a set of
  confirmers. Sizes off the stop, with smaller size for stacked same-direction trades and a cap on
  open risk per direction. Moves stops to break-even at +0.75R, takes profit then trails. A lockout
  stops it and the perp bot from trading the same coin at once. Settings in `config.json`;
  `tests/` has offline tests.
  - Run: `./run.sh` (uses `perpbot/.env` and `perpbot/.venv`). Keep-alive: `./watchdog.sh`.
    Stop the loop with `touch STOP_LOOP`.
  - Tests: `../perpbot/.venv/bin/python tests/focus_tests.py` (and the other files in `tests/`).

### Reviews

- **review/**, **review2/** and `review-20261025.md` - scripts that pull fills from Hyperliquid,
  rebuild round trips and measure what worked (MFE, trigger breakdowns, replays).
  Run e.g. `python review2/pull.py && python review2/build.py && python review2/an.py`.
- **commander/** - team notes: board, failure modes, health and reporting rules.

### Solana copy-trading and research (mostly stopped)

- **selfcopy/** - copies buys from a roster of vetted Solana wallets with small fixed stakes,
  filters and exits. Paper by default; live only if a `LIVE` file exists.
  Run: `./start.sh` (paper) or `./start.sh --live`; stop: `./stop.sh`. Tests: `python test_*.py`.
- **copyfomo/** - notes and a screenshot helper from following traders on the Fomo app.
- **runner-radar/** - scans new Solana coins for runners, grades them and runs paper variants
  (`run_loop.sh`, `variants_loop.sh`).
- **scout/**, **onchain-intel/**, **trader-analysis/** - wallet and trader research: find
  profitable wallets, check their real on-chain results, build the copy roster.
  Run the individual scripts with `python <script>.py`; most need `HELIUS_API_KEY`.
- **hunter/** - early token hunter prototype (`python hunter/hunter.py`).
- **rugdiag/** - backtest of rug-pull detection rules.
- **sol-trend/** - Solana trend-following research (closed, see `CLOSED.md`).
- **lab/**, **lab2/** - backtests and forward tests behind the decisions above (`lab/config.toml`).
- **polymarket-lab/** - Polymarket weather and up/down research (closed, see `CLOSED.md`).
- **x-intel/**, **x-pulse/** - read-only X/Reddit sentiment and caller tracking (`python x-pulse/pulse.py`).

## Safety notes

- The Hyperliquid key must be a trade-only API wallet key, never the main wallet key.
- Only one instance of each bot may run (`bot.lock`); the run scripts refuse to start a second one.
