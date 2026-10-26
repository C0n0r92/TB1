#!/usr/bin/env python3
"""Older-coins breakout (Chunk's runner-radar/oldcoins.py rules, read-only copy of the logic) - PAPER backtest, no network.
Live-rule baseline OC_live (Zero 23:39 update): stop = breakout-bar low clamped to [2.5%, 8%] below entry (1h) / [2.5%, 6%] (15m);
activity filter (live spec: $ vol of last 4 candles >= $150k 1h / $40k 15m; thin filter liq/mcap>0.4 & vol24/liq<0.05); 1h: close > EMA50 > EMA200, close > prior-24-bar high, vol > prior-20-bar mean, vol24 >= $1M;
15m: 1h EMA50 > EMA200 (last closed hour), 15m close > 15m EMA50, > prior-24-bar (6 h) high, vol > prior-20 mean.
TP half at +15% (1h) / +10% (15m), rest exits on close < EMA20 (same tf), entries 21:00-07:30 Dublin, flat at 07:45 Dublin.
Entry = next bar open; stop checked before TP inside a bar; gap through stop fills at the open. 10% of book per trade, max 3 open,
one position per token. Universe point-in-time: age >= 7 d, mcap $5-200M (supply x price), liq >= $500k (CPMM sqrt-price scaling), vol24 >= $1M."""
import json, math, os, random, statistics, sys, time, bisect, re, csv, itertools, datetime as dt
from zoneinfo import ZoneInfo
import midcap_momentum as mm
import scoring
from labcore import LAB, atomic_write
D = os.path.join(LAB, "data", "midcap"); OH = os.path.join(D, "ohlcv"); OUT = os.path.join(LAB, "out")
DUB = ZoneInfo("Europe/Dublin"); DAY = 86400; SIZE_F = 0.10; MAX_OPEN = 3; BOOK_SOL = 0.928
EXCL = set("""SOL WSOL USDC USDT PYUSD USDS USDE USDH UXD USDY DAI FDUSD TUSD USD1 USDG EURC JLP MSOL JITOSOL BSOL JUPSOL INF HSOL
STSOL BNSOL DSOL VSOL WBTC CBBTC WETH ETH BTC ZBTC TBTC XBTC XAUT PAXG ZEC HYPE WHYPE""".split())
TOKENIZED = re.compile(r"^[A-Z0-9]{1,6}x$")          # xStocks (TSLAx, CRCLx, SPYx ...) excluded like Chunk's wrapped/tokenized filter
AVOID = set()
try:
    for r in csv.DictReader(open("/workspace/onchain-intel/avoid.csv")): AVOID.update((r.get("mints") or "").split(";"))
except Exception: pass

def dmin(t): d = dt.datetime.fromtimestamp(t, DUB); return d.hour * 60 + d.minute
def uhour(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).hour
def bookday(t): return (dt.datetime.fromtimestamp(t, DUB) - dt.timedelta(hours=8)).date().isoformat()   # night 20:00-08:00 Dublin keyed by its start date
def in_window(t): m = dmin(t); return m >= 21 * 60 or m < 7 * 60 + 30

# ---------------- cost model ----------------
FIT = json.load(open(os.path.join(OUT, ".fs_rows.json")))["fit"]["forms"]["logliq"]["coef"]   # Jupiter-quote fit (copy_fee_sensitivity v2)
def real_cost(liq, size_usd, solpx, prio=0.0005):
    pool = max(0.0025, (FIT[0] + FIT[1] * math.log10(max(liq, 1) / 1e5)) / 2)      # pool fee, floored at 0.25%/side
    return pool + 2 * size_usd / liq + (prio + 5e-6) * solpx / size_usd           # + CPMM impact (Chunk's 2*size/liq) + priority+base fee
COSTS = {"c1.0": lambda liq, z, sp: 0.01, "c0.3": lambda liq, z, s: 0.003, "c0.5": lambda liq, z, s: 0.005, "real_P0.0001": lambda liq, z, s: real_cost(liq, z, s, 0.0001),
         "real_P0.0005": lambda liq, z, s: real_cost(liq, z, s, 0.0005), "chunk_1pct": lambda liq, z, s: 0.01 + 2 * z / liq}
MAIN = "real_P0.0005"

