"""SOL trend/breakout research run (PAPER). Writes out/*.csv|json, out/summary.json; leaderboard rows SOLT_*.
Usage: .venv/bin/python run.py"""
import os, json, itertools, time, hashlib, csv
import numpy as np, pandas as pd
import engine as E
ROOT = E.ROOT; OUT = os.path.join(ROOT, "out"); LAB = "/workspace/lab"
RNG = np.random.default_rng(7)
H5 = 1 / 12   # hours per 5m bar

# ---------- data ----------
d5 = E.load5()
t5 = d5.t.values.astype(np.int64)
gaps5 = int(((np.diff(t5) != 300)).sum()); gap_list = [(int(t5[i]), int(t5[i + 1] - t5[i])) for i in np.where(np.diff(t5) != 300)[0]]
T0, T1 = int(t5[0]), int(t5[-1])
BARS = {}
for tf in E.TF_MIN:
    b = E.indicators(E.resample(d5, tf)); BARS[tf] = b
# sanity: resampled 1h vs native 1h
n1 = pd.read_csv(os.path.join(E.DATA, "SOLUSDT_1h.csv")); n1["t"] = n1.t // 1000
mm = BARS["1h"].merge(n1, on="t", suffixes=("", "_n"))
resample_check = float((mm.c - mm.c_n).abs().max())
cb = pd.read_csv(os.path.join(E.DATA, "COINBASE_SOLUSD_1h.csv"))
mc_ = BARS["1h"].merge(cb, on="t", suffixes=("", "_cb"))
cb_basis = float(((mc_.c / mc_.c_cb - 1).abs()).median()) if len(mc_) else None

warm_t = int(BARS["4h"].tc.values[210])          # first time every TF has 210 bars of warm-up
HOLD = warm_t + int(0.6 * (T1 - warm_t))          # holdout: last 40% of usable time is out-of-sample
FIX = {}
for tf, b in BARS.items():
    m = np.full(len(t5), -1, np.int64); idx = ((b.tc.values - T0) // 300).astype(np.int64)
    ok = (idx >= 0) & (idx < len(t5)); ok[ok] &= t5[idx[ok]] == b.tc.values[ok]; m[idx[ok]] = np.where(ok)[0]; FIX[tf] = m

# ---------- carry (per 5m bar, fraction of notional) ----------
zero = np.zeros(len(t5))
JUP_L = 0.00003 * H5; JUP_S = 0.00003 * H5      # Jupiter borrow: assume 0.003%/h both sides (observed 0.0016%/h long, 0.0007%/h short; utilisation varies)
fund = pd.read_csv(os.path.join(E.DATA, "OKX_SOL_funding.csv"))
fr = np.full(len(t5), np.nan)
ft = (fund.fundingTime.values // 1000).astype(np.int64); rate = fund.realizedRate.values
pos = np.searchsorted(t5, ft)
for i in range(len(ft) - 1): fr[pos[i]:pos[i + 1]] = rate[i + 1] / 8 * H5     # rate paid at the NEXT funding stamp accrues over the interval
have = ~np.isnan(fr)
FALL = 0.00003 * H5   # conservative fallback outside OKX history: pay 0.003%/h whatever the side
DRIFT_L = np.where(have, fr, FALL); DRIFT_S = np.where(have, -fr, FALL)
CARRY = {"spot": (zero, zero), "jup": (np.full(len(t5), JUP_L), np.full(len(t5), JUP_S)), "drift": (DRIFT_L, DRIFT_S)}
PERP_FEE = 0.0006   # Jupiter base fee 0.06%/side; Drift(now Velocity) regular taker 6 bps
COSTS = {"spot": {"lo": 0.001, "mid": 0.002, "hi": 0.003},
         "jup": {"lo": PERP_FEE + 0.0005, "mid": PERP_FEE + 0.001, "hi": PERP_FEE + 0.002},
         "drift": {"lo": PERP_FEE + 0.0005, "mid": PERP_FEE + 0.001, "hi": PERP_FEE + 0.002}}

SIGCACHE = {}
def sig(tf, trend, level, confirm):
    k = (tf, trend, level, confirm)
    if k not in SIGCACHE: SIGCACHE[k] = E.signals(BARS[tf], trend, level, confirm)
    return SIGCACHE[k]

def run(V):
    b = BARS[V["tf"]]; L, S = sig(V["tf"], V["trend"], V["level"], V["confirm"])
    cL, cS = CARRY[V["venue"]]
    tr = E.simulate(t5, d5.o.values, d5.h.values, d5.l.values, b.tc.values.astype(np.int64), b.c.values, b.atr.values, L, S, FIX[V["tf"]],
                    1 if V["side"] == "ls" else 0, V["stop"], 1 if V["exit"].startswith("trail") else 0,
                    float(V["exit"][2:]) if V["exit"].startswith("rr") else 0.0, float(V["exit"][5:]) if V["exit"].startswith("trail") else 0.0,
                    V["cycle"] * 60, COSTS[V["venue"]][V["cost"]], cL, cS, 0)
    return tr

def boot_ci(r, n=1000):
    if len(r) < 2: return (np.nan, np.nan)
    m = r[RNG.integers(0, len(r), (n, len(r)))].mean(1); return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))

