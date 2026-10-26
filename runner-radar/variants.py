#!/usr/bin/env python3
"""runner-radar variants: PAPER ONLY. Re-plays every coin the scanner evaluated (scanned.jsonl) under
several rule sets and grades them with grade.py's exact bet logic ($5, -25% stop, half at 2x, 2% fee/side,
candles strictly after the signal). Adds an 08:00 Europe/Dublin close (what the live wallet does).

Never touches scan.py, signals.jsonl or live/. Reads Pulse (/workspace/x-intel, /workspace/x-pulse) and
Scout (/workspace/onchain-intel) files only POINT-IN-TIME: a file version counts for a signal only if it
existed (snapshotted, mtime <= signal time) and per-entry timestamps, when present, are <= signal time.

  python3 variants.py                 # snapshot intel + grade all variants -> variants_latest.txt, variants.csv
  python3 variants.py --snapshot-only # cheap: just snapshot intel files / capture holders (run after every scan)
  python3 variants.py --no-fetch      # grade from cached candles only (no network)
"""
import argparse, csv, glob, hashlib, json, os, re, shutil, statistics, sys, time, datetime as dt
from zoneinfo import ZoneInfo
from common import BASE, get_json, f, read_jsonl, valid_sol, clean
from grade import simulate, CHECKS, HORIZON

DUB = ZoneInfo("Europe/Dublin")
SCANNED = os.path.join(BASE, "scanned.jsonl")
SNAPDIR = os.path.join(BASE, "intel_snapshots")
CANDLES = os.path.join(BASE, "candles_cache")
HOLDERS = os.path.join(BASE, "intel_snapshots", "holders.jsonl")

VARIANTS = [  # key, label, min score, extra rule
    ("A", "baseline: score >= 55 (live rules)", 55, None),
    ("B", "strict: score >= 65", 65, None),
    ("C", "loose: score >= 50", 50, None),
    ("D", "baseline + X buzz (Pulse): rising +5, skip fading/rugs", 55, "x"),
    ("E", "baseline + on-chain (Scout): skip avoid-list, +5/smart wallet (max +10)", 55, "onchain"),
]
BUZZ_BOOST, SMART_BOOST, SMART_MAX = 5.0, 5.0, 10.0
X_MAX_STALE_H, ONCHAIN_MAX_STALE_H = 2.0, 48.0
HOLDER_MAX_LAG_S = 15 * 60       # holder lists fetched >15 min after the signal are lookahead -> ignored

