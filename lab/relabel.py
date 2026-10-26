#!/usr/bin/env python3
"""24h relabel (PAPER ONLY). Every token the radar ever scanned gets a FINAL label once it is >= 24 h past its first
scan (one DexScreener batch call per 30 due tokens, cached; never re-fetched), and a PROVISIONAL label before that.
  RUG      price at 24h <= -80% vs first scan, or pool liquidity <= 20% of first-scan liquidity
  dead     liquidity < $1k or no pair any more (not a RUG by price)
  runner   price at 24h >= +100% vs first scan
  survivor everything else (ret24 recorded)
Then guard evaluation: for each token's first scan row (and its best-score row), which rugguard categories fired
(live log or replay) vs the label -> out/guard_eval.md: rugs caught vs survivors/runners rejected per category, the
funded-rugger rule on its own, and the age gate at 0/15/30/45/60/90 min. Labels: data/labels.csv."""
import argparse, csv, json, os, sys, time
from labcore import *
import guards

LABELS = os.path.join(DATA, "labels.csv"); SNAP24 = os.path.join(DATA, "ds_24h.json")

def label_of(ret, liq_ratio, liq_now):
    if ret is None: return "dead"
    if ret <= -0.8 or (liq_ratio is not None and liq_ratio <= 0.2): return "RUG"
    if liq_now is not None and liq_now < 1000: return "dead"
    if ret >= 1.0: return "runner"
    return "survivor"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config"); ap.add_argument("--no-network", action="store_true")
    a = ap.parse_args(); cfg = load_config(a.config); now = time.time()
    rows = [r for r in read_jsonl(cfg["paths"]["radar_scanned"]) if valid_sol(r.get("token"))]
    for r in rows: r["t"] = ts_of(r["ts"])
    first, best = {}, {}
    for r in sorted(rows, key=lambda r: r["t"]):
        first.setdefault(r["token"], r)
        if (r.get("score") or 0) > (best.get(r["token"], {}).get("score") or -1): best[r["token"]] = r
    snap = load_json(SNAP24, {}) or {}
    due = [t for t, r in first.items() if now >= r["t"] + 86400 and t not in snap]
    if due and not a.no_network:
        for i in range(0, len(due), 30):
            res = get_json("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(due[i:i + 30]), cfg["fetch"]["dex_spacing_s"])
            if res is None: continue
            bestp = {}
            for p in res:
                t = (p.get("baseToken") or {}).get("address"); l = fnum((p.get("liquidity") or {}).get("usd"))
                if t in due and (t not in bestp or l > bestp[t]["liq"]):
                    bestp[t] = {"price": fnum(p.get("priceUsd")), "liq": l, "mcap": fnum(p.get("marketCap") or p.get("fdv")), "pair": p.get("pairAddress")}
            for t in due[i:i + 30]:
                snap[t] = {**bestp.get(t, {"price": None, "liq": 0}), "fetched_at": now, "late_h": round((now - first[t]["t"] - 86400) / 3600, 2)}
        atomic_write(SNAP24, json.dumps(snap))
    polls = liq_polls(); out = []
    for tok, r0 in first.items():
        p0, l0 = fnum(r0.get("price"), None), fnum(r0.get("liq"), None)
        c = load_candles(r0.get("pair")) or {}; cs = [x for x in c.get("rows", []) if r0["t"] <= x[0] <= r0["t"] + 86400]
        mx = max((x[2] for x in cs), default=None); mn = min((x[3] for x in cs), default=None)
        if tok in snap:
            s = snap[tok]; kind = "final"; pn, ln = s.get("price"), s.get("liq")
            if (not pn) and cs and cs[-1][0] >= r0["t"] + 86400 - 3600: pn = cs[-1][4]
        else:
            kind = "provisional"; pl = [p for p in polls.get(tok, []) if p["ts"] <= r0["t"] + 86400]
            if pl: pn, ln = pl[-1]["price"], pl[-1]["liq"]
            elif cs: pn, ln = cs[-1][4], None
            else:
                rl = [x for x in rows if x["token"] == tok]; pn, ln = fnum(rl[-1].get("price"), None), fnum(rl[-1].get("liq"), None)
        ret = (pn / p0 - 1) if pn and p0 else None
        lr = (ln / l0) if ln is not None and l0 else None
        out.append({"token": tok, "symbol": clean(r0.get("symbol")), "first_scan": r0["ts"], "label": label_of(ret, lr, ln), "kind": kind,
                    "due_utc": iso(r0["t"] + 86400), "ret24": round(ret, 3) if ret is not None else "", "liq_ratio": round(lr, 3) if lr is not None else "",
                    "max_up": round(mx / p0 - 1, 3) if mx and p0 else "", "max_down": round(mn / p0 - 1, 3) if mn and p0 else "",
                    "first_score": r0.get("score"), "best_score": best[tok].get("score"), "age_h_first": r0.get("age_h")})
    tmp = LABELS + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()) if out else ["token"]); w.writeheader(); w.writerows(out)
    os.replace(tmp, LABELS)
    guard_eval(cfg, rows, out, best, now)
    print(f"labels: {sum(o['kind']=='final' for o in out)} final, {sum(o['kind']=='provisional' for o in out)} provisional, "
          f"{len(due)} became due this run")

