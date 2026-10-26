#!/usr/bin/env python3
"""RSI(2) daily pullback — PAPER-FORWARD watch (Lab). PAPER ONLY: no trading, no keys, no messages.
Rule = sw_backtest.py family (c), tf=1d, books SW_rsi2_1d_X5 and SW_rsi2_1d_X10:
  entry signal on a CLOSED daily bar: close > SMA200(close) and RSI2 (Wilder/ewm alpha=1/2) < X  -> buy at NEXT bar open
  exit  signal on a CLOSED daily bar: RSI2 > 70 or close > SMA5                                  -> sell at NEXT bar open
  (exit checked from the entry bar's own close; a sym may re-enter at the same open it exits; no stop, so no stop extra)
Book (= sw_backtest.book): stake = 10% of realised equity (start $1,000), max 3 open, one position per sym,
  same-open entries taken in SYMS order. Cost (= cost_side 'hi'): 0.30%/side + 2*$50/liq per side (liq $30M SOL, $2M others),
  +0.10% on stop fills (never used by this rule). ret = px_out*(1-cs)/(px_in*(1+cs)) - 1.
Data: data-api.binance.vision /api/v3/klines <SYM>USDT 1d, limit 400 -> 7 requests per run. Only bars with close_time < now are
  used for signals; the in-progress bar is used ONLY for its (already fixed) open price to fill orders from yesterday's close.
Forward start is FLAT: at initialisation only the latest closed bar is evaluated (no back-filled positions).
Idempotent: state.last_bar = last processed closed bar; re-runs on the same day process nothing new and never re-enter.
Files: forward/rsi2_state.json (state), forward/rsi2_daily.jsonl (events), forward/rsi2.log (stderr via cron).
Usage: rsi2_daily.py [--dry-run]  |  rsi2_daily.py --replay  (offline parity check vs sw_backtest on data/sw_candles)"""
import json, os, sys, time, urllib.request, fcntl, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.dirname(HERE)
STATE = os.path.join(HERE, "rsi2_state.json"); EVENTS = os.path.join(HERE, "rsi2_daily.jsonl"); LOCK = os.path.join(HERE, ".rsi2.lock")
SYMS = ["SOL", "JUP", "BONK", "WIF", "JTO", "PYTH", "RAY"]
BOOKS = {"X5": 5, "X10": 10}
LIQ = {"SOL": 30e6}; TICKET = 50.0; BASE_SIDE = 0.0030; STOP_EXTRA = 0.0010
START_EQ = 1000.0; SIZE = 0.10; MAXOPEN = 3; DAY = 86400_000
API = "https://data-api.binance.vision/api/v3/klines?symbol={}USDT&interval=1d&limit=400"

def cs(sym): return BASE_SIDE + 2 * TICKET / LIQ.get(sym, 2e6)
def iso(ms): return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
def now_iso(): return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get(url):
    last = None
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lab-rsi2-forward/1.0"}), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e; print(f"{now_iso()} ERR {url} {e}", file=sys.stderr, flush=True); time.sleep(5 * (a + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")

def indicators(closes):
    """-> per-bar (rsi2 or None, sma5 or None, sma200 or None); same maths as sw_backtest (pandas ewm adjust=False)."""
    out = []; up = dn = None; a = 0.5
    for i, c in enumerate(closes):
        r = None
        if i >= 1:
            d = c - closes[i - 1]; u, w = max(d, 0.0), max(-d, 0.0)
            up = u if up is None else (1 - a) * up + a * u
            dn = w if dn is None else (1 - a) * dn + a * w
            r = None if dn == 0 else 100 - 100 / (1 + up / dn)
        s5 = sum(closes[i - 4:i + 1]) / 5 if i >= 4 else None
        s200 = sum(closes[i - 199:i + 1]) / 200 if i >= 199 else None
        out.append((r, s5, s200))
    return out

def new_state():
    return {"version": 1, "created": now_iso(), "last_bar": None, "last_heartbeat_bar": None,
            "books": {b: {"X": x, "cash_eq": START_EQ, "open": [], "pending": [], "closed": 0} for b, x in BOOKS.items()}}

