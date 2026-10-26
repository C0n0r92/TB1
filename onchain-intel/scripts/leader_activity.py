#!/usr/bin/env python3
"""Leader activity feed for Copycat (read-only; FREE public RPC only, 0 Helius credits; never signs anything).

Writes /workspace/onchain-intel/leader-activity.json with, per tracked leader:
  handle, wallets, last_swap_utc, swaps_1h, swaps_6h, minutes_idle, sources, notes.

Leaders = selfcopy/roster.json (active) + onchain-intel/data/leader_mappings.json + winners/wallets.csv.
Only handles with an evidenced wallet are tracked; leaderboard handles without a wallet are listed in "unmapped".

Swap detection (per signature, via getTransaction, cached by signature in data/leader_activity_cache.json):
  succeeded tx AND the wallet signed it (or it is the fee payer) AND a non-quote token balance owned by the
  wallet changed AND the wallet's quote balance (SOL lamports incl. wSOL, USDC, USDT) moved the opposite way.
  Unsigned incoming transfers (airdrop/dust spam) are therefore never counted.
Cost per hourly run: 1-3 getSignaturesForAddress per wallet + getTransaction only for NEW signatures.
"""
import json, os, sys, time, re, csv, urllib.request, datetime

BASE = "/workspace/onchain-intel"
OUT = os.path.join(BASE, "leader-activity.json")
CACHE_FN = os.path.join(BASE, "data", "leader_activity_cache.json")
RPCS = ["https://solana-rpc.publicnode.com", "https://api.mainnet-beta.solana.com"]   # public only, no keys
QUOTE = {"So11111111111111111111111111111111111111112", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
         "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}
LOOKBACK_MAX_TX = int(os.environ.get("LA_MAX_TX", "60"))   # max NEW getTransaction per wallet per run
UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 leader-activity"}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def rpc(method, params, tries=6):
    for a in range(tries):
        url = RPCS[a % len(RPCS)]
        try:
            req = urllib.request.Request(url, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), UA)
            r = json.load(urllib.request.urlopen(req, timeout=30))
            if "error" in r:
                if a < tries - 1: time.sleep(1.5 * (a + 1)); continue
                return None
            return r.get("result")
        except Exception:
            time.sleep(1.5 * (a + 1))
    return None

def leaders():
    L = {}
    def add(handle, w, src, conf=None):
        if not w or not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", w): return
        e = L.setdefault(handle, {"handle": handle, "wallets": [], "sources": [], "confidence": conf})
        if w not in e["wallets"]: e["wallets"].append(w)
        if src not in e["sources"]: e["sources"].append(src)
        if conf and not e.get("confidence"): e["confidence"] = conf
    try:
        for x in json.load(open("/workspace/selfcopy/roster.json")).get("leaders", []):
            if x.get("active", True): add(x["label"], x.get("wallet"), "selfcopy/roster.json", x.get("confidence"))
    except Exception as ex: print("roster read failed:", ex, file=sys.stderr)
    try:
        for h, v in json.load(open(os.path.join(BASE, "data", "leader_mappings.json"))).items():
            if not h.startswith("_") and isinstance(v, dict):
                add(h, v.get("wallet"), "leader_mappings.json", v.get("confidence"))
                if h in L and v.get("status"): L[h]["status"] = v["status"]
    except Exception as ex: print("mappings read failed:", ex, file=sys.stderr)
    try:
        for r in csv.DictReader(open(os.path.join(BASE, "winners", "wallets.csv"))):
            h = re.split(r"[ (]", (r.get("label") or "").strip())[0] or r["address"][:8]
            add(h, r["address"], "winners/wallets.csv", r.get("confidence"))
    except Exception as ex: print("winners read failed:", ex, file=sys.stderr)
    return L

def copies_now():
    """Active copyfomo copies per Copycat's own logs (untrusted text, used only as a tag):
    handles in the latest settings-backup / backup-after-edit group of copyfomo/skips-log.csv,
    minus any handle with a later 'stop copying' entry in copyfomo/x-watch-log.md."""
    fn = "/workspace/copyfomo/skips-log.csv"
    if not os.path.exists(fn): return set(), None
    groups = {}
    for row in csv.reader(open(fn)):
        if len(row) < 3 or not any(f in ("settings-backup", "backup-after-edit") for f in row[1:3]): continue
        h = row[2] if row[1] in ("settings-backup",) else row[1]
        groups.setdefault(row[0], set()).add(h.strip())
    if not groups: return set(), None
    ts = max(groups); act = set(groups[ts])
    wl = "/workspace/copyfomo/x-watch-log.md"
    if os.path.exists(wl):
        for l in open(wl):
            m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\dZ)", l)
            if m and m.group(1) > ts and "stop copying" in l:
                for h in list(act):
                    if h in l: act.discard(h)
    return act, ts