def mc_dd(r, n=1000, stake=100.0):
    if len(r) == 0: return (np.nan,) * 3
    x = np.array([RNG.permutation(r) for _ in range(n)]) * stake
    eq = 100 + np.cumsum(x, 1); pk = np.maximum.accumulate(np.concatenate([np.full((n, 1), 100.0), eq], 1), 1)[:, 1:]
    dd = ((pk - eq).max(1)) / 100.0; return tuple(float(np.quantile(dd, q)) for q in (0.05, 0.5, 0.95))

def stats(tr, full=False):
    r = tr[:, 5] if len(tr) else np.zeros(0); ins = tr[:, 0] < HOLD if len(tr) else np.zeros(0, bool)
    ri, ro = r[ins], r[~ins]
    s = {"trades": len(r), "n_in": int(ins.sum()), "n_out": int((~ins).sum()),
         "mean": float(r.mean()) if len(r) else np.nan, "win": float((r > 0).mean()) if len(r) else np.nan,
         "pnl": float(r.sum() * 100), "pnl_in": float(ri.sum() * 100), "pnl_out": float(ro.sum() * 100),
         "mean_in": float(ri.mean()) if len(ri) else np.nan, "mean_out": float(ro.mean()) if len(ro) else np.nan,
         "sr_in": float(ri.mean() / ri.std()) if len(ri) > 2 and ri.std() > 0 else np.nan,
         "sr_out": float(ro.mean() / ro.std()) if len(ro) > 2 and ro.std() > 0 else np.nan,
         "t_in": float(ri.mean() / ri.std() * np.sqrt(len(ri))) if len(ri) > 2 and ri.std() > 0 else -9,
         "cum_out": float(np.prod(1 + ro) - 1) if len(ro) else 0.0, "cum_all": float(np.prod(1 + r) - 1) if len(r) else 0.0}
    if full:
        s["ci"] = boot_ci(r); s["ci_out"] = boot_ci(ro); s["mc"] = mc_dd(r)
        mo = pd.Series(r * 100, index=pd.to_datetime(tr[:, 1], unit="s")).resample("MS").sum() if len(r) else pd.Series(dtype=float)
        # months with no trade count as flat (not profitable)
        allm = pd.date_range(pd.to_datetime(warm_t, unit="s").normalize().replace(day=1), pd.to_datetime(T1, unit="s"), freq="MS")
        mo = mo.reindex(allm, fill_value=0.0); s["months"] = len(mo); s["months_prof"] = int((mo > 0).sum())
        roll = mo.rolling(3).sum().dropna(); s["roll3_prof"] = float((roll > 0).mean()) if len(roll) else np.nan
        s["ex_best"] = float((r.sum() - r.max()) * 100) if len(r) else np.nan
        # equity-curve max DD in trade order, $100 per trade
        eq = 100 + np.cumsum(r * 100); s["dd_hist"] = float(((np.maximum.accumulate(np.r_[100, eq])[1:] - eq).max()) / 100) if len(r) else 0
        hold = (tr[:, 1] - tr[:, 0]) / 3600; s["hold_h_med"] = float(np.median(hold)) if len(r) else np.nan
        s["exposure_out"] = float(hold[~ins].sum() * 3600 / (T1 - HOLD)) if len(r) else 0
    return s

def score(s):
    sc = {}
    r = s["sr_out"]; sc["sc_oos_risk"] = 1 if (s["n_out"] < 2 or not np.isfinite(r) or r <= 0) else 2 if r < 0.1 else 3 if r < 0.2 else 4 if r < 0.35 else 5
    p95 = s["mc"][2]; sc["sc_drawdown"] = 1 if p95 > 0.5 else 2 if p95 > 0.3 else 3 if p95 > 0.2 else 4 if p95 > 0.1 else 5
    n = s["trades"]; sc["sc_trades"] = 1 if n < 10 else 2 if n < 25 else 3 if n < 50 else 4 if n < 100 else 5
    m = s["mean"]; sc["sc_edge"] = 5 if s["ci"][0] > 0 else 4 if m > 0.05 else 3 if m > 0 else 2 if m > -0.05 else 1
    f = s["months_prof"] / s["months"] if s["months"] >= 3 else 0
    sc["sc_stability"] = 5 if f >= 0.8 else 4 if f >= 0.6 else 3 if f >= 0.5 else 2 if f >= 0.3 else 1
    sc["score_total"] = sum(sc.values()); return sc