# ---------------- data ----------------
def load():
    toks, sol = mm.load()
    solT = sorted(sol); solV = [sol[t] for t in solT]
    def solpx(t): k = bisect.bisect_right(solT, t) - 1; return solV[max(k, 0)]
    out = {}
    for m, k in toks.items():
        s = (k["sym"] or "").upper()
        if s in EXCL or TOKENIZED.match(k["sym"] or "") or m in AVOID: continue
        k["e50"], k["e200"] = k["ema"][50], k["ema"][200]
        f = os.path.join(OH, f"rows15_{m}.json")
        if os.path.exists(f):
            r = [x for x in json.load(open(f)) if x[4] > 0]
            if len(r) >= 120:
                k["m15"] = dict(T=[int(x[0]) for x in r], O=[x[1] for x in r], H=[x[2] for x in r], L=[x[3] for x in r], C=[x[4] for x in r], V=[x[5] for x in r])
                C15 = k["m15"]["C"]; k["m15"]["e50"] = mm.ema(C15, 50); k["m15"]["e20"] = mm.ema(C15, 20)
        out[m] = k
    return out, solpx

UNIVS = {"old": dict(age=7, mc_lo=5e6, mc_hi=2e8, liq=5e5, vol=1e6),          # 23:39 live universe
         "wide": dict(age=3, mc_lo=3e6, mc_hi=1e9, liq=3e5, vol=7.5e5)}       # 23:54 widened universe (Zero)
U = dict(UNIVS["old"])
def set_univ(name): U.clear(); U.update(UNIVS[name])
def elig(k, i):
    t = k["T"][i]; c = k["C"][i]
    if t - k["birth"] < U["age"] * DAY: return False
    mc = c * k["supply"]; liq = k["liq_now"] * math.sqrt(c / k["px_now"])
    return U["mc_lo"] <= mc <= U["mc_hi"] and liq >= U["liq"]

def liq_at(k, c): return k["liq_now"] * math.sqrt(c / k["px_now"])

# ---------------- signals ----------------
def signals_1h(toks, t_lo):
    """all live-rule 1h breakouts (without vol threshold and activity filter applied; those are stored as fields)."""
    S = []
    for m, k in toks.items():
        T, O, H, Lo, C, V, E50, E200 = k["T"], k["O"], k["H"], k["L"], k["C"], k["V"], k["e50"], k["e200"]
        for i in range(220, len(C) - 1):
            if T[i + 1] < t_lo: continue
            if not (C[i] > E50[i] > E200[i] and C[i] > max(H[i - 24:i])): continue
            if T[i + 1] - T[i] > 3 * 3600 or not elig(k, i): continue
            v24 = sum(V[j] for j in range(i, -1, -1) if T[j] > T[i] - DAY)
            if v24 < U["vol"]: continue
            act = sum(V[i - 3:i + 1])                                                   # live spec: $ volume of the last 4 closed 1h candles (>= $150k)
            c_ = C[i]; liq_ = k["liq_now"] * math.sqrt(c_ / k["px_now"]); mc_ = c_ * k["supply"]
            if liq_ / mc_ > 0.4 and v24 / liq_ < 0.05: continue                         # live 'thin_activity' universe filter
            S.append(dict(tf="1h", mint=m, sym=k["sym"], i=i, t=T[i + 1], vr=V[i] / max(sum(V[i - 20:i]) / 20, 1e-9), act=act,
                          low=Lo[i], liq=liq_at(k, C[i])))
    return S

def signals_15m(toks, t_lo):
    S = []
    for m, k in toks.items():
        q = k.get("m15")
        if not q: continue
        T, O, H, Lo, C, V, E50 = q["T"], q["O"], q["H"], q["L"], q["C"], q["V"], q["e50"]
        TH = k["T"]
        for i in range(80, len(C) - 1):
            if T[i + 1] < t_lo or T[i + 1] - T[i] > 45 * 60: continue
            if not (C[i] > E50[i] and C[i] > max(H[i - 24:i])): continue
            h = bisect.bisect_right(TH, T[i] + 900 - 3600) - 1                        # last 1h bar closed by this 15m close
            if h < 220 or not (k["e50"][h] > k["e200"][h]) or not elig(k, h): continue
            v24 = sum(k["V"][j] for j in range(h, -1, -1) if TH[j] > TH[h] - DAY)
            if v24 < U["vol"]: continue
            act = sum(V[i - 3:i + 1])                                                   # live spec: $ volume of the last 4 closed 15m candles (>= $40k)
            c_ = k["C"][h]; liq_ = k["liq_now"] * math.sqrt(c_ / k["px_now"]); mc_ = c_ * k["supply"]
            if liq_ / mc_ > 0.4 and v24 / liq_ < 0.05: continue
            S.append(dict(tf="15m", mint=m, sym=k["sym"], i=i, t=T[i + 1], vr=V[i] / max(sum(V[i - 20:i]) / 20, 1e-9), act=act,
                          low=Lo[i], liq=liq_at(k, C[i])))
    return S

