#!/usr/bin/env python3
"""runner-radar scan: PAPER ONLY. Finds young Solana memecoin pairs that look like
they're early in a run, scores momentum + health, logs candidates to signals.jsonl.
Runs once and exits; schedule every ~10 min. No wallets, no keys, no trading."""
import argparse, json, os, sys, time, datetime as dt
from common import BASE, get_json, clean, valid_sol, f, dex_tokens, read_jsonl
import rugguard

SIGNALS = os.path.join(BASE, "signals.jsonl")
SCANLOG = os.path.join(BASE, "scanned.jsonl")   # every evaluated pair (for later threshold tuning)

AGE_MIN_H, AGE_MAX_H = 0.25, 6.0
MCAP_MIN, MCAP_MAX = 50_000, 2_000_000
LIQ_MIN_FILTER, LIQ_HARD = 15_000, 10_000
TOP10_MAX = 35.0
QUOTES = {"So11111111111111111111111111111111111111112",
          "EPjFWN1bG3s5gjSn6Ftzz3vWwfoF2e8DMRp6A1Pz8YSd",  # USDC
          "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}  # USDT
# Known AMM vault authorities (pool-owned token accounts) to exclude from holder share
AMM_AUTH = {"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",   # Raydium AMM v4
            "GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL",   # Raydium CPMM
            "WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh"}    # Raydium LaunchLab

def log(*a):
    print(*a, file=sys.stderr)

# ---------- discovery ----------
def discover():
    found, src = {}, {}
    def add(addr, s):
        if valid_sol(addr) and addr not in QUOTES:
            found.setdefault(addr, set()).add(s); src[s] = src.get(s, 0) + 1
    for path, s in [("token-profiles/latest/v1", "ds_profiles"),
                    ("token-boosts/latest/v1", "ds_boosts"),
                    ("token-boosts/top/v1", "ds_boosts_top"),
                    ("community-takeovers/latest/v1", "ds_cto")]:
        r = get_json("https://api.dexscreener.com/" + path)
        for t in r or []:
            if isinstance(t, dict) and t.get("chainId") == "solana":
                add(t.get("tokenAddress"), s)
    for q in ("pumpswap", "pump", "raydium", "meteora", "SOL"):
        r = get_json("https://api.dexscreener.com/latest/dex/search?q=" + q)
        for p in (r or {}).get("pairs") or []:
            if p.get("chainId") == "solana":
                add((p.get("baseToken") or {}).get("address"), "ds_search")
    gecko_pools = {}
    for dur in ("5m", "1h", "6h"):
        for page in (1, 2):
            r = get_json(f"https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?duration={dur}&page={page}")
            for p in (r or {}).get("data") or []:
                base = ((p.get("relationships") or {}).get("base_token") or {}).get("data", {}).get("id", "")
                addr = base.split("solana_", 1)[-1]
                add(addr, f"gt_trend_{dur}")
                gecko_pools[p.get("attributes", {}).get("address")] = p.get("attributes", {})
    return found, src, gecko_pools

def best_pairs(tokens):
    pairs = dex_tokens("solana", tokens)
    best = {}
    for p in pairs:
        if p.get("chainId") != "solana":
            continue
        a = (p.get("baseToken") or {}).get("address")
        if a not in tokens:
            continue
        liq = f((p.get("liquidity") or {}).get("usd"))
        if a not in best or liq > f((best[a].get("liquidity") or {}).get("usd")):
            best[a] = p
    return best

def gecko_multi(pool_addrs, cache):
    need = [a for a in pool_addrs if a and a not in cache]
    for i in range(0, len(need), 30):
        r = get_json("https://api.geckoterminal.com/api/v2/networks/solana/pools/multi/" + ",".join(need[i:i+30]))
        for p in (r or {}).get("data") or []:
            at = p.get("attributes") or {}
            cache[at.get("address")] = at
    return cache

# ---------- health ----------
def rug_report(mint):
    r = get_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report")
    return r if isinstance(r, dict) and r.get("mint") else None

def rpc_authorities(mint):
    r = get_json("https://api.mainnet-beta.solana.com", {"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                 "params": [mint, {"encoding": "jsonParsed"}]})
    try:
        info = r["result"]["value"]["data"]["parsed"]["info"]
        return info.get("mintAuthority"), info.get("freezeAuthority"), True
    except Exception:
        return None, None, False

def rpc_top10(mint, pool_owners):
    """Public RPC getTokenLargestAccounts is often 429-limited; best-effort fallback."""
    r = get_json("https://api.mainnet-beta.solana.com", {"jsonrpc": "2.0", "id": 1,
                 "method": "getTokenLargestAccounts", "params": [mint]}, retries=1)
    s = get_json("https://api.mainnet-beta.solana.com", {"jsonrpc": "2.0", "id": 1,
                 "method": "getTokenSupply", "params": [mint]}, retries=1)
    try:
        accts = r["result"]["value"]; sup = f(s["result"]["value"]["uiAmount"])
    except Exception:
        return None
    # owners not returned here; can only drop accounts that are themselves pool vaults -> assume largest is pool
    vals = sorted((f(a.get("uiAmount")) for a in accts), reverse=True)[1:11]
    return 100 * sum(vals) / sup if sup else None

def health(mint, pair):
    pool_keys = {pair.get("pairAddress")}
    rep = rug_report(mint)
    h = {"src": None, "mint_auth": None, "freeze_auth": None, "top10": None, "rugged": False, "lp_locked": None}
    if rep:
        h["src"] = "rugcheck"
        h["mint_auth"], h["freeze_auth"] = rep.get("mintAuthority"), rep.get("freezeAuthority")
        h["rugged"] = bool(rep.get("rugged"))
        for m in rep.get("markets") or []:
            pool_keys |= {m.get("pubkey"), m.get("liquidityA"), m.get("liquidityB"),
                          (m.get("liquidityAAccount") or {}).get("owner"), (m.get("liquidityBAccount") or {}).get("owner")}
            if m.get("pubkey") == pair.get("pairAddress"):
                h["lp_locked"] = (m.get("lp") or {}).get("lpLockedPct")
        known = rep.get("knownAccounts") or {}
        hold = []
        for t in rep.get("topHolders") or []:
            own, addr = t.get("owner"), t.get("address")
            ktype = ((known.get(own) or known.get(addr) or {}).get("type") or "").upper()
            if own in pool_keys or addr in pool_keys or own in AMM_AUTH or ktype == "AMM":
                continue
            hold.append(f(t.get("pct")))
        if rep.get("topHolders") is not None:
            h["top10"] = round(sum(sorted(hold, reverse=True)[:10]), 2)
        h["insiders"] = bool(rep.get("graphInsidersDetected"))
        h["rc"] = rugguard.rc_extract(rep, pair.get("pairAddress"))
        return h
    ma, fa, ok = rpc_authorities(mint)
    if ok:
        h.update(src="rpc", mint_auth=ma, freeze_auth=fa)
        h["top10"] = rpc_top10(mint, pool_keys)
    return h

# ---------- scoring ----------
def ramp(x, lo, hi, pts):
    if x <= lo: return 0.0
    if x >= hi: return float(pts)
    return pts * (x - lo) / (hi - lo)

def score(p, gk, h, age_h, copycats=0):
    pc, vol, tx = p.get("priceChange") or {}, p.get("volume") or {}, p.get("txns") or {}
    m5, h1 = f(pc.get("m5")), f(pc.get("h1"))
    v5, vh1 = f(vol.get("m5")), f(vol.get("h1"))
    b5, s5 = f((tx.get("m5") or {}).get("buys")), f((tx.get("m5") or {}).get("sells"))
    b1, s1 = f((tx.get("h1") or {}).get("buys")), f((tx.get("h1") or {}).get("sells"))
    liq, mcap = f((p.get("liquidity") or {}).get("usd")), f(p.get("marketCap") or p.get("fdv"))
    reasons, rejects, s = [], [], 0.0

    # hard rejects
    if not h.get("src"): rejects.append("health data unavailable (can't verify authorities)")
    if h.get("rugged"): rejects.append("rugcheck: rugged")
    if h.get("mint_auth"): rejects.append("mint authority active")
    if h.get("freeze_auth"): rejects.append("freeze authority active")
    if h.get("top10") is not None and h["top10"] > TOP10_MAX: rejects.append(f"top10 {h['top10']:.0f}% > {TOP10_MAX:.0f}%")
    if liq < LIQ_HARD: rejects.append(f"liquidity ${liq:,.0f} < $10k")
    if (s1 > 1.5 * max(b1, 1) and s1 > 30) or (s5 > 2 * max(b5, 1) and s5 > 10): rejects.append("sells >> buys")

    # momentum (max ~60)
    accel = v5 / (vh1 / 12) if vh1 > 0 else 0
    a = ramp(accel, 1.0, 3.0, 18); s += a
    if a > 0: reasons.append(f"vol accel {accel:.1f}x")
    m = ramp(m5, 2, 20, 12)
    if m5 > 60: m -= 10; reasons.append(f"chase risk m5 +{m5:.0f}%")
    s += m
    if m5 > 2: reasons.append(f"5m +{m5:.0f}%")
    s += ramp(h1, 0, 150, 8)
    if h1 > 0: reasons.append(f"1h +{h1:.0f}%")
    br5 = b5 / (b5 + s5) if b5 + s5 else 0
    br1 = b1 / (b1 + s1) if b1 + s1 else 0
    s += ramp(br5, 0.5, 0.7, 6) + ramp(br1, 0.5, 0.65, 4)
    if br5 > 0.55: reasons.append(f"5m buys {br5:.0%}")
    # buyer growth (GeckoTerminal unique buyers): 5m buyers vs avg 5m over last 1h
    tr = (gk or {}).get("transactions") or {}
    by5, by1 = f((tr.get("m5") or {}).get("buyers")), f((tr.get("h1") or {}).get("buyers"))
    bg = by5 / (by1 / 12) if by1 > 0 else 0
    g = ramp(bg, 1.0, 2.5, 12); s += g
    if gk and g > 0: reasons.append(f"buyer growth {bg:.1f}x ({by5:.0f} buyers/5m)")

    # health (max ~40)
    lr = liq / mcap if mcap else 0
    s += ramp(lr, 0.05, 0.2, 10); reasons.append(f"liq/mcap {lr:.2f}")
    if h.get("src") and not h.get("mint_auth") and not h.get("freeze_auth"):
        s += 8; reasons.append("mint+freeze revoked")
    t10 = h.get("top10")
    if t10 is not None:
        s += 12 if t10 < 15 else 8 if t10 < 22 else 4 if t10 < 30 else 0
        reasons.append(f"top10 {t10:.0f}% (ex-pool)")
    else:
        reasons.append("top10 unknown")
    if h.get("insiders"): s -= 5; reasons.append("insider network flagged")
    s += 5 if 0.5 <= age_h <= 3 else 2
    if copycats >= 2:
        s -= 8; reasons.append(f"copycat: {copycats+1} live tokens share this ticker")
    return round(max(0, min(100, s)), 1), reasons, rejects, {"accel": round(accel, 2), "buyer_growth": round(bg, 2),
            "buy_ratio_5m": round(br5, 2), "m5": m5, "h1": h1, "liq_mcap": round(lr, 3)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=55)
    ap.add_argument("--max-health", type=int, default=25, help="max health lookups per run")
    ap.add_argument("--max-launch", type=int, default=4, help="max Scout launch-forensics checks per run")
    ap.add_argument("--dry-run", action="store_true", help="evaluate and print, but write nothing")
    args = ap.parse_args()
    t0 = time.time(); now_ms = t0 * 1000
    seen = {r["token"] for r in read_jsonl(SIGNALS)}
    found, src, gcache = discover()
    log(f"discovered {len(found)} solana tokens  sources={src}")
    best = best_pairs(list(found))
    pre = []
    for a, p in best.items():
        age_h = (now_ms - f(p.get("pairCreatedAt"), now_ms)) / 3.6e6
        mcap, liq = f(p.get("marketCap") or p.get("fdv")), f((p.get("liquidity") or {}).get("usd"))
        if AGE_MIN_H <= age_h <= AGE_MAX_H and MCAP_MIN <= mcap <= MCAP_MAX and liq >= LIQ_MIN_FILTER:
            pre.append((a, p, age_h))
    log(f"{len(best)} with pairs -> {len(pre)} pass age/mcap/liq prefilter")
    # cheap momentum pre-rank so the health budget goes to the most interesting
    pre.sort(key=lambda x: -(f((x[1].get("volume") or {}).get("m5")) / max(f((x[1].get("volume") or {}).get("h1")) / 12, 1)))
    pre = [x for x in pre if x[0] not in seen][:args.max_health]
    symcount = {}
    for p in best.values():
        k = clean((p.get("baseToken") or {}).get("symbol"), 16).upper()
        symcount[k] = symcount.get(k, 0) + 1
    gecko_multi([p.get("pairAddress") for _, p, _ in pre], gcache)
    new, evaluated, launch_checks = 0, [], 0
    prev = {}
    for r0 in read_jsonl(SCANLOG):
        prev.setdefault(r0.get("token"), []).append(r0)
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for a, p, age_h in pre:
        h = health(a, p)
        sc, reasons, rejects, feats = score(p, gcache.get(p.get("pairAddress")), h, age_h,
                                         symcount.get(clean((p.get("baseToken") or {}).get("symbol"), 16).upper(), 1) - 1)
        row = {"ts": ts, "token": a, "pair": p.get("pairAddress"), "dex": clean(p.get("dexId"), 20),
               "symbol": clean((p.get("baseToken") or {}).get("symbol"), 16),
               "name": clean((p.get("baseToken") or {}).get("name")),
               "price": f(p.get("priceUsd")), "mcap": f(p.get("marketCap") or p.get("fdv")),
               "liq": f((p.get("liquidity") or {}).get("usd")), "age_h": round(age_h, 2),
               "score": sc, "features": feats, "top10": h.get("top10"), "health_src": h.get("src"),
               "sources": sorted(found.get(a, [])), "reasons": reasons, "rejects": rejects,
               "url": f"https://dexscreener.com/solana/{p.get('pairAddress')}"}
        # ---- rug guards (rugguard.py) ----
        tnow = dt.datetime.fromisoformat(ts)
        recent = [q for q in prev.get(a, []) if 0 < (tnow - dt.datetime.fromisoformat(q["ts"])).total_seconds() <= 5400]
        gk = gcache.get(p.get("pairAddress")) or {}
        by5 = f((((gk.get("transactions") or {}).get("m5")) or {}).get("buyers")) or None
        x = h.get("rc") or {}
        grej, gpen, gwhy = rugguard.guard(row, x, recent, by5)
        rejects += grej; reasons += gwhy
        row["score"] = sc = round(max(0, sc - gpen), 1)
        if not rejects and sc >= args.threshold and launch_checks < args.max_launch:
            launch_checks += 1
            lrej, lpen, lwhy = rugguard.scout_verdict(rugguard.scout_check(a))
            rejects += lrej; reasons += lwhy
            row["score"] = sc = round(max(0, sc - lpen), 1)
        elif not rejects and sc >= args.threshold:
            rejects.append("launch check budget used up this run (re-checked next scan)")
        evaluated.append(row)
        extra = {"holders": x.get("holders"), "buyers5": by5, "lp_locked": x.get("lp_locked"),
                 "danger": x.get("danger"), "creator": x.get("creator"), "creator_pct": x.get("creator_pct"),
                 "quote_usd": x.get("quote_usd"), "guard_penalty": gpen}
        if not args.dry_run:
            with open(SCANLOG, "a") as fh: fh.write(json.dumps({**row, "guard": extra}) + "\n")
        if not rejects and sc >= args.threshold:
            if not args.dry_run:
                with open(SIGNALS, "a") as fh: fh.write(json.dumps(row) + "\n")
            new += 1
    evaluated.sort(key=lambda r: -r["score"])
    for r in evaluated:
        tag = "SIGNAL" if (not r["rejects"] and r["score"] >= args.threshold) else ("REJECT" if r["rejects"] else "  low ")
        print(f"{tag} {r['score']:5.1f} {r['symbol']:<12} mcap ${r['mcap']:>10,.0f} liq ${r['liq']:>8,.0f} age {r['age_h']:.1f}h  "
              f"{'; '.join(r['rejects']) or ', '.join(r['reasons'])}\n        {r['url']}")
    print(f"\n{ts}: {'DRY RUN (nothing written) ' if args.dry_run else ''}evaluated {len(evaluated)}, new signals {new}, total signals {len(seen)+new}, {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
