import pickle, statistics, collections, datetime as dt
from if_backtest import stats, EXITS, FAST, WS, RS, DELAYS
meta, G = pickle.load(open("out/.if_grid.pkl", "rb"))
span_h = (meta["span"][1] - meta["span"][0]) / 3600
print(meta["n_pools"], "pools", meta["days"][0], meta["days"][-1], round(span_h), "h")
res = {}
for k, tr in G.items():
    a, i, o = stats(tr, "net_p1"); b, bi, bo = stats(tr, "net_base"); res[k] = (a, i, o, b, bi, bo)
pos_is = [k for k, v in res.items() if v[1]["n"] >= 20 and v[1]["mean"] > 0]
pos_both = [k for k in pos_is if res[k][2]["n"] >= 5 and res[k][2]["mean"] > 0]
print("variants", len(res), "IS>0 (n>=20):", len(pos_is), "IS&OOS>0:", len(pos_both))
allm = [v[0]["mean"] for v in res.values() if v[0]["n"]]
print("mean of variant means p1", statistics.fmean(allm), "best", max(allm), "worst", min(allm))
rk = sorted([k for k in res if res[k][1]["n"] >= 20], key=lambda k: -res[k][1]["mean"])
def nm(k): W, R, d, (tp, sl, h) = k; return f"IF_w{W}_r{int(R)}_d{d:02d}_tp{int(tp*100):02d}_sl{int(sl*100):02d}_h{h:02d}"
for k in rk[:8]:
    a, i, o, b, bi, bo = res[k]
    print(nm(k), "n", a["n"], f"win {a['win']:.0%} p1 {a['mean']:+.3f} base {b['mean']:+.3f} | IS n{i['n']} {i['mean']:+.3f} | OOS n{o['n']} {o['mean']:+.3f} ci {o['ci'][0] if o['ci'][0] is None else round(o['ci'][0],3)},{o['ci'][1] if o['ci'][1] is None else round(o['ci'][1],3)} win {o.get('win',0):.0%}")
print("radar-style exit +20/-15/60 vs 30:")
for W in WS:
  for R in RS:
    for d in (15,):
      for ex in ((0.2,0.15,60),(0.2,0.15,30)):
        a,i,o,b,bi,bo = res[(W,R,d,ex)]; print(" ", nm((W,R,d,ex)), a["n"], f"win {a.get('win',0):.0%} p1 {a.get('mean',0):+.3f} IS {i.get('mean',0):+.3f} OOS n{o['n']} {o.get('mean',0):+.3f}")
# by delay / by exit dims averaged
for name, idx in (("delay", 2), ("W", 0), ("R", 1)):
    d = collections.defaultdict(list)
    for k, v in res.items():
        if v[0]["n"]: d[k[idx]].append(v[0]["mean"])
    print(name, {kk: round(statistics.fmean(vv), 4) for kk, vv in sorted(d.items())})
dd = collections.defaultdict(list)
for k, v in res.items():
    if v[0]["n"]: dd[k[3]].append(v[0]["mean"])
print("exit avg", sorted([(round(statistics.fmean(v), 4), e) for e, v in dd.items()], reverse=True)[:6])
pickle.dump(res, open("out/.if_res.pkl", "wb"))
