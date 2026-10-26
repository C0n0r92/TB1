"""SOL trend/breakout study (PAPER/BACKTEST ONLY). Oracle, 2026-10-23.
Windows (UTC):  PRE  = data start+warm-up -> 2025-10-23  (untouched 2nd holdout, includes SOL's late-2024/2025 rallies)
                TRAIN= 2025-10-23 -> 2026-05-23 (selection happens ONLY here)
                OOS  = 2026-05-23 -> end         (held out)
Main test window ("12m") = TRAIN+OOS. Signals use closed bars only; fills at 5m open after TF close + bot cycle.
Outputs: ../out/grid.csv, ../out/finalists.json, ../leaderboard.csv, ../out/baselines.json, ../out/walkforward.json"""
import os, json, itertools, time
import numpy as np, pandas as pd
import common as C, engine as E
RNG = np.random.default_rng(11); OUT = os.path.join(C.ROOT, "out")
S = C.Sim(); t5 = S.t5; o5 = S.d5.o.values; c5 = S.d5.c.values
ts = lambda x: int(pd.Timestamp(x, tz="UTC").timestamp())
T_END = int(t5[-1]) + 300; T_TRAIN = ts("2025-10-23"); T_OOS = ts("2026-05-23")
T_PRE = int(S.BARS["4h"].tc.values[210])  # every TF warmed up (210 4h bars)
WIN = {"pre": (T_PRE, T_TRAIN), "train": (T_TRAIN, T_OOS), "oos": (T_OOS, T_END), "12m": (T_TRAIN, T_END)}

def bh(a, b_, cost=0.0022):
    ia, ib = np.searchsorted(t5, a), np.searchsorted(t5, b_) - 1; seg = c5[ia:ib + 1]
    return float(seg[-1] / o5[ia] * (1 - cost) ** 2 - 1), float((1 - seg / np.maximum.accumulate(seg)).max())
BH = {w: bh(*v) for w, v in WIN.items()}

def sl(tr, w):
    a, b_ = WIN[w]; return tr[(tr[:, 0] >= a) & (tr[:, 0] < b_)] if len(tr) else tr
def tstat(r): return float(r.mean() / r.std() * np.sqrt(len(r))) if len(r) > 2 and r.std() > 0 else -9.0
def streak(r):
    m = c = 0
    for x in r:
        c = c + 1 if x <= 0 else 0; m = max(m, c)
    return m
def boot(r, n=2000):
    if len(r) < 3: return (np.nan, np.nan)
    m = r[RNG.integers(0, len(r), (n, len(r)))].mean(1); return float(np.quantile(m, .025)), float(np.quantile(m, .975))
def basic(tr):
    r = tr[:, 5] if len(tr) else np.zeros(0)
    return {"n": int(len(r)), "pnl": float(r.sum() * 100), "mean": float(r.mean() * 100) if len(r) else np.nan, "t": tstat(r),
            "win": float((r > 0).mean()) if len(r) else np.nan, "cum": float(np.prod(1 + r) - 1) if len(r) else 0.0}
def months(tr, w="12m"):
    a, b_ = WIN[w]; x = sl(tr, w)
    allm = pd.date_range(pd.to_datetime(a, unit="s").normalize().replace(day=1), pd.to_datetime(b_ - 1, unit="s"), freq="MS")
    mo = pd.Series(x[:, 5], index=pd.to_datetime(x[:, 1], unit="s")).resample("MS").sum() if len(x) else pd.Series(dtype=float)
    mo = mo.reindex(allm, fill_value=0.0); return int((mo > 0).sum()), len(mo), [round(v * 100, 2) for v in mo.values]
def maxdd(r):  # $100 fixed stake per trade, in % of $100
    if not len(r): return 0.0
    eq = np.cumsum(r * 100); return float((np.maximum.accumulate(np.r_[0, eq])[1:] - eq).max())

# ---------------- grid ----------------
GRID = dict(tf=["5m", "15m", "1h", "4h"], trend=["none", "ema200up", "ema50_200", "htf"], level=["n20", "n55", "pivot"],
            confirm=["close", "vol", "retest"], stop=[1.5, 2.5], exit=["rr2", "rr3", "trail3"])