class Engine:
    """Step engine shared by the live run and the offline --replay parity test."""
    def __init__(self, state, emit): self.s = state; self.emit = emit

    def fill_pending(self, bars):
        """bars[sym] = {ts: (o,h,l,c,closed)}; fill orders whose fill-bar open is known. Exits before entries (book() order)."""
        for bname, bk in self.s["books"].items():
            still = []
            fills = sorted(bk["pending"], key=lambda p: (p["fill_ts"], 0 if p["side"] == "sell" else 1, SYMS.index(p["sym"])))
            for p in fills:
                b = bars.get(p["sym"], {}).get(p["fill_ts"])
                if b is None: still.append(p); continue
                px = b[0]
                if p["side"] == "sell":
                    pos = next((q for q in bk["open"] if q["sym"] == p["sym"]), None)
                    if pos is None: continue
                    c = cs(p["sym"]); ret = px * (1 - c) / (pos["px_in"] * (1 + c)) - 1
                    pnl = pos["stake"] * ret; bk["cash_eq"] += pnl; bk["open"].remove(pos); bk["closed"] += 1
                    self.emit({"type": "exit", "book": bname, "sym": p["sym"], "date": iso(p["fill_ts"]), "px_in": pos["px_in"], "px_out": px,
                               "entry_date": pos["entry_date"], "stake": round(pos["stake"], 4), "ret": round(ret, 6), "pnl": round(pnl, 4),
                               "reason": p["reason"], "exit": "rule", "realised_equity": round(bk["cash_eq"], 4), "trade_no": bk["closed"]})
                else:
                    if len(bk["open"]) >= MAXOPEN or any(q["sym"] == p["sym"] for q in bk["open"]):
                        self.emit({"type": "skip", "book": bname, "sym": p["sym"], "date": iso(p["fill_ts"]),
                                   "why": "max_open" if len(bk["open"]) >= MAXOPEN else "already_open"}); continue
                    stake = SIZE * bk["cash_eq"]
                    pos = {"sym": p["sym"], "entry_date": iso(p["fill_ts"]), "entry_ts": p["fill_ts"], "px_in": px, "stake": stake,
                           "signal_date": p["signal_date"], "rsi2_at_signal": p.get("rsi2")}
                    bk["open"].append(pos)
                    self.emit({"type": "entry", "book": bname, "sym": p["sym"], "date": iso(p["fill_ts"]), "px_in": px,
                               "stake": round(stake, 4), "signal_date": p["signal_date"], "open_count": len(bk["open"])})
            bk["pending"] = still

    def on_close(self, ts, ind):
        """Process closed bar ts for all syms. ind[sym] = (close, rsi2, sma5, sma200) or None if sym has no bar at ts."""
        fts = ts + DAY
        for bname, bk in self.s["books"].items():
            X = bk["X"]
            exiting = set()
            for pos in bk["open"]:
                v = ind.get(pos["sym"])
                if v is None: continue
                c, r, s5, s200 = v
                why = [w for w, ok in (("rsi2>70", r is not None and r > 70), ("close>sma5", s5 is not None and c > s5)) if ok]
                if why and not any(p["sym"] == pos["sym"] and p["side"] == "sell" for p in bk["pending"]):
                    bk["pending"].append({"side": "sell", "sym": pos["sym"], "fill_ts": fts, "signal_date": iso(ts), "reason": "+".join(why)})
                    exiting.add(pos["sym"])
                    self.emit({"type": "signal", "book": bname, "side": "sell", "sym": pos["sym"], "signal_date": iso(ts), "close": c,
                               "rsi2": None if r is None else round(r, 3), "sma5": s5, "reason": "+".join(why), "fill": "next open " + iso(fts)})
            held = {q["sym"] for q in bk["open"]} - exiting
            for sym in SYMS:
                v = ind.get(sym)
                if v is None or sym in held: continue
                c, r, s5, s200 = v
                if s200 is not None and r is not None and c > s200 and r < X:
                    bk["pending"].append({"side": "buy", "sym": sym, "fill_ts": fts, "signal_date": iso(ts), "rsi2": round(r, 3)})
                    self.emit({"type": "signal", "book": bname, "side": "buy", "sym": sym, "signal_date": iso(ts), "close": c,
                               "rsi2": round(r, 3), "sma200": round(s200, 8), "fill": "next open " + iso(fts)})

    def heartbeat(self, ts, last_close, extra=None):
        hb = {"type": "heartbeat", "bar": iso(ts), "books": {}}
        for bname, bk in self.s["books"].items():
            opens = []; mtm = bk["cash_eq"]
            for q in bk["open"]:
                lc = last_close.get(q["sym"]); c = cs(q["sym"])
                ur = (lc * (1 - c) / (q["px_in"] * (1 + c)) - 1) if lc else 0.0
                mtm += q["stake"] * ur
                opens.append({"sym": q["sym"], "entry_date": q["entry_date"], "px_in": q["px_in"], "last_close": lc,
                              "stake": round(q["stake"], 2), "unreal_ret": round(ur, 5)})
            hb["books"][bname] = {"realised_equity": round(bk["cash_eq"], 4), "mtm_equity": round(mtm, 4), "open": opens,
                                  "pending": [{k: p[k] for k in ("side", "sym", "signal_date")} | {"fill_date": iso(p["fill_ts"])} for p in bk["pending"]],
                                  "closed_trades": bk["closed"]}
        if extra: hb.update(extra)
        self.emit(hb)

def series(rows):
    """rows: list of (ts,o,h,l,c,closed) sorted -> closed-bar indicator map + all-bars dict."""
    closed = [r for r in rows if r[5]]
    ind = indicators([r[4] for r in closed])
    return {r[0]: (r[4],) + ind[i] for i, r in enumerate(closed)}, {r[0]: (r[1], r[2], r[3], r[4], r[5]) for r in rows}

