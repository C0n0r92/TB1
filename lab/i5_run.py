"""I5 runner: quick-exit grid for the five-ideas first read. Paper only, cached data only."""
import json, pickle, sys, time, statistics
import i5_sim as M, i5_events as E, i5_more as X
OUT = "/workspace/lab/out"
def span(ev): ts = [e["t"] for e in ev]; return (max(ts) - min(ts)) / 3600 if len(ts) > 1 else None
def summ(G, sp, ev):
    b = M.best_is(G); S = G[b]; nb = M.neighbours(G, b)
    pos = [M.rname(r) for r in G if G[r]["all"]["n"] and G[r]["all"]["mean"] > 0]
    oos_pos = [M.rname(r) for r in G if G[r]["oos"]["n"] and G[r]["oos"]["mean"] > 0]
    f = lambda z: None if z is None else round(z, 4)
    return dict(n_events=len(ev), best=M.rname(b), n=S["all"]["n"], win=f(S["all"]["win"]), mean=f(S["all"]["mean"]), med=f(S["med"]),
                is_n=S["is_"]["n"], is_mean=f(S["is_"]["mean"]), oos_n=S["oos"]["n"], oos_mean=f(S["oos"]["mean"]), ci=[f(x) for x in S["ci"]],
                oos_ci=[f(x) for x in M.boot_ci([t["ret"] for t in S["tr"] if t["is_oos"]])],
                why=S["why"], score=S["sc"]["score_total"], sc={k: S["sc"][k] for k in S["sc"] if k.startswith("sc_")},
                nbrs={M.rname(r): (f(G[r]["all"]["mean"]), f(G[r]["oos"]["mean"])) for r in nb},
                n_pos=len(pos), pos=pos[:8], n_oos_pos=len(oos_pos), grid_mean=f(statistics.fmean(G[r]["all"]["mean"] for r in G if G[r]["all"]["n"])),
                span_h=span(ev), per_h=(S["all"]["n"] / span(ev)) if span(ev) else None, ex_best=round(S["ex_best"], 2), skipped=S["skipped"],
                split=sp, max_ret=f(max((t["ret"] for t in S["tr"]), default=None)))
def sets():
    ev, empty = E.graduations(); yield "I2", "G0", ev, "", f"all graduations (backfill on-chain sample); {empty if isinstance(empty,int) else len(empty)} never-traded pools excluded"
    yield "I2", "GF", E.grad_filtered(ev), "PROXY", "graduations, enter 5 min after migration if pump-curve liq>=$40k and first-5-min vol>=$20k (holder filter approximated by early volume)"
    for s, nm in (("EB_PIT_n3_w30", "C3pit"), ("EB_PIT_n2_w30", "C2pit"), ("EB_ALL_n3_w30", "C3all")):
        e, la = E.cl_proxy(s); yield "I1", nm, e, ("PROXY LOOKAHEAD" if la else "PROXY"), f"Scout early-buyer confluence {s} as stand-in (0 live-leader 3+ consensus events exist)"
    d, c = X.dips(); d2, c2 = X.dips_coarse(); yield "I3", "Dspec", d + d2, "", f"dip 30-50%/<=10min, liq>=$200k at signal (1m {c}, coarse {c2}); creator-selling untested"
    d, c = X.dips(min_liq=50e3); yield "I3", "D50k", d, "PROXY", f"dip 30-50%/<=10min on 1m, liq>=$50k (relaxed from $200k for n) {c}; LP burned by construction, creator-selling untested"
    r, c = X.revivals(); yield "I5", "Rall", r, "PROXY", f"revival: bar vol/liq (5-min rate) >=5x trailing-24h mean, age>=1d, {c}; 15m bars = 15-min window"
    r, c = X.revivals(green=True); yield "I5", "Rgreen", r, "PROXY", f"revival as Rall + green spike bar {c}"
if __name__ == "__main__":
    R = {}; ROWS = []; CFG = []
    for idea, nm, ev, label, note in sets():
        t = time.time()
        for model in ("A", "B"):
            G, sp = M.grid(ev, model=model)
            R[f"{idea}_{nm}_{model}"] = dict(summ(G, sp, ev), label=label, note=note)
            if model == "A":
                rows, cfgs = M.rows_for(f"{idea}{nm}", G, f"I5_{idea}", note, label); ROWS += rows; CFG += cfgs
            print(idea, nm, model, json.dumps({k: R[f'{idea}_{nm}_{model}'][k] for k in ('n_events','best','n','win','mean','is_n','is_mean','oos_n','oos_mean','oos_ci','score','n_pos','n_oos_pos','grid_mean','per_h','why')}), round(time.time() - t, 1), flush=True)
            print("   nbrs", R[f"{idea}_{nm}_{model}"]["nbrs"], flush=True)
    json.dump(R, open(OUT + "/.i5_results.json", "w"), indent=1, default=str)
    json.dump(dict(rows=ROWS, variant_configs=CFG), open(OUT + "/.i5_rows.json", "w"), default=str)
    print("rows", len(ROWS))
