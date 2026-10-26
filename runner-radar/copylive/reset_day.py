#!/usr/bin/env python3
"""Daily halt-baseline reset for the 24/7 copy book (user 21:25Z 24 Oct: "Yes, run it 24/7 with the same caps").
Run at every 5-min check; it is IDEMPOTENT and only acts on the first run on/after 00:00 Europe/Dublin of a new day.
  - day key = "day-YYYY-MM-DD" (Dublin calendar date). If night-start.json's key already covers today's Dublin date
    (its last 10 chars >= today), it does nothing (exit 0, "no-op").
  - else: equity = free SOL + holdings at market, taken from the watcher's state.json "equity" if fresh (<=120 s, source
    exactly "wallet_holdings"), otherwise computed fresh (getBalance + token accounts x DexScreener priceUsd / SOL-USD).
    Writes night-start.json {night: day-key, sol: equity} FIRST, then session.json key/night_start_sol/halt_at_sol
    (= (1 - halt_frac) x equity) - both atomic (tmp + os.replace). Watcher reads both files every tick, no restart needed.
    Because the key changes, state.json halted_nights from the previous day no longer applies (a halt blocks only its day).
  - read-only toward the outside world; never trades. Exit 0 = ok/no-op, 2 = equity unavailable/unpriced (retry next check).
Options: --dir DIR (test on a copy), --now ISO (simulate a time), --dry-run (print, write nothing)."""
import argparse, json, os, sys, time, datetime as dt
from zoneinfo import ZoneInfo
DUB = ZoneInfo("Europe/Dublin")
HERE = os.path.dirname(os.path.abspath(__file__))

def load(fn):
    with open(fn) as f: return json.load(f)
def save(fn, obj):
    tmp = fn + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, indent=1)
    os.replace(tmp, fn)
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def fresh_equity():
    sys.path.insert(0, HERE)
    import common as c
    bal = c.sol_balance(); hold = c.wallet_holdings(); solpx = c.sol_usd()
    dex = c.dex_pairs(list(hold)) if hold else {}
    val, unpriced = bal, []
    for m, ui in hold.items():
        p = (dex.get(m) or {}).get("price")
        if not p or not solpx: unpriced.append(m); continue
        if ui * p < 0.50: continue          # dust, same rule as watch.py
        val += ui * p / solpx
    return bal, val, unpriced

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dir", default=HERE); ap.add_argument("--now"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    t = dt.datetime.fromisoformat(a.now.replace("Z", "+00:00")).timestamp() if a.now else time.time()
    fs, fn_, fst = (os.path.join(a.dir, x) for x in ("session.json", "night-start.json", "state.json"))
    s, ns = load(fs), load(fn_)
    today = dt.datetime.fromtimestamp(t, DUB).strftime("%Y-%m-%d")
    cur = str(ns.get("night") or "")
    if cur[-10:] >= today and s.get("key") == cur:
        print(f"no-op: {iso(t)} Dublin date {today}; current key {cur} (sol {ns.get('sol')}, halt {s.get('halt_at_sol')})"); return 0
    frac = float((s.get("day_reset") or {}).get("halt_frac") or (s.get("rules") or {}).get("night_loss_frac") or 0.10)
    eq, src = None, None
    try:
        e = load(fst).get("equity") or {}
        if e.get("source") == "wallet_holdings" and e.get("equity_sol") and abs(t - dt.datetime.fromisoformat(e["ts"].replace("Z", "+00:00")).timestamp()) <= 120:
            eq, src = float(e["equity_sol"]), f"watcher state.json equity {e['ts']} (free {e.get('free_sol')})"
    except Exception: pass
    if eq is None:
        try: bal, val, unp = fresh_equity()
        except Exception as ex: print(f"ERROR: equity unavailable ({ex!r}); NOT reset, retry next check"); return 2
        if unp: print(f"ERROR: unpriced holdings {unp}; NOT reset, retry next check"); return 2
        eq, src = round(val, 6), f"fresh read (free {bal:.6f})"
    key = f"day-{today}"; halt = round((1 - frac) * eq, 6)
    new_ns = dict(night=key, sol=round(eq, 6), ts=iso(t), note=f"daily reset 00:00 Dublin: equity {src}; prev {cur} sol {ns.get('sol')}; halt -{frac*100:.0f}% -> {halt}")
    msg = f"RESET {cur} -> {key}: baseline {eq:.6f} SOL ({src}), halt_at {halt}"
    if a.dry_run: print("DRY RUN (nothing written): " + msg); return 0
    if cur: save(os.path.join(a.dir, f"night-start.{cur}.json"), ns)        # archive the old baseline
    save(fn_, new_ns)                                                          # night-start first, then the session key
    s["key"] = key; s["night_start_sol"] = round(eq, 6); s["halt_at_sol"] = halt
    s.setdefault("day_reset_log", []).append(dict(ts=iso(t), prev=cur, key=key, sol=round(eq, 6), halt_at=halt))
    s["day_reset_log"] = s["day_reset_log"][-14:]
    save(fs, s)
    if a.dir == HERE:
        with open("/workspace/runner-radar/live/trades-log.md", "a") as f: f.write(f"- {iso(t)} day reset (reset_day.py): {msg}\n")
    print(msg); return 0

if __name__ == "__main__": sys.exit(main())