def unmapped(mapped):
    hs = set()
    fn = "/workspace/copyfomo/leaderboard-2026-10-23.md"
    if os.path.exists(fn):
        for l in open(fn):
            m = re.match(r"\|\s*\d+\s*\|\s*([^|\s]+)\s*\|", l)
            if m: hs.add(m.group(1))
    return sorted(h for h in hs if h not in mapped)

def classify(tx, w):
    if not tx or tx.get("meta") is None or tx["meta"].get("err") is not None: return False
    msg = tx["transaction"]["message"]; keys = msg["accountKeys"]
    pk = [k["pubkey"] if isinstance(k, dict) else k for k in keys]
    signed = any((k.get("pubkey") == w and k.get("signer")) for k in keys if isinstance(k, dict)) or (pk and pk[0] == w)
    if not signed: return False
    meta = tx["meta"]
    def bal(lst):
        d = {}
        for b in lst or []:
            if b.get("owner") == w:
                d[b["mint"]] = d.get(b["mint"], 0) + float(b["uiTokenAmount"].get("uiAmountString") or 0)
        return d
    pre, post = bal(meta.get("preTokenBalances")), bal(meta.get("postTokenBalances"))
    dtok = {m: post.get(m, 0) - pre.get(m, 0) for m in set(pre) | set(post)}
    i = pk.index(w) if w in pk else None
    dsol = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9 if i is not None else 0
    dsol += dtok.get("So11111111111111111111111111111111111111112", 0)  # wSOL counts as SOL
    dq = dsol + sum(v for m, v in dtok.items() if m in QUOTE and not m.startswith("So111"))
    nonq = [v for m, v in dtok.items() if m not in QUOTE and abs(v) > 0]
    if not nonq: return False
    # buy: token up & quote down ; sell: token down & quote up (fee-only moves of <0.0001 SOL ignored)
    return any((v > 0 and dq < -1e-4) or (v < 0 and dq > 1e-4) for v in nonq)

def sync_active_hours(byh):
    """write active_hours into data/leader_mappings.json (per handle) and winners/wallets.csv columns (atomic)."""
    fn = os.path.join(BASE, "data", "leader_mappings.json")
    try:
        M = json.load(open(fn)); ch = False
        for h, v in M.items():
            if isinstance(v, dict) and h in byh and "active_hours" in byh[h]:
                ah = dict(byh[h]["active_hours"]); ah.pop("hour_hist_utc", None); v["active_hours"] = ah; ch = True
        if ch:
            tmp = fn + ".tmp"; json.dump(M, open(tmp, "w"), indent=1); os.replace(tmp, fn)
    except Exception as ex: print("mappings active-hours write failed:", ex, file=sys.stderr)
    cfn = os.path.join(BASE, "winners", "wallets.csv")
    try:
        rows = list(csv.DictReader(open(cfn))); flds = list(rows[0].keys()) if rows else []
        add = ["active_tag", "day_share_07_20", "night_share_20_07", "peak_hours_utc", "active_n_swaps", "active_window_utc"]
        flds += [f for f in add if f not in flds]
        bw = {}
        for h, r in byh.items():
            for w in r["wallets"]: bw[w] = r.get("active_hours")
        for r in rows:
            p = bw.get(r["address"])
            if p:
                r.update({"active_tag": p["tag"], "day_share_07_20": p["day_share_07_20"], "night_share_20_07": p["night_share_20_07"],
                          "peak_hours_utc": " ".join(map(str, p["peak_hours_utc"])), "active_n_swaps": p["n_swaps"], "active_window_utc": p["window_utc"]})
        tmp = cfn + ".tmp"
        with open(tmp, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=flds); wr.writeheader(); wr.writerows(rows)
        os.replace(tmp, cfn)
    except Exception as ex: print("wallets.csv active-hours write failed:", ex, file=sys.stderr)

