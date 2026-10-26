# Older-coins live setups, per setup, old vs wide universe (2026-10-23T23:56:02+00:00, PAPER research only)

Headline cost = 1% per side (= 2% round trip). Also: real_P0.0005 / real_P0.0001 = liquidity-scaled pool fee + 2 x size/liq + priority fee at a 10% x 0.928 SOL ticket; chunk_1pct = 1%/side + 2 x size/liq; flat 0.5% and 0.3%/side.
Universes: old = age >= 7 d, mcap $5-200M, liq >= $500k, vol24 >= $1M; wide = age >= 3 d, mcap $3M-1B, liq >= $300k, vol24 >= $750k (point-in-time approximations; 220 closed 1h bars still needed for EMA200, as in oldcoins.py). Both: thin-activity skip, avoid list, stables/LST/wrapped/tokenized excluded.
Live params: 1h breakout stop = breakout low clamped 2.5-8%, TP +15% half, trail 1h EMA20, act $150k/4 bars; 15m breakout clamp 2.5-6%, TP +10% half, trail 15m EMA20, act $40k/4 bars; C = 15m pullback (Lab spec, not yet in oldcoins.py or trades-log.md): last closed 1h C > EMA50 > EMA200, 15m low <= EMA20 < close, close > 15m EMA50, >= 3 of the prior 4 closes above EMA20; stop = pullback low clamped 2.5-6%, TP +10% half, trail 15m EMA20, act $40k, no volume test. All: entries 21:00-07:30 Dublin at next bar open, flat 07:45. 'all signals' = every qualifying signal (per-trade test); 'book' = max 3 open, one per token, 10% each. IS = first 70% of nights, OOS = last 30%.

