"""Grid-run the complete-set sim, score on Lab's rubric, write out/ and upsert PMUD_* leaderboard rows (headline grid only)."""
import json, os, sys, itertools, statistics as S, collections
sys.path.insert(0, "/workspace/polymarket-lab/weather")
import pm_score as PS, sim
ROOT = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(ROOT, "data", "markets.json")))
BS = [0.40, 0.42, 0.44, 0.46, 0.48]; TS = [0.94, 0.96, 0.98]; STEPS = [5, 10, 15]
MODELS = [("touch", 0), ("queue", 50), ("queue", 200), ("through", 0)]
grid = list(itertools.product(["1h", "4h"], BS, TS, STEPS, MODELS))
res = {}
for hz, b, T, st, (fm, Q) in grid:
    tr = sim.run(M, hz, b, T, st, fm, Q)
    PS.holdout_split(tr, 0.4)
    sc = PS.score(tr) if tr else {"trades": 0, "net_profit_after_costs": 0}
    pairs = [p for t in tr for p in t["pairs"]]
    sc.update({"n_pairs": len(pairs), "avg_pair_cost": round(S.fmean(pairs), 4) if pairs else None,
               "n_leftover": sum(t["leftover"] for t in tr), "leftover_pnl": round(sum(t["left_pnl"] for t in tr), 2),
               "pair_pnl": round(sum(len(t["pairs"]) * sim.SH - sum(t["pairs"]) * sim.SH for t in tr), 2),
               "markets": sum(1 for m in M if ("4h" in m["series"]) == (hz == "4h"))})
    res[(hz, b, T, st, fm, Q)] = sc
# neighbour flag along b for each (hz,T,step,model)
for hz, T, st, (fm, Q) in itertools.product(["1h", "4h"], TS, STEPS, MODELS):
    fl = PS.lucky([(b, res[(hz, b, T, st, fm, Q)]) for b in BS])
    for b in BS: res[(hz, b, T, st, fm, Q)]["lucky_number"] = fl[b]
def name(k):
    hz, b, T, st, fm, Q = k
    return f"PMUD_{hz}_b{int(b*100)}_T{int(T*100)}_c{st}_{fm}{Q if fm=='queue' else ''}"
rows = []
for k, v in res.items():
    hz, b, T, st, fm, Q = k
    if st == 10 and T == 0.96 and fm == "queue" and Q == 50:      # headline grid -> leaderboard
        rows.append(dict(v, variant=name(k), family="polymarket_updown", variants_tried=len(grid),
                         note=f"Up/Down complete-set PAPER sim on public taker tape; {hz}; leg1 bid {b}, target pair {T}; checks every {st}m; queue-ahead {Q} sh; 7d BTC+ETH; pairs={v['n_pairs']} avg pair cost={v['avg_pair_cost']} leftovers={v['n_leftover']} (pnl {v['leftover_pnl']})"))
PS.upsert_leaderboard(rows, "PMUD_")
json.dump({name(k): v for k, v in res.items()}, open(os.path.join(ROOT, "out", "grid.json"), "w"), indent=1)
L = ["| variant | mkts w/ fills | pairs | avg pair cost | leftovers | leftover $ | pair $ | net $ | mean ret | CI95 | OOS | score | cand | lucky |", "|" + "---|" * 14]
for k in sorted(res, key=lambda k: (k[0], k[4], k[5], k[3], k[2], k[1])):
    v = res[k]
    if k[3] != 10 and not (k[4] == "queue" and k[5] == 50): continue
    L.append(f"| {name(k)} | {v['trades']} | {v['n_pairs']} | {v['avg_pair_cost']} | {v['n_leftover']} | {v['leftover_pnl']} | {v['pair_pnl']} | {v['net_profit_after_costs']} | {v.get('mean_ret','')} | {v.get('ci95_mean_ret','')} | {v.get('holds_out_of_sample','')} | {v.get('score_total','')} | {v.get('candidate','')} | {v.get('lucky_number','')} |")
open(os.path.join(ROOT, "out", "scorecard.md"), "w").write("# Polymarket Up/Down complete-set - scorecard (PAPER SIM)\n\n" + "\n".join(L) + "\n")
print("\n".join(L))
