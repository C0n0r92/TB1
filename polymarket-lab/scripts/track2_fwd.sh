#!/bin/bash
# Forward (post-start) Track 2 data: closed 1h/4h BTC/ETH/SOL markets + public taker tape, last 2 days -> updown/data/markets_fwd.json
cd /workspace/polymarket-lab/updown && UD_DAYS=2 UD_OUT=markets_fwd.json UD_SERIES=btc-up-or-down-hourly,eth-up-or-down-hourly,solana-up-or-down-hourly,btc-up-or-down-4h,eth-up-or-down-4h,sol-up-or-down-4h python3 fetch.py | tail -2
