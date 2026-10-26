#!/usr/bin/env python3
"""Survivor-momentum variant (Zero 2026-10-23, PAPER ONLY, no trading).
Idea: at a check time T (20/30/45/60 min after a radar signal) BUY only coins whose pool liquidity is UP >= X% vs the
signal AND whose price is up vs the signal (optional chase cap), plus mcap/liq sanity and Scout's avoid list as known then.
Point-in-time rules:
  * decision time t_dec = first 5-min candle opening at/after signal + T; price = that candle's open (fill there + slippage).
  * liquidity = newest observation with signal <= ts <= t_dec and t_dec - ts <= 15 min, from: radar scan rows (rescans),
    Lab DexScreener polls (data/liq_polls.jsonl, same pair only), Chunk's live check log (trades-log.md, Dublin time) and
    Chunk paper-buys.jsonl. No observation -> the coin is EXCLUDED (status no_liq) unless price already fails (price is from
    candles, so a 'price not up' rejection is still point-in-time). The *_LIQEST rows instead estimate liq = liq0*sqrt(p/p0)
    (constant-product, NO LP adds/removals) and are labelled ESTIMATE: that estimate cannot see the LP-add signal at all.
  * Scout avoid list: newest oc_avoid snapshot with valid_from <= t_dec (token in 'mints' column, or creator/top holder
    captured <= 15 min after the signal in the avoid 'address' column). Before the first snapshot (20:50Z) -> 'no list yet' = pass.
Exits/costs are backtest.simulate() unchanged: stop -25% (gap-through fills at candle close), sell half at 2x, 2%/side,
$0.05/tx, slippage 0.5% + 2 x size/liq, max 3 open, flat by 08:00 Dublin.
Writes out/survivor_momentum.json, out/sm_trades.csv, out/leaderboard_extra_SM.json (merged into leaderboard.csv by backtest.py).
Usage: python3 survivor_momentum.py [--fetch]   (--fetch: GeckoTerminal candles for uncovered pairs, <= 8 calls, 12 s apart)"""
import argparse, csv, json, math, os, random, re, statistics, sys, time, datetime as dt
from labcore import *
from sources import radar_rows
import backtest as B, scoring

FRESH_S = 900
TS = [20, 30, 45, 60]; XS = [0.0, 0.2, 0.4]; CAPS = [None, 1.0, 2.0]
CENTER = (30, 0.2, 1.0)                 # pre-registered centre cell (middle of every axis), chosen before looking at results
SANITY = {"min_liq": 20000.0, "max_mcap_liq": 20.0}   # generic bounds (liq >= $20k, mcap <= 20x liq), not tuned

def capname(c): return "none" if c is None else f"{int(c*100)}"
def vname(T, X, cap, tag=""): return f"SM_T{T}_X{int(X*100)}_cap{capname(cap)}{tag}"

