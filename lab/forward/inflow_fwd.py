#!/usr/bin/env python3
"""PAPER ONLY inflow-spike forward test (Lab, 2026-10-24, for Zero). No keys, no wallets, no trades, no LLM/bot usage.
Polls free public GeckoTerminal (discovery + per-pool trades) and DexScreener (prices) through Lab's shared cross-process
throttle (data/backfill/.gecko_calls.log, >= SPACING s between ANY two Lab calls -> Lab total <= ~7.5/min).

Signal (central setting W=3 min, R=3x; frozen before forward start):
  over the last W min of trades: buy USD/min >= R x prior-30-min buy USD/min, unique buyers/min >= R x prior rate,
  net buy USD (buys - sells) > 0, >= 5 unique buyers in W;  pool liquidity >= $20k, pool age >= 5 min.
Entry: paper, 15 s after the signal (actual delay logged; it is >= 15 s because of the throttle), 0.04 SOL stake.
Exit (two tracks on the same entry): sell all at +20% (filled AT the +20% level, never better), -15% stop (filled at the
observed price, so gaps go through), time limit 30 min (track T30) / 60 min (track T60). Max 3 open positions.
Costs: 2%/side fee + slippage 0.5% + 2 x stake/liquidity per side (= net_base); net_p1 adds 2 x (0.0001 priority + 0.000005 base)
SOL / 0.04 SOL; net_p5 adds 2 x (0.0005 + 0.000005). Token-account rent (0.00203 SOL) assumed reclaimed (not charged).
Usage:  python3 inflow_fwd.py            (loop; run under nohup, pidfile forward/inflow.pid)
        python3 inflow_fwd.py --summary
"""
import json, os, sys, time, fcntl, urllib.request, urllib.error, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE)
LOG = os.path.join(HERE, "inflow_fwd.jsonl"); STATE = os.path.join(HERE, "inflow_state.json"); PID = os.path.join(HERE, "inflow.pid")
GLOCK = os.path.join(LAB, "data", "backfill", ".gecko_calls.log")
SPACING = 8.0
W_MIN, R, PRIOR_MIN, MIN_BUYERS = 3, 3.0, 30, 5
MIN_LIQ, MIN_AGE_MIN = 20000.0, 5.0
DELAY_S, STAKE_SOL = 15, 0.04
TP, SL, HOLDS = 0.20, 0.15, (30, 60)
# 2026-10-24 15:25Z: fast track added per Zero. Backtest IS-best fast combo = TP +8% / SL -15% / 5 min (IF_w5_r2_d30_tp08_sl15_h05);
# it LOST in-sample and held out (-6.6% / -6.9% per trade), it is only "least bad", so it runs as an extra track, not a replacement.
TRACKS = [("T30", 0.20, 0.15, 30), ("T60", 0.20, 0.15, 60), ("F08_15_5", 0.08, 0.15, 5)]
FEE, BASE_SLIP, IMPACT = 0.02, 0.005, 2.0
MAX_OPEN = 3
UA = {"User-Agent": "lab-paper-inflow/1.0", "Accept": "application/json"}
GT = "https://api.geckoterminal.com/api/v2/networks/solana"
DISCOVERY = [GT + "/new_pools?page=1", GT + "/trending_pools?duration=5m&page=1", GT + "/new_pools?page=2", GT + "/trending_pools?duration=1h&page=1"]

def now(): return time.time()
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def pts(s): return dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
def emit(ev, **kw):
    row = {"ts": iso(now()), "event": ev, **kw}
    with open(LOG, "a") as fh: fh.write(json.dumps(row) + "\n")
    return row

CALLS = [0]
def get(url, tries=2):
    for i in range(tries):
        with open(GLOCK, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX); fh.seek(0); lines = fh.read().splitlines()
            try: last = float(lines[-1].split()[0]) if lines else 0
            except Exception: last = 0
            w = SPACING - (now() - last)
            if w > 0: time.sleep(w)
            fh.write(f"{now():.1f} inflow_fwd {url.split('//')[-1][:80]}\n"); fh.flush()
        CALLS[0] += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(30 * (i + 1)); continue
            return None
        except Exception: time.sleep(3)
    return None

