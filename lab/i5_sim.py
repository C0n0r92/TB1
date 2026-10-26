"""PAPER ONLY. Ideas-5 (I5_) quick-exit simulator shared by ideas 1,2,3,5 (Zero 2026-10-24 first read).
Event = dict(t=signal ts (s), bars=[[t,o,h,l,c,(v)],...] (step seconds), step, liq=pool liq USD at signal, liq_kind, key, src).
Entry at t+delay inside the bar containing it: px = o + frac*(c-o) (frac = position inside bar), x (1 + slip).
Costs: 2%/side fee + $0.05/tx + slippage 0.5% + 2*size/liq (liq ~ sqrt(price) between polls), cap 50%.
Exit checks per bar: STOP FIRST (open<=stop -> fill open; close<stop -> fill close; else stop x 0.975), then TP (fill max(open,tp)),
then time limit (exit at close of the bar that reaches entry+hold). Entry bar: conservative model 'A' checks the stop against the
entry bar's LOW (we cannot see intra-minute order); 'B' (optimistic) starts checking from the next bar. Max 3 open per variant.
Holdout = latest 30% of events by time. Selection on in-sample only."""
import math, statistics, random, itertools, datetime as dt
import scoring
FEE = 0.02; TX = 0.05; BASE_SLIP = 0.005; IMP = 2.0; SIZE = 10.0; EQUITY = 100.0
TPS = (0.10, 0.15, 0.20); SLS = (0.10, 0.15); HOLDS = (5, 15, 30); DELAYS = (5, 15)
GRID = list(itertools.product(TPS, SLS, HOLDS, DELAYS))
def slip(size, liq): return min(0.5, BASE_SLIP + IMP * size / max(liq, 500.0))
def rname(r): tp, sl, h, d = r; return f"tp{int(tp*100):02d}_sl{int(sl*100):02d}_h{h:02d}_d{d:02d}"

def sim1(e, tp, sl, hold_m, delay, model="A", size=SIZE):
    bars, step = e["bars"], e["step"]; te = e["t"] + delay
    i = next((k for k, b in enumerate(bars) if b[0] <= te < b[0] + step), None)
    if i is None:
        i = next((k for k, b in enumerate(bars) if b[0] >= te and b[0] - te <= 120), None)   # first bar within 2 min
        if i is None: return None
        frac = 0.0
    else: frac = (te - bars[i][0]) / step
    o, h, l, c = bars[i][1:5]; mid0 = o + frac * (c - o)
    if mid0 <= 0: return None
    liq0 = e["liq"]; s_in = slip(size, liq0); px_in = mid0 * (1 + s_in)
    tokens = size * (1 - FEE) / px_in - 0.0; cost_in = TX
    stop = px_in * (1 - sl); tgt = px_in * (1 + tp); t_end = te + hold_m * 60
    exit_px = None; why = None; t_exit = None; mn = 1.0
    if model == "A" and l <= stop and frac > 0:
        exit_px = c if c < stop else stop * 0.975; why = "stop"; t_exit = bars[i][0] + step
    k = i + 1
    while exit_px is None and k < len(bars):
        b = bars[k]; o, h, l, c = b[1:5]
        if b[0] >= t_end: exit_px = o; why = "time"; t_exit = b[0]; break   # next bar open after time limit
        mn = min(mn, l / px_in)
        if l <= stop:
            exit_px = o if o <= stop else (c if c < stop else stop * 0.975); why = "stop"; t_exit = b[0] + step; break
        if h >= tgt: exit_px = max(o, tgt); why = "tp"; t_exit = b[0] + step; break
        if b[0] + step >= t_end: exit_px = c; why = "time"; t_exit = b[0] + step; break
        k += 1
    if exit_px is None:                          # data ran out (pool stopped trading = no bars): last close, flagged
        last = bars[-1]; exit_px = last[4]; why = "nodata"; t_exit = max(last[0] + step, te)
    liq_x = liq0 * math.sqrt(max(exit_px / mid0, 1e-6)); s_out = slip(size * exit_px / px_in, liq_x)
    proceeds = tokens * exit_px * (1 - s_out) * (1 - FEE) - TX - cost_in
    ret = proceeds / size - 1
    return dict(t=e["t"], t_entry=te, t_exit=t_exit, ret=ret, pnl=ret * size, why=why, key=e.get("key"), src=e.get("src"), sl_in=s_in)

def run(events, tp, sl, hold_m, delay, model="A", split=None, size=SIZE):
    ev = sorted(events, key=lambda x: x["t"]); open_ = []; out = []; skipped = 0
    for e in ev:
        te = e["t"] + delay; open_ = [x for x in open_ if x > te]
        if len(open_) >= 3: skipped += 1; continue
        r = sim1(e, tp, sl, hold_m, delay, model, size)
        if r is None: continue
        r["is_oos"] = split is not None and e["t"] >= split; out.append(r); open_.append(r["t_exit"])
    return out, skipped

def boot_ci(x, it=2000, seed=7):
    if len(x) < 2: return (None, None)
    R = random.Random(seed); m = sorted(statistics.fmean(R.choices(x, k=len(x))) for _ in range(it)); return m[int(.025 * it)], m[int(.975 * it)]

