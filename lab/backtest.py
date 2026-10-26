#!/usr/bin/env python3
"""Lab backtest: PAPER ONLY. Replays radar scans / Chunk buys / copyfomo skips+copies against cached 5-min candles
with realistic costs, per variant from config.toml. Strictly point-in-time: a decision at time t only uses data with
timestamp <= t (scan row at t, candles that CLOSED before entry, intel snapshots valid at t, liq polls <= t).
Outputs: leaderboard.csv, out/trades.csv, out/summary.json, out/summary.txt.  No network."""
import argparse, csv, json, math, os, random, statistics, sys, time
from labcore import *
from sources import all_entries
import guards, scoring, copytrade

# ---------------- costs ----------------
def slip(cfg, liq, bet=None):
    C = cfg["costs"]; bet = C["bet_usd"] if bet is None else bet
    return min(C["max_slippage"], C["base_slippage"] + C["impact_mult"] * bet / max(liq or 0, C["liq_floor_usd"]))

class Liq:
    """Pool liquidity at time t: newest DexScreener poll <= t (within 30 min), else liq_at_signal*sqrt(p/p_signal)."""
    def __init__(self, polls, token, liq0, p0, default=20000.0):
        self.polls, self.liq0, self.p0, self.default = polls.get(token, []), liq0, p0, default
    def at(self, t, price):
        best = None
        for r in self.polls:
            if r["ts"] <= t and t - r["ts"] <= 1800: best = r
        if best: return best["liq"]
        if self.liq0 and self.p0 and price: return self.liq0 * math.sqrt(max(price, 1e-18) / self.p0)
        return self.default
    def min_ratio(self, t0, t1):
        v = [r["liq"] for r in self.polls if t0 <= r["ts"] <= t1]
        return (min(v) / self.liq0) if v and self.liq0 else None

def stake(cfg, V, e):
    C = cfg["costs"]; m = (e.get("_size") or 1.0) * V["size_mult"]
    if V["stake_pct"] > 0:
        assert V["stake_pct"] <= 0.15, f"{V['name']}: stake_pct above the 15% hard cap"
        return V["stake_pct"] * C["start_equity_usd"] * m
    return C["bet_usd"] * m