def holds(s):
    return "yes" if (s["n_out"] >= 20 and s["pnl_in"] > 0 and s["mean_out"] > 0 and s["ci_out"][0] > 0) else \
        (f"insufficient (n_out={s['n_out']}<20)" if s["n_out"] < 20 else "no")

def name(V):
    return "SOLT_{track}_{tf}_{trend}_{level}_{confirm}_s{stop}_{exit}_{venue}_c{cost}_cy{cycle}".format(**V)

# ---------- main grid ----------
GRID = dict(tf=["5m", "15m", "1h", "4h"], trend=["none", "ema200", "ema50_200", "hhhl"], level=["n20", "n55", "pivot"],
            confirm=["close", "vol", "retest"], stop=[1.5, 2.0, 3.0], exit=["rr2", "rr3", "trail3"])
TRACKS = {"A": dict(side="long", venue="spot"), "B": dict(side="ls", venue="jup")}
tried = set(); rows = {}
t_start = time.time()
for track, base in TRACKS.items():
    for combo in itertools.product(*GRID.values()):
        V = dict(zip(GRID.keys(), combo), track=track, cost="mid", cycle=5, **base)
        tr = run(V); s = stats(tr); rows[name(V)] = (V, s); tried.add(name(V))
print("grid done", len(rows), round(time.time() - t_start, 1), "s", flush=True)
grid_df = pd.DataFrame([{**V, **{k: v for k, v in s.items()}} for V, s in rows.values()])
grid_df.to_csv(os.path.join(OUT, "grid.csv"), index=False)

# ---------- buy & hold ----------
c5 = d5.c.values; o5 = d5.o.values
def bh(t_a, t_b, cost):
    ia, ib = np.searchsorted(t5, t_a), np.searchsorted(t5, t_b) - 1
    seg = c5[ia:ib + 1]; ret = seg[-1] / o5[ia] * (1 - cost) ** 2 - 1
    dd = float((1 - seg / np.maximum.accumulate(seg)).max()); return float(ret), dd
BH = {"in": bh(warm_t, HOLD, 0.002), "out": bh(HOLD, T1, 0.002), "all": bh(warm_t, T1, 0.002)}

# ---------- selection (in-sample only) ----------
def pick(track, k=5, min_in=30):
    g = grid_df[(grid_df.track == track) & (grid_df.n_in >= min_in)].sort_values("t_in", ascending=False)
    return g.head(k)
DEFAULTS = {  # pre-registered "boring" settings, written before looking at results
    "A": [dict(tf="1h", trend="ema50_200", level="n20", confirm="close", stop=2.0, exit="trail3"),
          dict(tf="4h", trend="ema200", level="n55", confirm="close", stop=2.0, exit="trail3")],
    "B": [dict(tf="1h", trend="ema50_200", level="n20", confirm="close", stop=2.0, exit="trail3"),
          dict(tf="4h", trend="ema200", level="n55", confirm="close", stop=2.0, exit="trail3")]}

def neighbours(V):
    out = []
    if V["level"].startswith("n"):
        Ns = [10, 20, 30, 40, 55, 80, 100]; i = Ns.index(int(V["level"][1:]))
        for j in (i - 1, i + 1):
            if 0 <= j < len(Ns): out.append(("level", f"n{Ns[j]}"))
    st = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]; i = st.index(V["stop"])
    for j in (i - 1, i + 1):
        if 0 <= j < len(st): out.append(("stop", st[j]))
    ex = ["rr1.5", "rr2", "rr2.5", "rr3", "rr4"] if V["exit"].startswith("rr") else ["trail2", "trail2.5", "trail3", "trail4", "trail5"]
    i = ex.index(V["exit"])
    for j in (i - 1, i + 1):
        if 0 <= j < len(ex): out.append(("exit", ex[j]))
    tfs = list(E.TF_MIN); i = tfs.index(V["tf"])
    for j in (i - 1, i + 1):
        if 0 <= j < len(tfs): out.append(("tf", tfs[j]))
    return out

finalists = []
for track in TRACKS:
    sel = [dict(r[list(GRID)].to_dict(), **TRACKS[track], track=track, cost="mid", cycle=5, role=f"IS-rank{i+1}") for i, (_, r) in enumerate(pick(track).iterrows())]
    sel += [dict(D, **TRACKS[track], track=track, cost="mid", cycle=5, role=f"default{i+1}") for i, D in enumerate(DEFAULTS[track])]
    finalists += sel

