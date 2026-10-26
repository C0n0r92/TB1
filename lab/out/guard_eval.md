# Guard evaluation @ 2026-10-24T15:25:34+00:00 (PAPER ONLY)

Tokens with a scan score >= 55: 82 (77 RUG/dead, 5 survivor/runner). Labels: 0 final (24h), rest PROVISIONAL (label from the latest price, not 24h).
Replay caveat: pre-guard rows use holder data fetched AFTER the scan unless src=replay_pit.

| guard category | RUG/dead caught | survivors/runners rejected | uniquely rejected survivors |
|---|---|---|---|
| age | 70/77 | 2/5 Moustache, HUG | Moustache, HUG |
| holders | 8/77 | 0/5  |  |
| launch_fullcurve | 7/77 | 0/5  |  |
| launch_funded | 2/77 | 0/5  |  |
| launch_rugger | 1/77 | 1/5 COIL | COIL |
| liqdrop | 11/77 | 1/5 YMB | YMB |
| lp_danger | 16/77 | 0/5  |  |
| m5 | 6/77 | 0/5  |  |
| wash | 5/77 | 0/5  |  |

## (b) age gate: when do rugs happen? (pair age when price first <= -80% of the signal price; 5m candles)

| token | label | age at signal (min) | age at -80% (min) | ret signal->age45 | ret age45->last |
|---|---|---|---|---|---|
| GRINDCORE | RUG | 26 | 54 | -12% | -94% |
| YMB | RUG | 20 | 33 | -99% | -1% |
| NVIDIA | RUG | 32 | 35 | -100% | -2% |
| Tiggien | RUG | 356 |  | -14% | -1% |
| Weazel | RUG | 64 | 62 | -10% | -100% |
| CI | RUG | 131 | 134 | -7% | -100% |
| YMB | survivor | 313 |  | +3% | -50% |
| FOMO | RUG | 17 | 16 | -98% | -3% |
| Mr Beast | RUG | 23 | 27 | -99% | -1% |
| BITCHES | RUG | 21 | 298 | +76% | -100% |
| MCRIBUNKS | RUG | 17 | 64 | -33% | -99% |
| TRUTH | RUG | 21 | 408 | +21% | -92% |
| DROOLING | RUG | 23 | 100 | -34% | -99% |
| GTA6 Coin | RUG | 29 | 35 | -90% | -97% |
| Speed | RUG | 53 | 64 | +226% | -100% |
| TRUTH | RUG | 20 |  | +26% | +246584695% |
| MrBeast | RUG | 25 | 26 |  |  |
| GTA6 | RUG | 16 | 30 |  |  |
| fomo | RUG | 18 | 62 | +75% | -100% |
| YMBCOIN | RUG | 26 | 275 | -13% | -100% |
| Rockstar | RUG | 17 | 36 | -100% | -3% |
| Moustache | runner | 16 |  | +39% | +55% |
| zCondom | RUG | 23 | 27 | -99% | +7% |
| YMB | RUG | 34 | 212 | -4% | -99% |
| NVIDIA | RUG | 19 | 22 | -100% | -1% |
| SpaceX AI | RUG | 60 | 65 | +1191% | -100% |
| Gemini | RUG | 16 | 13 |  |  |
| Rockstar | RUG | 18 | 24 | -100% | +2% |
| Speed | RUG | 23 | 24 | -100% | -1% |
| NVIDIA | RUG | 27 | 32 | -98% | -1% |
| Gemini | RUG | 39 | 38 | -99% | +1% |
| Moustache | RUG | 16 |  |  |  |
| YMB | RUG | 18 |  |  |  |
| HTTP2Shell | RUG | 35 | 60 | +169% | -64% |
| KURIBO | RUG | 29 | 99 | +49% | -95% |
| GTA6 | RUG | 52 | 56 | -1% | -99% |
| IC | RUG | 42 | 63 | +1% | -99% |
| NVIDIA | RUG | 16 | 61 | +9% | -100% |
| ChatGPT | RUG | 20 | 22 | -98% | +0% |
| Moustache | RUG | 16 |  | +20% | +11% |
| FOMO | RUG | 22 | 67 | +89% | -100% |
| ELON | RUG | 32 | 200 | -10% | -94% |
| Moustache | RUG | 19 | 202 | +11% | -88% |
| MrBeast | RUG | 16 | 14 |  |  |
| Google | RUG | 23 | 51 | +64% | -100% |
| SpaceX | RUG | 30 | 42 |  |  |
| STANLEY | RUG | 18 | 24 | -98% | -3% |
| baldcat | RUG | 15 |  |  |  |
| baldcat | RUG | 25 |  | +71% | +59% |
| X | RUG | 17 | 37 | -100% | -2% |
| Rockstar | RUG | 25 | 40 | -100% | -0% |
| BARRON | RUG | 21 | 40 |  |  |
| Claude AI | RUG | 17 | 30 | -100% | -1% |
| MrBeast | RUG | 17 | 61 | +99% | -100% |
| Fomo | RUG | 35 | 61 | +23% | -100% |
| OpenAI | RUG | 19 | 69 | +88% | -100% |
| SLOPCOIN | survivor | 194 |  | -20% | -24% |
| BIO | RUG | 37 | 122 | -4% | -98% |
| Pumptache | RUG | 19 |  | +77% | +196% |
- gate 15 min: 2/48 candle-covered coins that ever hit -80% had done so before that age
- gate 20 min: 3/48 candle-covered coins that ever hit -80% had done so before that age
- gate 30 min: 11/48 candle-covered coins that ever hit -80% had done so before that age
- gate 45 min: 23/48 candle-covered coins that ever hit -80% had done so before that age
- gate 60 min: 26/48 candle-covered coins that ever hit -80% had done so before that age
- gate 90 min: 38/48 candle-covered coins that ever hit -80% had done so before that age