def walk(k, s, P):
    """exit legs for one signal under params P (stop_lo, stop_hi, tp, trail) -> (legs[(frac, px)], entry, exit_t, why)"""
    q = k if s["tf"] == "1h" else k["m15"]
    T, O, H, Lo, C = q["T"], q["O"], q["H"], q["L"], q["C"]; E20 = k["e20"] if s["tf"] == "1h" else q["e20"]
    j = s["i"] + 1; e = O[j]
    st = min(max(s["low"], e * (1 - P["stop_hi"])), e * (1 - P["stop_lo"]))          # breakout low clamped to [stop_lo, stop_hi] below entry
    tp = e * (1 + P["tp"]) if P["tp"] else None; rem = 1.0; legs = []; tpf = 0.5
    eod_bar = 7 * 60 if s["tf"] == "1h" else 7 * 60 + 30
    for x in range(j, len(C)):
        if Lo[x] <= st: legs.append((rem, min(O[x], st) if x > j else st)); return legs, e, T[x], "stop"
        if dmin(T[x]) == eod_bar:
            legs.append((rem, (O[x] + C[x]) / 2 if s["tf"] == "1h" else C[x])); return legs, e, T[x] + (1800 if s["tf"] == "1h" else 900), "eod"
        if x > j and T[x] - T[j] > 26 * 3600:                                           # missed the 07:xx bar (data gap): flat at this open
            legs.append((rem, O[x])); return legs, e, T[x], "eod_gap"
        if tp and rem == 1.0 and H[x] >= tp: legs.append((tpf, tp)); rem -= tpf; continue
        if rem < 1.0 and C[x] < E20[x]: legs.append((rem, C[x])); return legs, e, T[x] + (3600 if s["tf"] == "1h" else 900), "trail"
    return None

def trades(toks, sigs, P, cost, solpx):
    out = []
    for s in sigs:
        if s["vr"] <= P["vth"] or s["act"] < P["act"]: continue
        if P["hours"] == "live":
            if not in_window(s["t"]): continue
        elif P["hours"] != "all":
            a, b = P["hours"]
            if not (a <= uhour(s["t"]) < b): continue
        w = walk(toks[s["mint"]], s, P)
        if not w: continue
        legs, e, xt, why = w
        z = SIZE_F * BOOK_SOL * solpx(s["t"]); c = COSTS[cost](s["liq"], z, solpx(s["t"]))
        ret = sum(f * px * (1 - c) for f, px in legs) / (e * (1 + c)) - 1
        out.append(dict(s, exit_t=xt, ret=ret, why=why, cost=c, pnl=SIZE_F * ret))       # pnl = fraction of book
    return out

def book(tr):
    tr = sorted(tr, key=lambda x: (x["t"], -x["vr"])); open_, took = [], []
    for c in tr:
        open_ = [o for o in open_ if o["exit_t"] > c["t"]]
        if len(open_) >= MAX_OPEN or any(o["mint"] == c["mint"] for o in open_): continue
        open_.append(c); took.append(c)
    return took

# ---------------- stats ----------------
def boot_mean(x, n=5000, seed=7):
    if len(x) < 2: return (None, None)
    r = random.Random(seed); b = sorted(statistics.fmean(r.choices(x, k=len(x))) for _ in range(n)); return b[int(.025 * n)], b[int(.975 * n) - 1]

def nightly(tr, days):
    d = {k: 0.0 for k in days}; n = {k: 0 for k in days}
    for t in tr:
        k = bookday(t["t"])
        if k in d: d[k] += t["pnl"]; n[k] += 1
    return d, n

