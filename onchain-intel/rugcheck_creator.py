#!/usr/bin/env python3
"""Buy-time rug / dev-pattern flag for a pump.fun (or pumpswap-graduated) mint.   READ-ONLY, never signs.
usage: python3 rugcheck_creator.py <mint> [--fresh] [--no-funding]
prints one JSON object: {"verdict": "block"|"caution"|"ok"|"unknown", "score", "reasons", "evidence", ...}
Checks: (1) creator / launch-slot wallets already in known_ruggers.json (rugged before)
        (2) SOL funding of creator (2 hops) + top launch-slot buyers (1 hop) vs known ruggers/funders,
            and launch-slot buyers sharing ONE funder (bundle network)
        (3) same-block bundle: wallets & % supply bought in the create slot (+1), create-tx co-signers
        (4) full-curve dev buy (dev buys >80 SOL / >70% supply in the create tx)
        (5) fresh creator (first funded < 1h before launch)   (6) rugcheck.xyz summary as a cross-check
RPC: Helius if HELIUS_API_KEY / /home/box/.scout-secrets/helius.env exists (key never printed), else public RPC."""
import os, sys, json, time, re, urllib.request, concurrent.futures as cf, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "scripts"))
from sol import rpc, sigs, tx, deltas, HAVE_HELIUS
import funding
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
CACHE = os.path.join(HERE, "data", "rugcheck"); os.makedirs(CACHE, exist_ok=True)
K = json.load(open(os.path.join(HERE, "known_ruggers.json"))) if os.path.exists(os.path.join(HERE, "known_ruggers.json")) else {"wallets": {}, "funders": {}}
RUG, FUN = K["wallets"], K["funders"]
try:  # public-label-confirmed exchange/custodial hot wallets are neutral, never a rugger-funder link
    for _w in json.load(open(os.path.join(HERE, "custodial_ignore.json")))["wallets"]: FUN.pop(_w["address"], None)
except Exception: pass
# known ruggers also include avoid.csv dev/bundler rows
try:
    import csv
    for r in csv.DictReader(open(os.path.join(HERE, "avoid.csv"))):
        if r.get("address") and r.get("date_added") and r["address"] not in RUG and (r.get("type") or "").startswith("dev"):
            RUG[r["address"]] = {"role": "creator (avoid.csv)", "tokens": [{"mint": m} for m in (r.get("mints") or "").split()],
                                 "date_added": r["date_added"], "reason": r.get("reason")}
except Exception: pass

def rugcheck_api(mint):
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary",
                                   headers={"User-Agent": "onchain-intel/1.0"}), timeout=8)
        j = json.loads(r.read()); return {"score": j.get("score"), "score_normalised": j.get("score_normalised"),
                                          "risks": [x.get("name") for x in j.get("risks") or []]}
    except Exception as e:
        return {"error": type(e).__name__}

def _lookahead_safe(mint):
    """Drop known-rugger/funder evidence that only comes from this mint (no look-ahead in back-tests)."""
    rug = {a: v for a, v in RUG.items() if not v.get("tokens") or any(t.get("mint") != mint for t in v["tokens"])}
    fun = {}
    for a, v in FUN.items():
        rs = [r for r in v.get("ruggers", []) if r in rug]
        if rs: fun[a] = {**v, "n_ruggers_funded": len(rs)}
    return rug, fun

