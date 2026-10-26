"""Score live forward paper trades and the backfill on Lab's METHOD rubric; neighbour sweep over margin; calibration;
write out/scorecard.md + out/*.json and upsert PMW_* rows into /workspace/lab/leaderboard.csv."""
import json, os, glob, collections, statistics as S
import pmw_common as C, pm_score as PS, paper

CFG = json.load(open(os.path.join(C.ROOT, "config.json")))
HALF_SPREAD = 0.02

def calib_table(pairs):
    """pairs: (p, outcome). Brier + reliability by 0.1 bucket."""
    if not pairs: return None, []
    br = S.fmean((p - o) ** 2 for p, o in pairs)
    b = collections.defaultdict(list)
    for p, o in pairs: b[min(9, int(p * 10))].append((p, o))
    rel = [(f"{k/10:.1f}-{(k+1)/10:.1f}", len(v), round(S.fmean(p for p, _ in v), 3), round(S.fmean(o for _, o in v), 3)) for k, v in sorted(b.items())]
    return round(br, 4), rel

def backfill_trades(margin, fee_mode):
    p = os.path.join(C.DATA, "backfill", "brackets.jsonl")
    out = []
    for r in C.read_jsonl(p):
        if r.get("price") is None or r.get("price_age_min", 999) > 360: continue
        ask = min(0.999, r["price"] + HALF_SPREAD)
        if not (CFG["min_ask"] <= ask <= CFG["max_ask"]): continue
        rate = (r.get("fee_rate") if fee_mode == "market" else CFG["conservative_fee_rate"])
        fee_sh = C.fee_per_share(ask, {"rate": rate if rate is not None else 0.05})
        edge = r["p_model"] - ask - fee_sh
        if edge <= margin: continue
        sh = CFG["stake_usd"] / ask; cost = CFG["stake_usd"] + fee_sh * sh
        pnl = sh * r["won"] - cost
        out.append({"t_entry": r["decision_ts"], "day": r["date"], "cost": cost, "pnl": pnl, "ret": pnl / cost, "slug": r["slug"],
                    "bracket": r["bracket"], "p_model": r["p_model"], "ask": ask})
    return out

def run_set(label, get_trades, prefix, note):
    res = {}
    for fm in CFG["fee_modes"]:
        sweep = []
        for m in CFG["margins"]:
            tr = get_trades(m, fm)
            PS.holdout_split(tr, CFG["holdout_frac"])
            sc = PS.score(tr) if tr else None
            sweep.append((m, sc or {"trades": 0, "net_profit_after_costs": 0}))
        fl = PS.lucky([(m, s) for m, s in sweep])
        for m, s in sweep:
            name = f"{prefix}_m{int(round(m*100)):02d}_{'fee' if fm=='market' else 'fee5'}"
            res[name] = dict(s, variant=name, lucky_number=fl[m], family="polymarket_weather", note=note.format(m=m, fm=fm))
    return res

def main():
    live = [t for t in paper.settled()]
    def live_trades(m, fm):
        name = f"PMW_m{int(round(m*100)):02d}_{'fee' if fm=='market' else 'fee5'}"
        return [dict(t) for t in live if t["variant"] == name and t["pnl"] is not None]
    n_open = collections.Counter(t["variant"] for t in live if t["pnl"] is None)
    R = {}
    R.update(run_set("live", live_trades, "PMW_live", "Polymarket weather LIVE forward paper; margin {m}; fee={fm}; $5 stake; real logged book depth"))
    R.update(run_set("backfill", backfill_trades, "PMW_bf", "Polymarket weather BACKFILL (OPTIMISTIC: ask=hist price+0.02, no depth); margin {m}; fee={fm}; decision=local day start-24h; day-2 det. forecasts"))
    for k, v in R.items():
        if k.startswith("PMW_live"): v["open"] = n_open.get(k.replace("PMW_live", "PMW"), 0)
    rows = [v for k, v in sorted(R.items())]
    tried_p = "/workspace/polymarket-lab/data/variants_tried.json"
    for r in rows: r["variants_tried"] = len(rows)
    PS.upsert_leaderboard(rows, "PMW_")
    # calibration (backfill: all brackets; market Brier only where a price existed -> subset)
    bfr = C.read_jsonl(os.path.join(C.DATA, "backfill", "brackets.jsonl"))
    bm, brel = calib_table([(r["p_model"], r["won"]) for r in bfr])
    sub = [r for r in bfr if r.get("price") is not None]
    bm_sub, _ = calib_table([(r["p_model"], r["won"]) for r in sub]); bk_sub, krel = calib_table([(r["price"], r["won"]) for r in sub])
    # live calibration: one point per token per lead bucket (first snapshot in bucket), resolved events only
    res = {r["event_id"]: r for r in C.read_jsonl(os.path.join(C.DATA, "resolutions.jsonl"))}
    seen = set(); lp = []; lk = []
    for f in sorted(glob.glob(os.path.join(C.DATA, "snapshots", "*.jsonl"))):
        info = {}
        for r in C.read_jsonl(f):
            if r.get("model_info"): info[(r["ts"], r["event_id"])] = r["model_info"]
            if r["event_id"] not in res or r["p_model"] is None or r["mid"] is None: continue
            h = (info.get((r["ts"], r["event_id"])) or {}).get("hours_to_day_end")
            if h is None: continue
            bkt = "0-12h" if h <= 12 else "12-24h" if h <= 24 else "24-48h" if h <= 48 else ">48h"
            if (r["token"], bkt) in seen: continue
            seen.add((r["token"], bkt)); o = int(res[r["event_id"]]["winner_token"] == r["token"])
            lp.append((r["p_model"], o)); lk.append((r["mid"], o))
    lm, lrel = calib_table(lp); lkm, _ = calib_table(lk)
    md = ["# Polymarket weather - scorecard (auto)", f"_updated {C.iso(C.now_utc())}_", "",
          "BACKFILL = historical replay, OPTIMISTIC fills. LIVE = forward paper test from logged books. Never mix them.", "",
          "| variant | trades | win | net $ | mean ret | CI95 | OOS | score | cand | lucky | MC DD p95 | open |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['variant']} | {r.get('trades',0)} | {r.get('win_rate','')} | {r.get('net_profit_after_costs','')} | {r.get('mean_ret','')} | {r.get('ci95_mean_ret','')} | {r.get('holds_out_of_sample','')} | {r.get('score_total','')} | {r.get('candidate','')} | {r.get('lucky_number','')} | {r.get('mc_dd_p95','')} | {r.get('open','')} |")
    md += ["", "## Calibration", f"- Backfill model Brier (all {len(bfr)} brackets): {bm}",
           f"- Backfill subset with a market price ({len(sub)} brackets, model p>=0.05 only): model {bm_sub} vs market {bk_sub} (lower is better)",
           f"- Live (resolved, one point per token per lead bucket, n={len(lp)}): model {lm} vs market mid {lkm}", "",
           "Backfill model reliability (bucket, n, mean p, hit rate):"] + [f"- {x}" for x in brel] + ["", "Live model reliability:"] + [f"- {x}" for x in lrel]
    open(os.path.join(C.OUT, "scorecard.md"), "w").write("\n".join(md) + "\n")
    json.dump({"rows": rows, "calib": {"bf_model": bm, "bf_model_sub": bm_sub, "bf_market_sub": bk_sub, "live_model": lm, "live_market": lkm,
               "bf_rel": brel, "bf_market_rel": krel, "live_rel": lrel}}, open(os.path.join(C.OUT, "score.json"), "w"), indent=1, default=str)
    print("\n".join(md[:30]))

if __name__ == "__main__":
    main()