# ---------------- liquidity observations (point-in-time) ----------------
_LIQ = re.compile(r"liq\s+~?(?:\$([\d.,]+)(k|M)?\s*)?\(?([+-]\d+(?:\.\d+)?)(?:\s*to\s*[+-]?\d+)?%")
_PRC = re.compile(r"(?:price\s+(?:\$[\d.e-]+\s*\()?|already\s+)([+-]\d+(?:\.\d+)?)%")
def chunk_obs(cfg, sigs):
    """Parse Chunk's live check lines: '- HH:MM Dublin: ... SYMBOL (...): price +86% vs signal, liq $109k (+40%) ...'."""
    p = cfg["paths"]["chunk_trades_md"]; out = []
    if not os.path.exists(p): return out
    syms = sorted({s["symbol"] for s in sigs}, key=len, reverse=True); bysym = {s["symbol"]: s for s in sigs}
    pat = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(s) for s in syms) + r")(?![A-Za-z])")
    night = None
    for line in open(p):
        m = re.match(r"##\s*Night of (\d{4}-\d{2}-\d{2})", line)
        if m: night = m.group(1); continue
        m = re.match(r"-\s*(\d{1,2}):(\d{2})\s*Dublin", line)
        if not (m and night): continue
        d = dt.datetime.fromisoformat(night).replace(hour=int(m.group(1)), minute=int(m.group(2)), tzinfo=DUB)
        if d.hour < 12: d += dt.timedelta(days=1)
        t = d.timestamp(); hits = list(pat.finditer(line))
        for i, h in enumerate(hits):
            seg = line[h.end(): hits[i + 1].start() if i + 1 < len(hits) else len(line)]
            s = bysym[h.group(1)]
            if t < s["t"]: continue
            lm = _LIQ.search(seg)
            if not lm: continue
            liq = None
            if lm.group(1):
                liq = float(lm.group(1).replace(",", "")) * (1e3 if lm.group(2) == "k" else 1e6 if lm.group(2) == "M" else 1)
            ratio = 1 + float(lm.group(3)) / 100
            pm = _PRC.search(seg); mc = re.search(r"mcap \$([\d.]+)(k|M)", seg)
            out.append({"ts": t, "token": s["token"], "liq": liq if liq else ratio * s["liq"], "liq_ratio": ratio,
                        "price_chg": float(pm.group(1)) / 100 if pm else None,
                        "mcap": float(mc.group(1)) * (1e3 if mc.group(2) == "k" else 1e6) if mc else None,
                        "src": "chunk_log", "note": clean(seg, 70)})
    for r in read_jsonl(os.path.join(os.path.dirname(p), "paper-buys.jsonl")):
        tok = r.get("contract_address"); s = next((x for x in sigs if x["token"] == tok), None)
        if s and r.get("liq_usd"):
            out.append({"ts": ts_of(r["ts"]), "token": tok, "liq": fnum(r["liq_usd"]), "liq_ratio": fnum(r["liq_usd"]) / s["liq"],
                        "mcap": fnum(r.get("mcap_usd"), None), "src": "chunk_paper"})
    return out

def all_obs(cfg, cands, radar):
    by = {}
    pairs = {c["token"]: c["pair"] for c in cands}
    for r in radar:                                       # radar rescans (same pair)
        if r["token"] in pairs and r["pair"] == pairs[r["token"]]:
            by.setdefault(r["token"], []).append({"ts": r["t"], "liq": r["liq"], "mcap": r["mcap"], "price": r["price"], "src": "scan"})
    for r in read_jsonl(LIQ_POLLS):                       # Lab DexScreener polls (same pair only)
        if r.get("token") in pairs and r.get("pair") == pairs[r["token"]]:
            by.setdefault(r["token"], []).append({"ts": r["ts"], "liq": r["liq"], "mcap": r.get("mcap"), "price": r.get("price"), "src": "ds_poll"})
    for o in chunk_obs(cfg, cands):
        by.setdefault(o["token"], []).append(o)
    for v in by.values(): v.sort(key=lambda o: o["ts"])
    return by

# ---------------- Scout avoid list at time t ----------------
_AV = {}
def avoid_at(idx, t):
    c = [r for r in idx if r["src"] == "oc_avoid" and r["valid_from"] <= t]
    if not c: return None
    f = max(c, key=lambda r: r["valid_from"])["file"]
    if f not in _AV:
        toks, wals = set(), set()
        try:
            for r in csv.DictReader(open(f, newline="")):
                r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
                da = parse_ts(r.get("date_added")) if r.get("date_added") else None
                for a in _ADDR_IN.findall(r.get("mints", "") + " " + r.get("token", "") + " " + r.get("mint", "")):
                    toks.add((a, da))
                if valid_sol(r.get("address", "")): wals.add((r["address"], da))
        except Exception: pass
        _AV[f] = (toks, wals)
    toks, wals = _AV[f]
    return ({a for a, d in toks if d is None or d <= t}, {a for a, d in wals if d is None or d <= t})

