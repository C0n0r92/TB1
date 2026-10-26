"""I5 ideas 3 (dip-buy) and 5 (revival): event builders from cached candles only (no API calls)."""
import json, glob, os, math, csv, statistics, bisect
import i5_events as E
D = "/workspace/lab/data"

def _pumpliq(key, p, t):
    if not key.endswith("pump") or p * 1e9 < 1e5: return None       # only graduated PumpSwap-style (CPMM, LP burned) pools
    return E.liq_pump(p, t)

def series1m():
    """Union of cached 1m series keyed by pool: backfill graduations, CR winner candles, CL candles, FE live mints."""
    S = {}
    for f in glob.glob(D + "/backfill/candles1m/*.json"):
        x = json.load(open(f)); r = x.get("rows") or []
        if len(r) > 20: S[x.get("pool") or f] = dict(mint=x["mint"], rows=r, src="backfill")
    for f in glob.glob(D + "/cr/wcandles/*.json"):
        x = json.load(open(f)); r = x.get("rows1") or []; mint = os.path.basename(f).split("_")[1]
        if len(r) > 20 and x.get("pool") not in S: S[x["pool"]] = dict(mint=mint, rows=r, src="cr_w")
    for f in glob.glob(D + "/cl/candles/*.json"):
        x = json.load(open(f))
        for s in x.get("series") or []:
            r = s.get("rows") or []
            if len(r) > 20 and s.get("pool") not in S and s.get("dex") != "pump-fun": S[s["pool"]] = dict(mint=x["mint"], rows=r, src="cl")
    for f in glob.glob(D + "/fe/*.json"):
        x = json.load(open(f)); r = x.get("rows1") or []
        if len(r) > 20 and x.get("pool") not in S: S[x["pool"]] = dict(mint=x["mint"], rows=r, src="fe")
    for v in S.values(): v["rows"] = sorted({int(b[0]): [int(b[0])] + list(b[1:6]) for b in v["rows"] if b[4] > 0}.values())
    return S

def gt5():
    out = {}
    for f in glob.glob(D + "/mr_candles/gt_*_5m.csv"):
        sym = os.path.basename(f)[3:-7]; pj = json.load(open(f.replace("_5m.csv", "_pool.json")))
        R = []
        for row in csv.reader(open(f)):
            try: R.append([int(float(row[0])) // 1000] + [float(z) for z in row[1:6]])
            except ValueError: continue
        R.sort(); out[sym] = dict(rows=R, liq_now=float(pj["reserve_usd"]), px_now=R[-1][4], src="gt5")
    return out

def midcap15():
    import oc_backtest as O
    toks, _ = O.load(); out = {}
    for m, k in toks.items():
        if "m15" not in k: continue
        q = k["m15"]; R = [[q["T"][i], q["O"][i], q["H"][i], q["L"][i], q["C"][i], q["V"][i]] for i in range(len(q["T"]))]
        out[m] = dict(rows=R, liq_now=k["liq_now"], px_now=k["px_now"], birth=k.get("birth"), sym=k["sym"], src="mid15")
    return out

def _liq_scaled(s, p): return s["liq_now"] * math.sqrt(max(p, 1e-18) / s["px_now"])

def dips(min_liq=200e3, lo=0.30, hi=0.50, win_s=600, cool_s=3600, vol_cap=None):
    """Signal at a bar close: close is 30-50% below the max high of the bars inside the last 10 min (incl. this bar);
    liquidity at the signal price >= $200k. Rug proxy: PumpSwap LP burned at graduation (LP-intact by construction);
    creator-selling NOT observable in cached candles (untested). vol_cap: optional 'not a dump-out' proxy = skip if
    signal-bar volume > vol_cap x liquidity."""
    ev = []; cnt = {}
    def scan(key, R, step, liqf, src, win):
        last = -1e18
        for i, b in enumerate(R):
            t = b[0]; j = i
            while j > 0 and R[j - 1][0] > t - win: j -= 1
            hmax = max(x[2] for x in R[j:i + 1]); c = b[4]
            if hmax <= 0: continue
            dd = 1 - c / hmax
            if not (lo <= dd <= hi) or t - last < cool_s: continue
            L = liqf(c, t)
            if not L or L < min_liq: continue
            if vol_cap and b[5] > vol_cap * L: continue
            last = t; ev.append(dict(t=t + step, bars=R, step=step, liq=L, key=key, src=src, dd=dd)); cnt[src] = cnt.get(src, 0) + 1
    for pool, s in series1m().items():
        scan(s["mint"], s["rows"], 60, lambda p, t, m=s["mint"]: _pumpliq(m, p, t), "1m_" + s["src"], win_s)
    return ev, cnt

def dips_coarse(min_liq=200e3, lo=0.30, hi=0.50, cool_s=3600):
    """Older-coin proxy: 5m (2 bars = 10 min, gt_ memes) and 15m (1 bar, midcap) -- the 15m one is '<=15 min', labelled."""
    ev = []; cnt = {}
    for nm, (S, step, win) in {"gt5": (gt5(), 300, 600), "mid15": (midcap15(), 900, 900)}.items():
        for key, s in S.items():
            R = s["rows"]; last = -1e18
            for i, b in enumerate(R):
                t = b[0]; j = max(0, i - (win // step) + 1)
                hmax = max(x[2] for x in R[j:i + 1]); c = b[4]; dd = 1 - c / hmax if hmax > 0 else 0
                if not (lo <= dd <= hi) or t - last < cool_s: continue
                L = _liq_scaled(s, c)
                if L < min_liq: continue
                last = t; ev.append(dict(t=t + step, bars=R, step=step, liq=L, key=key, src=nm, dd=dd)); cnt[nm] = cnt.get(nm, 0) + 1
    return ev, cnt

def revivals(mult=5.0, base_h=24, min_age_d=1.0, cool_h=6, min_ratio=0.02, green=False, srcs=("gt5", "mid15")):
    """Coin >=1 day old (first cached bar or pool birth >= 24h before). Spike: bar volume/liquidity (normalised to a
    5-min rate) >= mult x its trailing base_h mean, and >= min_ratio absolute (avoid zero baselines).
    15m bars give a 15-min (not 5-min) window -- labelled proxy."""
    ev = []; cnt = {}
    SS = {}
    if "gt5" in srcs: SS["gt5"] = (gt5(), 300)
    if "mid15" in srcs: SS["mid15"] = (midcap15(), 900)
    for nm, (S, step) in SS.items():
        nb = int(base_h * 3600 / step)
        for key, s in S.items():
            R = s["rows"]; last = -1e18; t0 = min(R[0][0], s.get("birth") or R[0][0])
            ratio = [b[5] / _liq_scaled(s, b[4]) * (300 / step) for b in R]
            csum = [0.0]
            for z in ratio: csum.append(csum[-1] + z)
            for i in range(nb, len(R)):
                t = R[i][0]
                if t - t0 < min_age_d * 86400 or t - last < cool_h * 3600: continue
                base = (csum[i] - csum[i - nb]) / nb
                if ratio[i] < min_ratio or base <= 0 or ratio[i] < mult * base: continue
                if green and R[i][4] < R[i][1]: continue
                L = _liq_scaled(s, R[i][4]); last = t
                ev.append(dict(t=t + step, bars=R, step=step, liq=L, key=key, src=nm, spike=ratio[i] / base)); cnt[nm] = cnt.get(nm, 0) + 1
    return ev, cnt