# ---------------- one trade ----------------
def simulate(cfg, V, e, candles, polls, now, reentry_ok=True):
    C, S = cfg["costs"], cfg["sim"]; bet, fee, fx = stake(cfg, V, e), C["fee_per_side"], C["fixed_cost_usd"]
    CS = S["candle_s"]; t0 = e["t"]
    delay = V["entry_delay_min"] + (e.get("_wait_min") or 0)
    t_in = t0 + delay * 60
    if now < t_in + CS: return {"status": "pending"}
    cs = [c for c in candles if c[0] >= t0]                                  # candles STARTING at/after the signal
    if not cs: return {"status": "no_candles"}
    if delay > 0 or not e.get("price"):
        ec = [c for c in cs if c[0] >= t_in]
        if not ec or ec[0][0] - t_in > 1800: return {"status": "skip", "why": "no trades near entry time (dead)"}
        t_entry, p_entry, path = ec[0][0], ec[0][1], ec
    else:
        t_entry, p_entry, path = t0, e["price"], cs
    p_sig = e.get("price") or p_entry
    liq = Liq(polls, e["token"], e.get("liq"), p_sig)
    if delay > 0:                                     # survival checks use only information at entry time
        chg = p_entry / p_sig - 1
        if chg < V["survive_max_dd"]: return {"status": "skip", "why": f"survival: price {chg:+.0%} at entry"}
        if chg > V["survive_max_up"]: return {"status": "skip", "why": f"chase cap: price {chg:+.0%} at entry"}
        if V["survive_min_liq_ratio"] and e.get("liq") and liq.at(t_entry, p_entry) / e["liq"] < V["survive_min_liq_ratio"]:
            return {"status": "skip", "why": "survival: liquidity shrank"}
    if e.get("age_h") is not None and not e.get("_reentry"):
        age_in = e["age_h"] + (t_entry - t0) / 3600
        if age_in < V["min_age_h"] - 1e-9 or age_in > V["max_age_h"]: return {"status": "skip", "why": f"pair age {age_in:.2f}h at entry"}
    L_in = liq.at(t_entry, p_entry)
    if V["max_ticket_pct"] > 0 and bet > V["max_ticket_pct"] * L_in:
        return {"status": "skip", "why": f"ticket ${bet:.0f} > {V['max_ticket_pct']:.1%} of pool ${L_in:,.0f}"}
    s_in = slip(cfg, L_in, bet); px_in = p_entry * (1 + s_in)
    units = u0 = (bet * (1 - fee) - fx) / px_in
    deadline = min(t_entry + V["max_hold_h"] * 3600, (e.get("_t_sig") or t0) + S["horizon_h"] * 3600)
    if S["dublin_close"]: deadline = min(deadline, next_dublin_close(t_entry))
    ladders = [tuple(x) for x in V["ladder"]] if V["ladder"] else ([(V["tp_mult"], V["tp_frac"])] if V["tp_mult"] else [])
    cash, li, hwm, lo, exit_t, exit_px, why = 0.0, 0, p_entry, p_entry, None, None, None
    fixed = p_entry * (1 + V["stop"])
    def sell(u, px, t):
        s = slip(cfg, liq.at(t, px), u * px); return u * px * (1 - s) * (1 - fee) - fx
    for c in path:
        st, o, h, l, cl = c[:5]
        if st >= deadline: break
        lvl = fixed
        if V["trail"] and hwm >= p_entry * (1 + V["trail_activate"]): lvl = max(lvl, hwm * (1 - V["trail"]))
        if li and V["trail_after_tp"]: lvl = max(lvl, hwm * (1 - V["trail_after_tp"]))
        lo = min(lo, l)
        if l <= lvl:                                     # stop (checked first = conservative)
            fill = min(o, cl) if o <= lvl else (cl if cl < lvl else lvl)   # gap-through fills at the candle close
            cash += sell(units, fill, st + CS); units = 0; exit_t, exit_px, why = st + CS, fill, "stop" if lvl == fixed else "trail"
            break
        while li < len(ladders) and units > 1e-18 and h >= p_entry * ladders[li][0]:
            u = min(units, u0 * ladders[li][1]) if V["ladder"] else units * ladders[li][1]
            cash += sell(u, p_entry * ladders[li][0], st + CS); units -= u; li += 1
        if units <= 1e-18: exit_t, exit_px, why = st + CS, p_entry * ladders[li - 1][0], "tp"; break
        hwm = max(hwm, h)
        if V["liq_exit_drop"] and liq.at(st + CS, cl) <= (1 - V["liq_exit_drop"]) * L_in:
            cash += sell(units, cl, st + CS); units = 0; exit_t, exit_px, why = st + CS, cl, "liq_exit"; break
        if V["time_stop_h"] and st + CS >= t_entry + V["time_stop_h"] * 3600 and hwm < p_entry * (1 + V["time_stop_gain"]):
            cash += sell(units, cl, st + CS); units = 0; exit_t, exit_px, why = st + CS, cl, "time_stop"; break
        if st + CS >= deadline:
            cash += sell(units, cl, st + CS); units = 0; exit_t, exit_px, why = st + CS, cl, "time"; break
    status = "closed"
    if units > 0:
        last = [c for c in path if c[0] < deadline]
        lastc = last[-1] if last else path[0]
        if now >= deadline:   # coin stopped trading before the deadline: sell at the last print
            cash += sell(units, lastc[4], deadline); exit_t, exit_px, why = deadline, lastc[4], "time (last print)"
        else:
            cash += sell(units, lastc[4], now); exit_t, exit_px, why = None, lastc[4], "open (marked)"; status = "open"
        units = 0
    rug = lo <= p_entry * (1 - C["rug_drawdown"])
    mr = liq.min_ratio(t_entry, exit_t or now)
    if mr is not None and mr <= 1 - C["rug_drawdown"]: rug = True
    if rug and why in ("stop", "trail", "time", "time (last print)", "liq_exit", "time_stop") and exit_px is not None \
            and exit_px <= p_entry * (1 - C["rug_drawdown"]):
        cash = min(cash, C["rug_max_recovery"] * bet)
    pnl = cash - bet
    out = {"status": status, "t_entry": t_entry, "p_entry": p_entry, "slip_in": s_in, "exit_t": exit_t, "exit_px": exit_px,
           "exit": why, "pnl": pnl, "ret": pnl / bet, "bet": bet, "rug": rug, "min_ret": lo / p_entry - 1, "tp_hit": li > 0}
    if V["reentry"] and reentry_ok and li > 0 and status == "closed":
        out["reentry"] = reentry(cfg, V, e, candles, polls, now, exit_t, L_in, t_entry, deadline)
    return out