def run_live(dry=False):
    lockf = open(LOCK, "w")
    try: fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError: print(f"{now_iso()} already running, skip", file=sys.stderr); return
    state = json.load(open(STATE)) if os.path.exists(STATE) else None
    init = state is None
    if init: state = new_state()
    evs = []
    def emit(e): e = {"ts": now_iso()} | e; evs.append(e)
    now = int(time.time() * 1000); IND = {}; BARS = {}
    for s in SYMS:
        k = get(API.format(s)); time.sleep(0.5)
        rows = [(int(b[0]), float(b[1]), float(b[2]), float(b[3]), float(b[4]), int(b[6]) < now) for b in k]
        IND[s], BARS[s] = series(rows)
    last_closed = max(max(IND[s]) for s in SYMS if IND[s])
    eng = Engine(state, emit)
    if init:
        todo = [last_closed]; emit({"type": "init", "note": "forward watch started FLAT; only the latest closed bar is evaluated",
                                    "first_bar": iso(last_closed), "books": list(BOOKS), "start_equity": START_EQ})
    else:
        todo = sorted({t for s in SYMS for t in IND[s] if t > state["last_bar"]})
    eng.fill_pending(BARS)                 # orders from earlier closes whose fill open is now known
    for ts in todo:
        eng.on_close(ts, {s: (IND[s][ts] if ts in IND[s] else None) for s in SYMS})
        eng.fill_pending(BARS)             # fill at next open if that bar (closed or in-progress) is already listed
        state["last_bar"] = ts
    if todo and state.get("last_heartbeat_bar") != last_closed:
        lc = {s: IND[s][max(IND[s])][0] for s in SYMS if IND[s]}
        info = {s: {"close": IND[s][last_closed][0], "rsi2": None if IND[s][last_closed][1] is None else round(IND[s][last_closed][1], 2),
                    "above_sma200": None if IND[s][last_closed][3] is None else IND[s][last_closed][0] > IND[s][last_closed][3]}
                for s in SYMS if last_closed in IND[s]}
        eng.heartbeat(last_closed, lc, {"market": info})
        state["last_heartbeat_bar"] = last_closed
    if dry:
        for e in evs: print(json.dumps(e))
        return
    with open(EVENTS, "a") as fh:
        for e in evs: fh.write(json.dumps(e) + "\n")
    state["updated"] = now_iso()
    tmp = STATE + ".tmp"; json.dump(state, open(tmp, "w"), indent=1); os.replace(tmp, STATE)
    print(f"{now_iso()} ok last_bar={iso(state['last_bar'])} events={len(evs)}", file=sys.stderr)

def replay():
    """Offline parity check: run the step engine over cached full-history candles from the eval start, compare with sw_backtest."""
    import csv
    sys.path.insert(0, LAB); import sw_backtest as sb, pandas as pd
    D = os.path.join(LAB, "data", "sw_candles"); IND = {}; BARS = {}
    for s in SYMS:
        rows = [(int(r["ts"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]), True) for r in csv.DictReader(open(os.path.join(D, f"bn_{s}_1d.csv")))]
        IND[s], BARS[s] = series(rows)
    start = int(pd.Timestamp("2024-03-05", tz="UTC").timestamp() * 1000)
    end = min(max(IND[s]) for s in SYMS)
    st = new_state(); evs = []
    eng = Engine(st, lambda e: evs.append(e))
    for ts in sorted({t for s in SYMS for t in IND[s] if start - DAY <= t < end}):
        eng.on_close(ts, {s: IND[s].get(ts) for s in SYMS}); eng.fill_pending(BARS)
    for b, X in BOOKS.items():
        mine = [(e["sym"], e["date"]) for e in evs if e["type"] == "exit" and e["book"] == b]
        mine_in = [(e["sym"], e["date"]) for e in evs if e["type"] == "entry" and e["book"] == b]
        cfg = {"fam": "rsi", "tf": "1d", "X": X}; S, _, E = sb.window("1d"); allt = []
        for s in SYMS: allt += sb.gen(sb.load(s, "1d"), s, cfg, "hi", S, E)
        taken = sb.book(allt)
        ref_in = [(t["sym"], t["t_in"].strftime("%Y-%m-%d")) for t in taken]
        ref_out = [(t["sym"], t["t_out"].strftime("%Y-%m-%d")) for t in taken if t["exit"] == "rule"]
        r_eq = 1000 * (1 + sum(t["stake"] * t["ret"] for t in taken if t["exit"] == "rule"))
        print(f"{b}: entries fwd={len(mine_in)} ref={len(ref_in)} match={sorted(mine_in)==sorted(ref_in)} | "
              f"exits fwd={len(mine)} ref={len(ref_out)} match={sorted(mine)==sorted(ref_out)} | realised eq fwd={st['books'][b]['cash_eq']:.2f} ref~{r_eq:.2f}")
        if sorted(mine_in) != sorted(ref_in):
            print("  only fwd:", sorted(set(mine_in) - set(ref_in))[:10]); print("  only ref:", sorted(set(ref_in) - set(mine_in))[:10])

if __name__ == "__main__":
    if "--replay" in sys.argv: replay()
    else: run_live(dry="--dry-run" in sys.argv)