def block_boot_nights(vals, nb=5000, block=3, seed=11):
    """circular block bootstrap over consecutive nights (block keeps cross-night dependence; a night is one unit, so same-night coin correlation is kept)."""
    r = random.Random(seed); N = len(vals); out = []
    for _ in range(nb):
        s = []
        while len(s) < N: st = r.randrange(N); s += [vals[(st + h) % N] for h in range(block)]
        out.append(s[:N])
    return out

def pct(x, p): x = sorted(x); return x[min(len(x) - 1, max(0, int(round(p * (len(x) - 1)))))]

def night_dist(nv, nn):
    vals = [nv[k] for k in sorted(nv)]; cnt = [nn[k] for k in sorted(nn)]
    if not vals: return None
    f = lambda v: dict(med=statistics.median(v), p10=pct(v, .1), p90=pct(v, .9), p_up10=sum(x >= .10 for x in v) / len(v), p_dn20=sum(x <= -.20 for x in v) / len(v),
                       mean=statistics.fmean(v), p_pos=sum(x > 0 for x in v) / len(v))
    base = f(vals); B = block_boot_nights(vals); bs = [f(b) for b in B]
    ci = {k: (pct([b[k] for b in bs], .025), pct([b[k] for b in bs], .975)) for k in base}
    # 30-night compounded path from the same blocks
    r30 = []
    rr = random.Random(5)
    for _ in range(5000):
        s = []
        while len(s) < 30: st = rr.randrange(len(vals)); s += [vals[(st + h) % len(vals)] for h in range(3)]
        e = 1.0
        for v in s[:30]: e *= 1 + v
        r30.append(e - 1)
    return dict(base, ci=ci, n_nights=len(vals), trades_per_night=statistics.fmean(cnt), zero_trade_share=sum(c == 0 for c in cnt) / len(cnt),
                max_trades=max(cnt), m30=statistics.median(r30), p10_30=pct(r30, .1), p90_30=pct(r30, .9), worst=min(vals), best=max(vals))

def summ(tr, days_is, days_oos):
    i = [t for t in tr if bookday(t["t"]) in days_is]; o = [t for t in tr if bookday(t["t"]) in days_oos]
    r = lambda x: [t["ret"] for t in x]
    def one(x, dd):
        if not x: return dict(n=0, mean=None, med=None, win=None, ci=(None, None), book=0.0, perday=0.0)
        return dict(n=len(x), mean=statistics.fmean(r(x)), med=statistics.median(r(x)), win=sum(v > 0 for v in r(x)) / len(x), ci=boot_mean(r(x)),
                    book=sum(t["pnl"] for t in x), perday=sum(t["pnl"] for t in x) / max(len(dd), 1))
    return dict(all=one(tr, days_is + days_oos), IS=one(i, days_is), OOS=one(o, days_oos))

def signals_15c(toks, t_lo):
    """Setup C (Zero 23:54, not yet in oldcoins.py): 15m pullback to the 15m EMA20 inside a 1h uptrend.
    Lab spec: last closed 1h bar C > EMA50 > EMA200; 15m bar low <= EMA20 and close > EMA20 (touch-and-hold),
    close > 15m EMA50, >= 3 of the prior 4 closes above EMA20 (a pullback, not a chop), stop = pullback-bar low clamped 2.5-6%."""
    S = []
    for m, k in toks.items():
        q = k.get("m15")
        if not q: continue
        T, O, H, Lo, C, V, E50, E20 = q["T"], q["O"], q["H"], q["L"], q["C"], q["V"], q["e50"], q["e20"]
        TH = k["T"]
        for i in range(80, len(C) - 1):
            if T[i + 1] < t_lo or T[i + 1] - T[i] > 45 * 60: continue
            if not (Lo[i] <= E20[i] < C[i] and C[i] > E50[i] and sum(C[j] > E20[j] for j in range(i - 4, i)) >= 3): continue
            h = bisect.bisect_right(TH, T[i] + 900 - 3600) - 1
            if h < 220 or not (k["C"][h] > k["e50"][h] > k["e200"][h]) or not elig(k, h): continue
            v24 = sum(k["V"][j] for j in range(h, -1, -1) if TH[j] > TH[h] - DAY)
            if v24 < U["vol"]: continue
            c_ = k["C"][h]; liq_ = k["liq_now"] * math.sqrt(c_ / k["px_now"]); mc_ = c_ * k["supply"]
            if liq_ / mc_ > 0.4 and v24 / liq_ < 0.05: continue
            S.append(dict(tf="15m", setup="C", mint=m, sym=k["sym"], i=i, t=T[i + 1], vr=V[i] / max(sum(V[i - 20:i]) / 20, 1e-9),
                          act=sum(V[i - 3:i + 1]), low=Lo[i], liq=liq_at(k, C[i])))
    return S