def guard_eval(cfg, rows, labels, best, now, min_score=55):
    """Per token use the best-scoring scan row (what would have been the signal). Only tokens whose best score >= 55."""
    lab = {l["token"]: l for l in labels}
    rs = sorted(rows, key=lambda r: r["t"]); ev = []
    for tok, r in best.items():
        if (r.get("score") or 0) < min_score: continue
        g = guards.replay(cfg, r, [x for x in rs if x["t"] < r["t"]])
        ages = [x.get("age_h") or 0 for x in rs if x["token"] == tok and (x.get("score") or 0) >= min_score]
        ev.append({"tok": tok, "sym": lab[tok]["symbol"], "label": lab[tok]["label"], "kind": lab[tok]["kind"], "ret": lab[tok]["ret24"],
                   "cats": set(g["cats"]) - {"launch_budget"}, "src": g["src"], "old": bool(g["old"]), "age_first_ok": min(ages) if ages else 0,
                   "age_max": max(ages) if ages else 0})
    bad = [e for e in ev if e["label"] in ("RUG", "dead")]; good = [e for e in ev if e["label"] in ("survivor", "runner")]
    L = [f"# Guard evaluation @ {iso(now)} (PAPER ONLY)", "",
         f"Tokens with a scan score >= {min_score}: {len(ev)} ({len(bad)} RUG/dead, {len(good)} survivor/runner). Labels: "
         f"{sum(e['kind']=='final' for e in ev)} final (24h), rest PROVISIONAL (label from the latest price, not 24h).",
         "Replay caveat: pre-guard rows use holder data fetched AFTER the scan unless src=replay_pit.", "",
         "| guard category | RUG/dead caught | survivors/runners rejected | uniquely rejected survivors |", "|---|---|---|---|"]
    cats = sorted({c for e in ev for c in e["cats"]} | {"age"})
    for c in cats:
        rc = [e for e in bad if c in e["cats"]]; sc = [e for e in good if c in e["cats"]]
        uniq = [e["sym"] for e in sc if e["cats"] == {c} or (e["cats"] - {"age"}) == {c}]
        L.append(f"| {c} | {len(rc)}/{len(bad)} | {len(sc)}/{len(good)} {', '.join(e['sym'] for e in sc)[:80]} | {', '.join(uniq)} |")
    # (b) rug timing: at what pair age did each RUG first trade <= -80% vs its signal price? A gate of X min only helps
    # against rugs that happen before age X (and costs whatever survivors move before age X).
    L += ["", "## (b) age gate: when do rugs happen? (pair age when price first <= -80% of the signal price; 5m candles)", "",
          "| token | label | age at signal (min) | age at -80% (min) | ret signal->age45 | ret age45->last |", "|---|---|---|---|---|---|"]
    timing = []
    for e in ev:
        r = best[e["tok"]]; c = load_candles(r.get("pair")) or {}; p0 = fnum(r.get("price"), None)
        cs = [x for x in c.get("rows", []) if x[0] >= r["t"] - 300]
        if not cs or not p0: continue
        a0 = (r.get("age_h") or 0) * 60
        age_at = lambda x: a0 + (x[0] - r["t"]) / 60
        rug = next((age_at(x) for x in cs if x[3] <= 0.2 * p0), None)
        c45 = next((x for x in cs if age_at(x) >= 45), None)
        r1 = (c45[1] / p0 - 1) if c45 else None; r2 = (cs[-1][4] / c45[1] - 1) if c45 else None
        timing.append((e, a0, rug))
        L.append(f"| {e['sym']} | {e['label']} | {a0:.0f} | {'' if rug is None else f'{rug:.0f}'} | "
                 f"{'' if r1 is None else f'{r1:+.0%}'} | {'' if r2 is None else f'{r2:+.0%}'} |")
    for m in (15, 20, 30, 45, 60, 90):
        n = sum(1 for e, a0, rug in timing if rug is not None and rug < m)
        L.append(f"- gate {m} min: {n}/{sum(1 for _, _, rg in timing if rg is not None)} candle-covered coins that ever hit -80% had done so before that age")
    L += ["", "Note: pre-guard signalled coins were never rescanned, so 'caught by the age gate' there means the radar "
          "would have had to rescan them later; in live operation a young coin is re-scored at the next scan.", "",
          "## per-token", "", "| token | label | ret24 | kind | guard categories | src |", "|---|---|---|---|---|---|"]
    for e in sorted(ev, key=lambda e: e["label"]):
        L.append(f"| {e['sym']} | {e['label']} | {e['ret']} | {e['kind']} | {', '.join(sorted(e['cats'])) or '-'}{' +old rejects' if e['old'] else ''} | {e['src']} |")
    atomic_write(os.path.join(OUT, "guard_eval.md"), "\n".join(L) + "\n")

if __name__ == "__main__":
    main()
