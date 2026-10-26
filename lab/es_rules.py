#!/usr/bin/env python3
"""PAPER ONLY. ES task 3: candle-only exit rules applied to winners' own entries. PRE-REGISTERED on batch 1 (families + grids fixed
before any batch-2 rule result was looked at; feature effects on b1: exits come deeper below peak / below entry, volume roll-over NOT
significant on b1). Entry = close of candle at/after t+10 s (as wn_b2.trail). Hard stop close <= -25% (+2 pts slip), time stop 6 h / end of data.
Signal exits fill at the signal candle close with +2 pts slip (same as wn_b2 trail exits). Cost 4.7% if approx mcap < $1M else 2%.
Families:  VOL  exit when 3-min volume < X * peak 3-min volume since entry AND close <= peak_close*(1-y), armed once peak >= entry*(1+z)
           RED  exit when >= k consecutive red 1-m candles AND close <= peak_close*(1-y)
           UW   exit when close <= entry*(1-u) after h minutes held (cut losers early; the b1 'exits are underwater' effect)
-> out/es_rules.json"""
import json, bisect, random, statistics as S, datetime as dt, collections
from es_common import trips, summ, boot
from cl_sim import sim, DEFAULT
T_ = trips()
def run(tr, rule, sl=0.25, tmax=6 * 3600):
    rows = tr["rows"]; i = tr["i0"]; e = rows[i][4]; cost = tr["cost"]; pk = e; pkc = e; vq = collections.deque(); pk3 = 0.0; reds = 0
    fam = rule[0]
    for x in rows[i + 1:]:
        c = x[4]
        if x[0] - rows[i][0] > tmax: return c / e - 1 - cost, x[0], "time"
        pk = max(pk, x[2] or c); pkc = max(pkc, c)
        vq.append((x[0], x[5] or 0))
        while vq and vq[0][0] <= x[0] - 180: vq.popleft()
        v3 = sum(v for _, v in vq); pk3 = max(pk3, v3)
        reds = reds + 1 if c < x[1] else 0
        if c <= e * (1 - sl): return c / e - 1 - cost - 0.02, x[0], "stop"
        if fam == "VOL":
            _, X, y, z = rule
            if pk >= e * (1 + z) and v3 < X * pk3 and c <= pkc * (1 - y): return min(c / e, 10) - 1 - cost - 0.02, x[0], "sig"
        elif fam == "RED":
            _, k, y = rule
            if reds >= k and c <= pkc * (1 - y): return min(c / e, 10) - 1 - cost - 0.02, x[0], "sig"
        elif fam == "UW":
            _, u, h = rule
            if x[0] - rows[i][0] >= h * 60 and c <= e * (1 - u): return c / e - 1 - cost - 0.02, x[0], "sig"
        elif fam == "TRAIL":
            _, tp, arm = rule
            if pk >= e * (1 + arm) and c <= pk * (1 - tp): return min(c / e, 10) - 1 - cost - 0.02, x[0], "sig"
    return rows[-1][4] / e - 1 - cost, rows[-1][0], "eod"
RULES = [("VOL", X, y, z) for X in (0.15, 0.3, 0.5) for y in (0.1, 0.2, 0.3) for z in (0.0, 0.2)] + \
        [("RED", k, y) for k in (2, 3, 4) for y in (0.1, 0.2, 0.3)] + [("UW", u, h) for u in (0.05, 0.1, 0.15) for h in (15, 30, 60)]
name = lambda r: "ES_" + r[0] + "_" + "_".join(str(int(v * 100)) if isinstance(v, float) else str(v) for v in r[1:])
NB = {"VOL": [(0.15, 0.3, 0.5), (0.1, 0.2, 0.3), (0.0, 0.2)], "RED": [(2, 3, 4), (0.1, 0.2, 0.3)], "UW": [(0.05, 0.1, 0.15), (15, 30, 60)]}
def neighbours(r):
    out = []
    for j, grid in enumerate(NB[r[0]]):
        k = grid.index(r[1 + j])
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(grid): rr = list(r); rr[1 + j] = grid[kk]; out.append(tuple(rr))
    return out
