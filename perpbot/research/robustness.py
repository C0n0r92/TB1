"""Diagnostics: OOS across the whole grid for the vote blends (is the winner a lucky cell?), per-symbol split, buy&hold."""
from backtest import *
for name, fn in [("Vote 3-of-4", vote_fn(list(STRATS), 3)), ("Vote 2-of-3", vote_fn(["EMA50/200","Supertrend","BB-breakout"], 2))]:
    for tf, sm in itertools.product(TFS, STOPS):
        i = metrics(*book(fn, tf, sm, "IS")); o = metrics(*book(fn, tf, sm, "OOS"))
        print(f"{name} {tf} stop{sm}: IS {i['ret']:+.1%} pf{i['pf']:.2f} n{i['n']} | OOS {o['ret']:+.1%} dd{o['maxdd']:.1%} pf{o['pf']:.2f} n{o['n']}")
fn = vote_fn(list(STRATS), 3)
for s in SYMS:
    df = DATA[(s,"4h")]; d = fn(df); (a0,a1),(b0,b1) = bounds(df)
    for lab,(lo,hi) in [("IS",(a0,a1)),("OOS",(b0,b1))]:
        m = metrics(*simulate(df, d, 1.5, lo, hi)); bh = df.close.iat[hi-1]/df.close.iat[lo]-1
        print(f"3of4 4h {s} {lab}: ret {m['ret']:+.1%} n{m['n']} pf{m['pf']:.2f}  | buy&hold {bh:+.1%}")
