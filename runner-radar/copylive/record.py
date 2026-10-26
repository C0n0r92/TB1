#!/usr/bin/env python3
"""Record Chunk's MANUAL Banana Gun fills for the copylive book (local files only; no trading).
  python3 record.py buy  <mint> <sol_in> <tokens> <entry_px_usd> <leader> <leader_px> <leader_ts>
  python3 record.py sell <mint> <fraction_of_ORIGINAL> <sol_out> <reason>
  python3 record.py clear <mint|ALL>      # drop a pending action (e.g. trade failed / decided not to act)
  python3 record.py status
entry_px_usd may be 'auto' = sol_in*SOL_USD/tokens. reasons: sl_-15% sl_breakeven tp_+40%_25% tp_+100%_25%
tp_+40%_and_+100%_25%+25% sl_trail_... leader_sold_keep10 tp_leftover_+500% close_0745_dublin night_halt_-20% manual"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *   # noqa

def main(a):
    if not a: print(__doc__); return 2
    cmd = a[0]
    with Lock():
        P = load(F["positions"], {}); st = load(F["state"], {}) or {}
        pend = st.setdefault("pending", {})
        if cmd == "buy" and len(a) == 8:
            mint, sol_in, tokens = a[1], float(a[2]), float(a[3])
            px = a[4]
            px = (sol_in * sol_usd() / tokens) if px == "auto" else float(px)
            if mint in P and P[mint].get("status") == "open": print("already open:", mint); return 1
            tk = (dex_pairs([mint]).get(mint) or {}).get("ticker")
            P[mint] = dict(mint=mint, ticker=tk, leader=a[5], leader_px=float(a[6]), leader_ts=a[7], sol_in=sol_in,
                           tokens_orig=tokens, tokens_left=tokens, entry_px=px, opened_ts=iso(), tp_level=0,
                           leader_sold=False, status="open", sol_out=0.0, sells=[])
            pend.pop(mint, None)
            chase = px / float(a[6]) - 1 if float(a[6]) else None
            fill = dict(ts=iso(), side="buy", mint=mint, ticker=tk, sol_in=sol_in, tokens=tokens, entry_px=px,
                        leader=a[5], leader_px=float(a[6]), leader_ts=a[7], entry_vs_leader_pct=None if chase is None else round(chase*100, 2))
        elif cmd == "sell" and len(a) == 5:
            mint, frac, sol_out, reason = a[1], float(a[2]), float(a[3]), a[4]
            p = P.get(mint)
            if not p or p.get("status") != "open": print("no open position:", mint); return 1
            tok = min(p["tokens_left"], frac * p["tokens_orig"])
            if p["tokens_left"] - tok < 1e-6 * p["tokens_orig"]: tok = p["tokens_left"]
            p["tokens_left"] -= tok; p["sol_out"] += sol_out
            p["tp_level"] = tp_level_after(reason, int(p.get("tp_level") or 0))
            if reason.startswith("leader_sold"): p["leader_sold"] = True
            p["sells"].append(dict(ts=iso(), fraction=frac, tokens=tok, sol_out=sol_out, reason=reason))
            fill = dict(ts=iso(), side="sell", mint=mint, ticker=p.get("ticker"), fraction=frac, tokens=tok, sol_out=sol_out, reason=reason)
            if p["tokens_left"] <= 0:
                p["status"] = "closed"; p["closed_ts"] = iso()
                p["pnl_sol"] = round(p["sol_out"] - p["sol_in"], 6); p["pnl_pct"] = round(100 * p["pnl_sol"] / p["sol_in"], 2)
                fill.update(closed=True, pnl_sol=p["pnl_sol"], pnl_pct=p["pnl_pct"])
                P[f"{mint}:closed:{p['closed_ts']}"] = P.pop(mint)
            pend.pop(mint, None)
            if pend.get("__ALL__") and not any(v.get("status") == "open" for v in P.values()): pend.pop("__ALL__", None)
        elif cmd == "clear" and len(a) == 2:
            if a[1] == "ALL": pend.clear()
            else: pend.pop(a[1], None)
            save(F["state"], st); print("cleared"); return 0
        elif cmd == "status":
            for m, p in P.items(): print(m[:12], p.get("ticker"), p["status"], f"left {p['tokens_left']:.4g}/{p['tokens_orig']:.4g}",
                                         f"in {p['sol_in']} out {p['sol_out']:.6f} tp{p.get('tp_level')} leader_sold={p.get('leader_sold')}")
            print("pending:", pend); print("night:", load(F["night"], {})); return 0
        else:
            print(__doc__); return 2
        save(F["positions"], P); save(F["state"], st); append(F["fills"], fill)
        print(json.dumps(fill)); return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
