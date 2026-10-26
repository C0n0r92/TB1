"""METHOD.md scoring: 1-5 on five criteria, Monte-Carlo drawdown, night stability, lucky-number flags, variants_tried."""
import hashlib, json, os, random, statistics
from labcore import DATA, night_of, atomic_write, load_json

def mc_drawdown(pnls, equity, iters=1000, seed=7):
    """Reshuffle trade order `iters` times -> (p5, p50, p95) of max drawdown as a fraction of starting equity."""
    if not pnls: return None
    rnd, dds = random.Random(seed), []
    for _ in range(iters):
        x = pnls[:]; rnd.shuffle(x); eq = pk = equity; m = 0.0
        for p in x:
            eq += p; pk = max(pk, eq); m = max(m, pk - eq)
        dds.append(m / equity)
    dds.sort(); q = lambda f: dds[min(len(dds) - 1, int(f * len(dds)))]
    return q(0.05), q(0.50), q(0.95)

def nights(trades):
    d = {}
    for t in trades: d.setdefault(night_of(t["t"]), 0.0); d[night_of(t["t"])] += t["pnl"]
    return d

def band(x, cuts):            # cuts ascending -> 1..5
    return 1 + sum(x > c for c in cuts) if x is not None else 1

def score(st_all, st_out, closed, mc):
    s = {}
    oos = [t["ret"] for t in closed if t.get("is_oos")]
    if len(oos) >= 2 and statistics.pstdev(oos) > 0:
        r = statistics.fmean(oos) / statistics.pstdev(oos); s["sc_oos_risk"] = 1 if r <= 0 else band(r, [-1e9, 0.1, 0.2, 0.35])
    else: s["sc_oos_risk"] = 1
    p95 = mc[2] if mc else None
    s["sc_drawdown"] = 1 if p95 is None else 5 - sum(p95 > c for c in (0.10, 0.20, 0.30, 0.50)) if p95 <= 0.50 else 1
    s["sc_trades"] = band(st_all["trades"], [9, 24, 49, 99])
    m = st_all.get("mean_ret")
    if m is None: s["sc_edge"] = 1
    elif st_all.get("ci_lo", -1) > 0: s["sc_edge"] = 5
    else: s["sc_edge"] = 4 if m > 0.05 else 3 if m > 0 else 2 if m > -0.05 else 1
    n = nights(closed)
    if len(n) < 3: s["sc_stability"] = 1
    else:
        f = sum(v > 0 for v in n.values()) / len(n)
        s["sc_stability"] = 5 if f >= 0.8 else 4 if f >= 0.6 else 3 if f >= 0.5 else 2 if f >= 0.3 else 1
    s["score_total"] = sum(s.values()); s["nights"] = len(n)
    s["nights_profitable"] = sum(v > 0 for v in n.values())
    return s

def lucky_flags(board, families):
    """families: {family: [(value, variant_name)]}. A profitable member whose sweep neighbour is unprofitable (or has
    < 5 trades) = 'single lucky number'."""
    byname = {b["variant"]: b for b in board}; flag = {}
    for fam, mem in families.items():
        mem = sorted(mem, key=lambda x: x[0])
        prof = [(byname[n]["trades"] or 0) >= 5 and (byname[n]["net_profit_after_costs"] or 0) > 0 for _, n in mem]
        for i, (_, n) in enumerate(mem):
            if not prof[i]: continue
            nb = [prof[j] for j in (i - 1, i + 1) if 0 <= j < len(mem)]
            if nb and not all(nb): flag[n] = f"yes ({fam})"
            else: flag.setdefault(n, "no")
    return flag

def variants_tried(variants):
    p = os.path.join(DATA, "variants_tried.json"); d = load_json(p, {}) or {}
    for V in variants:
        h = hashlib.sha1(json.dumps({k: v for k, v in V.items() if k != "name"}, sort_keys=True, default=str).encode()).hexdigest()[:12]
        d.setdefault(h, V["name"])
    atomic_write(p, json.dumps(d, indent=0)); return len(d)