def fnum(x, d=0.0):
    try: return float(x)
    except Exception: return d

def cost_side(liq_usd, stake_usd): return FEE + BASE_SLIP + IMPACT * stake_usd / max(liq_usd, 1000.0)

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {"open": [], "pending": [], "seen": {}, "cooldown": {}, "sol_usd": 100.0, "started": now(), "disc_i": 0, "cand": []}
def save_state(S):
    json.dump(S, open(STATE + ".tmp", "w")); os.replace(STATE + ".tmp", STATE)

def discover(S):
    url = DISCOVERY[S["disc_i"] % len(DISCOVERY)]; S["disc_i"] += 1
    d = get(url)
    if not d or "data" not in d: return
    cands = []
    for p in d["data"]:
        a = p.get("attributes", {}); addr = a.get("address"); liq = fnum(a.get("reserve_in_usd"))
        q = fnum(a.get("quote_token_price_usd"))
        if a.get("name", "").endswith("/ SOL") and 50 < q < 1000: S["sol_usd"] = q
        try: age = (now() - pts(a["pool_created_at"])) / 60
        except Exception: continue
        if liq < MIN_LIQ or age < MIN_AGE_MIN: continue
        if age > 3 * 1440 or liq > 2e6: continue                          # memecoins only: skip majors/stables/old pools (15:14Z)
        tx = a.get("transactions", {}); m5 = tx.get("m5", {}); h1 = tx.get("h1", {})
        b5, u5, bh = m5.get("buys", 0) or 0, m5.get("buyers", 0) or 0, h1.get("buys", 0) or 0
        if u5 < MIN_BUYERS: continue
        pre = (b5 / 5) / max(bh / 60, 0.2) if age > 15 else 9.9          # cheap pre-screen only; real test uses trades
        if pre < 1.0: continue                                             # loose pre-screen (15:11Z: was 1.5, too few checks)
        if now() < S["cooldown"].get(addr, 0): continue
        cands.append({"pool": addr, "name": a.get("name"), "liq": liq, "age_min": round(age, 1), "pre": round(pre, 2),
                      "attr": {"h1_buys": bh, "m5_buys": b5, "h1_buyers": h1.get("buyers", 0) or 0, "h1_vol": fnum((a.get("volume_usd") or {}).get("h1"))},
                      "mint": ((p.get("relationships") or {}).get("base_token") or {}).get("data", {}).get("id", "").replace("solana_", "")})
    cands.sort(key=lambda c: -c["pre"])
    have = {c["pool"] for c in S["cand"]}
    S["cand"] = (S["cand"] + [c for c in cands if c["pool"] not in have])[:12]