TRACKS = {"A": dict(side="long", venue="spot"), "B": dict(side="ls", venue="jup")}
t0 = time.time(); rows = []; TR = {}
for track, base in TRACKS.items():
    for combo in itertools.product(*GRID.values()):
        V = dict(zip(GRID, combo), track=track, **base); V["stop"] = float(V["stop"])
        tr = S.run(V); TR[C.name(V)] = tr
        row = {"name": C.name(V), **V}
        for w in WIN: row.update({f"{k}_{w}": v for k, v in basic(sl(tr, w)).items()})
        rows.append(row)
grid = pd.DataFrame(rows); grid.to_csv(os.path.join(OUT, "grid.csv"), index=False)
print("grid", len(grid), "configs", round(time.time() - t0, 1), "s", flush=True)

# ---------------- baselines: trend filter alone (no breakout) ----------------
def trend_only(tf, rule, side, venue, slip="mid", delay=300):
    b = S.BARS[tf]; c = b.c.values
    if rule == "ema200": up = c > b.ema200.values; dn = c < b.ema200.values
    else: up = (b.ema50.values > b.ema200.values); dn = (b.ema50.values < b.ema200.values)
    p_tf = np.where(up, 1.0, np.where(dn, -1.0 if side == "ls" else 0.0, 0.0)); p_tf[:210] = 0
    idx = np.searchsorted(b.tc.values, t5 - delay, side="right") - 1      # last TF bar closed >= delay before this 5m open
    pos = np.where(idx >= 0, p_tf[np.clip(idx, 0, None)], 0.0)
    r5 = np.r_[o5[1:] / o5[:-1] - 1, 0.0]
    cL, cS = S.CARRY[venue]; carry = np.where(pos > 0, cL, np.where(pos < 0, cS, 0.0))
    cost = np.abs(np.diff(np.r_[0, pos])) * (C.FEE[venue] + C.SLIP[slip])
    net = pos * r5 - carry - cost; out = {}
    for w, (a, b_) in WIN.items():
        m = (t5 >= a) & (t5 < b_); eq = np.cumprod(1 + net[m])
        out[w] = {"ret": float(eq[-1] - 1), "maxdd": float((1 - eq / np.maximum.accumulate(eq)).max()), "switches": int((np.abs(np.diff(pos[m])) > 0).sum()),
                  "exposure": float((pos[m] != 0).mean())}
    return out
BASE = {"buy_hold": {w: {"ret": BH[w][0], "maxdd": BH[w][1]} for w in WIN}}
for tf in ("1h", "4h"):
    for rule in ("ema200", "ema50_200"):
        BASE[f"A_trendonly_{tf}_{rule}"] = trend_only(tf, rule, "long", "spot")
        BASE[f"B_trendonly_{tf}_{rule}_jup"] = trend_only(tf, rule, "ls", "jup")
        BASE[f"B_trendonly_{tf}_{rule}_drift"] = trend_only(tf, rule, "ls", "drift")
json.dump(BASE, open(os.path.join(OUT, "baselines.json"), "w"), indent=1)

# ---------------- finalists: top-5 by TRAIN t-stat (min 25 train trades) + pre-registered defaults ----------------
DEFAULTS = [dict(tf="1h", trend="ema50_200", level="n20", confirm="close", stop=2.5, exit="trail3"),
            dict(tf="4h", trend="ema200up", level="n55", confirm="close", stop=2.5, exit="trail3")]
def neighbours(V):
    out = []
    lv = ["n20", "n55", "pivot"]; out += [("level", x) for x in lv if x != V["level"]]
    st = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]; i = st.index(V["stop"]); out += [("stop", st[j]) for j in (i - 1, i + 1) if 0 <= j < len(st)]
    ex = ["rr1.5", "rr2", "rr2.5", "rr3", "rr4"] if V["exit"].startswith("rr") else ["trail2", "trail2.5", "trail3", "trail4", "trail5"]
    i = ex.index(V["exit"]); out += [("exit", ex[j]) for j in (i - 1, i + 1) if 0 <= j < len(ex)]
    tfs = list(E.TF_MIN); i = tfs.index(V["tf"]); out += [("tf", tfs[j]) for j in (i - 1, i + 1) if 0 <= j < len(tfs)]
    out += [("confirm", x) for x in ("close", "vol", "retest") if x != V["confirm"]]
    return out