detail = []
for V in finalists:
    role = V.pop("role"); V["stop"] = float(V["stop"])
    tr = run(V); s = stats(tr, True); sc = score(s)
    nb = []
    for key, val in neighbours(V):
        W = dict(V, **{key: val}); tried.add(name(W)); sw = stats(run(W)); nb.append((key, val, sw["pnl"], sw["pnl_out"], sw["trades"]))
    lucky = "yes" if s["pnl"] > 0 and any(p <= 0 or n < 5 for _, _, p, _, n in nb) else ("no" if s["pnl"] > 0 else "n/a")
    sens = {}
    for cost in ("lo", "mid", "hi"):
        for cyc in (0, 5, 10, 15):
            W = dict(V, cost=cost, cycle=cyc); tried.add(name(W)); sw = stats(run(W)); sens[f"{cost}/cy{cyc}"] = (round(sw["pnl"], 1), round(sw["pnl_out"], 1), round(sw["cum_out"], 3), sw["trades"])
    venues = {}
    if V["track"] == "B":
        for ven in ("jup", "drift"):
            W = dict(V, venue=ven); tried.add(name(W)); sw = stats(run(W), True); venues[ven] = sw
    # random-entry baseline: same OOS trade count & hold-time distribution, random entry 5m bars in OOS, random side for B
    ro_mask = tr[:, 0] >= HOLD; holds_b = ((tr[ro_mask, 1] - tr[ro_mask, 0]) // 300).astype(int); rnd_means = []
    io = np.searchsorted(t5, HOLD); cost = COSTS[V["venue"]]["mid"]
    if len(holds_b) >= 2:
        for _ in range(1000):
            st_i = RNG.integers(io, len(t5) - holds_b.max() - 2, len(holds_b)); en = st_i + RNG.permutation(holds_b)
            dsign = np.ones(len(st_i)) if V["side"] == "long" else RNG.choice([-1.0, 1.0], len(st_i))
            rnd_means.append(np.mean(dsign * (o5[en] / o5[st_i] - 1) - 2 * cost))
        rnd = np.array(rnd_means); rand_p = float((rnd >= s["mean_out"]).mean()); rand_q = (float(np.quantile(rnd, 0.05)), float(np.median(rnd)), float(np.quantile(rnd, 0.95)))
    else: rand_p, rand_q = np.nan, (np.nan,) * 3
    detail.append(dict(V=V, role=role, s=s, sc=sc, nb=nb, lucky=lucky, sens=sens, venues=venues, rand_p=rand_p, rand_q=rand_q,
                       holds=holds(s), name=name(V)))
    print(role, name(V), sc["score_total"], round(s["pnl"], 1), round(s["pnl_out"], 1), s["trades"], flush=True)

# ---------- walk-forward re-optimisation (rolling: train trailing 9 months, trade next 3) ----------
def walk_forward(track):
    g = [(V, s) for V, s in rows.values() if V["track"] == track]
    cache = {}
    res = []; step = 91 * 86400; train = 273 * 86400; t = warm_t + train
    while t < T1:
        best, bv = -1e9, None
        for V, _ in g:
            n = name(V)
            if n not in cache: cache[n] = run(V)
            tr = cache[n]; m = (tr[:, 0] >= t - train) & (tr[:, 0] < t); r = tr[m, 5]
            if len(r) >= 15 and r.std() > 0:
                ts_ = r.mean() / r.std() * np.sqrt(len(r))
                if ts_ > best: best, bv = ts_, n
        tr = cache[bv]; m = (tr[:, 0] >= t) & (tr[:, 0] < t + step); r = tr[m, 5]
        res.append({"start": str(pd.to_datetime(t, unit="s").date()), "chosen": bv, "train_t": round(best, 2), "n": int(len(r)),
                    "pnl": round(float(r.sum() * 100), 1), "bh": round(bh(t, min(t + step, T1), 0.002)[0] * 100, 1)})
        t += step
    return res
WF = {tr_: walk_forward(tr_) for tr_ in TRACKS}

json.dump({"T0": T0, "T1": T1, "warm_t": warm_t, "HOLD": HOLD, "gaps5": gaps5, "gap_list": gap_list[:20], "resample_check": resample_check,
           "cb_basis_med": cb_basis, "BH": BH, "WF": WF, "variants_tried": len(tried), "okx_funding_from": int(ft.min()),
           "okx_mean_8h": float(rate.mean()), "detail": detail}, open(os.path.join(OUT, "summary.json"), "w"), default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o), indent=1)
print("done", len(tried), "variants", round(time.time() - t_start, 1), "s")