def spike(trades, T, age_min, attr=None):
    """returns (fired, stats). trades: GT attributes list."""
    rows = []
    for t in trades:
        a = t["attributes"]
        if a.get("is_anomalous"): continue
        rows.append((pts(a["block_timestamp"]), a["kind"], fnum(a.get("volume_in_usd")), a.get("tx_from_address")))
    if not rows: return False, {"why": "no_trades"}
    oldest = min(r[0] for r in rows); w0 = T - 60 * W_MIN
    prior_start = max(T - 60 * (W_MIN + PRIOR_MIN), oldest, T - 60 * age_min)
    prior_min = (w0 - prior_start) / 60
    if prior_min < 2:
        # busy coin: the last 300 trades don't reach back far enough. Fallback (15:14Z, logged as prior_src=attr):
        # window = last min(W, covered span) of trades; prior rate = (h1 - m5) buy COUNT / 55 min and h1 unique buyers / 60 from GT pool attributes.
        span = (T - oldest) / 60
        if not attr or span < 0.5 or age_min < 10: return False, {"why": "prior_window_too_short", "prior_min": round(prior_min, 1), "span_min": round(span, 1)}
        wm = min(W_MIN, span); w0 = T - 60 * wm; win = [r for r in rows if r[0] > w0]
        nb_w = sum(1 for r in win if r[1] == "buy"); bw = sum(r[2] for r in win if r[1] == "buy"); sw = sum(r[2] for r in win if r[1] == "sell")
        uw = len({r[3] for r in win if r[1] == "buy"})
        pr_b = max(attr["h1_buys"] - attr["m5_buys"], 0) / 55; pr_u = attr["h1_buyers"] / 60
        vr = (nb_w / wm) / max(pr_b, 0.2); ur = (uw / wm) / max(pr_u, 0.1)
        st = {"prior_src": "attr", "win_min": round(wm, 2), "buys_w": nb_w, "buy_usd_w": round(bw), "sell_usd_w": round(sw), "net_usd_w": round(bw - sw),
              "buyers_w": uw, "buy_count_ratio": round(vr, 2), "buyer_ratio": round(ur, 2)}
        return (vr >= R and ur >= R and bw - sw > 0 and uw >= MIN_BUYERS), st
    win = [r for r in rows if r[0] > w0]; pri = [r for r in rows if prior_start <= r[0] <= w0]
    bw = sum(r[2] for r in win if r[1] == "buy"); sw = sum(r[2] for r in win if r[1] == "sell")
    bp = sum(r[2] for r in pri if r[1] == "buy")
    uw = len({r[3] for r in win if r[1] == "buy"}); up = len({r[3] for r in pri if r[1] == "buy"})
    vr = (bw / W_MIN) / max(bp / prior_min, 1.0); ur = (uw / W_MIN) / max(up / prior_min, 0.1)
    st = {"prior_src": "trades", "buy_usd_w": round(bw), "sell_usd_w": round(sw), "net_usd_w": round(bw - sw), "buyers_w": uw, "buyers_prior": up,
          "prior_min": round(prior_min, 1), "vol_ratio": round(vr, 2), "buyer_ratio": round(ur, 2), "truncated_prior": prior_min < PRIOR_MIN - 0.5}
    return (vr >= R and ur >= R and bw - sw > 0 and uw >= MIN_BUYERS), st

def check_candidate(S):
    if not S["cand"]: return False
    c = S["cand"].pop(0); S["cooldown"][c["pool"]] = now() + 300
    d = get(f"{GT}/pools/{c['pool']}/trades")
    if not d or "data" not in d: return True
    T = now(); fired, st = spike(d["data"], T, c["age_min"], c.get("attr"))
    emit("check", pool=c["pool"], name=c["name"], liq=round(c["liq"]), age_min=c["age_min"], fired=fired, **st)
    if not fired: return True
    nopen = len(S["open"]) + len(S["pending"])
    if c["pool"] in S["seen"] and now() - S["seen"][c["pool"]] < 3600:
        emit("signal_skip", pool=c["pool"], name=c["name"], why="re-signal within 60 min", **st); return True
    if nopen >= MAX_OPEN:
        emit("signal_skip", pool=c["pool"], name=c["name"], why="max_open", **st); return True
    S["seen"][c["pool"]] = T; S["cooldown"][c["pool"]] = T + 3600
    S["pending"].append({"pool": c["pool"], "name": c["name"], "mint": c["mint"], "t_sig": T, "due": T + DELAY_S, "liq_sig": c["liq"], "age_min": c["age_min"]})
    emit("signal", pool=c["pool"], name=c["name"], mint=c["mint"], liq=round(c["liq"]), age_min=c["age_min"], **st)
    return True

