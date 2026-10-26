"""LIVE forward paper trader (PAPER ONLY). Uses only the latest snapshot rows (point-in-time book + model prob at that ts).
Buys YES on a bracket when p_model - avg_fill - taker_fee/share > margin. Fixed stake, walks the logged ask depth, one entry
per (variant, token). Settles on Gamma resolution. Variants = margin x fee_mode."""
import json, os, glob
import pmw_common as C

CFG = json.load(open(os.path.join(C.ROOT, "config.json")))
TF = os.path.join(C.DATA, "paper_trades.jsonl")

def variants():
    for fm in CFG["fee_modes"]:
        for m in CFG["margins"]: yield f"PMW_m{int(round(m*100)):02d}_{'fee' if fm=='market' else 'fee5'}", m, fm

def walk(asks, usd):
    got_sh = spent = 0.0
    for px, sz in asks:
        take = min(sz, (usd - spent) / px)
        got_sh += take; spent += take * px
        if spent >= usd - 1e-9: break
    return (spent / got_sh, got_sh, spent) if got_sh else (None, 0, 0)

def main():
    files = sorted(glob.glob(os.path.join(C.DATA, "snapshots", "*.jsonl")))
    if not files: return
    rows = C.read_jsonl(files[-1]); last = max(r["ts"] for r in rows); rows = [r for r in rows if r["ts"] == last]
    info = {r["event_id"]: r["model_info"] for r in rows if r.get("model_info")}
    have = {(t["variant"], t["token"]) for t in C.read_jsonl(TF)}
    new = []
    for r in rows:
        mi = info.get(r["event_id"]) or {}
        h = mi.get("hours_to_day_end")
        if r["p_model"] is None or r["ask"] is None or r["bid"] is None or not r.get("accepting"): continue
        if CFG.get("require_calib", True) and not mi.get("calib"): continue  # uncalibrated ensemble is over-dispersed
        if h is None or h < CFG.get("min_lead_h", 1.0) or h > CFG["max_lead_h"]: continue
        if not (CFG["min_ask"] <= r["ask"] <= CFG["max_ask"]) or r["spread"] > 0.10: continue
        avg, sh, spent = walk([tuple(x) for x in r["ask_depth"]], CFG["stake_usd"])
        if not avg or spent < CFG["stake_usd"] * 0.999: continue  # not enough logged depth for full stake
        for name, m, fm in variants():
            if (name, r["token"]) in have: continue
            sched = r.get("fee") if fm == "market" else {"rate": CFG["conservative_fee_rate"]}
            fee_sh = C.fee_per_share(avg, sched)
            edge = r["p_model"] - avg - fee_sh
            if edge > m:
                new.append({"variant": name, "margin": m, "fee_mode": fm, "t_entry": r["ts"], "token": r["token"], "event_id": r["event_id"],
                            "slug": r["slug"], "date": r["date"], "city": r["city"], "kind": r["kind"], "bracket": r["bracket"],
                            "p_model": r["p_model"], "ask": r["ask"], "avg_fill": round(avg, 4), "shares": round(sh, 4),
                            "cost": round(spent + fee_sh * sh, 4), "fee": round(fee_sh * sh, 4), "edge": round(edge, 4),
                            "hours_to_day_end": h, "mode": "live_forward", "model_version": CFG.get("model_version"), "calibrated": bool((mi or {}).get("calib"))})
                have.add((name, r["token"]))
    if new: C.append_jsonl(TF, new)
    print(f"paper: {len(new)} new paper entries at {last}")

def settled():
    res = {r["event_id"]: r for r in C.read_jsonl(os.path.join(C.DATA, "resolutions.jsonl"))}
    out = []
    for t in C.read_jsonl(TF):
        r = res.get(t["event_id"])
        if r:
            pay = t["shares"] if r["winner_token"] == t["token"] else 0.0
            t["pnl"] = round(pay - t["cost"], 4); t["ret"] = round(t["pnl"] / t["cost"], 4); t["won"] = int(pay > 0)
        else: t["pnl"] = None
        t["day"] = t["date"]; out.append(t)
    return out

if __name__ == "__main__":
    main()
