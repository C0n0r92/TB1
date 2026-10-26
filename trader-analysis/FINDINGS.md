# Trader on-chain analysis, 2026-10-23 (partial, deadline cut)
- sol_sigs.json: last <=1000 Solana signatures per trader (public RPC)
- tx/: ~219 fully fetched recent Solana txs (interleaved across the 8 traders, most recent first)
- tx_classification.json: what those txs are
Finding: the recent Solana activity is almost all pump.fun "DistributeFeeToHolders" payouts (other people's txs that pay small fees to holders), plus inbound SOL/token spam. Only 1 self-signed swap in the sample (_benjitrades). No copyable Solana trade history was found in the recent window.
The EVM addresses (ExactTallTakin, BtheBezel, bystevenr checked) are EIP-7702 delegated EOAs (code 0xef0100e6cae83bde06e4c305530e199d7217f42808555b), so trades are relayed and the nonce is ~1. _benjitrades is the exception: an ordinary EOA with nonce 4558 on Base and 6081 on BSC.
Blocked: base.blockscout.com sits behind a Cloudflare challenge; public Base/BSC RPC eth_getLogs is rate-limited or needs an address; no Robinhood Chain explorer was reachable/known. So EVM swap history, win rate and copier PnL: UNKNOWN.
