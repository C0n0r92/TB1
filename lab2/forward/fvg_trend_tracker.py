#!/usr/bin/env python3
"""Forward PAPER tracker: maj_1h FVG retest, trend filter on, regime gate 'trending'. NO trading, NO keys.
Idempotent: every run (1) appends newly CLOSED 1h bars from data-api.binance.vision to forward/cache,
(2) recomputes the whole forward simulation deterministically from the frozen rules + start_time,
(3) appends to fvg_trend.jsonl only records whose id is not already there, (4) rewrites summary.md.
Run hourly (cron minute 5) under flock."""
import csv, hashlib, json, os, sys, time, urllib.request, datetime as dt
sys.dont_write_bytecode = True
F = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(F, "frozen"))
import numpy as np, pandas as pd
import smc, regime                                   # frozen copies (hash-checked below)

CFG = json.load(open(os.path.join(F, "fvg_trend_config.json")))
CACHE, JL, SUM = os.path.join(F, "cache"), os.path.join(F, "fvg_trend.jsonl"), os.path.join(F, "summary.md")
BASE, HR = "https://data-api.binance.vision/api/v3/klines", 3_600_000

def log(*a): print(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), *a, flush=True)

def check_frozen():
    c = {k: v for k, v in CFG.items() if k not in ("config_sha256", "hash_note")}
    h = hashlib.sha256(json.dumps(c, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if h != CFG["config_sha256"]: sys.exit("CONFIG HASH MISMATCH - refusing to run")
    for k, v in CFG["code_hashes"].items():
        if hashlib.sha256(open(os.path.join(F, "frozen", k), "rb").read()).hexdigest() != v: sys.exit(f"FROZEN CODE CHANGED: {k}")
    assert (smc.EXPIRE, smc.TIMEOUT, smc.MINW, smc.STOPB) == (CFG["expire_bars"], CFG["timeout_bars"], CFG["min_zone_atr"], CFG["stop_buffer_atr"])
    assert regime.DEFAULT == CFG["regime_gate"]["params"]

def update(sym, now_ms):
    f = os.path.join(CACHE, f"{sym}_1h.csv")
    rows = [r for r in csv.reader(open(f))][1:] if os.path.exists(f) else []
    rows = [r for r in rows if int(r[0]) + HR <= now_ms]           # never keep a bar that had not closed
    start = int(rows[-1][0]) - 2 * HR if rows else now_ms - 400 * 86400_000   # re-fetch last 3 bars: self-heals a partial bar
    keep = {int(r[0]): r for r in rows}; new = 0
    while start + HR <= now_ms:
        u = f"{BASE}?symbol={sym}USDT&interval=1h&startTime={start}&limit=1000"
        d = None
        for k in range(4):
            try: d = json.load(urllib.request.urlopen(u, timeout=30)); break
            except Exception as e: err = e; time.sleep(2 + 3 * k)
        if d is None: log("fetch FAIL", sym, err); return False
        d = [x for x in d if int(x[6]) < now_ms]                   # closed bars only
        if not d: break
        for x in d:
            r = [str(x[0]), x[1], x[2], x[3], x[4], x[5], x[7]]
            if keep.get(int(x[0])) != r: keep[int(x[0])] = r; new += 1
        start = int(d[-1][0]) + HR; time.sleep(0.2)
    rows = [keep[k] for k in sorted(keep)]
    if True:                                                    # always rewrite (atomic)
        tmp = f + ".tmp"
        with open(tmp, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["t_ms", "o", "h", "l", "c", "v", "qv"]); w.writerows(rows)
        os.replace(tmp, f)
    return True

def frame(sym):
    r = list(csv.reader(open(os.path.join(CACHE, f"{sym}_1h.csv"))))[1:]
    idx = pd.to_datetime([int(x[0]) + HR for x in r], unit="ms", utc=True)      # index = bar CLOSE time
    df = pd.DataFrame({k: [float(x[i]) for x in r] for i, k in ((1, "o"), (2, "h"), (3, "l"), (4, "c"), (6, "v"))}, index=idx)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[df.c > 0]

def iso(t): return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%MZ")

def forward(sym, df, rtab, t_start, R, cost):
    """Frozen smc.simulate logic, restricted to signals after t_start; returns records, open trades marked."""
    O, H, L, C = (df[k].values for k in "ohlc"); idx = df.index; recs = []; free = -1
    ev = [e for e in smc.events(df, "FVG") if idx[e["j"]] > t_start]
    if not ev: return recs
    tags = regime.regime_at([idx[e["j"]] for e in ev], rtab)["regime"]
    tag = dict(zip(tags.index, tags.values))
    for e in sorted(ev, key=lambda x: x["j"]):
        j = e["j"]; t_sig = idx[j]; rg = tag.get(t_sig, "na")
        if not e["trend"] or rg != CFG["regime_gate"]["label"]: continue      # gate: trend filter + trending regime
        base = dict(sym=sym, t_sig=iso(t_sig), regime=rg, zb=e["zb"], zt=e["zt"], stop=e["stop"])
        sid = f"FVG|{sym}|{iso(t_sig)}"
        if j + 1 >= len(C): continue                                           # (events() never returns this)
        if j + 1 <= free:
            recs.append(dict(id=sid, type="signal", status="skipped_position_open", **base)); continue
        ent = O[j+1]; st = e["stop"]; risk = ent - st
        if risk <= 0 or risk / ent < 4 * cost or risk / ent > CFG["max_risk"]:
            recs.append(dict(id=sid, type="signal", status="skipped_risk", entry=ent, risk_pct=(risk / ent if ent else None), **base)); continue
        tp = ent + R * risk
        recs.append(dict(id=sid, type="signal", status="taken", t_entry=iso(idx[j] ), entry_bar_open=iso(idx[j+1] - pd.Timedelta(hours=1)),
                         entry=ent, tp=tp, risk_pct=risk / ent, **base))
        x = None
        for k in range(j+1, min(len(C), j+1+smc.TIMEOUT)):
            if k > j+1 and O[k] <= st: x = (k, O[k], "stop"); break
            if L[k] <= st: x = (k, st, "stop"); break
            if k > j+1 and O[k] >= tp: x = (k, tp, "tp"); break
            if H[k] >= tp: x = (k, tp, "tp"); break
        if x is None:
            if j + smc.TIMEOUT <= len(C) - 1: k = j + smc.TIMEOUT; x = (k, C[k], "time")
            else: free = 10**12; continue                                    # still open: block later signals on this token
        k, px, why = x
        ret = (px * (1 - cost)) / (ent * (1 + cost)) - 1
        recs.append(dict(id="OUT|" + sid, type="outcome", sym=sym, t_sig=iso(t_sig), t_exit=iso(idx[k]), why=why,
                         entry=ent, exit=px, gross=px / ent - 1, ret=ret, bars=int(k - j)))
        free = k
    return recs

def summary(allrecs, px, t_start, cost, open_now, failed):
    out = [r for r in allrecs if r["type"] == "outcome"]; r = np.array([o["ret"] for o in out])
    L = [f"# Forward paper test: maj_1h FVG retest, trend on, gate=trending (PAPER ONLY)",
         f"Updated {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}. Start {CFG['start_time']}. Config sha256 `{CFG['config_sha256'][:16]}…`. R={CFG['R']}, cost {cost*100:.1f}%/side.",
         ""]
    if len(r):
        bs = np.random.default_rng(7).choice(r, (5000, len(r))).mean(1)
        L += [f"- Closed trades: **{len(r)}**, net/trade **{r.mean()*100:+.2f}%** (95% bootstrap CI {np.percentile(bs,2.5)*100:+.2f}% .. {np.percentile(bs,97.5)*100:+.2f}%), "
              f"win {np.mean(r>0)*100:.0f}%, sum {r.sum()*100:+.2f}%, compounded {(np.prod(1+r)-1)*100:+.2f}%."]
        if len(r) < 30: L += [f"- n={len(r)} is far too small to say anything; the backtest needed 50+ held-out trades for a claim."]
    else:
        L += ["- Closed trades: **0** so far."]
    L += [f"- Open positions: {len(open_now)} {', '.join(open_now) if open_now else ''}",
          f"- Skipped (position open / risk filter): {sum(1 for x in allrecs if x.get('status')=='skipped_position_open')} / {sum(1 for x in allrecs if x.get('status')=='skipped_risk')}"]
    hold = {}
    for s, df in px.items():
        a = df.c[df.index <= t_start]; b = df.c
        if len(a) and len(b) and b.index[-1] > t_start: hold[s] = b.iloc[-1] / a.iloc[-1] * (1 - cost) / (1 + cost) - 1
    last = max(df.index[-1] for df in px.values())
    if hold:
        L += [f"- Benchmarks: hold from the last 1h close at or before start to the close of {iso(last)}, one round trip of costs:",
              f"  - Hold SOL: {hold.get('SOL', float('nan'))*100:+.2f}%",
              f"  - Equal-weight majors ({len(hold)}): {np.mean(list(hold.values()))*100:+.2f}%",
              f"  - Strategy, equal capital split across the {len(CFG['majors'])} tokens (sum of returns / {len(CFG['majors'])}): {(r.sum()/len(CFG['majors']) if len(r) else 0)*100:+.2f}%"]
    if failed: L += [f"- Fetch failures this run (will retry next hour): {', '.join(failed)}"]
    L += ["", "Records: forward/fvg_trend.jsonl (signal + outcome, append-only, de-duplicated by id). Log: forward/cron.log.",
          f"Backtest reference: test 2026-08-15..10-23 trending subset n=71, +1.63%/trade; train trending n=138, -0.51%/trade. The gate was not train-selected."]
    tmp = SUM + ".tmp"; open(tmp, "w").write("\n".join(L) + "\n"); os.replace(tmp, SUM)

def main():
    check_frozen()
    now_ms = int(time.time() * 1000); t_start = pd.Timestamp(CFG["start_time"])
    syms = list(dict.fromkeys(CFG["majors"] + ["BTC"])); failed = [s for s in syms if not update(s, now_ms)]
    if "SOL" in failed or "BTC" in failed: log("SOL/BTC fetch failed; no regime -> skipping this run"); return 1
    px = {s: frame(s) for s in CFG["majors"]}
    rtab = regime.build(sol=px["SOL"], btc=frame("BTC"))
    recs = []
    for s in CFG["majors"]:
        if s in failed: continue
        recs += forward(s, px[s], rtab, t_start, CFG["R"], CFG["cost_per_side"])
    have = []
    if os.path.exists(JL): have = [json.loads(l) for l in open(JL) if l.strip()]
    ids = {h["id"] for h in have}; new = [r for r in recs if r["id"] not in ids]
    if new:
        with open(JL, "a") as fh:
            for r in new: r["logged_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"); fh.write(json.dumps(r, default=float) + "\n")
    allrecs = have + new; outs = {r["id"][4:] for r in allrecs if r["type"] == "outcome"}
    open_now = [r["id"] for r in allrecs if r.get("status") == "taken" and r["id"] not in outs]
    summary(allrecs, px, t_start, CFG["cost_per_side"], open_now, failed)
    last = max(df.index[-1] for df in px.values())
    log(f"ok last_bar_close={iso(last)} new_records={len(new)} total={len(allrecs)} open={len(open_now)} failed={failed}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