# ---------------- one decision ----------------
def decide(cfg, e, T, X, cap, cdl, obs, idx, sanity=True, scout=True, liq_est=False):
    """-> (status, why, info). status: pass | fail | no_liq | no_candles"""
    t_in = e["t"] + T * 60
    ec = [c for c in cdl if c[0] >= t_in]
    if not cdl: return "no_candles", "no candles", {}
    if not ec or ec[0][0] - t_in > 1800: return "fail", "no trades near check time (dead)", {}
    t_dec, p = ec[0][0], ec[0][1]; chg = p / e["price"] - 1
    info = {"t_dec": t_dec, "chg": chg}
    if chg <= 0: return "fail", f"price {chg:+.0%} (not up)", info
    if cap is not None and chg > cap: return "fail", f"chase cap: price {chg:+.0%} > +{cap:.0%}", info
    o = [x for x in obs.get(e["token"], []) if e["t"] < x["ts"] <= t_dec and t_dec - x["ts"] <= FRESH_S]
    if o:
        o = o[-1]; liq = o["liq"]; info.update(liq=liq, liq_src=o["src"], liq_age_min=(t_dec - o["ts"]) / 60)
        mcap = o.get("mcap") or (e["mcap"] * (1 + chg))
    elif liq_est:
        liq = e["liq"] * math.sqrt(1 + chg); mcap = e["mcap"] * (1 + chg); info.update(liq=liq, liq_src="ESTIMATE sqrt")
    else:
        return "no_liq", "no liquidity observation <=15 min before check", info
    lr = liq / e["liq"] - 1; info["liq_chg"] = lr
    if lr < X: return "fail", f"liq {lr:+.0%} < +{X:.0%}", info
    if sanity:
        if liq < SANITY["min_liq"]: return "fail", f"sanity: liq ${liq:,.0f} < ${SANITY['min_liq']:,.0f}", info
        if mcap and mcap / liq > SANITY["max_mcap_liq"]: return "fail", f"sanity: mcap/liq {mcap/liq:.1f} > {SANITY['max_mcap_liq']}", info
    if scout:
        av = avoid_at(idx, t_dec)
        if av is None: info["scout"] = "no list yet"
        else:
            h = holders_at(cfg, e["token"], e["t"])
            hs = (set(h.get("holders") or []) | ({h["creator"]} if h.get("creator") else set())) if h else set()
            if e["token"] in av[0] or hs & av[1]: return "fail", "scout avoid-list", info
            info["scout"] = "clear" + ("" if h else " (no holder snapshot)")
    return "pass", "", info

def body(cs):   # wick-free candles: stop/TP see only open/close (sensitivity for single-print wicks)
    return [(c[0], c[1], max(c[1], c[4]), min(c[1], c[4]), c[4]) + tuple(c[5:]) for c in cs]

def run_variant(cfg, V, ents, T, X, cap, cdl, obs, polls, idx, now, split, bodystop=False, **kw):
    res, dec = [], []
    for e in ents:
        st, why, info = decide(cfg, e, T, X, cap, cdl(e["pair"]), obs, idx, **kw)
        dec.append({"e": e, "status": st, "why": why, **info})
        if st != "pass": continue
        r = B.simulate(cfg, V, e, body(cdl(e["pair"])) if bodystop else cdl(e["pair"]), polls, now); r["e"] = e; r["info"] = info; res.append(r)
    res.sort(key=lambda r: (r.get("t_entry", r["e"]["t"]), -(r["e"].get("score") or 0)))
    open_exits, trades = [], []
    for r in res:
        if r["status"] in ("closed", "open"):
            open_exits = [x for x in open_exits if x > r["t_entry"]]
            if len(open_exits) >= cfg["sim"]["max_open"]: r.update(status="skip", why="max_open")
            else: open_exits.append(r["exit_t"] or 1e18)
        r["t"] = r["e"]["t"]; r["is_oos"] = r["t"] >= split; trades.append(r)
    return trades, dec

def boot_median(rets, iters=5000, seed=7):
    if not rets: return None
    rnd = random.Random(seed); b = sorted(statistics.median(rnd.choices(rets, k=len(rets))) for _ in range(iters))
    return b[int(0.025 * iters)], b[int(0.975 * iters) - 1]