pooled = sorted(T_, key=lambda tr: tr["t"]); cut = pooled[int(len(pooled) * 0.7)]["t"]
TR = collections.defaultdict(list)   # name -> list of dict(t, ret, b, late)
def add(nm, tr, ret, te=None, why=None): TR[nm].append(dict(t=tr["t"], ret=ret, b=tr["b"], late=tr["t"] >= cut, mint=tr["mint"], te=te, why=why))
for tr in T_:
    add("ACTUAL", tr, tr["act"])
    s = sim(dict(rows=tr["rows"], supply=1e9), tr["t"], dict(DEFAULT, cost_pump=tr["cost"], cost_big=tr["cost"]))
    if s: add("ES_BASE_fixed_SL25TP50_2h", tr, s["ret"])
    v = run(tr, ("TRAIL", 0.15, 0.2)); add("ES_BASE_trail15_arm20", tr, v[0], v[1], v[2])
    for r in RULES:
        v = run(tr, r); add(name(r), tr, v[0], v[1], v[2])
def st(x): return summ([y["ret"] for y in x])
res = dict(cut=dt.datetime.fromtimestamp(cut, dt.timezone.utc).isoformat(), rows={})
for nm, L in TR.items():
    res["rows"][nm] = dict(b1=st([x for x in L if x["b"] == "b1"]), b2=st([x for x in L if x["b"] == "b2"]),
                          early=st([x for x in L if not x["late"]]), late=st([x for x in L if x["late"]]),
                          sig_share=round(sum(x["why"] == "sig" for x in L) / len(L), 3) if L[0]["why"] else None)
best = {}
for fam in ("VOL", "RED", "UW"):
    c = [r for r in RULES if r[0] == fam]; b = max(c, key=lambda r: res["rows"][name(r)]["b1"]["mean"]); best[fam] = name(b)
    res.setdefault("picked_on_b1", {})[fam] = dict(rule=name(b), neighbours={name(n): {k: res["rows"][name(n)][k].get("mean") for k in ("b1", "b2")} for n in neighbours(b)})
res["luck"] = {}
for r in RULES:
    m = res["rows"][name(r)]["b1"]["mean"]
    res["luck"][name(r)] = "yes" if m > 0 and any(res["rows"][name(n)]["b1"]["mean"] <= 0 for n in neighbours(r)) else "no"
# post-exit drift of rule exits (do rule exits also precede declines?) for the picked rules
def drift(nm, H):
    out = {"b1": [], "b2": []}; idx = {(tr["mint"], tr["t"]): tr for tr in T_}
    for x in TR[nm]:
        if x["why"] != "sig": continue
        tr = idx[(x["mint"], x["t"])]
        from es_common import px
        p0 = px(tr, x["te"] + 59)
        if p0 and tr["rows"][-1][0] >= x["te"] + 59 + H: out[x["b"]].append(px(tr, x["te"] + 59 + H) / p0 - 1)
    return {b: summ(v) for b, v in out.items()}
res["rule_exit_drift"] = {nm: {"30m": drift(nm, 1800), "120m": drift(nm, 7200)} for nm in list(best.values()) + ["ES_BASE_trail15_arm20"]}
json.dump(dict(res, trades={k: v for k, v in TR.items()}), open("/workspace/lab/out/es_rules.json", "w"), indent=0)
for nm, v in res["rows"].items():
    print(f"{nm:28s} b1 n{v['b1']['n']} {v['b1']['mean']:+.3f} {v['b1']['ci_mean']} | b2 n{v['b2']['n']} {v['b2']['mean']:+.3f} {v['b2']['ci_mean']} | early {v['early']['mean']:+.3f} late {v['late']['mean']:+.3f} sig {v['sig_share']} luck {res['luck'].get(nm,'')}")
print(json.dumps(res["picked_on_b1"], indent=1)); print(json.dumps(res["rule_exit_drift"], indent=0)[:3000]); print("cut", res["cut"])
