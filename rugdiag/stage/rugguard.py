"""Rug guards for runner-radar (stdlib only, read-only). Added 2026-10-23 after every live signal that night rugged.

Root cause: on pump.fun/pumpswap coins the old health checks (mint+freeze revoked, LP burned, low top-10) are
passed by EVERY coin, so they don't separate rugs from runners. The rugs were operator-run: one wallet buys the
whole bonding curve in the create tx (instant graduation), spreads tokens over many small wallets (so top-10 looks
low), wash-trades to fake volume/"unique buyers" (which our momentum score rewards), then sells everything into
the pool. LP stays 100% burned; the pool's SOL side is simply drained (liquidity -> ~$2k, SOL side ~$36).

Signals that catch this at signal time:
  * holder count vs activity: real crowds leave holders; wash bots don't. 5-min unique buyers >= total holders,
    or a big market cap spread over a handful of holders, is fake.
  * launch forensics (Scout's rugcheck_creator.py, Helius): full-curve dev buy in the create tx, creator a known
    rugger / funded by a serial-rug funder.
  * price/liquidity already collapsing (m5 crash, liquidity falling between scans), extreme 5-min spikes.
  * rugcheck danger-level risks (incl. LP unlocked on non-burned pools).
All functions are pure so they can be back-tested on scanned.jsonl."""
import json, os, subprocess, sys

MIN_AGE_H = 0.75            # 45 min: most operator rugs tonight happened within ~20-60 min of launch
MIN_HOLDERS = 300           # fewer total holders than this = no real crowd yet
MAX_MCAP_PER_HOLDER = 1500  # $ of market cap per holder; organic pump.fun coins were $25-$420 tonight
WARN_MCAP_PER_HOLDER = 700
WASH_RATIO = 1.0            # 5-min unique buyers / total holders >= this -> wash trading
WARN_WASH_RATIO = 0.4
M5_CRASH = -50.0            # 5-min price change <= this: dumping right now
M5_SPIKE = 150.0            # 5-min price change >= this: vertical candle, top-buying risk
LIQ_DROP = 0.30             # liquidity fell >= 30% vs an earlier scan in the last 90 min
LP_LOCK_MIN = 50.0          # % LP locked/burned required on the traded pool
CREATOR_MAX_PCT = 5.0       # creator still holding > 5% of supply
SCOUT = "/workspace/onchain-intel/rugcheck_creator.py"

def rc_extract(rep, pair_addr):
    """Pull the extra rug-relevant fields out of a rugcheck.xyz full report."""
    out = {"holders": None, "danger": [], "lp_locked": None, "market_type": None, "launchpad": None,
           "creator": None, "creator_pct": None, "creator_tokens": None, "insider_nets": 0, "quote_usd": None}
    if not isinstance(rep, dict):
        return out
    out["holders"] = rep.get("totalHolders")
    out["danger"] = [str(r.get("name"))[:40] for r in rep.get("risks") or [] if (r.get("level") or "").lower() == "danger"]
    out["launchpad"] = (rep.get("launchpad") or {}).get("platform")
    out["creator"] = rep.get("creator")
    try:   # creatorBalance is in raw token units, like token.supply
        sup, cb = float((rep.get("token") or {}).get("supply") or 0), float(rep.get("creatorBalance") or 0)
        if sup: out["creator_pct"] = round(100 * cb / sup, 2)
    except (TypeError, ValueError):
        pass
    ct = rep.get("creatorTokens")
    out["creator_tokens"] = len(ct) if isinstance(ct, list) else 0
    out["insider_nets"] = len(rep.get("insiderNetworks") or [])
    for m in rep.get("markets") or []:
        if m.get("pubkey") == pair_addr:
            lp = m.get("lp") or {}
            out["lp_locked"], out["market_type"], out["quote_usd"] = lp.get("lpLockedPct"), m.get("marketType"), lp.get("quoteUSD")
    return out