# ---------------- main ----------------
LIVE = {"1h": dict(stop_lo=0.025, stop_hi=0.08, tp=0.15, vth=1.0, act=150e3, hours="live"),
        "15m": dict(stop_lo=0.025, stop_hi=0.06, tp=0.10, vth=1.0, act=40e3, hours="live")}
GRID = {"1h": dict(stop_lo=[0.015, 0.025, 0.04], stop_hi=[0.05, 0.08, 0.12], tp=[0.05, 0.10, 0.15, 0.25, None], vth=[0.0, 1.0, 1.5, 2.0, 3.0],
                   act=[0.0, 75e3, 150e3, 300e3, 600e3], hours=["live", "all", (18, 24), (0, 6), (6, 12), (12, 18)]),
        "15m": dict(stop_lo=[0.015, 0.025, 0.04], stop_hi=[0.04, 0.06, 0.09], tp=[0.05, 0.10, 0.15, 0.25, None], vth=[0.0, 1.0, 1.5, 2.0, 3.0],
                    act=[0.0, 20e3, 40e3, 80e3, 160e3], hours=["live", "all", (18, 24), (0, 6), (6, 12), (12, 18)])}
DIMS = ["stop_lo", "stop_hi", "tp", "vth", "act", "hours"]

def pname(tf, P):
    h = P["hours"] if isinstance(P["hours"], str) else f"{P['hours'][0]:02d}-{P['hours'][1]:02d}UTC"
    return f"{tf}_sl{P['stop_lo']*100:g}-{P['stop_hi']*100:g}_tp{'none' if P['tp'] is None else f'{P[chr(116)+chr(112)]*100:g}'}_v{P['vth']:g}_a{P['act']/1e3:g}k_{h}"

def neighbours(tf, P):
    out = []
    for d in DIMS:
        vals = GRID[tf][d]; i = vals.index(P[d])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals): out.append((d, dict(P, **{d: vals[j]})))
    return out

def daily_se(nv):
    v = list(nv.values()); return statistics.pstdev(v) / math.sqrt(len(v)) if len(v) > 1 else 1.0