def ds_prices(pools):
    out = {}
    for i in range(0, len(pools), 30):
        d = get("https://api.dexscreener.com/latest/dex/pairs/solana/" + ",".join(pools[i:i + 30]))
        for p in (d or {}).get("pairs") or []:
            out[p["pairAddress"]] = (fnum(p.get("priceUsd")), fnum((p.get("liquidity") or {}).get("usd")))
            if p.get("quoteToken", {}).get("symbol") == "SOL" and fnum(p.get("priceNative")) > 0:
                S_sol = fnum(p.get("priceUsd")) / fnum(p.get("priceNative")); out["_sol"] = S_sol
    return out

def net_parts(entry_mid, entry_liq, exit_mid, exit_liq, sol_usd):
    stake_usd = STAKE_SOL * sol_usd
    gross = exit_mid / entry_mid - 1
    nb = exit_mid * (1 - cost_side(exit_liq, stake_usd)) / (entry_mid * (1 + cost_side(entry_liq, stake_usd))) - 1
    return round(gross, 4), round(nb, 4), round(nb - 2 * (0.0001 + 0.000005) / STAKE_SOL, 4), round(nb - 2 * (0.0005 + 0.000005) / STAKE_SOL, 4)

def monitor(S):
    pools = sorted({p["pool"] for p in S["open"]} | {p["pool"] for p in S["pending"] if now() >= p["due"]})
    if not pools: return False
    px = ds_prices(pools); T = now()
    if px.get("_sol"): S["sol_usd"] = px["_sol"]
    for p in [q for q in S["pending"] if T >= q["due"]]:
        pr = px.get(p["pool"])
        if not pr or pr[0] <= 0:
            if T - p["due"] > 120: S["pending"].remove(p); emit("entry_fail", pool=p["pool"], name=p["name"], why="no price")
            continue
        S["pending"].remove(p)
        pos = {**p, "t_entry": T, "entry_mid": pr[0], "entry_liq": pr[1] or p["liq_sig"], "delay_s": round(T - p["t_sig"], 1),
               "tracks": {n: None for n, *_ in TRACKS}, "last_px": pr[0], "last_seen": T, "min_r": 0.0, "max_r": 0.0}
        S["open"].append(pos)
        emit("entry", pool=p["pool"], name=p["name"], mint=p["mint"], entry_px=pr[0], liq=round(pos["entry_liq"]), delay_s=pos["delay_s"],
             stake_sol=STAKE_SOL, stake_usd=round(STAKE_SOL * S["sol_usd"], 2), entry_cost_side=round(cost_side(pos["entry_liq"], STAKE_SOL * S["sol_usd"]), 4))
    for pos in list(S["open"]):
        pr = px.get(pos["pool"])
        if pr and pr[0] > 0: pos["last_px"], pos["last_seen"], liq = pr[0], T, (pr[1] or pos["entry_liq"])
        else: liq = None
        r = pos["last_px"] / pos["entry_mid"] - 1; pos["min_r"] = min(pos["min_r"], r); pos["max_r"] = max(pos["max_r"], r)
        age = (T - pos["t_entry"]) / 60
        for k, tp_k, sl_k, h in TRACKS:
            if pos["tracks"].get(k, "x"): continue
            reason = None; xm = pos["last_px"]; xl = liq or 0
            if liq is None and T - pos["last_seen"] > 300: reason, xm, xl = "no_data_rug", pos["last_px"] * 0.1, 1000
            elif liq is not None and liq < 2000: reason = "rug_liq"
            elif r <= -sl_k: reason = "stop"                       # fills at the observed price (gaps through)
            elif r >= tp_k: reason, xm = "tp", pos["entry_mid"] * (1 + tp_k)
            elif age >= h: reason = "time"
            if reason:
                g, nb, n1, n5 = net_parts(pos["entry_mid"], pos["entry_liq"], xm, max(xl, 1000), S["sol_usd"])
                pos["tracks"][k] = reason
                emit("exit", track=k, pool=pos["pool"], name=pos["name"], reason=reason, hold_min=round(age, 1), entry_px=pos["entry_mid"],
                     exit_px=xm, gross=g, net_base=nb, net_p1=n1, net_p5=n5, min_r=round(pos["min_r"], 4), max_r=round(pos["max_r"], 4),
                     t_sig=iso(pos["t_sig"]), delay_s=pos["delay_s"])
        if all(pos["tracks"].values()): S["open"].remove(pos)
    S["last_mon"] = T
    return True