def stats(tr):
    def part(z):
        if not z: return dict(n=0, mean=None, win=None, tot=0.0)
        return dict(n=len(z), mean=statistics.fmean(t["ret"] for t in z), win=sum(t["ret"] > 0 for t in z) / len(z), tot=sum(t["pnl"] for t in z))
    A, I, O = part(tr), part([t for t in tr if not t["is_oos"]]), part([t for t in tr if t["is_oos"]])
    ci = boot_ci([t["ret"] for t in tr]); mc = scoring.mc_drawdown([t["pnl"] for t in tr], EQUITY) if tr else None
    sc = scoring.score(dict(trades=len(tr), mean_ret=A["mean"], ci_lo=ci[0] if ci[0] is not None else -1), None, tr, mc)
    span_h = (max(t["t"] for t in tr) - min(t["t"] for t in tr)) / 3600 if len(tr) > 1 else None
    return dict(all=A, is_=I, oos=O, ci=ci, mc=mc, sc=sc, med=statistics.median([t["ret"] for t in tr]) if tr else None,
                ex_best=(sum(t["pnl"] for t in tr) - max(t["pnl"] for t in tr)) if tr else 0.0,
                why={w: sum(t["why"] == w for t in tr) for w in ("tp", "stop", "time", "nodata")}, span_h=span_h)

def split_of(events, frac=0.3):
    ts = sorted(e["t"] for e in events); return ts[int(len(ts) * (1 - frac))] if ts else None

def grid(events, model="A", span_h=None):
    sp = split_of(events); G = {}
    for r in GRID:
        tr, sk = run(events, *r, model=model, split=sp); s = stats(tr); s["skipped"] = sk; s["tr"] = tr
        s["per_h"] = len(tr) / span_h if span_h else None; G[r] = s
    return G, sp

def best_is(G, delay=None):
    c = [r for r in G if delay is None or r[3] == delay]
    return max(c, key=lambda r: (G[r]["is_"]["mean"] if G[r]["is_"]["n"] else -9))

def neighbours(G, r):
    tp, sl, h, d = r; nb = []
    for i, ax in enumerate((TPS, SLS, HOLDS)):
        j = ax.index(r[i])
        for jj in (j - 1, j + 1):
            if 0 <= jj < len(ax): q = list(r); q[i] = ax[jj]; nb.append(tuple(q))
    return nb

def rows_for(prefix, G, family, note, label=""):
    """leaderboard rows (same columns as FE) + lucky flags along each axis."""
    board = [dict(variant=f"I5_{prefix}_{rname(r)}", trades=G[r]["all"]["n"], net_profit_after_costs=G[r]["all"]["tot"]) for r in G]
    fams = {}
    for r in G:
        v = f"I5_{prefix}_{rname(r)}"; tp, sl, h, d = r
        fams.setdefault(f"tp_{sl}_{h}_{d}", []).append((tp, v)); fams.setdefault(f"sl_{tp}_{h}_{d}", []).append((sl, v)); fams.setdefault(f"h_{tp}_{sl}_{d}", []).append((h, v))
    lf = scoring.lucky_flags(board, fams); rows = []; cfgs = []
    for r in G:
        S = G[r]; v = f"I5_{prefix}_{rname(r)}"; A, I, O = S["all"], S["is_"], S["oos"]
        oci = boot_ci([t["ret"] for t in S["tr"] if t["is_oos"]])
        ho = ("yes" if (I["tot"] > 0 and (O["mean"] or 0) > 0 and (oci[0] or -1) > 0) else "no") if O["n"] >= 20 else f"insufficient (n_out={O['n']}<20)"
        cand = "yes" if S["sc"]["score_total"] >= 18 and A["n"] >= 50 and ho == "yes" and "LOOKAHEAD" not in label else "no"
        rows.append(dict(variant=v, trades=A["n"], win_rate=round(A["win"], 3) if A["n"] else "", net_profit_after_costs=round(A["tot"], 2),
            max_drawdown=round(S["mc"][1] * 100, 2) if S["mc"] else "", holds_out_of_sample=ho, n_in_sample=I["n"], n_out_of_sample=O["n"],
            mean_ret=round(A["mean"], 4) if A["n"] else "", median_ret=round(S["med"], 4) if A["n"] else "",
            ci95_mean_ret=f"[{S['ci'][0]:+.4f},{S['ci'][1]:+.4f}]" if S["ci"][0] is not None else "",
            oos_mean_ret=round(O["mean"], 4) if O["n"] else "", in_net_pnl=round(I["tot"], 2), out_net_pnl=round(O["tot"], 2),
            **{k: S["sc"][k] for k in ("sc_oos_risk", "sc_drawdown", "sc_trades", "sc_edge", "sc_stability", "score_total", "nights", "nights_profitable")},
            net_ex_best_trade=round(S["ex_best"], 2), mc_dd_p5=round(S["mc"][0], 3) if S["mc"] else "", mc_dd_p50=round(S["mc"][1], 3) if S["mc"] else "",
            mc_dd_p95=round(S["mc"][2], 3) if S["mc"] else "", candidate=cand, lucky_number=lf.get(v, "n/a (not profitable)"), family=family,
            note=(label + " " if label else "") + note))
        cfgs.append(dict(family=family, tp=r[0], sl=r[1], hold=r[2], delay=r[3], model="A", fee=FEE, size=SIZE, name=v))
    return rows, cfgs