def reentry(cfg, V, e, candles, polls, now, t_exit, L_in, t_entry, deadline):
    """Buy back ONCE after a take-profit: price pulls back 30-50% from the peak (never deeper), then a 5m close above the
    prior 3 highs on volume above their average, pool liquidity >= 80% of entry liquidity. Decided at the candle close,
    filled at the next candle open. Needs volume -> pre-volume candles return 'no volume'."""
    CS = cfg["sim"]["candle_s"]; R = V["reentry"]
    lo_pb, hi_pb = R.get("pullback_min", 0.30), R.get("pullback_max", 0.50)
    path = [c for c in candles if t_entry <= c[0] < deadline]
    peak, armed, liq = 0.0, False, Liq(polls, e["token"], e.get("liq"), e.get("price"))
    for i, c in enumerate(path):
        peak = max(peak, c[2])
        if c[0] + CS <= t_exit: continue
        dd = 1 - c[3] / peak
        if dd > hi_pb: return {"status": "none", "why": "pulled back > 50%"}
        if dd >= lo_pb: armed = True
        if not armed or i < 3: continue
        prev = path[i - 3:i]
        if c[4] > max(p[2] for p in prev):
            if len(c) < 6 or any(len(p) < 6 for p in prev): return {"status": "none", "why": "no volume data"}
            if c[5] <= statistics.fmean(p[5] for p in prev): continue
            if liq.at(c[0] + CS, c[4]) < 0.8 * L_in: continue
            if i + 1 >= len(path): return {"status": "none", "why": "trigger at window end"}
            n = path[i + 1]
            e2 = {**e, "t": n[0], "price": n[1], "liq": liq.at(c[0] + CS, c[4]), "_reentry": True, "_wait_min": 0,
                  "_t_sig": e.get("_t_sig") or e["t"], "symbol": (e.get("symbol") or "") + "(re)"}
            V2 = {**V, "entry_delay_min": 0}
            r = simulate(cfg, V2, e2, candles, polls, now, reentry_ok=False); r["e"] = e2; return r
    return {"status": "none", "why": "no setup"}

# ---------------- variant selection (point-in-time) ----------------
def make_filters(cfg, V_mod, idx):
    def pulse(V, e, sc):
        if V["pulse"] == "off": return sc, None, ""
        if not V_mod: return None, "pulse: no parser", "uncovered"
        v = V_mod.x_view(idx, e["t"])
        if v is None: return None, "pulse: no fresh data at signal time", "uncovered"
        if e["token"] in v["rugs"]: return None, "pulse: on rug list", ""
        b = v["buzz"].get(e["token"], "none")
        if b == "fading": return None, "pulse: buzz fading", ""
        if V["pulse"] == "require_rising" and b != "rising": return None, f"pulse: buzz {b}", ""
        return sc + (V["pulse_boost"] if b == "rising" else 0), None, f"buzz {b}"
    def scout(V, e, sc):
        if V["scout"] == "off": return sc, None, ""
        if not V_mod: return None, "scout: no parser", "uncovered"
        v = V_mod.oc_view(idx, e["t"])
        if v is None: return None, "scout: no fresh lists at signal time", "uncovered"
        h = holders_at(cfg, e["token"], e["t"])
        hs = (set(h.get("holders") or []) | ({h["creator"]} if h.get("creator") else set())) if h else set()
        if e["token"] in v["avoid_t"] or hs & v["avoid_w"]: return None, "scout: avoid-list token/creator/holder", ""
        n = len((hs & v["smart"]) | v["smart_buys"].get(e["token"], set()))
        return sc + min(V["scout_boost_max"], V["scout_boost"] * n), None, f"{n} smart" + ("" if h else ", no holder snapshot")
    return pulse, scout

