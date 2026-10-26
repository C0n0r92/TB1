#!/usr/bin/env python3
"""Phase 2 (PAPER ONLY): rules distilled from winners/ profile, tested on the BACKFILL graduation universe
(data/backfill/candles1m, read-only) EXCLUDING every mint the winners traded. Holdout by date. -> out/wn_results.json, out/.wn_rows.json"""
import json, glob, os, random, csv, statistics as S, datetime as dt
from cl_sim import sim, stats, row, boot, DEFAULT, OUT, DUB
import scoring
W = list(csv.DictReader(open("/workspace/onchain-intel/winners/trades.csv")))
WM = {r["mint"] for r in W}
night = lambda t: (dt.datetime.fromtimestamp(t, DUB) - dt.timedelta(hours=12)).date().isoformat()
WN = {night(dt.datetime.fromisoformat(r["entry_time"].replace("Z", "+00:00")).timestamp()) for r in W}
U = {}
for p in glob.glob("data/backfill/candles1m/*.json"):
    d = json.load(open(p))
    if not d["rows"] or d["mint"] in WM: continue
    rows = [r for r in sorted(d["rows"]) if r[4] and r[4] > 0][2:]          # drop first 2 (migration print artefacts)
    if len(rows) < 30: continue
    U.setdefault(d["mint"], dict(rows=rows, supply=1e9, t0=d.get("t_mig") or rows[0][0]))
def feats(rows, i, T):
    """features from candles strictly before T (rows[:i])"""
    past = rows[:i]
    if len(past) < 3: return None
    c = past[-1][4]
    def back(sec):
        b = [r for r in past if r[0] <= T - sec]
        return c / b[-1][4] - 1 if b else None
    return dict(mcap=c * 1e9, chg5=back(300), chg60=back(3600), vol60=sum(r[5] for r in past if r[0] >= T - 3600),
                n30=sum(1 for r in past if r[0] >= T - 1800), age_h=None,
                accel=(sum(r[5] for r in past if r[0] >= T - 900) / 15) / max(1e-9, sum(r[5] for r in past if T - 3600 <= r[0] < T - 900) / 45))
RULES = {
 "R1_quiet_small": dict(age=(0.5, 6), mcap=(25e3, 60e3), n30_max=10, chg60=(-0.30, 0.50), chg5_min=None),
 "R2_fresh_not_chased": dict(age=(0.25, 6), mcap=(0, 100e3), n30_max=None, chg60=(-1, 0.50), chg5_min=0.15),
 "R3_vol_accel": dict(age=(0.25, 6), mcap=(10e3, 300e3), n30_max=None, chg60=(-1, 0.50), chg5_min=0.0, accel=2.0),
}
def scan(cs, R, step=300):
    rows = cs["rows"]; t0 = cs["t0"]; ts = [r[0] for r in rows]; import bisect
    T = t0 + int(R["age"][0] * 3600); T -= T % 60
    while T <= t0 + R["age"][1] * 3600 and T <= rows[-1][0]:
        i = bisect.bisect_left(ts, T); f = feats(rows, i, T)
        if f and R["mcap"][0] <= f["mcap"] <= R["mcap"][1] and (R["n30_max"] is None or f["n30"] <= R["n30_max"]) \
           and f["chg60"] is not None and R["chg60"][0] <= f["chg60"] <= R["chg60"][1] \
           and (R["chg5_min"] is None or (f["chg5"] is not None and f["chg5"] >= R["chg5_min"])) \
           and (R.get("accel") is None or (f["accel"] >= R["accel"] and f["vol60"] >= 5e3)):
            return T, f
        T += step
    return None, None
def run_rule(R, cfg, strict=False):
    tr = []
    for m, cs in U.items():
        T, f = scan(cs, R)
        if T is None or (strict and night(T) in WN): continue
        r = sim(cs, T, cfg)
        if r: r.update(mint=m, night=night(T), **{k: f[k] for k in ("mcap", "chg5", "chg60", "n30", "vol60")} if False else {}); tr.append(r)
    return tr