def scout_check(mint, timeout=60):
    """Run Scout's launch forensics (Helius if Scout configured it; key handled inside Scout's code, never here).
    Returns dict or None if unavailable."""
    if not os.path.exists(SCOUT):
        return None
    try:
        r = subprocess.run([sys.executable, SCOUT, mint], capture_output=True, text=True, timeout=timeout,
                           cwd=os.path.dirname(SCOUT))
        return json.loads(r.stdout) if r.stdout.strip().startswith("{") else None
    except Exception:
        return None

def scout_verdict(sc):
    """-> (rejects, penalty, reasons)"""
    if not sc:
        return [], 0, ["launch check unavailable"]
    rs = [str(x) for x in sc.get("reasons") or []]
    rej, pen, why = [], 0, []
    for x in rs:
        lx = x.lower()
        if "full-curve dev buy" in lx: rej.append("launch: full-curve dev buy in create tx (operator coin)")
        elif "creator is a known rugger" in lx: rej.append("launch: creator is a known rugger")
        elif "funded" in lx and "known rugger" in lx and "creator funded" in lx: rej.append("launch: creator funded by known rugger/funder")
    if not rej:
        if any("same-block bundle" in x or "share one funder" in x for x in rs): pen += 10; why.append("launch: same-block bundle / one funder -10")
        elif sc.get("verdict") == "caution": pen += 4; why.append("launch: caution -4")
        elif sc.get("verdict") == "block": pen += 8; why.append("launch: block-level flags -8")
    return sorted(set(rej)), pen, why

def guard(row, x, prev_rows=(), buyers5=None):
    """row: scan row (needs age_h, mcap, liq, features.m5); x: rc_extract() dict; prev_rows: earlier scanned rows
    for the same token (oldest first); buyers5: GeckoTerminal unique buyers in last 5 min.
    -> (rejects, penalty, reasons)"""
    rej, pen, why = [], 0, []
    age, mcap, liq = row.get("age_h") or 0, row.get("mcap") or 0, row.get("liq") or 0
    m5 = (row.get("features") or {}).get("m5") or 0
    if age < MIN_AGE_H: rej.append(f"too young ({age*60:.0f} min < {MIN_AGE_H*60:.0f})")
    hol = x.get("holders")
    if hol is None:
        rej.append("holder count unavailable")
    else:
        if hol < MIN_HOLDERS: rej.append(f"only {hol} holders")
        mph = mcap / max(hol, 1)
        if mph > MAX_MCAP_PER_HOLDER: rej.append(f"${mph:,.0f} mcap per holder (thin/fake crowd)")
        elif mph > WARN_MCAP_PER_HOLDER: pen += 10; why.append(f"${mph:,.0f} mcap/holder -10")
        if buyers5:
            wr = buyers5 / max(hol, 1)
            if wr >= WASH_RATIO: rej.append(f"wash trading: {buyers5:.0f} buyers/5m vs {hol} holders")
            elif wr >= WARN_WASH_RATIO: pen += 8; why.append(f"buyers/holders {wr:.2f} -8")
    if m5 <= M5_CRASH: rej.append(f"crashing: 5m {m5:+.0f}%")
    elif m5 >= M5_SPIKE: rej.append(f"extreme 5m spike {m5:+.0f}%")
    elif m5 <= -25: pen += 6; why.append(f"5m {m5:+.0f}% -6")
    for p in prev_rows:
        if p.get("liq") and liq <= (1 - LIQ_DROP) * p["liq"]:
            rej.append(f"liquidity fell {100*(1-liq/p['liq']):.0f}% since {str(p.get('ts'))[11:16]}Z"); break
    if x.get("danger"): rej.append("rugcheck danger: " + ", ".join(x["danger"][:3]))
    lpl = x.get("lp_locked")
    if lpl is not None and lpl < LP_LOCK_MIN: rej.append(f"LP only {lpl:.0f}% locked/burned")
    if x.get("creator_pct") is not None and x["creator_pct"] > CREATOR_MAX_PCT: rej.append(f"creator holds {x['creator_pct']:.0f}%")
    if (x.get("creator_tokens") or 0) >= 3: pen += 8; why.append(f"creator launched {x['creator_tokens']} other tokens -8")
    return rej, pen, why