def main():
    toks, solpx = load()
    tmax = max(k["T"][-1] for k in toks.values())
    res = {}
    for tf in ("1h", "15m"):
        t_lo = tmax - 60 * DAY if tf == "1h" else min(k["m15"]["T"][80] for k in toks.values() if k.get("m15"))
        sigs = signals_1h(toks, t_lo) if tf == "1h" else signals_15m(toks, t_lo)
        d0 = dt.date.fromisoformat(bookday(max(t_lo, min(s["t"] for s in sigs)) if sigs else t_lo)); d1 = dt.date.fromisoformat(bookday(tmax - 9 * 3600))
        days = [(d0 + dt.timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]
        k70 = int(len(days) * 0.7); dIS, dOOS = days[:k70], days[k70:]
        # walk cache: same signal x (stop_lo, stop_hi, tp) reused across filters/costs
        wc = {}
        def run(P, cost):
            out = []
            for n, s in enumerate(sigs):
                if s["vr"] <= P["vth"] or s["act"] < P["act"]: continue
                if P["hours"] == "live":
                    if not in_window(s["t"]): continue
                elif P["hours"] != "all" and not (P["hours"][0] <= uhour(s["t"]) < P["hours"][1]): continue
                key = (n, P["stop_lo"], P["stop_hi"], P["tp"])
                if key not in wc: wc[key] = walk(toks[s["mint"]], s, P)
                w = wc[key]
                if not w: continue
                legs, e, xt, why = w
                z = SIZE_F * BOOK_SOL * solpx(s["t"]); c = COSTS[cost](s["liq"], z, solpx(s["t"]))
                ret = sum(f * px * (1 - c) for f, px in legs) / (e * (1 + c)) - 1
                out.append(dict(s, exit_t=xt, ret=ret, why=why, cost=c, pnl=SIZE_F * ret))
            return book(out)
        def ev(P, cost=MAIN):
            tr = run(P, cost); nvI, _ = nightly(tr, dIS); nvO, _ = nightly(tr, dOOS)
            nI = sum(1 for t in tr if bookday(t["t"]) in dIS)
            return dict(tr=tr, nI=nI, nO=len(tr) - nI, is_pd=statistics.fmean(nvI.values()), oos_pd=statistics.fmean(nvO.values()) if nvO else None,
                        is_obj=statistics.fmean(nvI.values()) - daily_se(nvI), nvI=nvI, nvO=nvO)
        G = GRID[tf]; allP = [dict(zip(DIMS, v)) for v in itertools.product(*[G[d] for d in DIMS])]
        t0 = time.time(); IS = {}
        for P in allP:
            tr = run(P, MAIN); nvI, _ = nightly([t for t in tr if bookday(t["t"]) in dIS], dIS)
            nI = sum(1 for t in tr if bookday(t["t"]) in dIS)
            IS[pname(tf, P)] = dict(P=P, nI=nI, is_pd=statistics.fmean(nvI.values()), is_obj=statistics.fmean(nvI.values()) - daily_se(nvI))
        minN = 30 if tf == "1h" else 20
        def lucky(P):
            me = IS[pname(tf, P)]
            return me["is_pd"] > 0 and any(IS[pname(tf, Q)]["is_pd"] <= 0 or IS[pname(tf, Q)]["nI"] < 5 for _, Q in neighbours(tf, P))
        ok = [v for v in IS.values() if v["nI"] >= minN and not lucky(v["P"])]
        best = max(ok, key=lambda v: v["is_obj"]) if ok else max(IS.values(), key=lambda v: v["is_obj"])
        live = ev(LIVE[tf]); tuned = ev(best["P"])
        bands = {c: ev(LIVE[tf], c) for c in COSTS}
        tbands = {c: ev(best["P"], c) for c in COSTS}
        # paired OOS night difference, block bootstrap
        ks = sorted(dOOS); diff = [tuned["nvO"][k] - live["nvO"][k] for k in ks]
        B = block_boot_nights(diff); dm = sorted(statistics.fmean(b) for b in B)
        dci = (dm[int(.025 * len(dm))], dm[int(.975 * len(dm)) - 1]) if diff else (None, None)
        nb = [(d, Q, IS[pname(tf, Q)], ev(Q)) for d, Q in neighbours(tf, best["P"])]
        nbl = [(d, Q, IS[pname(tf, Q)], ev(Q)) for d, Q in neighbours(tf, LIVE[tf])]
        noact = ev(dict(LIVE[tf], act=0.0))
        res[tf] = dict(days=days, dIS=dIS, dOOS=dOOS, nsig=len(sigs), live=live, tuned=tuned, best=best, bands=bands, tbands=tbands, diff=(statistics.fmean(diff) if diff else None, dci),
                       nb=nb, nbl=nbl, lucky_live=lucky(LIVE[tf]), lucky_best=lucky(best["P"]), n_grid=len(allP), secs=time.time() - t0, noact=noact,
                       rank_live=sorted(IS.values(), key=lambda v: -v["is_obj"]).index(IS[pname(tf, LIVE[tf])]) + 1)
        print(tf, "signals", len(sigs), "days", len(days), "grid", len(allP), f"{time.time()-t0:.0f}s", "best", pname(tf, best["P"]), flush=True)
    # combined live book (1h + 15m share max 3 open, one position per token) on the 15m window
    d15 = res["15m"]["days"]; both = book(res["1h"]["live"]["tr"] + res["15m"]["live"]["tr"]); both = [t for t in both if bookday(t["t"]) in d15]
    res["combined"] = dict(tr=both, days=d15)
    json.dump({tf: {k: (v if k not in ("live", "tuned", "bands", "tbands", "nb", "nbl", "noact", "tr") else None) for k, v in r.items()} for tf, r in res.items()},
              open(os.path.join(D, "oc_res_meta.json"), "w"), default=str)
    import pickle; pickle.dump(res, open(os.path.join(D, "oc_res.pkl"), "wb"))
    return res, toks, solpx

if __name__ == "__main__":
    main()