| universe | setup | cost | sample | trades (IS/OOS) | tokens | mean/trade [95% CI] | median | win | IS mean | OOS mean [CI] | book P&L (10%/trade) | exits stop/eod/trail | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| old | 1h_breakout | c1.0 | all_signals | 59 (49/10) | 11 | -2.14% [-3.01%, -1.32%] | -1.78% | 24% | -1.94% | -3.14% [-5.76%, -0.51%] | -12.63% | 18/41/0 | CLEARLY NEGATIVE |
| old | 1h_breakout | c1.0 | book_max3 | 38 (32/6) | 11 | -1.77% [-2.86%, -0.68%] | -1.31% | 32% | -1.58% | -2.73% [-5.61%, +0.15%] | -6.71% | 10/28/0 | CLEARLY NEGATIVE |
| old | 1h_breakout | real_P0.0005 | all_signals | 59 (49/10) | 11 | -1.74% [-2.61%, -0.92%] | -1.37% | 25% | -1.53% | -2.74% [-5.37%, -0.10%] | -10.25% | 18/41/0 |  |
| old | 1h_breakout | real_P0.0005 | book_max3 | 38 (32/6) | 11 | -1.36% [-2.46%, -0.27%] | -0.90% | 32% | -1.18% | -2.33% [-5.22%, +0.56%] | -5.17% | 10/28/0 |  |
| old | 1h_breakout | c0.5 | all_signals | 59 (49/10) | 11 | -1.16% [-2.03%, -0.33%] | -0.79% | 31% | -0.95% | -2.17% [-4.81%, +0.49%] | -6.83% | 18/41/0 |  |
| old | 1h_breakout | c0.5 | book_max3 | 38 (32/6) | 11 | -0.78% [-1.88%, +0.32%] | -0.32% | 39% | -0.59% | -1.76% [-4.66%, +1.15%] | -2.96% | 10/28/0 |  |
| old | 1h_breakout | c0.3 | all_signals | 59 (49/10) | 11 | -0.76% [-1.64%, +0.07%] | -0.39% | 42% | -0.55% | -1.78% [-4.43%, +0.89%] | -4.49% | 18/41/0 |  |
| old | 1h_breakout | c0.3 | book_max3 | 38 (32/6) | 11 | -0.38% [-1.49%, +0.72%] | +0.08% | 53% | -0.20% | -1.36% [-4.28%, +1.56%] | -1.44% | 10/28/0 |  |
| old | 1h_breakout | | window 61 nights, OOS from 2026-10-05, raw signals 224, median real cost/side +0.79% | | | | | | | | | | |
| old | 15m_breakout | c1.0 | all_signals | 105 (78/27) | 12 | -1.76% [-2.51%, -0.97%] | -4.43% | 28% | -1.59% | -2.25% [-3.45%, -1.05%] | -18.44% | 56/45/4 | CLEARLY NEGATIVE |
| old | 15m_breakout | c1.0 | book_max3 | 56 (45/11) | 12 | -1.85% [-2.90%, -0.69%] | -4.43% | 25% | -1.96% | -1.41% [-3.26%, +0.53%] | -10.38% | 32/22/2 | CLEARLY NEGATIVE |
| old | 15m_breakout | real_P0.0005 | all_signals | 105 (78/27) | 12 | -1.35% [-2.10%, -0.56%] | -4.04% | 29% | -1.18% | -1.84% [-3.05%, -0.65%] | -14.19% | 56/45/4 |  |
| old | 15m_breakout | real_P0.0005 | book_max3 | 56 (45/11) | 12 | -1.45% [-2.50%, -0.29%] | -4.04% | 25% | -1.56% | -1.00% [-2.86%, +0.95%] | -8.12% | 32/22/2 |  |
| old | 15m_breakout | c0.5 | all_signals | 105 (78/27) | 12 | -0.77% [-1.53%, +0.02%] | -3.47% | 33% | -0.60% | -1.26% [-2.48%, -0.06%] | -8.07% | 56/45/4 |  |
| old | 15m_breakout | c0.5 | book_max3 | 56 (45/11) | 12 | -0.87% [-1.92%, +0.30%] | -3.47% | 29% | -0.98% | -0.42% [-2.29%, +1.54%] | -4.86% | 32/22/2 |  |
| old | 15m_breakout | c0.3 | all_signals | 105 (78/27) | 12 | -0.37% [-1.13%, +0.42%] | -3.08% | 33% | -0.20% | -0.87% [-2.09%, +0.34%] | -3.90% | 56/45/4 |  |
| old | 15m_breakout | c0.3 | book_max3 | 56 (45/11) | 12 | -0.47% [-1.53%, +0.71%] | -3.08% | 29% | -0.58% | -0.02% [-1.89%, +1.95%] | -2.63% | 32/22/2 |  |
| old | 15m_breakout | | window 58 nights, OOS from 2026-10-06, raw signals 411, median real cost/side +0.79% | | | | | | | | | | |
| old | C_15m_pullback | c1.0 | all_signals | 319 (228/91) | 16 | -1.90% [-2.13%, -1.67%] | -2.20% | 12% | -2.05% | -1.53% [-1.95%, -1.06%] | -60.74% | 59/252/8 | CLEARLY NEGATIVE |
| old | C_15m_pullback | c1.0 | book_max3 | 93 (68/25) | 15 | -2.01% [-2.47%, -1.51%] | -2.26% | 11% | -2.18% | -1.55% [-2.29%, -0.66%] | -18.70% | 21/69/3 | CLEARLY NEGATIVE |
| old | C_15m_pullback | real_P0.0005 | all_signals | 319 (228/91) | 16 | -1.50% [-1.73%, -1.27%] | -1.79% | 14% | -1.65% | -1.12% [-1.54%, -0.65%] | -47.85% | 59/252/8 |  |
| old | C_15m_pullback | real_P0.0005 | book_max3 | 93 (68/25) | 15 | -1.61% [-2.07%, -1.11%] | -1.85% | 12% | -1.78% | -1.14% [-1.89%, -0.25%] | -14.95% | 21/69/3 |  |
| old | C_15m_pullback | c0.5 | all_signals | 319 (228/91) | 16 | -0.92% [-1.15%, -0.68%] | -1.21% | 19% | -1.07% | -0.54% [-0.96%, -0.07%] | -29.29% | 59/252/8 |  |
| old | C_15m_pullback | c0.5 | book_max3 | 93 (68/25) | 15 | -1.03% [-1.49%, -0.52%] | -1.27% | 16% | -1.20% | -0.56% [-1.31%, +0.33%] | -9.54% | 21/69/3 |  |
| old | C_15m_pullback | c0.3 | all_signals | 319 (228/91) | 16 | -0.52% [-0.75%, -0.29%] | -0.82% | 23% | -0.67% | -0.14% [-0.57%, +0.33%] | -16.62% | 59/252/8 |  |
| old | C_15m_pullback | c0.3 | book_max3 | 93 (68/25) | 15 | -0.63% [-1.09%, -0.12%] | -0.88% | 20% | -0.80% | -0.16% [-0.92%, +0.74%] | -5.85% | 21/69/3 |  |
| old | C_15m_pullback | | window 58 nights, OOS from 2026-10-06, raw signals 1356, median real cost/side +0.79% | | | | | | | | | | |
| wide | 1h_breakout | c1.0 | all_signals | 117 (95/22) | 15 | -2.27% [-3.05%, -1.45%] | -1.88% | 23% | -2.02% | -3.35% [-5.08%, -1.63%] | -26.53% | 43/74/0 | CLEARLY NEGATIVE |
| wide | 1h_breakout | c1.0 | book_max3 | 74 (61/13) | 15 | -1.93% [-2.95%, -0.86%] | -1.76% | 31% | -1.70% | -3.03% [-5.49%, -0.64%] | -14.29% | 27/47/0 | CLEARLY NEGATIVE |
| wide | 1h_breakout | real_P0.0005 | all_signals | 117 (95/22) | 15 | -1.87% [-2.65%, -1.05%] | -1.48% | 26% | -1.61% | -2.95% [-4.69%, -1.23%] | -21.82% | 43/74/0 |  |
| wide | 1h_breakout | real_P0.0005 | book_max3 | 74 (61/13) | 15 | -1.53% [-2.55%, -0.45%] | -1.36% | 34% | -1.29% | -2.63% [-5.10%, -0.23%] | -11.30% | 27/47/0 |  |
| wide | 1h_breakout | c0.5 | all_signals | 117 (95/22) | 15 | -1.29% [-2.08%, -0.46%] | -0.89% | 31% | -1.03% | -2.38% [-4.12%, -0.64%] | -15.04% | 43/74/0 |  |
| wide | 1h_breakout | c0.5 | book_max3 | 74 (61/13) | 15 | -0.95% [-1.97%, +0.14%] | -0.77% | 38% | -0.71% | -2.05% [-4.54%, +0.36%] | -7.00% | 27/47/0 |  |
| wide | 1h_breakout | c0.3 | all_signals | 117 (95/22) | 15 | -0.89% [-1.69%, -0.06%] | -0.50% | 37% | -0.64% | -1.99% [-3.74%, -0.24%] | -10.41% | 43/74/0 |  |
| wide | 1h_breakout | c0.3 | book_max3 | 74 (61/13) | 15 | -0.55% [-1.58%, +0.54%] | -0.38% | 45% | -0.31% | -1.66% [-4.15%, +0.76%] | -4.06% | 27/47/0 |  |
| wide | 1h_breakout | | window 61 nights, OOS from 2026-10-05, raw signals 403, median real cost/side +0.79% | | | | | | | | | | |
| wide | 15m_breakout | c1.0 | all_signals | 213 (153/60) | 14 | -1.84% [-2.41%, -1.25%] | -4.43% | 25% | -2.07% | -1.27% [-2.37%, -0.09%] | -39.23% | 116/89/8 | CLEARLY NEGATIVE |
| wide | 15m_breakout | c1.0 | book_max3 | 94 (70/24) | 14 | -2.01% [-2.87%, -1.10%] | -4.43% | 23% | -2.12% | -1.68% [-3.29%, +0.11%] | -18.89% | 54/37/3 | CLEARLY NEGATIVE |
| wide | 15m_breakout | real_P0.0005 | all_signals | 213 (153/60) | 14 | -1.44% [-2.00%, -0.84%] | -4.04% | 26% | -1.66% | -0.86% [-1.97%, +0.32%] | -30.63% | 116/89/8 |  |
| wide | 15m_breakout | real_P0.0005 | book_max3 | 94 (70/24) | 14 | -1.61% [-2.47%, -0.69%] | -4.04% | 23% | -1.72% | -1.27% [-2.89%, +0.53%] | -15.10% | 54/37/3 |  |
| wide | 15m_breakout | c0.5 | all_signals | 213 (153/60) | 14 | -0.86% [-1.42%, -0.26%] | -3.47% | 31% | -1.08% | -0.28% [-1.39%, +0.91%] | -18.22% | 116/89/8 |  |
| wide | 15m_breakout | c0.5 | book_max3 | 94 (70/24) | 14 | -1.02% [-1.89%, -0.10%] | -3.47% | 28% | -1.14% | -0.69% [-2.32%, +1.12%] | -9.63% | 54/37/3 |  |
| wide | 15m_breakout | c0.3 | all_signals | 213 (153/60) | 14 | -0.46% [-1.03%, +0.14%] | -3.08% | 31% | -0.69% | +0.12% [-1.00%, +1.32%] | -9.76% | 116/89/8 |  |
| wide | 15m_breakout | c0.3 | book_max3 | 94 (70/24) | 14 | -0.63% [-1.50%, +0.30%] | -3.08% | 28% | -0.74% | -0.29% [-1.93%, +1.52%] | -5.90% | 54/37/3 |  |
| wide | 15m_breakout | | window 58 nights, OOS from 2026-10-06, raw signals 760, median real cost/side +0.79% | | | | | | | | | | |
| wide | C_15m_pullback | c1.0 | all_signals | 465 (322/143) | 18 | -2.21% [-2.42%, -2.00%] | -2.31% | 11% | -2.26% | -2.12% [-2.47%, -1.76%] | -102.94% | 146/309/10 | CLEARLY NEGATIVE |
| wide | C_15m_pullback | c1.0 | book_max3 | 135 (94/41) | 18 | -2.29% [-2.70%, -1.84%] | -2.34% | 11% | -2.43% | -1.95% [-2.53%, -1.29%] | -30.85% | 47/83/5 | CLEARLY NEGATIVE |
| wide | C_15m_pullback | real_P0.0005 | all_signals | 465 (322/143) | 18 | -1.81% [-2.02%, -1.59%] | -1.90% | 14% | -1.85% | -1.72% [-2.07%, -1.35%] | -84.22% | 146/309/10 |  |
| wide | C_15m_pullback | real_P0.0005 | book_max3 | 135 (94/41) | 18 | -1.88% [-2.30%, -1.43%] | -1.93% | 12% | -2.03% | -1.55% [-2.13%, -0.88%] | -25.42% | 47/83/5 |  |
| wide | C_15m_pullback | c0.5 | all_signals | 465 (322/143) | 18 | -1.23% [-1.44%, -1.01%] | -1.32% | 18% | -1.27% | -1.14% [-1.49%, -0.77%] | -57.24% | 146/309/10 |  |
| wide | C_15m_pullback | c0.5 | book_max3 | 135 (94/41) | 18 | -1.30% [-1.72%, -0.85%] | -1.36% | 15% | -1.45% | -0.97% [-1.55%, -0.30%] | -17.60% | 47/83/5 |  |
| wide | C_15m_pullback | c0.3 | all_signals | 465 (322/143) | 18 | -0.84% [-1.04%, -0.62%] | -0.93% | 22% | -0.88% | -0.74% [-1.09%, -0.37%] | -38.83% | 146/309/10 |  |
| wide | C_15m_pullback | c0.3 | book_max3 | 135 (94/41) | 18 | -0.91% [-1.32%, -0.45%] | -0.96% | 18% | -1.05% | -0.57% [-1.15%, +0.10%] | -12.26% | 47/83/5 |  |
| wide | C_15m_pullback | | window 58 nights, OOS from 2026-10-06, raw signals 1937, median real cost/side +0.79% | | | | | | | | | | |