def check(mint, do_funding=True):
    RUG, FUN = _lookahead_safe(mint)
    t0 = time.time(); reasons, ev = [], {}; score = 0
    def flag(pts, why): nonlocal score; score += pts; reasons.append(why)
    import pda
    S = sigs(pda.bonding_curve(mint), limit_pages=40)      # short history, starts at the create tx
    # plus the mint's own recent history (catches same-slot AMM buys when the curve graduates in the create tx)
    seen = {s["signature"] for s in S}; S += [s for s in sigs(mint, limit_pages=40) if s["signature"] not in seen]
    if not S: return {"mint": mint, "verdict": "unknown", "reasons": ["no signatures from RPC"]}
    S.sort(key=lambda s: (s["slot"], s.get("transactionIndex", 0) or 0))
    first = tx(S[0]["signature"])
    logs = " ".join((first or {}).get("meta", {}).get("logMessages") or [])
    if not first or PUMP not in logs or not re.search(r"Instruction: Create(V2)?\b", logs):
        # old/busy coin: can't see launch slot on free RPC; fall back to rugcheck.xyz creator vs known lists
        out = {"mint": mint, "verdict": "unknown", "reasons": [f"create tx not reached ({len(S)} sigs scanned; launch-slot checks skipped)"],
               "rugcheck": rugcheck_api(mint)}
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report",
                           headers={"User-Agent": "onchain-intel/1.0"}), timeout=10).read())
            c = j.get("creator"); out["creator_rugcheck"] = c
            if c in RUG: out["verdict"] = "block"; out["reasons"].append(f"creator (per rugcheck.xyz) {c} is a known rugger")
            elif c and do_funding:
                for i, e in enumerate(funding.chain(c, 2)):
                    if e["from"] in RUG or (e["from"] in FUN and FUN[e["from"]]["n_ruggers_funded"] >= 2):
                        out["verdict"] = "block"; out["reasons"].append(f"creator funded (hop {i+1}) by known rugger/funder {e['from']}")
        except Exception as e: out["reasons"].append("rugcheck report unavailable: " + type(e).__name__)
        out["elapsed_s"] = round(time.time() - t0, 1); return out
    slot0, ts0 = S[0]["slot"], S[0]["blockTime"]
    sup = float((rpc("getTokenSupply", [mint]) or {}).get("value", {}).get("uiAmount") or 1e9)
    tok, sol, wsol, signers, _ = deltas(first, mint)
    creator = signers[0]; cosign = [s for s in signers[1:] if s != mint and tok.get(s, 0) > 0]
    dev_tokens = tok.get(creator, 0); dev_sol = -sol.get(creator, 0)
    ev["create_tx"] = "https://solscan.io/tx/" + S[0]["signature"]; ev["creator"] = creator
    ev["create_time_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts0))
    # same-block bundle
    buyers = collections.defaultdict(float); bsol = collections.defaultdict(float); n_tx = 0; signed = set()
    early = [s for s in S if s["err"] is None and s["slot"] <= slot0 + 1][:150]
    with cf.ThreadPoolExecutor(8) as ex: txs = list(ex.map(lambda s: tx(s["signature"]), early))
    for s, t in zip(early, txs):
        if not t: continue
        tk, so, ws, sg, _ = deltas(t, mint); n_tx += 1
        if s["slot"] != slot0 and not (set(sg) & set(signers)): continue   # slot0+1 only for create-tx co-signers
        signed |= set(sg)
        for o, d in tk.items(): buyers[o] += d
        for o in sg: bsol[o] += -(so.get(o, 0) + ws.get(o, 0))
    # net holdings after the launch slot, only wallets that signed (excludes curve/pool PDAs and plain transfer recipients)
    buyers = {o: v for o, v in buyers.items() if v > 0 and o in signed}
    # drop bonding-curve / pool accounts (they lose tokens, never gain), keep buyers
    pct = 100 * sum(buyers.values()) / sup
    ev.update(slot0_wallets=len(buyers), slot0_supply_pct=round(pct, 1), slot0_sol=round(sum(v for v in bsol.values() if v > 0), 2),
              create_tx_cosigners=len(cosign), dev_buy_sol=round(dev_sol, 3), dev_buy_supply_pct=round(100 * dev_tokens / sup, 1))
    if pct > 75: flag(3, f"same-block bundle: {len(buyers)} wallets bought {pct:.0f}% of supply in the create slot")
    elif pct > 40: flag(3, f"heavy create-slot buying: {pct:.0f}% of supply by {len(buyers)} wallets")
    elif pct > 25 or (pct > 15 and len(buyers) >= 5): flag(2, f"create-slot bundle: {len(buyers)} wallets, {pct:.0f}% supply")
    if len(cosign) >= 2: flag(1, f"create tx co-signed by {len(cosign)} buying wallets (multi-wallet bundle)")
    if dev_sol > 80 or dev_tokens > 0.7 * sup: flag(5, f"full-curve dev buy: creator bought {100*dev_tokens/sup:.0f}% for {dev_sol:.1f} SOL in create tx")
    elif dev_tokens > 0.2 * sup: flag(2, f"large dev buy {100*dev_tokens/sup:.0f}% of supply")
    # known ruggers
    if creator in RUG: flag(6, f"creator is a known rugger ({RUG[creator].get('role')}; {[x.get('sym') for x in RUG[creator].get('tokens', [])]})")
    kb = [b for b in buyers if b in RUG and b != creator]
    if kb: flag(4 if len(kb) >= 2 else 2, f"{len(kb)} create-slot wallets are known ruggers/bundlers"); ev["known_rugger_buyers"] = kb[:10]
    # funding
    if do_funding:
        chain = funding.chain(creator, 2); ev["creator_funding"] = chain
        for i, e in enumerate(chain):
            f = e["from"]
            if f in RUG: flag(5, f"creator funded (hop {i+1}) by known rugger {f}")
            if f in FUN:
                strong = FUN[f]["n_ruggers_funded"] >= 2
                flag(5 if strong else 2, f"creator funded (hop {i+1}) by {'known rugger funder' if strong else 'wallet that funded a rugger'} {f} ({FUN[f]['n_ruggers_funded']} ruggers)")
        if chain and chain[0].get("ts") and 0 <= ts0 - chain[0]["ts"] < 3600:
            flag(0 if (chain[0]["sol"] or 0) < 50 else 2, f"fresh creator: first funded {int((ts0-chain[0]['ts'])/60)} min before launch with {chain[0]['sol']} SOL")
        top = sorted(buyers, key=lambda b: -buyers[b])[:10]
        with cf.ThreadPoolExecutor(6) as ex: fr = dict(zip(top, ex.map(funding.funder, top)))
        cnt = collections.Counter(v["funder"] for v in fr.values() if v.get("funder"))
        shared = {f: n for f, n in cnt.items() if n >= 3}
        if shared: flag(0, f"{max(shared.values())} create-slot buyers share one funder {max(shared, key=shared.get)} (one operator)"); ev["shared_funders"] = shared
        hit = sorted({v["funder"] for v in fr.values() if v.get("funder") in RUG or (v.get("funder") in FUN and FUN[v["funder"]]["n_ruggers_funded"] >= 2)})
        weak = sorted({v["funder"] for v in fr.values() if v.get("funder") in FUN} - set(hit))
        if weak: flag(1, f"create-slot buyers funded by wallets that each funded 1 rugger (weak): {weak[:3]}")
        if hit: flag(3, f"create-slot buyers funded by known rugger/funder wallets: {hit[:3]}"); ev["buyer_funders_known"] = hit
    rc = rugcheck_api(mint); ev["rugcheck"] = rc
    # calibrated on 20 coins (2026-10-23): full-curve dev buy 4/5 dumped -> block; same-slot bundle alone 1/5 dumped
    # (CI) -> caution (bundlers exit 10-40 min after launch: small size, tight stop); known rugger/funder from ANOTHER coin -> block
    verdict = "block" if score >= 5 else "caution" if score >= 2 else "ok"
    return {"mint": mint, "verdict": verdict, "score": score, "reasons": reasons, "evidence": ev,
            "checked_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rpc": "helius" if HAVE_HELIUS else "public",
            "elapsed_s": round(time.time() - t0, 1), "known_ruggers_loaded": len(RUG), "known_funders_loaded": len(FUN)}

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a: print(__doc__); sys.exit(2)
    fn = os.path.join(CACHE, a[0] + ".json")
    if "--fresh" not in sys.argv and os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 600:
        print(open(fn).read()); sys.exit(0)
    r = check(a[0], "--no-funding" not in sys.argv)
    json.dump(r, open(fn, "w"), indent=1); print(json.dumps(r, indent=1))