def main():
    now = time.time()
    try: cache = json.load(open(CACHE_FN))
    except Exception: cache = {}
    L = leaders(); out = []; n_sig_calls = n_tx_calls = 0
    for h, e in sorted(L.items()):
        rec = {"handle": h, "wallets": e["wallets"], "sources": e["sources"], "mapping_confidence": e.get("confidence"), "mapping_status": e.get("status"),
               "last_swap_utc": None, "swaps_1h": 0, "swaps_6h": 0, "minutes_idle": None, "idle_over_60m": None, "notes": []}
        last = None
        for w in e["wallets"]:
            sigs = rpc("getSignaturesForAddress", [w, {"limit": 200}]); n_sig_calls += 1
            if sigs is None: rec["notes"].append(f"{w[:6]}: getSignaturesForAddress failed"); continue
            newtx = 0; wlast = None; back = None
            for s in sigs:
                sig, bt = s["signature"], s.get("blockTime") or 0
                if s.get("err") is not None: continue
                if bt < now - 6 * 3600 and wlast: break          # past the 6h window and last swap known
                if sig not in cache:
                    if newtx >= LOOKBACK_MAX_TX:
                        rec["notes"].append(f"{w[:6]}: tx-check cap {LOOKBACK_MAX_TX} hit; counts may be low"); break
                    tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}])
                    n_tx_calls += 1; newtx += 1
                    if tx is None: continue          # not cached -> retried next run
                    cache[sig] = {"w": w, "t": bt, "swap": classify(tx, w)}
                back = bt
                if cache[sig]["swap"]:
                    wlast = max(wlast or 0, bt)
                    if bt >= now - 3600: rec["swaps_1h"] += 1
                    if bt >= now - 6 * 3600: rec["swaps_6h"] += 1
            if wlast and (not last or wlast > last): last = wlast
            if sigs and len(sigs) == 200 and (sigs[-1].get("blockTime") or 0) > now - 6 * 3600:
                rec["notes"].append(f"{w[:6]}: >200 sigs in 6h; swaps_6h is a lower bound")
            if not wlast and back:
                rec["notes"].append(f"{w[:6]}: no swap in signatures checked back to {datetime.datetime.fromtimestamp(back, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}")
                lb = round((now - back) / 60, 1)
                rec["minutes_idle_at_least"] = max(rec.get("minutes_idle_at_least") or 0, lb)
        if last:
            rec["last_swap_utc"] = datetime.datetime.fromtimestamp(last, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            rec["minutes_idle"] = round((now - last) / 60, 1); rec["idle_over_60m"] = rec["minutes_idle"] > 60
            rec.pop("minutes_idle_at_least", None)
        elif rec.get("minutes_idle_at_least") is not None:
            rec["idle_over_60m"] = rec["minutes_idle_at_least"] > 60
        out.append(rec)
    # prune cache to 7 days
    cache = {k: v for k, v in cache.items() if v.get("t", 0) > now - 15 * 86400}   # 15d so active-hours profile has 14d
    tmp = CACHE_FN + ".tmp"; json.dump(cache, open(tmp, "w")); os.replace(tmp, CACHE_FN)
    # active-hours profile (0 credits): cache + on-disk Helius pages; then mirror into mappings + winners csv
    try:
        import active_hours as AH
        for r in out:
            r["active_hours"] = AH.profile(r["wallets"], cache, now)
        sync_active_hours({r["handle"]: r for r in out})
    except Exception as ex: print("active-hours failed:", ex, file=sys.stderr)
    act, when = copies_now()
    for r in out: r["in_copyfomo_copies_per_log"] = r["handle"] in act
    doc = {"generated_utc": datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "method": "public RPC getSignaturesForAddress + getTransaction (new sigs only, cached); swap = wallet-signed tx where a non-quote token owned by the wallet and its SOL/USDC/USDT move in opposite directions. 0 Helius credits.",
           "copies_source": f"copyfomo/skips-log.csv settings backups at {when}, minus later 'stop copying' in x-watch-log.md: {sorted(act)}" if when else None,
           "rpc_calls": {"getSignaturesForAddress": n_sig_calls, "getTransaction": n_tx_calls, "helius_credits": 0},
           "leaders": sorted(out, key=lambda r: -(r["minutes_idle"] or r.get("minutes_idle_at_least") or 0)),
           "unmapped_handles": unmapped(set(L))}
    tmp = OUT + ".tmp"; json.dump(doc, open(tmp, "w"), indent=1); os.replace(tmp, OUT)
    for r in doc["leaders"]:
        print(f"{r['handle']:16} {'COPY ' if r['in_copyfomo_copies_per_log'] else '     '}idle={r['minutes_idle'] if r['minutes_idle'] is not None else ('>=%s' % r.get('minutes_idle_at_least'))} 1h={r['swaps_1h']} 6h={r['swaps_6h']} last={r['last_swap_utc']} hours={(r.get('active_hours') or {}).get('tag')}/{(r.get('active_hours') or {}).get('day_share_07_20')}d n={(r.get('active_hours') or {}).get('n_swaps')} {'; '.join(r['notes'])}")
    print("calls", doc["rpc_calls"], "unmapped", len(doc["unmapped_handles"]))

if __name__ == "__main__":
    main()