Note: pre-guard signalled coins were never rescanned, so 'caught by the age gate' there means the radar would have had to rescan them later; in live operation a young coin is re-scored at the next scan.

## per-token

| token | label | ret24 | kind | guard categories | src |
|---|---|---|---|---|---|
| GRINDCORE | RUG | -0.95 | provisional | age | replay_lookahead |
| YMB | RUG | -0.989 | provisional | age, holders | replay_lookahead |
| NVIDIA | RUG | -0.998 | provisional | age, holders, launch_fullcurve, wash | replay_lookahead |
| Tiggien | RUG | -0.955 | provisional | liqdrop | live |
| Weazel | RUG | -0.996 | provisional | holders, launch_fullcurve, wash | replay_lookahead |
| CI | RUG | -0.998 | provisional | holders, wash | replay_lookahead |
| FOMO | RUG | -0.978 | provisional | age, holders, launch_fullcurve, liqdrop, m5, wash | replay_lookahead |
| Mr Beast | RUG | -0.987 | provisional | age, holders, launch_fullcurve, launch_funded, launch_rugger, liqdrop, wash | replay_lookahead |
| BITCHES | RUG | -0.997 | provisional | age, liqdrop | replay_lookahead |
| MCRIBUNKS | RUG | -0.994 | provisional | age, liqdrop | replay_pit |
| TRUTH | RUG | -0.898 | provisional | age, liqdrop | replay_pit |
| DROOLING | RUG | -0.99 | provisional | age, liqdrop | replay_pit |
| GTA6 Coin | RUG | -0.997 | provisional | age, launch_fullcurve, launch_funded, liqdrop | replay_pit |
| Speed | RUG | -0.998 | provisional | liqdrop, m5 | live |
| TRUTH | RUG | 3099622.486 | provisional | age, lp_danger | live |
| MrBeast | RUG | -0.997 | provisional | age | live |
| GTA6 | RUG | -0.971 | provisional | age, m5 | live |
| fomo | RUG | -0.997 | provisional | age | live |
| YMBCOIN | RUG | -0.996 | provisional | age, holders | live |
| Rockstar | RUG | -0.997 | provisional | age | live |
| zCondom | RUG | -0.989 | provisional | age | live |
| YMB | RUG | -0.986 | provisional | age | live |
| NVIDIA | RUG | -0.997 | provisional | age | live |
| SpaceX AI | RUG | -0.997 | provisional | liqdrop, m5 | live |
| Gemini | RUG | -0.979 | provisional | age | live |
| Rockstar | RUG | -0.997 | provisional | age | live |
| Speed | RUG | -0.997 | provisional | age | live |
| NVIDIA | RUG | -0.984 | provisional | age, m5 | live |
| Gemini | RUG | -0.995 | provisional | age | live |
| Moustache | RUG | 0.285 | provisional | age, lp_danger | live |
| YMB | RUG | 0.053 | provisional | age, lp_danger | live |
| HTTP2Shell | RUG | -0.051 | provisional | age, lp_danger | live |
| KURIBO | RUG | -0.932 | provisional | age | live |
| GTA6 | RUG | -0.989 | provisional | launch_fullcurve | live |
| IC | RUG | -0.994 | provisional | age | live |
| NVIDIA | RUG | -0.997 | provisional | age | live |
| ChatGPT | RUG | -0.984 | provisional | age | live |
| Moustache | RUG | 0.338 | provisional | age, lp_danger | live |
| FOMO | RUG | -0.997 | provisional | age | live |
| ELON | RUG | -0.94 | provisional | age | live |
| Moustache | RUG | -0.871 | provisional | age, lp_danger | live |
| MrBeast | RUG | -0.997 | provisional | age, lp_danger | live |
| Google | RUG | -0.998 | provisional | age | live |
| SpaceX | RUG | -0.998 | provisional | age | live |
| STANLEY | RUG | -0.984 | provisional | age | live |
| baldcat | RUG | 0.149 | provisional | age, lp_danger | live |
| baldcat | RUG | 1.732 | provisional | age, lp_danger | live |
| X | RUG | -0.997 | provisional | age | live |
| Rockstar | RUG | -0.997 | provisional | age | live |
| BARRON | RUG | -0.998 | provisional | age | live |
| Claude AI | RUG | -0.997 | provisional | age | live |
| MrBeast | RUG | -0.998 | provisional | age | live |
| PRIVACY | RUG | -0.881 | provisional | age | live |
| TRUMP | RUG | -0.565 | provisional | age, lp_danger | live |
| Fomo | RUG | -0.998 | provisional | age | live |
| PUMP DEV | RUG | 0.233 | provisional | age, lp_danger | live |
| MrBeast | RUG | -0.998 | provisional | age, lp_danger | live |
| OpenAI | RUG | -0.997 | provisional | age | live |
| XiaZheng | RUG | -0.761 | provisional | age, holders, lp_danger | live |
| Musktache | RUG | -0.985 | provisional | age | live |
| BIO | RUG | -0.985 | provisional | age | live |
| Dacity | RUG | -0.984 | provisional | age | live |
| Rockstar | RUG | -0.998 | provisional | age | live |
| IVANKA | RUG | -0.995 | provisional | age, liqdrop, m5 | live |
| Apple | RUG | -0.997 | provisional | age | live |
| Pumptache | RUG | -0.985 | provisional | age | live |
| GORD | RUG | -0.98 | provisional | age | live |
| Gemini | RUG | -0.996 | provisional | launch_fullcurve | live |
| MrBeast | RUG | -0.998 | provisional | age | live |
| Trumptache | RUG | -0.993 | provisional | age | live |
| PRINTCAT | RUG | -0.996 | provisional | age | live |
| PEPILL | RUG | -0.993 | provisional | age, lp_danger | live |
| ? | RUG | 0.112 | provisional | age, lp_danger | live |
| DOPE | RUG | 1.52 | provisional | age, lp_danger | live |
| DeepSeek | RUG | -0.998 | provisional | age | live |
| TikTok | RUG | -0.997 | provisional | age | live |
| PUMP | RUG | -0.989 | provisional | age | live |
| Moustache | runner | 1.139 | provisional | age | live |
| YMB | survivor | -0.78 | provisional | liqdrop | live |
| COIL | survivor | -0.228 | provisional | launch_rugger | live |
| SLOPCOIN | survivor | -0.54 | provisional | - | live |
| HUG | survivor | -0.252 | provisional | age | live |