_GI = {}
def guard_info(cfg, e, radar):
    k = (e["token"], e["t"])
    if k not in _GI:
        prev = [r for r in radar if r["t"] < e["t"]]
        _GI[k] = guards.replay(cfg, e, prev)
    return _GI[k]

def scout_policy(V, e):
    """-> (keep?, size multiplier, verdict). Verdict must be point-in-time (captured <= 15 min after the signal)."""
    if V["scout_creator"] == "off": return True, 1.0, ""
    v = e.get("scout_verdict")
    if not v:
        sc = guards.scout_at(e["token"], e["t"]); v = sc["verdict"] if sc and (sc["pit"] or V.get("scout_lookahead")) else "unknown"
    if v == "block": return False, 0, v
    if v == "caution":
        if V["scout_creator"] == "skip_caution": return False, 0, v
        if V["scout_creator"] == "half_caution": return True, 0.5, v
    return True, 1.0, v

def candidates(cfg, V, ents, filt):
    pulse, scout = filt; out, seen, notes = [], set(), {"uncovered": 0, "filtered": 0, "guard": {}, "scout": {}}
    rows = ents[V["source"]]; radar = ents["radar"]
    last_t = {}
    for r in radar: last_t[r["token"]] = max(last_t.get(r["token"], 0), r["t"])
    for e in rows:
        if e["token"] in seen: continue
        sc = e.get("score") or 0
        if V["source"] == "cluster" and not e.get("pit", True) and "LOOKAHEAD" not in V["name"]: continue   # forward-only unless labelled
        if V["source"] == "radar":
            if V["guard"] == "off":
                if e["rejects"] and not V["allow_rejects"]: continue
            else:
                g = guard_info(cfg, e, radar)
                if V["guard"] == "live" and g["src"] != "live": continue
                if g["old"] and not V["allow_rejects"]: continue
                if V["guard"] == "replay_pit" and not g["pit"]:
                    if sc >= V["min_score"]: notes["uncovered"] += 1
                    continue
                bad = sorted(set(g["cats"]) - set(V["guard_ignore"]) - {"age", "launch_budget"})
                sc = g["score"]
                if bad:
                    if sc >= V["min_score"]:
                        for c in bad: notes["guard"][c] = notes["guard"].get(c, 0) + 1
                    continue
                if sc < V["min_score"]: continue
                age = e.get("age_h") or 0
                if age < V["guard_min_age_h"]:
                    if "guard" in e or last_t.get(e["token"], 0) > e["t"]: continue   # radar rescans it: a later row decides
                    e = {**e, "_wait_min": (V["guard_min_age_h"] - age) * 60}   # never rescanned (old signal): wait in place
            if e["liq"] < V["min_liq"] or (e["mcap"] and e["liq"] / e["mcap"] < V["min_liq_mcap"]) or e["mcap"] > V["max_mcap"]: continue
            if e.get("top10") is not None and e["top10"] > V["max_top10"]: continue
            if V["entry_delay_min"] == 0 and not e.get("_wait_min") and (e["age_h"] < V["min_age_h"] or e["age_h"] > V["max_age_h"]): continue
        ok = True
        for fn in (pulse, scout):
            sc2, why, tag = fn(V, e, sc)
            if sc2 is None:
                if (e.get("score") or 0) >= V["min_score"] - 10: notes["uncovered" if tag == "uncovered" else "filtered"] += 1
                ok = False; break
            sc = sc2
        if not ok or (V["source"] == "radar" and sc < V["min_score"]): continue
        keep, mult, verdict = scout_policy(V, e)
        if verdict: notes["scout"][verdict] = notes["scout"].get(verdict, 0) + 1
        if not keep: continue
        if mult != 1.0: e = {**e, "_size": mult}
        if V["min_lp_locked"] >= 0:
            r = load_json(os.path.join(RUGC, e["token"] + ".json"))
            if not r or r.get("fetched_at", 0) - e["t"] > 900 or r.get("lp_locked") is None:
                notes["uncovered"] += 1; continue
            if r["lp_locked"] < V["min_lp_locked"]: continue
        seen.add(e["token"]); out.append(e)
    return out, notes