def board_row(cfg, V, trades, dec, split, n_tried):
    S = cfg["sim"]; closed = sorted([t for t in trades if t["status"] == "closed"], key=lambda t: t["exit_t"])
    st = B.stats(cfg, trades); si = B.stats(cfg, [t for t in trades if not t["is_oos"]]); so = B.stats(cfg, [t for t in trades if t["is_oos"]])
    mc = scoring.mc_drawdown([t["pnl"] for t in closed], cfg["costs"]["start_equity_usd"], S.get("mc_iters", 1000), S["seed"])
    scr = scoring.score(st, so, closed, mc)
    hold = f"insufficient (n_out={so['trades']}<{S['min_oos_trades']})" if so["trades"] < S["min_oos_trades"] else "see report"
    op = [t for t in trades if t["status"] == "open"]
    cnt = {k: sum(d["status"] == k for d in dec) for k in ("pass", "fail", "no_liq", "no_candles")}
    n = st["trades"]
    return {"variant": V["name"], "trades": n, "win_rate": round(st.get("win_rate", 0), 3) if n else "",
            "net_profit_after_costs": round(st.get("net_pnl", 0), 2) if n else "", "max_drawdown": round(st.get("max_dd_usd", 0), 2) if n else "",
            "holds_out_of_sample": hold, "n_in_sample": si["trades"], "n_out_of_sample": so["trades"],
            "mean_ret": round(st["mean_ret"], 3) if n else "", "median_ret": round(st["median_ret"], 3) if n else "",
            "ci95_mean_ret": f"[{st['ci_lo']:+.2f},{st['ci_hi']:+.2f}]" if n else "", "rug_rate": round(st["rug_rate"], 3) if n else "",
            "open": len(op), "skipped": sum(t["status"] == "skip" for t in trades), "pending": sum(t["status"] == "pending" for t in trades),
            "no_candles": cnt["no_candles"], "uncovered": cnt["no_liq"], "filtered_out": cnt["fail"],
            "oos_mean_ret": round(so["mean_ret"], 3) if so["trades"] else "", "in_net_pnl": round(si.get("net_pnl", 0), 2) if si["trades"] else "",
            "out_net_pnl": round(so.get("net_pnl", 0), 2) if so["trades"] else "",
            **{k: scr[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
            "net_ex_best_trade": round(sum(t["pnl"] for t in closed) - max(t["pnl"] for t in closed), 2) if closed else "",
            "mc_dd_p5": round(mc[0], 3) if mc else "", "mc_dd_p50": round(mc[1], 3) if mc else "", "mc_dd_p95": round(mc[2], 3) if mc else "",
            "nights": scr["nights"], "nights_profitable": scr["nights_profitable"], "candidate": "no", "lucky_number": "",
            "variants_tried": n_tried, "family": "survivor_momentum", "guard_rejects": "", "scout_verdicts": "", "reentry_none": "",
            "note": (f"PAPER survivor-momentum; open(marked) {len(op)} ${sum(t['pnl'] for t in op):+.2f}; "
                     f"{cnt['no_liq']} excluded no PIT liq" + ("; ESTIMATED liq (sqrt model, cannot see LP adds)" if "LIQEST" in V["name"] else ""))}

def fetch_missing(cfg, ents, cdl_raw, max_calls=8):
    calls = 0
    for e in ents:
        c = load_candles(e["pair"])
        if c and c["first"] <= e["t"] + 300: continue
        if calls >= max_calls: break
        before = int(e["t"] + 26 * 3600) if e["t"] + 26 * 3600 < time.time() else None
        url = (f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{e['pair']}/ohlcv/minute?aggregate=5&limit=300"
               f"&currency=usd&token=base" + (f"&before_timestamp={before}" if before else ""))
        r = get_json(url, 12.0); calls += 1
        try: rows = [[int(x[0])] + [float(v) for v in x[1:6]] for x in r["data"]["attributes"]["ohlcv_list"]]
        except Exception: continue
        merge_candles(e["pair"], rows, time.time(), before or time.time())
    return calls

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fetch", action="store_true"); a = ap.parse_args()
    cfg = load_config(); now = time.time(); idx = intel_index(cfg)
    radar = radar_rows(cfg)
    sig_keys = {(r["token"], r["ts"]) for r in read_jsonl(cfg["paths"]["radar_signals"])}
    sigs = [r for r in radar if (r["token"], r["ts"]) in sig_keys]
    seen, broad = set(), []
    for r in radar:                                                      # broad universe: first non-rejected row, score >= 45
        if not r["rejects"] and r["score"] >= 45 and r["token"] not in seen: seen.add(r["token"]); broad.append(r)
    if a.fetch: print("gecko calls:", fetch_missing(cfg, broad, None))
    cache = {}
    def cdl(pair):
        if pair not in cache: c = load_candles(pair); cache[pair] = [tuple(r) for r in c["rows"]] if c else []
        return cache[pair]
    S = load_json(os.path.join(OUT, "summary.json"), {}) or {}
    split = parse_ts((S.get("accrual") or {}).get("split")) or sorted(r["t"] for r in sigs)[int(len(sigs) * 0.6)]
    half = (min(r["t"] for r in sigs) + max(r["t"] for r in sigs)) / 2       # time-based halves of signal time (pre-registered)
    obs_s = all_obs(cfg, sigs, radar); obs_b = all_obs(cfg, broad, radar)
    polls_s = {k: [o for o in v if o.get("liq")] for k, v in obs_s.items()}; polls_b = {k: [o for o in v if o.get("liq")] for k, v in obs_b.items()}
    base = {**{k: v for k, v in load_config()["variants"][0].items() if k != "name"}}
    grid, out_rows, report = [], [], {"generated": iso(now), "split_pipeline": iso(split), "half_split": iso(half),
                                       "n_signals": len(sigs), "n_broad": len(broad), "sanity": SANITY, "fresh_s": FRESH_S, "cells": {}}
    report["signals_per_night"] = {}
    for s in sigs: report["signals_per_night"][night_of(s["t"])] = report["signals_per_night"].get(night_of(s["t"]), 0) + 1
    report["obs"] = {s["symbol"]: [(round((o["ts"] - s["t"]) / 60, 1), round(o["liq"] / s["liq"] - 1, 2), o["src"]) for o in obs_s.get(s["token"], []) if o["ts"] > s["t"] and o["ts"] - s["t"] <= 75 * 60] for s in sigs}
    specs = [(T, X, cap, "", dict(), sigs, obs_s, polls_s) for T in TS for X in XS for cap in CAPS]
    cT, cX, cC = CENTER
    specs += [(cT, cX, cC, "_nosanity", dict(sanity=False), sigs, obs_s, polls_s),
              (cT, cX, cC, "_noscout", dict(scout=False), sigs, obs_s, polls_s),
              (cT, cX, cC, "_LIQEST", dict(liq_est=True), sigs, obs_s, polls_s),
              (cT, cX, cC, "_broad45", dict(), broad, obs_b, polls_b),
              (20, 0.2, None, "_broad45", dict(), broad, obs_b, polls_b)]
    specs += [(T, X, cap, "_bodystop", dict(bodystop=True), sigs, obs_s, polls_s) for T in TS for X in XS for cap in CAPS]
    allV = []
    for T, X, cap, tag, kw, U, ob, po in specs:
        V = {**base, "name": vname(T, X, cap, tag), "entry_delay_min": T, "survive_max_dd": -1.0, "survive_max_up": 99,
             "survive_min_liq_ratio": 0, "min_score": 0, "sm_liq_up": X, "sm_cap": cap, "sm_tag": tag, "sm_sanity": SANITY, "sm_rule": "survivor_momentum_v1", "sm_bodystop": "bodystop" in tag}
        allV.append(V)
    n_tried = scoring.variants_tried(allV)
    trades_out = []
    for V, (T, X, cap, tag, kw, U, ob, po) in zip(allV, specs):
        trades, dec = run_variant(cfg, V, U, T, X, cap, cdl, ob, po, idx, now, split, **kw)
        row = board_row(cfg, V, trades, dec, split, n_tried); out_rows.append(row)
        tr = [t for t in trades if t["status"] in ("closed", "open")]
        rets = [t["ret"] for t in tr]
        report["cells"][V["name"]] = {
            "T": T, "X": X, "cap": cap, "tag": tag, "universe": "broad45" if "broad" in tag else "signals",
            "decisions": {k: sum(d["status"] == k for d in dec) for k in ("pass", "fail", "no_liq", "no_candles")},
            "passed": [d["e"]["symbol"] for d in dec if d["status"] == "pass"],
            "no_liq": [d["e"]["symbol"] for d in dec if d["status"] == "no_liq"],
            "fail_why": {d["e"]["symbol"]: d["why"] for d in dec if d["status"] == "fail"},
            "trades_incl_open": len(tr), "closed": row["trades"], "open": row["open"],
            "pnl_incl_open": round(sum(t["pnl"] for t in tr), 2), "hit_rate_incl_open": round(sum(r > 0 for r in rets) / len(rets), 3) if rets else None,
            "median_incl_open": round(statistics.median(rets), 3) if rets else None, "mean_incl_open": round(statistics.fmean(rets), 3) if rets else None,
            "median_ci": boot_median(rets), "pnl_ex_best_incl_open": round(sum(t["pnl"] for t in tr) - max(t["pnl"] for t in tr), 2) if tr else None,
            "h1_pnl": round(sum(t["pnl"] for t in tr if t["t"] < half), 2), "h1_n": sum(t["t"] < half for t in tr),
            "h2_pnl": round(sum(t["pnl"] for t in tr if t["t"] >= half), 2), "h2_n": sum(t["t"] >= half for t in tr),
            "trades": [{"sym": t["e"]["symbol"], "status": t["status"], "entry": iso(t["t_entry"]), "chg_at_check": round(t["info"]["chg"], 3),
                        "liq_chg": round(t["info"].get("liq_chg", 0), 3), "liq_src": t["info"].get("liq_src"), "scout": t["info"].get("scout"),
                        "exit": t.get("exit"), "ret": round(t.get("ret", 0), 3), "pnl": round(t.get("pnl", 0), 2)} for t in trades]}
        for t in trades:
            trades_out.append({"variant": V["name"], "symbol": t["e"]["symbol"], "signal_ts": iso(t["e"]["t"]), "status": t["status"],
                               "entry_ts": iso(t["t_entry"]) if t.get("t_entry") else "", "entry_px": t.get("p_entry", ""),
                               "chg_at_check": round(t["info"]["chg"], 3), "liq_chg": round(t["info"].get("liq_chg", 0), 3),
                               "liq_src": t["info"].get("liq_src", ""), "exit": t.get("exit", ""), "ret": round(t.get("ret", 0), 3),
                               "pnl": round(t.get("pnl", 0), 2), "token": t["e"]["token"]})
    # lucky-number flags along every axis of the main grid (signals universe, sanity+scout on)
    fam = {}
    for T in TS:
        for X in XS:
            fam[f"SM_T{T}_X{int(X*100)}:cap"] = [(9.0 if c is None else c, vname(T, X, c)) for c in CAPS]
        for c in CAPS: fam[f"SM_T{T}_cap{capname(c)}:X"] = [(X, vname(T, X, c)) for X in XS]
    for X in XS:
        for c in CAPS: fam[f"SM_X{int(X*100)}_cap{capname(c)}:T"] = [(T, vname(T, X, c)) for T in TS]
    lf = scoring.lucky_flags(out_rows, fam)
    for r in out_rows: r["lucky_number"] = lf.get(r["variant"], "n/a (0 trades)" if not r["trades"] else "n/a (<5 trades)")
    report["variants_tried"] = n_tried
    keep = lambda n: "_bodystop" not in n or n in (vname(cT, cX, cC, "_bodystop"), vname(20, 0.2, None, "_bodystop"), vname(30, 0.2, None, "_bodystop"))
    atomic_write(os.path.join(OUT, "leaderboard_extra_SM.json"), json.dumps([r for r in out_rows if keep(r["variant"])], indent=0))
    atomic_write(os.path.join(OUT, "survivor_momentum.json"), json.dumps(report, indent=1, default=str))
    with open(os.path.join(OUT, "sm_trades.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(trades_out[0].keys())); w.writeheader(); w.writerows(trades_out)
    print(f"survivor_momentum: {len(sigs)} signals, {len(broad)} broad rows, {len(allV)} variants, variants_tried={n_tried}")

if __name__ == "__main__":
    main()