def rand_ctl(R, cfg, draws=20, seed=5):
    """random entry time in the same age window on every universe token (unconditional baseline)."""
    rnd = random.Random(seed); out = []
    for m, cs in U.items():
        t0 = cs["t0"]; hi = min(t0 + R["age"][1] * 3600, cs["rows"][-1][0])
        lo = t0 + R["age"][0] * 3600
        if hi <= lo: continue
        for _ in range(draws // 10):
            r = sim(cs, rnd.uniform(lo, hi), cfg)
            if r: out.append(r["ret"])
    return out
if __name__ == "__main__":
    allt = sorted(cs["t0"] for cs in U.values()); HO = allt[int(0.6 * (len(allt) - 1))]
    EXITS = {"dflt": DEFAULT, "quick": dict(DEFAULT, sl=0.20, tp=0.30, hold_m=30)}
    res = dict(universe=len(U), excluded_winner_mints=len(WM), holdout_after=HO, winner_nights=len(WN), tests={}, controls={})
    rows_out, cfgs, fams = [], [], {}
    def T_(name, R, cfg, strict=False, fam="wn", note=""):
        tr = run_rule(R, cfg, strict); st = stats(tr, HO)
        res["tests"][name] = dict(rule=R, cfg=cfg, strict=strict, **st); cfgs.append(dict(cfg, rule=R, strict=strict, name=name))
        r = row(name, tr, st, fam, note, False) if tr else None
        if r: rows_out.append(r)
        return st
    for rn, R in RULES.items():
        for en, cfg in EXITS.items():
            T_(f"WN_{rn}_{en}", R, cfg, note=f"winners-profile rule {rn}, exit {en}; backfill graduations excl. winner mints")
        T_(f"WN_{rn}_dflt_strictnights", R, DEFAULT, strict=True, note="also excludes every Dublin night a winner traded")
        res["controls"][rn] = {en: (lambda x: dict(n=len(x), mean=S.fmean(x) if x else None, ci=boot(x)))(rand_ctl(R, cfg)) for en, cfg in EXITS.items()}
    # neighbour sweeps (default exit): perturb each threshold
    swe = {"R1_quiet_small": [("mcap", [(15e3, 45e3), (25e3, 60e3), (35e3, 80e3)]), ("n30_max", [5, 10, 20]), ("chg60", [(-0.3, 0.25), (-0.3, 0.5), (-0.3, 1.0)])],
           "R2_fresh_not_chased": [("chg5_min", [0.08, 0.15, 0.30]), ("chg60", [(-1, 0.25), (-1, 0.5), (-1, 1.0)]), ("mcap", [(0, 60e3), (0, 100e3), (0, 200e3)])],
           "R3_vol_accel": [("accel", [1.5, 2.0, 3.0]), ("chg60", [(-1, 0.25), (-1, 0.5), (-1, 1.0)])]}
    for rn, lst in swe.items():
        for p, vals in lst:
            fam = f"WN_{rn}@{p}"; fams[fam] = []
            for k, v in enumerate(vals):
                R = dict(RULES[rn], **{p: v}); nm = f"WN_{rn}_dflt" if R == RULES[rn] else f"WN_{rn}__{p}{k}"
                if nm not in res["tests"]: T_(nm, R, DEFAULT, fam="wn_sweep", note=f"sweep {p}={v}")
                fams[fam].append((k, nm))
    flags = scoring.lucky_flags(rows_out, fams)
    for r in rows_out: r["lucky_number"] = flags.get(r["variant"], "n/a")
    json.dump(res, open(os.path.join(OUT, "wn_results.json"), "w"), indent=1, default=str)
    json.dump(dict(rows=rows_out, variant_configs=cfgs), open(os.path.join(OUT, ".wn_rows.json"), "w"), default=str)
    print("universe", len(U), "holdout after", dt.datetime.utcfromtimestamp(HO))
    for k, v in res["tests"].items():
        if v.get("trades"): print(f"{k:42s} n={v['trades']:3d} mean={v['mean_ret']:+.3f} ci=[{v["ci_lo"] or 0:+.3f},{v["ci_hi"] or 0:+.3f}] oos n={v['n_out']} m={v['oos_mean'] if v['oos_mean'] is None else round(v['oos_mean'],3)}")
    print(json.dumps(res["controls"], default=str))