# ---------------- stats ----------------
def stats(cfg, trades):
    S, C = cfg["sim"], cfg["costs"]
    tr = sorted([t for t in trades if t["status"] == "closed"], key=lambda t: t["exit_t"])
    n = len(tr)
    d = {"trades": n, "open": sum(t["status"] == "open" for t in trades)}
    if not n: return d
    rets = [t["ret"] for t in tr]; eq, peak, mdd = C["start_equity_usd"], C["start_equity_usd"], 0.0
    for t in tr:
        eq += t["pnl"]; peak = max(peak, eq); mdd = max(mdd, peak - eq)
    rnd = random.Random(S["seed"]); bs = sorted(statistics.fmean(rnd.choices(rets, k=n)) for _ in range(S["bootstrap_iters"]))
    d.update(win_rate=sum(r > 0 for r in rets) / n, median_ret=statistics.median(rets), mean_ret=statistics.fmean(rets),
             net_pnl=sum(t["pnl"] for t in tr), staked=C["bet_usd"] * n, max_dd_usd=mdd, max_dd_pct=mdd / C["start_equity_usd"],
             rug_rate=sum(t["rug"] for t in tr) / n, ci_lo=bs[int(0.025 * len(bs))], ci_hi=bs[int(0.975 * len(bs)) - 1],
             first=min(t["t"] for t in tr), last=max(t["t"] for t in tr))
    return d