def ts_of(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()

def parse_ts(v):
    if v is None or v == "": return None
    if isinstance(v, (int, float)): return v / 1000 if v > 1e11 else float(v)
    try: return ts_of(v)
    except Exception:
        try: x = float(v); return x / 1000 if x > 1e11 else x
        except Exception: return None

def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(timespec="seconds")
def night_of(t):  # night label = Dublin date the evening started (08:00-11:59 counts as previous night)
    return (dt.datetime.fromtimestamp(t, DUB) - dt.timedelta(hours=12)).date().isoformat()
def next_close(t):  # first 08:00 Europe/Dublin strictly after t
    d = dt.datetime.fromtimestamp(t, DUB)
    c = d.replace(hour=8, minute=0, second=0, microsecond=0)
    if c <= d: c = (d + dt.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return c.timestamp()

# ---------------- intel snapshots (point-in-time) ----------------
def sources(a):
    return {"x_hot": os.path.join(a.x_intel, "hot.json"), "x_rugs": os.path.join(a.x_intel, "rugs.json"),
            "x_pulse": os.path.join(a.x_pulse, "latest.json"),
            "oc_smart": os.path.join(a.onchain, "smart_wallets.json"), "oc_avoid": os.path.join(a.onchain, "avoid.csv")}

def snapshot(a):
    """Copy each intel file into intel_snapshots/<name>/ whenever its content changes. valid_from = file mtime."""
    idx_path = os.path.join(SNAPDIR, "index.jsonl")
    idx = read_jsonl(idx_path)
    known = {(r["src"], r["sha"]) for r in idx}
    os.makedirs(SNAPDIR, exist_ok=True)
    for name, path in sources(a).items():
        if not os.path.isfile(path): continue
        data = open(path, "rb").read()
        sha = hashlib.sha256(data).hexdigest()[:16]
        if (name, sha) in known: continue
        mt = os.path.getmtime(path)
        d = os.path.join(SNAPDIR, name); os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, f"{int(mt)}_{sha}{os.path.splitext(path)[1]}")
        open(fn, "wb").write(data)
        with open(idx_path, "a") as fh:
            fh.write(json.dumps({"src": name, "sha": sha, "file": fn, "valid_from": mt, "captured": time.time()}) + "\n")

def snap_at(idx, name, t, max_stale_h):
    """Latest snapshot of `name` whose valid_from <= t and not older than max_stale_h."""
    c = [r for r in idx if r["src"] == name and r["valid_from"] <= t and t - r["valid_from"] <= max_stale_h * 3600]
    return max(c, key=lambda r: r["valid_from"]) if c else None

ADDR_KEYS = ("token", "ca", "mint", "address", "contract", "contract_address", "token_address", "tokenAddress", "_mint")
WAL_KEYS = ("wallet", "address", "owner", "account", "pubkey", "_mint")
TS_KEYS = ("ts", "first_seen", "seen_at", "flagged_at", "added", "added_at", "timestamp", "time", "detected_at",
           "created_at", "updated", "updated_at", "first_seen_at")
UP = re.compile(r"\b(ris\w*|up\w*|accel\w*|grow\w*|heat\w*|surg\w*|spik\w*|new)\b")
DOWN = re.compile(r"\b(fad\w*|down\w*|fall\w*|declin\w*|cool\w*|dead|dying|stale|drop\w*)\b")
RUG = re.compile(r"\b(rug\w*|scam|honeypot|shill\w*)\b")

def entries(obj, hint=""):
    """Flatten unknown JSON shapes into dicts with a `_hint` (parent key) and `_mint` when keyed by address."""
    out = []
    if isinstance(obj, list):
        for e in obj:
            if isinstance(e, dict): out.append({**e, "_hint": hint})
            elif isinstance(e, str) and valid_sol(e): out.append({"_mint": e, "_hint": hint})
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if valid_sol(k):
                out.append({**(v if isinstance(v, dict) else {"value": v}), "_mint": k, "_hint": hint})
            elif isinstance(v, (list, dict)):
                out += entries(v, (hint + " " + k).strip())
    return out

def first(e, keys):
    for k in keys:
        if isinstance(e.get(k), str) and valid_sol(e[k]): return e[k]
    return None

def entry_ts(e):
    for k in TS_KEYS:
        t = parse_ts(e.get(k))
        if t: return t
    return None

def buzz_of(e):
    txt = " ".join([e.get("_hint", "")] + [str(e.get(k, "")) for k in
                   ("trend", "direction", "buzz_trend", "status", "momentum", "state", "label", "flag", "verdict")]).lower()
    rug = bool(RUG.search(txt)) or any(bool(e.get(k)) for k in ("rug", "rugged", "is_rug", "scam"))
    if DOWN.search(txt): return "fading", rug
    if UP.search(txt): return "rising", rug
    for k in ("velocity", "delta", "change", "accel", "buzz_change", "slope", "growth", "mentions_change_pct", "trend_score"):
        v = e.get(k)
        if isinstance(v, (int, float)) and v != 0: return ("rising" if v > 0 else "fading"), rug
    return "unknown", rug

def load_json(path):
    try: return json.load(open(path))
    except Exception: return None

def x_view(idx, t):
    """What Pulse files said at time t: {mint: (buzz, rug)} plus set of rug mints. None if no usable file."""
    snaps = [s for s in (snap_at(idx, "x_hot", t, X_MAX_STALE_H), snap_at(idx, "x_pulse", t, X_MAX_STALE_H)) if s]
    rug_s = snap_at(idx, "x_rugs", t, 24 * 7)
    if not snaps and not rug_s: return None
    buzz, rugs = {}, set()
    for s in snaps:
        for e in entries(load_json(s["file"])):
            m = first(e, ADDR_KEYS); et = entry_ts(e)
            if not m or (et and et > t): continue
            b, r = buzz_of(e)
            if r: rugs.add(m)
            if b != "unknown" or m not in buzz: buzz[m] = b
    if rug_s:
        for e in entries(load_json(rug_s["file"]), "rugs"):
            m = first(e, ADDR_KEYS); et = entry_ts(e)
            if m and not (et and et > t): rugs.add(m)
    return {"buzz": buzz, "rugs": rugs, "files": [os.path.basename(s["file"]) for s in snaps + ([rug_s] if rug_s else [])]}

def oc_view(idx, t):
    sm, av = snap_at(idx, "oc_smart", t, ONCHAIN_MAX_STALE_H), snap_at(idx, "oc_avoid", t, ONCHAIN_MAX_STALE_H)
    if not sm and not av: return None
    smart, smart_buys, avoid_w, avoid_t = set(), {}, set(), set()
    if sm:
        for e in entries(load_json(sm["file"])):
            w = first(e, WAL_KEYS); et = entry_ts(e)
            if not w or (et and et > t): continue
            smart.add(w)
            for k in ("tokens", "buys", "recent_buys", "positions", "early_buys"):
                for b in entries(e.get(k)) if isinstance(e.get(k), (list, dict)) else []:
                    m, bt = first(b, ADDR_KEYS), entry_ts(b)
                    if m and bt and bt <= t: smart_buys.setdefault(m, set()).add(w)   # untimed buys = lookahead risk, ignored
    if av:
        try:
            for r in csv.DictReader(open(av["file"], newline="")):
                r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
                et = entry_ts(r)
                if et and et > t: continue
                w = next((r[k] for k in ("wallet", "address", "owner", "account") if valid_sol(r.get(k, ""))), None)
                m = next((r[k] for k in ("token", "mint", "ca") if valid_sol(r.get(k, ""))), None)
                if w: avoid_w.add(w)
                if m: avoid_t.add(m)
        except Exception: pass
    return {"smart": smart, "smart_buys": smart_buys, "avoid_w": avoid_w, "avoid_t": avoid_t}

def capture_holders(a, rows):
    """Right after a scan, record top holders + creator of fresh candidates (only once Scout's lists exist),
    so variant E can check them against the avoid/smart lists without later (lookahead) data."""
    src = sources(a)
    if a.no_fetch or not (os.path.isfile(src["oc_smart"]) or os.path.isfile(src["oc_avoid"])): return
    have = {r["token"] for r in read_jsonl(HOLDERS)}
    now = time.time()
    fresh = {}
    for r in rows:
        if not r["rejects"] and r["score"] >= 45 and now - ts_of(r["ts"]) <= 20 * 60 and r["token"] not in have:
            fresh.setdefault(r["token"], r)
    for m in list(fresh)[:15]:
        rep = get_json(f"https://api.rugcheck.xyz/v1/tokens/{m}/report")
        if not isinstance(rep, dict): continue
        hold = sorted({h.get("owner") for h in rep.get("topHolders") or [] if valid_sol(h.get("owner") or "")})
        with open(HOLDERS, "a") as fh:
            fh.write(json.dumps({"token": m, "fetched_at": time.time(), "creator": rep.get("creator"), "holders": hold}) + "\n")

# ---------------- candles ----------------
def candles(pool, t0, now, no_fetch):
    os.makedirs(CANDLES, exist_ok=True)
    fn = os.path.join(CANDLES, pool + ".json")
    c = load_json(fn) if os.path.exists(fn) else None
    end = t0 + HORIZON
    ok = c and c["first"] <= t0 + 300 and (c["last_ts"] >= end or now - c["fetched_at"] < 45 * 60)
    if not ok and not no_fetch:
        url = (f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute"
               f"?aggregate=5&limit=300&currency=usd&token=base")
        if now > end + 600: url += f"&before_timestamp={int(end + 600)}"   # anchor old windows (limit=300 ~ 25 h)
        r = get_json(url)
        try:
            rows = sorted((int(x[0]), f(x[1]), f(x[2]), f(x[3]), f(x[4])) for x in r["data"]["attributes"]["ohlcv_list"])
        except Exception:
            rows = None
        if rows:
            old = {x[0]: x for x in (c or {}).get("rows", [])}
            old.update({x[0]: tuple(x) for x in rows})
            allr = sorted(old.values())
            c = {"fetched_at": now, "first": min(allr[0][0], (c or {}).get("first", 1e18)), "last_ts": now if now < end else max(now, end),
                 "rows": allr}
            json.dump(c, open(fn, "w"))
    if not c: return None
    return [tuple(x) for x in c["rows"] if t0 <= x[0] <= end] or None   # only candles STARTING after the signal

def simulate_gap(entry, cs, bet, stop, tp, fee):
    """Pessimistic twin of grade.simulate: if a candle crashes through the stop, fill at that candle's
    close (or the stop, whichever is lower) instead of exactly -25%. Rugs then show their real damage."""
    units, cash, half = bet * (1 - fee) / entry, 0.0, False
    for _, o, h, l, c in cs:
        if l <= entry * (1 + stop):
            cash += units * min(entry * (1 + stop), c, o) * (1 - fee); return cash - bet
        if not half and h >= entry * tp:
            cash += units / 2 * entry * tp * (1 - fee); units /= 2; half = True
    return cash + units * cs[-1][4] * (1 - fee) - bet

def grade_one(s, a, now):
    t0, entry = ts_of(s["ts"]), s["price"]
    age = now - t0
    cs = candles(s["pair"], t0, now, a.no_fetch) if entry and s.get("pair") else None
    r = {"t0": t0, "age_h": age / 3600}
    if not cs:
        r["status"] = "pending" if age < 900 else "no candles"; return r
    for name, secs in CHECKS:
        w = [c for c in cs if c[0] <= t0 + secs]
        r[f"ret_{name}"] = w[-1][4] / entry - 1 if age >= secs and w else None
    r["max_ret"] = max(c[2] for c in cs) / entry - 1
    r["hit_2x"] = int(r["max_ret"] >= a.tp - 1)
    close = next_close(t0)
    cc = [c for c in cs if c[0] + 300 <= close] or cs[:1]          # candles fully before 08:00 Dublin
    matured = now >= close
    pnl, half, note = simulate(entry, cc, a.bet, a.stop, a.tp, a.fee, matured)
    r["pnl"], r["note"] = pnl, note.replace("@24h", "@08:00 close")
    r["pnl_gap"] = simulate_gap(entry, cc, a.bet, a.stop, a.tp, a.fee)
    r["status"] = "final" if matured and age >= HORIZON else "open"
    return r

# ---------------- variants ----------------
def pick(rows, key, min_score, kind, idx, holders):
    """First row per token that qualifies under this variant, using only data available at that row's time."""
    out, seen, covered, uncovered, notes = [], set(), 0, [], {}
    for r in sorted(rows, key=lambda r: r["ts"]):
        if r["rejects"] or r["token"] in seen: continue
        t, sc, why = ts_of(r["ts"]), r["score"], []
        if kind == "x":
            v = x_view(idx, t)
            if v is None:
                if sc >= min_score - BUZZ_BOOST: uncovered.append(night_of(t))
                continue
            if r["token"] in v["rugs"]:
                if sc >= min_score - BUZZ_BOOST: notes[r["token"]] = "skipped: on Pulse rug list"
                continue
            b = v["buzz"].get(r["token"], "none")
            if b == "fading":
                if sc >= min_score - BUZZ_BOOST: notes[r["token"]] = "skipped: buzz fading"
                continue
            if b == "rising": sc += BUZZ_BOOST; why.append(f"buzz rising +{BUZZ_BOOST:.0f}")
            else: why.append(f"buzz {b}")
        elif kind == "onchain":
            v = oc_view(idx, t)
            if v is None:
                if sc >= min_score - SMART_MAX: uncovered.append(night_of(t))
                continue
            h = holders.get(r["token"])
            if h and h["fetched_at"] - t > HOLDER_MAX_LAG_S: h = None
            hs = set(h["holders"]) | ({h["creator"]} if h and h.get("creator") else set()) if h else set()
            bad = (r["token"] in v["avoid_t"]) or bool(hs & v["avoid_w"])
            if bad:
                if sc >= min_score - SMART_MAX: notes[r["token"]] = "skipped: avoid-list token/creator/holder"
                continue
            n = len((hs & v["smart"]) | v["smart_buys"].get(r["token"], set()))
            if n: sc += min(SMART_MAX, SMART_BOOST * n); why.append(f"{n} smart wallet(s)")
            if not h: why.append("no holder snapshot")
        if sc < min_score: continue
        seen.add(r["token"]); covered += 1
        out.append((r, sc, ", ".join(why)))
    return out, uncovered, notes

def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None

def pct(x): return "n/a" if x is None else f"{x:+.0%}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bet", type=float, default=5.0); ap.add_argument("--stop", type=float, default=-0.25)
    ap.add_argument("--tp", type=float, default=2.0); ap.add_argument("--fee", type=float, default=0.02)
    ap.add_argument("--snapshot-only", action="store_true"); ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--x-intel", default="/workspace/x-intel"); ap.add_argument("--x-pulse", default="/workspace/x-pulse")
    ap.add_argument("--onchain", default="/workspace/onchain-intel")
    ap.add_argument("--out-dir", default=BASE, help="where variants_latest.txt / variants.csv go (testing)")
    a = ap.parse_args()
    global SNAPDIR, HOLDERS
    if a.out_dir != BASE:
        SNAPDIR = os.path.join(a.out_dir, "intel_snapshots"); HOLDERS = os.path.join(SNAPDIR, "holders.jsonl")
    rows = read_jsonl(SCANNED)
    snapshot(a)
    capture_holders(a, rows)
    if a.snapshot_only: return
    now = time.time()
    idx = read_jsonl(os.path.join(SNAPDIR, "index.jsonl"))
    holders = {}
    for h in read_jsonl(HOLDERS): holders.setdefault(h["token"], h)
    graded, lines, summary = {}, [], {}
    nights = sorted({night_of(ts_of(r["ts"])) for r in rows})
    for key, label, ms, kind in VARIANTS:
        picks, uncovered, notes = pick(rows, key, ms, kind, idx, holders)
        res = []
        for r, sc, why in picks:
            gk = (r["token"], r["ts"])
            if gk not in graded: graded[gk] = grade_one(r, a, now)
            res.append((r, sc, why, graded[gk]))
        waiting = kind is not None and not picks and (uncovered or not idx or not any(
            s["src"].startswith("x_" if kind == "x" else "oc_") for s in idx))
        summary[key] = (label, res, uncovered, notes, waiting)
    # ---- csv upsert: one row per (night, variant) ----
    cols = ["date", "variant", "signals", "wins", "losses", "hit_2x", "median_return", "sim_pnl",
            "status", "staked", "open_or_ungraded", "med_ret_1h", "med_ret_4h", "med_ret_24h", "uncovered", "sim_pnl_gapfill", "updated"]
    csvp = os.path.join(a.out_dir, "variants.csv")
    old = list(csv.DictReader(open(csvp))) if os.path.exists(csvp) else []
    new = {}
    for key, (label, res, unc, notes, waiting) in summary.items():
        for n in nights:
            rs = [x for x in res if night_of(ts_of(x[0]["ts"])) == n]
            g = [x[3] for x in rs if "pnl" in x[3]]
            un = sum(1 for x in rs if "pnl" not in x[3])
            if waiting and not rs:
                row = {"date": n, "variant": key, "status": "waiting for data"}
            else:
                row = {"date": n, "variant": key, "signals": len(rs), "wins": sum(x["pnl"] > 0 for x in g),
                       "losses": sum(x["pnl"] <= 0 for x in g), "hit_2x": sum(x["hit_2x"] for x in g),
                       "median_return": "" if not g else round(med([x["pnl"] / a.bet for x in g]), 3),
                       "sim_pnl": round(sum(x["pnl"] for x in g), 2),
                       "status": "final" if g and not un and all(x["status"] == "final" for x in g) else "provisional",
                       "staked": round(a.bet * len(g), 2),
                       "open_or_ungraded": sum(x["status"] != "final" for x in g) + un,
                       **{f"med_ret_{c}": ("" if med([x.get(f'ret_{c}') for x in g]) is None else round(med([x.get(f'ret_{c}') for x in g]), 3)) for c, _ in CHECKS},
                       "uncovered": unc.count(n) if kind_of(key) else "",
                       "sim_pnl_gapfill": round(sum(x["pnl_gap"] for x in g), 2)}
            row["updated"] = iso(now)
            new[(n, key)] = row
    keep = [r for r in old if (r["date"], r["variant"]) not in new]
    with open(csvp + ".tmp", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        w.writerows(sorted(keep + list(new.values()), key=lambda r: (r["date"], r["variant"])))
    os.replace(csvp + ".tmp", csvp)
    # ---- human summary ----
    L = [f"runner-radar paper variants @ {iso(now)}  (bet ${a.bet:.0f}, stop {a.stop:.0%}, half at {a.tp:.0f}x, "
         f"fee {a.fee:.0%}/side, exit 08:00 Dublin; PAPER ONLY)", ""]
    L.append(f"{'var':<3} {'signals':>7} {'graded':>6} {'W':>3} {'L':>3} {'2x':>3} {'med ret':>8} {'PnL $':>7} {'med 1h':>7} {'med 4h':>7} {'med 24h':>7} {'gapPnL':>7}  rule")
    for key, (label, res, unc, notes, waiting) in summary.items():
        g = [x[3] for x in res if "pnl" in x[3]]
        if waiting:
            L.append(f"{key:<3} {'waiting for data':>40}   {label}  (input files missing or not fresh at any signal time)"); continue
        L.append(f"{key:<3} {len(res):>7} {len(g):>6} {sum(x['pnl']>0 for x in g):>3} {sum(x['pnl']<=0 for x in g):>3} "
                 f"{sum(x['hit_2x'] for x in g):>3} {pct(med([x['pnl']/a.bet for x in g])):>8} {sum(x['pnl'] for x in g):>+7.2f} "
                 f"{pct(med([x.get('ret_1h') for x in g])):>7} {pct(med([x.get('ret_4h') for x in g])):>7} {pct(med([x.get('ret_24h') for x in g])):>7} {sum(x['pnl_gap'] for x in g):>+7.2f}  {label}"
                 + (f"  [{len(unc)} candidates before data existed, not counted]" if unc and kind_of(key) else ""))
    for key, (label, res, unc, notes, waiting) in summary.items():
        if waiting: continue
        L += ["", f"--- {key}: {label}"]
        for r, sc, why, g in res:
            dub = dt.datetime.fromtimestamp(ts_of(r["ts"]), DUB).strftime("%a %H:%M")
            if "pnl" in g:
                L.append(f"  {dub} {r['symbol']:<12} score {r['score']:5.1f}{'' if sc == r['score'] else f'->{sc:.1f}'}  max {g['max_ret']:+6.0%}  "
                         f"bet {g['pnl']:+6.2f} (gap {g['pnl_gap']:+5.2f})  {g['note']} [{g['status']}]" + (f"  ({why})" if why else "") + f"  {r['url']}")
            else:
                L.append(f"  {dub} {r['symbol']:<12} score {r['score']:5.1f}  {g['status']}  {r['url']}")
        for m, n in notes.items(): L.append(f"  {m[:8]}... {n}")
    L += ["", "PnL $ = grade.py logic (stop fills exactly at -25%). gapPnL = same trades but a stop that a candle crashes",
          "through fills at that candle's close/open (closer to what a real sell gets in a rug or 5-min dump).",
          "Notes: same approximations as grade.py (entry = scan price, stops fill exactly at -25%, stop assumed first if a",
          "candle hits both). Each variant takes a coin's FIRST qualifying scan. scan.py never re-scans a coin once it has",
          "signalled at >=55, so B can't see coins that later climbed to 65, and C/D/E only see rescans of coins below 55.",
          "D/E only use intel files snapshotted at or before each signal (intel_snapshots/); signals before the data existed",
          "are excluded. Treat any variant with < ~50 graded signals as noise."]
    out = "\n".join(L)
    open(os.path.join(a.out_dir, "variants_latest.txt"), "w").write(out + "\n")
    print(out)

def kind_of(key): return next(k for kk, _, _, k in VARIANTS if kk == key)

if __name__ == "__main__":
    main()
