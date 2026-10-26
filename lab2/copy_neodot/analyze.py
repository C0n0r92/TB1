"""Summarise replay_rows.json -> results.md / results.csv. Bootstrap 5000, seed 7, 95% percentile CI."""
import json, os, random, csv, statistics as st
H = os.path.dirname(os.path.abspath(__file__)); D = json.load(open(os.path.join(H, "replay_rows.json")))
R = D["rows"]
def boot(v, n=5000, seed=7):
    rnd = random.Random(seed); m = sum(v) / len(v); bs = sorted(sum(rnd.choice(v) for _ in v) / len(v) for _ in range(n))
    return m, bs[int(.025 * n)], bs[int(.975 * n)], sum(1 for b in bs if b > 0) / n
def sel(**k): return [r for r in R if all(r[a] == b for a, b in k.items())]
def pct(x): return f"{100*x:+.1f}%"
out = []; csvrows = []
splits = (("train", lambda r: r["split"] == "train"), ("held_out", lambda r: r["split"] == "held_out"), ("all", lambda r: True))
out.append("## Main grid (base costs: venue fee + CPMM slippage + 5000 lamports + 0.001 SOL priority per tx)\n")
out.append("| split | exit | size | L | n | mean/trade | 95% CI | P(mean>0) boot | median | win% | his gross mean (same trips) |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|")
for sp, f in splits:
    for ex in ("mirror", "ladder"):
        for x in (0.05, 0.1):
            for L in (0, 5, 15, 30):
                rr = [r for r in sel(exit=ex, size=x, L=L, cost="base") if f(r)]; v = [r["ret"] for r in rr]
                m, lo, hi, pp = boot(v); hg = st.mean(r["his_gross"] for r in rr)
                out.append(f"| {sp} | {ex} | {x} | {'0 (ref)' if L == 0 else L} | {len(v)} | {pct(m)} | [{pct(lo)}, {pct(hi)}] | {pp:.2f} | {pct(st.median(v))} | {100*sum(1 for a in v if a > 0)/len(v):.0f}% | {pct(hg)} |")
                csvrows.append(dict(split=sp, exit=ex, size=x, L=L, cost="base", n=len(v), mean=m, lo=lo, hi=hi, p_pos=pp, median=st.median(v)))
out.append("\n## Cost of each latency step (paired, same trips; mean difference in return per trade, 95% bootstrap CI)\n")
out.append("| split | exit | size | step | mean cost per trade | 95% CI |"); out.append("|---|---|---|---|---|---|")
for sp, f in splits:
    for ex in ("mirror", "ladder"):
        for x in (0.05, 0.1):
            for a, b in ((0, 5), (5, 15), (15, 30), (5, 30)):
                A = {r["i"]: r["ret"] for r in sel(exit=ex, size=x, L=a, cost="base") if f(r)}
                B = {r["i"]: r["ret"] for r in sel(exit=ex, size=x, L=b, cost="base") if f(r)}
                v = [A[i] - B[i] for i in A]; m, lo, hi, _ = boot(v)
                out.append(f"| {sp} | {ex} | {x} | {a}s→{b}s | {pct(-m) if m < 0 else '-'+pct(m)[1:]} | [{pct(-hi)}, {pct(-lo)}] |")
                csvrows.append(dict(split=sp, exit=ex, size=x, L=f"{a}->{b}", cost="step", n=len(v), mean=-m, lo=-hi, hi=-lo))
out.append("\n(step cost shown as change in return: negative = latency costs you that many % points per trade)\n")
out.append("## Cost sensitivity (mirror exit, all reconstructed trips)\n")
out.append("| size | L | base (0.001 prio) | low prio 0.0002 | high prio 0.003 | +1% bot fee/swap |"); out.append("|---|---|---|---|---|---|")
for x in (0.05, 0.1):
    for L in (5, 15, 30):
        c = [boot([r["ret"] for r in sel(exit="mirror", size=x, L=L, cost=t)])[0] for t in ("base", "lowprio", "highprio", "botfee1pct")]
        out.append(f"| {x} | {L} | " + " | ".join(pct(a) for a in c) + " |")
out.append("\n## Per-trip (mirror, 0.1 SOL, base) \n")
out.append("| # | sym | split | venue model | his gross | L0 | L5 | L15 | L30 | ladder L5 | ladder L5 events |"); out.append("|---|---|---|---|---|---|---|---|---|---|---|")
for i in sorted({r["i"] for r in R}):
    g = {(r["L"], r["exit"]): r for r in R if r["i"] == i and r["size"] == 0.1 and r["cost"] == "base"}
    r0 = g[(0, "mirror")]
    out.append(f"| {i} | {r0['sym']} | {r0['split']} | {r0['kind']} | {pct(r0['his_gross'])} | " + " | ".join(pct(g[(L, 'mirror')]['ret']) for L in (0, 5, 15, 30)) + f" | {pct(g[(5,'ladder')]['ret'])} | {' '.join(str(e[0]) for e in g[(5,'ladder')]['log'])} |")
out.append("\n## Not reconstructed\n")
out.append("| # | sym | split | his gross | reason |"); out.append("|---|---|---|---|---|")
for u in D["unrec"]: out.append(f"| {u['i']} | {u['sym']} | {u['split']} | {u['his_gross']:+.1f}% | {u['why']} |")
ru = [u["his_gross"] / 100 for u in D["unrec"]]; rr = [r["his_gross"] for r in sel(exit="mirror", size=0.1, L=0, cost="base")]
out.append(f"\nHis own gross on unreconstructed trips: mean {pct(st.mean(ru))} (n={len(ru)}) vs reconstructed {pct(st.mean(rr))} (n={len(rr)}).")
open(os.path.join(H, "results_tables.md"), "w").write("\n".join(out))
with open(os.path.join(H, "results.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(csvrows[0].keys()) + ["p_pos", "median"]); w.writeheader(); [w.writerow(r) for r in csvrows]
print("\n".join(out))