def expand_sweeps(cfg):
    """[[sweep]] base=<variant> param=<key> values=[...] -> generated variants '<base>@<param>=<v>' in one family."""
    base = {v["name"]: v for v in cfg["variants"]}; out = list(cfg["variants"]); fam = {}
    for sw in cfg.get("sweep", []):
        B = base[sw["base"]]; f = f"{sw['base']}:{sw['param']}"; mem = fam.setdefault(f, [])
        for val in sw["values"]:
            if B.get(sw["param"]) == val: mem.append((val, B["name"])); continue
            nv = {**B, sw["param"]: val, "name": f"{sw['base']}@{sw['param']}={val}", "_family": f, "note": ""}
            if sw["param"] == "entry_delay_min": nv["name"] = f"{sw['base']}@wait={val}m"
            out.append(nv); mem.append((val, nv["name"]))
    return out, fam

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config"); ap.add_argument("--only", help="comma list of variant names")
    a = ap.parse_args(); cfg = load_config(a.config); S = cfg["sim"]; now = time.time()
    os.makedirs(OUT, exist_ok=True)
    ents = all_entries(cfg); idx = intel_index(cfg); Vm = radar_intel_module(cfg); filt = make_filters(cfg, Vm, idx)
    polls = liq_polls(); cache = {}
    def cdl(pair):
        if pair not in cache: c = load_candles(pair) if pair else None; cache[pair] = [tuple(r) for r in c["rows"]] if c else []
        return cache[pair]
    radar_ok = [e for e in ents["radar"] if not e["rejects"]]
    split = parse_ts(S["holdout_start"]) if S.get("holdout_start") else None
    if split is None and radar_ok:
        ts = sorted(e["t"] for e in radar_ok); split = ts[min(len(ts) - 1, int(len(ts) * (1 - S["holdout_fraction"])))]
    rows, board, allt = [], [], []
    allv, families = expand_sweeps(cfg)
    allv += copytrade.variant_defs(cfg)
    variants = [v for v in allv if not a.only or v["name"] in a.only.split(",")]
    n_tried = scoring.variants_tried(allv)
    for V in variants:
        cands, notes = candidates(cfg, V, ents, filt) if V["source"] in ents else ([], {"uncovered": 0, "filtered": 0, "guard": {}, "scout": {}})
        trades, open_exits = [], []
        res = []
        if V["source"] == "trader_trades":
            trades = copytrade.run(cfg, V, split); notes["guard"] = {}; res = None
        for e in cands if res is not None else []:
            r = simulate(cfg, V, e, cdl(e.get("pair")), polls, now); r.update(e=e); res.append(r)
            re_ = r.pop("reentry", None)
            if re_ and re_.get("status") in ("closed", "open"): res.append(re_)
            elif re_: notes.setdefault("reentry_none", {}); notes["reentry_none"][re_["why"]] = notes["reentry_none"].get(re_["why"], 0) + 1
        res = res or []
        res.sort(key=lambda r: (r.get("t_entry", r["e"]["t"]), -(r["e"].get("score") or 0)))
        for r in res:                                     # max concurrent positions
            if r["status"] in ("closed", "open"):
                open_exits = [x for x in open_exits if x > r["t_entry"]]
                if len(open_exits) >= S["max_open"]: r.update(status="skip", why=f"max_open {S['max_open']}")
                else: open_exits.append(r["exit_t"] or 1e18)
            r["t"] = r["e"]["t"]; r["is_oos"] = split is not None and r["t"] >= split
            trades.append(r)
        closed = sorted([t for t in trades if t["status"] == "closed"], key=lambda t: t["exit_t"])
        st_all = stats(cfg, trades); st_in = stats(cfg, [t for t in trades if not t["is_oos"]]); st_out = stats(cfg, [t for t in trades if t["is_oos"]])
        cnt = {k: sum(t["status"] == k for t in trades) for k in ("closed", "open", "skip", "pending", "no_candles")}
        if st_out["trades"] < S["min_oos_trades"]: hold = f"insufficient (n_out={st_out['trades']}<{S['min_oos_trades']})"
        elif st_in.get("net_pnl", 0) > 0 and st_out.get("mean_ret", -1) > 0 and st_out.get("ci_lo", -1) > 0: hold = "yes"
        elif st_in.get("net_pnl", 0) > 0 and st_out.get("mean_ret", -1) > 0: hold = "weak (OOS mean>0, CI spans 0)"
        else: hold = "no"
        waiting = not cands and (notes["uncovered"] or V["source"] != "radar" or V["min_lp_locked"] >= 0)
        if V["source"] == "trader_trades": waiting = not trades
        mc = scoring.mc_drawdown([t["pnl"] for t in closed], cfg["costs"]["start_equity_usd"], S.get("mc_iters", 1000), S["seed"])
        scr = scoring.score(st_all, st_out, closed, mc)
        cand = scr["score_total"] >= 18 and st_all["trades"] >= 50 and hold == "yes" and "LOOKAHEAD" not in V["name"] and V.get("guard") != "replay"  # optimistic variants never qualify
        board.append({"variant": V["name"], "trades": st_all["trades"],
                      "win_rate": round(st_all.get("win_rate", 0), 3) if st_all["trades"] else "",
                      "net_profit_after_costs": round(st_all.get("net_pnl", 0), 2) if st_all["trades"] else "",
                      "max_drawdown": round(st_all.get("max_dd_usd", 0), 2) if st_all["trades"] else "",
                      "holds_out_of_sample": "waiting for data" if waiting else hold,
                      "n_in_sample": st_in["trades"], "n_out_of_sample": st_out["trades"],
                      "mean_ret": round(st_all["mean_ret"], 3) if st_all["trades"] else "",
                      "median_ret": round(st_all["median_ret"], 3) if st_all["trades"] else "",
                      "ci95_mean_ret": f"[{st_all['ci_lo']:+.2f},{st_all['ci_hi']:+.2f}]" if st_all["trades"] else "",
                      "rug_rate": round(st_all["rug_rate"], 3) if st_all["trades"] else "",
                      "open": cnt["open"], "skipped": cnt["skip"], "pending": cnt["pending"], "no_candles": cnt["no_candles"],
                      "uncovered": notes["uncovered"], "filtered_out": notes["filtered"],
                      "oos_mean_ret": round(st_out["mean_ret"], 3) if st_out["trades"] else "",
                      "in_net_pnl": round(st_in.get("net_pnl", 0), 2) if st_in["trades"] else "",
                      "out_net_pnl": round(st_out.get("net_pnl", 0), 2) if st_out["trades"] else "",
                      **{k: scr[k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total")},
                      "net_ex_best_trade": round(sum(t["pnl"] for t in closed) - max(t["pnl"] for t in closed), 2) if closed else "",
                      "mc_dd_p5": round(mc[0], 3) if mc else "", "mc_dd_p50": round(mc[1], 3) if mc else "",
                      "mc_dd_p95": round(mc[2], 3) if mc else "", "nights": scr["nights"], "nights_profitable": scr["nights_profitable"],
                      "candidate": "yes" if cand else "no", "lucky_number": "", "variants_tried": n_tried,
                      "family": V.get("_family", ""), "guard_rejects": ";".join(f"{k}={v}" for k, v in sorted(notes.get("guard", {}).items())),
                      "scout_verdicts": ";".join(f"{k}={v}" for k, v in sorted(notes.get("scout", {}).items())),
                      "reentry_none": ";".join(f"{k}={v}" for k, v in sorted(notes.get("reentry_none", {}).items())),
                      "note": V.get("note", "")})
        for t in trades:
            e = t["e"]
            allt.append({"variant": V["name"], **{k: "" for k in ("signal_ts","symbol","score","status","why_skipped","entry_ts","entry_px","slip_in","exit_ts","exit_px","exit","pnl_usd","ret","min_ret","rug","sample","liq_at_signal","token","pair","src")}, **(t.get("row") or {})}) if t.get("row") else allt.append({"variant": V["name"], "signal_ts": iso(e["t"]), "symbol": clean(e.get("symbol")), "score": e.get("score"),
                         "status": t["status"], "why_skipped": t.get("why", ""), "entry_ts": iso(t["t_entry"]) if t.get("t_entry") else "",
                         "entry_px": t.get("p_entry", ""), "slip_in": round(t["slip_in"], 4) if t.get("slip_in") is not None else "",
                         "exit_ts": iso(t["exit_t"]) if t.get("exit_t") else "", "exit_px": t.get("exit_px", ""), "exit": t.get("exit", ""),
                         "pnl_usd": round(t["pnl"], 2) if "pnl" in t else "", "ret": round(t["ret"], 3) if "ret" in t else "",
                         "min_ret": round(t["min_ret"], 3) if "min_ret" in t else "", "rug": int(t.get("rug", False)),
                         "sample": "out" if t["is_oos"] else "in", "liq_at_signal": round(e.get("liq") or 0), "token": e["token"],
                         "pair": e.get("pair") or "", "src": e["src"], "bet": round(t["bet"], 2) if t.get("bet") else ""})
        rows.append((V, st_all, st_in, st_out))
    lf = scoring.lucky_flags(board, families)
    for bb in board: bb["lucky_number"] = lf.get(bb["variant"], "n/a" if not bb["trades"] else ("no" if bb["variant"] in lf else "untested"))
    cols = list(board[0].keys()) if board else ["variant"]
    # keep rows from side tracks (e.g. polymarket-weather PMW_*, polymarket-updown PMUD_*) that write out/leaderboard_extra_*.json
    import glob as _glob
    extra_rows = []
    for _p in [_q for _q in sorted(_glob.glob(os.path.join(OUT, "leaderboard_extra_*.json"))) if os.path.basename(_q)[18:20] in ("SM", "CL", "WN", "FS", "MC", "BF", "CR", "MR", "L2", "SW", "FE", "ES", "IF")]:   # 2026-10-23: survivor_momentum SM_*, copy fee sensitivity FS_*, 30d copy replay CR_*, midcap momentum MC_*, backfill replay BF_* rows, mean-reversion dip MR_* (2026-10-24), swing 4h/1d SW_* (2026-10-24), fast exit FE_* (2026-10-24), exit-signal ES_* (2026-10-24), inflow-spike proxy IF_* (2026-10-24); Polymarket PMW_/PMUD_ moved to Oracle and stay unmerged
        try: extra_rows += [r for r in json.load(open(_p)) if r.get("variant") not in {b["variant"] for b in board}]
        except Exception: pass
    with open(os.path.join(LAB, "leaderboard.csv") + ".tmp", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(board); w.writerows(extra_rows)
    os.replace(os.path.join(LAB, "leaderboard.csv") + ".tmp", os.path.join(LAB, "leaderboard.csv"))
    with open(os.path.join(OUT, "trades.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(allt[0].keys()) if allt else ["variant"]); w.writeheader(); w.writerows(allt)
    # data accrual
    sc = read_jsonl(cfg["paths"]["radar_scanned"]); sg = read_jsonl(cfg["paths"]["radar_signals"])
    span_h = (max(ts_of(r["ts"]) for r in sc) - min(ts_of(r["ts"]) for r in sc)) / 3600 if sc else 0
    acc = {"scan_rows": len(sc), "scan_runs": len({r["ts"] for r in sc}), "distinct_tokens": len({r["token"] for r in sc}),
           "signals": len(sg), "span_h": round(span_h, 2), "first": sc[0]["ts"] if sc else None, "last": sc[-1]["ts"] if sc else None,
           "signals_per_h": round(len(sg) / span_h, 2) if span_h else None,
           "new_tokens_per_h": round(len({r['token'] for r in sc}) / span_h, 2) if span_h else None,
           "liq_polls": sum(len(v) for v in polls.values()), "intel_snapshots": len(idx),
           "chunk_buys": len(ents["chunk_live"]), "copyfomo_skips": len(ents["copyfomo_skips"]), "copyfomo_copies": len(ents["copyfomo_trades"]),
           "split": iso(split) if split else None}
    acc["variants_tried"] = n_tried
    summ = {"generated": iso(now), "config": {k: cfg[k] for k in ("costs", "sim")}, "accrual": acc, "leaderboard": board}
    atomic_write(os.path.join(OUT, "summary.json"), json.dumps(summ, indent=1, default=str))
    L = [f"Lab backtest @ {iso(now)} (PAPER ONLY). ${cfg['costs']['bet_usd']:.0f}/trade, fee {cfg['costs']['fee_per_side']:.0%}/side, "
         f"slippage {cfg['costs']['base_slippage']:.1%} + {cfg['costs']['impact_mult']:g}x size/liq, gap-through stops fill at candle close, "
         f"max {S['max_open']} open, flat by 08:00 Dublin. OOS split at {acc['split']}.",
         f"Data: {acc['scan_rows']} scan rows / {acc['scan_runs']} scans / {acc['distinct_tokens']} tokens / {acc['signals']} radar signals "
         f"over {acc['span_h']} h ({acc['signals_per_h']}/h). Chunk buys {acc['chunk_buys']}, copyfomo skips {acc['copyfomo_skips']}, copies {acc['copyfomo_copies']}.", "",
         f"variants tried so far (multiple-testing count): {n_tried}", "",
         f"{'variant':<34}{'n':>3}{'in/out':>7}{'win':>5}{'median':>8}{'mean':>7}{'CI95 mean':>16}{'P&L $':>8}{'maxDD $':>8}{'rug':>5}  OOS"]
    for b in board:
        L.append(f"{b['variant'][:33]:<34}{b['trades']:>3}{str(b['n_in_sample'])+'/'+str(b['n_out_of_sample']):>7}"
                 f"{(format(b['win_rate'],'.0%') if b['trades'] else '-'):>5}{(format(b['median_ret'],'+.0%') if b['trades'] else '-'):>8}"
                 f"{(format(b['mean_ret'],'+.0%') if b['trades'] else '-'):>7}{b['ci95_mean_ret'] or '-':>16}"
                 f"{(format(b['net_profit_after_costs'],'+.2f') if b['trades'] else '-'):>8}{(format(b['max_drawdown'],'.2f') if b['trades'] else '-'):>8}"
                 f"{(format(b['rug_rate'],'.0%') if b['trades'] else '-'):>5}  {b['holds_out_of_sample']}"
                 + f"  score {b['score_total']}/25" + (f" LUCKY" if str(b['lucky_number']).startswith('yes') else "")
                 + (f"  (+{b['open']} open, {b['skipped']} skipped, {b['pending']} pending)" if b['open'] or b['skipped'] or b['pending'] else ""))
    L += ["", "Any variant with < ~50 closed trades (and < 20 out-of-sample) is noise. Do not pick winners off this table yet."]
    atomic_write(os.path.join(OUT, "summary.txt"), "\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