def loop():
    open(PID, "w").write(str(os.getpid()))
    S = load_state(); emit("start", pid=os.getpid(), setting=dict(W_min=W_MIN, R=R, prior_min=PRIOR_MIN, min_buyers=MIN_BUYERS, min_liq=MIN_LIQ,
                      min_age_min=MIN_AGE_MIN, delay_s=DELAY_S, stake_sol=STAKE_SOL, tp=TP, sl=SL, holds=HOLDS, tracks=TRACKS, spacing_s=SPACING))
    S.setdefault("last_disc", 0); S.setdefault("last_mon", 0); last_hb = now()
    while True:
        try:
            T = now()
            due = [p for p in S["pending"] if T >= p["due"]]
            if due or (S["open"] and T - S["last_mon"] >= 15): monitor(S)
            elif T - S["last_disc"] >= 40 or not S["cand"]:
                if T - S["last_disc"] >= 25: discover(S); S["last_disc"] = now()
                elif not check_candidate(S): time.sleep(2)
            elif not check_candidate(S): time.sleep(2)
            S["cooldown"] = {k: v for k, v in S["cooldown"].items() if v > now()}
            S["seen"] = {k: v for k, v in S["seen"].items() if now() - v < 7200}
            save_state(S)
            if now() - last_hb > 600:
                emit("heartbeat", calls=CALLS[0], open=len(S["open"]), pending=len(S["pending"]), cand=len(S["cand"]), sol_usd=round(S["sol_usd"], 2)); last_hb = now()
        except Exception as e:
            emit("error", err=repr(e)[:300]); time.sleep(10)

def summary():
    ev = [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []
    if not ev: print("no events yet"); return
    starts = [e for e in ev if e["event"] == "start"]; t0 = pts(starts[0]["ts"]) if starts else pts(ev[0]["ts"])
    hrs = max((now() - t0) / 3600, 1e-6)
    chk = sum(e["event"] == "check" for e in ev); print(f"pools checked against trades: {chk}")
    sig = sum(e["event"] == "signal" for e in ev); skip = sum(e["event"] == "signal_skip" for e in ev); ent = sum(e["event"] == "entry" for e in ev)
    print(f"PAPER inflow forward since {iso(t0)} ({hrs:.2f} h): signals {sig} ({sig/hrs:.2f}/h), skipped {skip}, entries {ent} ({ent/hrs:.2f}/h)")
    for k in [n for n, *_ in TRACKS]:
        x = [e for e in ev if e["event"] == "exit" and e["track"] == k]
        if not x: print(f"  {k}: 0 closed trades"); continue
        m = lambda f: sum(e[f] for e in x) / len(x)
        wins = sum(e["net_p1"] > 0 for e in x); rs = {}
        for e in x: rs[e["reason"]] = rs.get(e["reason"], 0) + 1
        print(f"  {k}: {len(x)} closed ({len(x)/hrs:.2f}/h), win rate {wins/len(x):.0%} (net @0.04 SOL p0.0001), avg net/trade: "
              f"2%/side base {m('net_base'):+.1%} | @0.04 SOL prio 0.0001 {m('net_p1'):+.1%} | prio 0.0005 {m('net_p5'):+.1%} | gross {m('gross'):+.1%}; "
              f"sum @0.04 SOL {sum(e['net_p1'] for e in x)*STAKE_SOL:+.4f} SOL; exits {rs}")
    print("  small sample: do not read anything into < 30 trades per track.")

if __name__ == "__main__":
    if "--summary" in sys.argv: summary()
    else: loop()