def rand_entry(tr, w, side, venue, n=1000):
    x = sl(tr, w); a, b_ = WIN[w]
    if len(x) < 3: return np.nan
    hb = ((x[:, 1] - x[:, 0]) // 300).astype(int); ia, ib = np.searchsorted(t5, a), np.searchsorted(t5, b_) - hb.max() - 2
    if ib <= ia: return np.nan
    cost = C.FEE[venue] + C.SLIP["mid"]; real = x[:, 5].mean(); ge = 0
    for _ in range(n):
        s_ = RNG.integers(ia, ib, len(hb)); e_ = s_ + RNG.permutation(hb)
        d = np.ones(len(s_)) if side == "long" else RNG.choice([-1.0, 1.0], len(s_))
        ge += np.mean(d * (o5[e_] / o5[s_] - 1) - 2 * cost) >= real
    return ge / n

def score(f):
    sc = {}
    def oo(o): return 1 if o["n"] < 5 or o["pnl"] <= 0 else 2 if o["n"] < 20 or o["mean"] < 0.05 else 3 if o["t"] < 1 else 4 if o["t"] < 2 else 5
    sc["oos"] = min(oo(f["oos"]), oo(f["pre"]))   # BOTH unseen periods (later OOS and earlier PRE) must hold up
    s_ = f["streak"]; sc["streak"] = 5 if s_ <= 5 else 4 if s_ <= 7 else 3 if s_ <= 10 else 2 if s_ <= 14 else 1
    n = f["12m"]["n"]; sc["trades"] = 1 if n < 10 else 2 if n < 25 else 3 if n < 50 else 4 if n < 100 else 5
    m, h = f["12m"], f["hi12"]
    sc["profit"] = 1 if m["pnl"] <= 0 else 2 if h["pnl"] <= 0 else 3 if m["mean"] < 0.15 else 4 if f["ci12"][0] <= 0 else 5
    mp = f["months_prof"] / f["months_n"]; sc["consistency"] = 5 if mp >= .7 else 4 if mp >= .6 else 3 if mp >= .5 else 2 if mp >= .35 else 1
    if f["nbr_pos"] < 0.75: sc["consistency"] = min(sc["consistency"], 3)   # unstable at nearby settings caps consistency
    if f["pre"]["pnl"] <= 0: sc["consistency"] = min(sc["consistency"], 3)  # loses in the untouched pre-period
    sc["total"] = sum(sc.values()); return sc

final = []
for track, base in TRACKS.items():
    g = grid[(grid.track == track) & (grid.n_train >= 25)].sort_values("t_train", ascending=False).head(5)
    sel = [(r[list(GRID)].to_dict(), f"train-rank{i + 1}") for i, (_, r) in enumerate(g.iterrows())] + [(D, f"default{i + 1}") for i, D in enumerate(DEFAULTS)]
    for P, role in sel:
        V = dict(P, track=track, **base); V["stop"] = float(V["stop"]); tr = TR.get(C.name(V)); tr = S.run(V) if tr is None else tr
        f = {"name": C.name(V), "role": role, "V": V}
        for w in WIN: f[w] = basic(sl(tr, w))
        r12 = sl(tr, "12m")[:, 5]
        f["streak"] = streak(r12); f["maxdd12"] = maxdd(r12); f["ci12"] = boot(r12); f["ci_oos"] = boot(sl(tr, "oos")[:, 5])
        f["months_prof"], f["months_n"], f["monthly"] = months(tr)
        f["hi12"] = basic(sl(S.run(V, slip="hi"), "12m")); f["lo12"] = basic(sl(S.run(V, slip="lo"), "12m"))
        f["cycles"] = {}
        for cy in (0, 5, 10, 15):
            x = S.run(V, cycle=cy); f["cycles"][cy] = {w: round(basic(sl(x, w))["pnl"], 1) for w in ("12m", "oos")}
        f["slips"] = {s: {w: round(basic(sl(S.run(V, slip=s), w))["pnl"], 1) for w in ("12m", "oos", "pre")} for s in ("lo", "mid", "hi")}
        nb = []
        for k, v in neighbours(V):
            W = dict(V, **{k: v}); x = sl(S.run(W), "12m"); nb.append((k, v, round(basic(x)["pnl"], 1), len(x)))
        f["nbrs"] = nb; f["nbr_pos"] = float(np.mean([p > 0 for _, _, p, _ in nb]))
        if track == "B": f["venues"] = {ven: {w: round(basic(sl(S.run(V, venue=ven), w))["pnl"], 1) for w in ("12m", "oos", "pre")} for ven in ("jup", "drift")}
        f["rand_p_oos"] = rand_entry(tr, "oos", V["side"], V["venue"]); f["rand_p_12m"] = rand_entry(tr, "12m", V["side"], V["venue"])
        r = sl(tr, "12m"); f["exposure_12m"] = float((r[:, 1] - r[:, 0]).sum() / (WIN["12m"][1] - WIN["12m"][0])) if len(r) else 0.0
        if track == "B" and len(r):
            f["long_short"] = {"long": basic(r[r[:, 2] > 0]), "short": basic(r[r[:, 2] < 0])}
        f["score"] = score(f)
        f["candidate"] = bool(f["score"]["total"] >= 18 and f["12m"]["n"] >= 50 and f["nbr_pos"] >= 0.75 and f["oos"]["pnl"] > 0)
        final.append(f); print(track, role, f["name"], f["score"], f["12m"]["n"], round(f["12m"]["pnl"], 1), round(f["oos"]["pnl"], 1), round(f["pre"]["pnl"], 1), flush=True)

# ---------------- rolling walk-forward over full 2y: pick best grid config on trailing 6 months (t-stat, >=15 trades), trade next 2 months ----------------
def walk(track):
    names = [n for n in TR if n.startswith(f"SOLT_{track}_")]; res = []; step, train = 61 * 86400, 182 * 86400; t = T_PRE + train
    while t < T_END:
        best, bn = -1e9, None
        for n in names:
            x = TR[n]; r = x[(x[:, 0] >= t - train) & (x[:, 0] < t), 5]
            if len(r) >= 15 and (v := tstat(r)) > best: best, bn = v, n
        x = TR[bn]; r = x[(x[:, 0] >= t) & (x[:, 0] < min(t + step, T_END)), 5]
        res.append({"start": str(pd.to_datetime(t, unit="s").date()), "chosen": bn, "train_t": round(best, 2), "n": int(len(r)), "pnl": round(float(r.sum() * 100), 1),
                    "bh": round(bh(t, min(t + step, T_END))[0] * 100, 1)}); t += step
    return res
WF = {k: walk(k) for k in TRACKS}
json.dump(WF, open(os.path.join(OUT, "walkforward.json"), "w"), indent=1)
json.dump({"WIN": {k: [str(pd.to_datetime(a, unit='s')), str(pd.to_datetime(b_, unit='s'))] for k, (a, b_) in WIN.items()}, "BH": BH, "final": final,
           "n_configs": int(len(grid))}, open(os.path.join(OUT, "finalists.json"), "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
lb = []
for f in final:
    lb.append({"id": f["name"], "track": f["V"]["track"], "role": f["role"], "venue": f["V"]["venue"], "tf": f["V"]["tf"], "trend": f["V"]["trend"], "level": f["V"]["level"],
               "confirm": f["V"]["confirm"], "stop_atr": f["V"]["stop"], "exit": f["V"]["exit"], "cost_basis": "fee+0.2%slip/side, 5min cycle",
               "trades_12m": f["12m"]["n"], "n_train": f["train"]["n"], "n_oos": f["oos"]["n"], "pnl_12m_pct": round(f["12m"]["pnl"], 1),
               "pnl_12m_slip0.1": f["slips"]["lo"]["12m"], "pnl_12m_slip0.3": f["slips"]["hi"]["12m"], "pnl_train": round(f["train"]["pnl"], 1),
               "pnl_oos": round(f["oos"]["pnl"], 1), "pnl_pre": round(f["pre"]["pnl"], 1), "mean_trade_pct": round(f["12m"]["mean"], 3),
               "ci12_lo": round(f["ci12"][0] * 100, 3), "ci12_hi": round(f["ci12"][1] * 100, 3), "win": round(f["12m"]["win"], 2), "worst_streak": f["streak"],
               "maxdd_pct": round(f["maxdd12"], 1), "months_prof": f"{f['months_prof']}/{f['months_n']}", "nbr_pos": round(f["nbr_pos"], 2),
               "rand_p_oos": f["rand_p_oos"], "bh_oos_pct": round(BH["oos"][0] * 100, 1), "bh_12m_pct": round(BH["12m"][0] * 100, 1),
               **{f"sc_{k}": v for k, v in f["score"].items()}, "candidate": f["candidate"]})
pd.DataFrame(lb).sort_values(["track", "sc_total"], ascending=[True, False]).to_csv(os.path.join(C.ROOT, "leaderboard.csv"), index=False)
print("BH", {k: (round(v[0] * 100, 1), round(v[1] * 100, 1)) for k, v in BH.items()})
print("WF", {k: (sum(x["pnl"] for x in v), len(v)) for k, v in WF.items()}); print("done", round(time.time() - t0, 1), "s")
