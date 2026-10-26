"""Complete-set accumulation simulation on 1h/4h BTC/ETH Up-or-Down (PAPER, public taker tape only).
Passive bids at b on both sides; after leg1 fills, passive bid on the other side at T-b (posted at the NEXT check).
Fill models on the taker tape (takerOnly trades from data-api):
  touch  : any taker print at or through our level fills us (optimistic)
  queue  : prints AT our level first consume Q shares queued ahead of us; a print THROUGH our level fills us
  through: only prints strictly through our level fill us (conservative)
Up bid at L is hit by taker SELL Up at p<=L, or taker BUY Down at q>=1-L (mint match). Symmetric for Down.
Maker fee 0 (crypto_fees_v2 is taker-only); maker rebates ignored (conservative). Unmatched legs held to resolution."""
import json, os, sys, itertools, collections, datetime as dt
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/workspace/lab/polymarket-weather")
import pmw_common as C

SH = 10            # shares per leg (Polymarket min order 5)
PRE_MIN = 30       # start checking 30 min before the candle opens
MAXP = 3           # max completed pairs per market
TICK = 0.01

def ts(s): return C.parse_ts(s).timestamp()

def prints_for(trades, k):
    """Return list of (t, price_in_side_k_terms_for_a_bid, size) of taker prints that could hit a resting bid on side k."""
    out = []
    for x in trades:
        if x["o"] == k and x["s"] == "SELL": out.append((x["t"], x["p"], x["q"]))
        elif x["o"] == 1 - k and x["s"] == "BUY": out.append((x["t"], round(1 - x["p"], 4), x["q"]))
    out.sort(); return out

def last_price(trades, k, t):
    """Last traded price of side k (in side-k terms) at or before t."""
    lp = None
    for x in trades:
        if x["t"] > t: break
        lp = x["p"] if x["o"] == k else 1 - x["p"]
    return lp

class Order:
    def __init__(s, side, px, t0): s.side, s.px, s.t0, s.ahead, s.filled_t, s.scan = side, px, t0, None, None, t0

def try_fill(o, prints, t1, model, Q):
    """Advance order over prints in (o.t0, t1]. Returns fill time or None."""
    if o.filled_t: return o.filled_t
    if o.ahead is None: o.ahead = Q if model == "queue" else 0
    for (t, p, q) in prints[o.side]:
        if t <= o.scan: continue
        if t > t1: break
        if p < o.px - 1e-9:                                 # traded through
            o.filled_t = t; return t
        if abs(p - o.px) < 1e-9:                            # traded at our level
            if model == "touch": o.filled_t = t; return t
            if model == "queue":
                o.ahead -= q
                if o.ahead <= -SH: o.filled_t = t; return t
    o.scan = max(o.scan, t1)
    return None

def sim_market(m, b, T, step_min, model, Q):
    tr = sorted(m["trades"], key=lambda x: x["t"])
    if not tr: return None
    prints = {0: prints_for(tr, 0), 1: prints_for(tr, 1)}
    t_end = ts(m["end"]); t = ts(m["start"]) - PRE_MIN * 60
    pairs, legs, state, open_o, leg1 = [], [], "idle", [], None
    while t < t_end - 60:
        tn = min(t + step_min * 60, t_end)
        if state == "idle" and len(pairs) < MAXP and t_end - t > 10 * 60:
            open_o = []
            for k in (0, 1):
                lp = last_price(tr, k, t)
                if lp is not None and lp > b + TICK: open_o.append(Order(k, b, t))
            if open_o: state = "leg1"
        # advance to next check
        if state == "leg1":
            fills = [(try_fill(o, prints, tn, model, Q), o) for o in open_o]
            fills = [(ft, o) for ft, o in fills if ft]
            if len(fills) == 2:                             # both sides filled at b before we could react: free pair
                pairs.append(2 * b); state = "idle"; open_o = []
            elif len(fills) == 1:
                leg1 = fills[0][1]; state = "need_leg2"; open_o = [o for o in open_o if o is not leg1]
                # the other leg1 order still rests until the next check (we only act at checks)
        elif state == "need_leg2":
            # we are at a check after leg1 filled: first see if the stale other-side b order filled meanwhile
            stale = [o for o in open_o if o.side != leg1.side and o.px == b]
            if stale and try_fill(stale[0], prints, t, model, Q):
                pairs.append(2 * b); state = "idle"; open_o = []; leg1 = None
            else:
                k2 = 1 - leg1.side; lp = last_price(tr, k2, t)
                c = round(T - b, 2)
                if lp is not None: c = min(c, round(lp - TICK, 2))
                o2 = Order(k2, c, t); open_o = [o2]; state = "leg2"
        if state == "leg2":
            if try_fill(open_o[0], prints, tn, model, Q):
                pairs.append(b + open_o[0].px); state = "idle"; open_o = []; leg1 = None
        t = tn
    left = None
    if state in ("need_leg2", "leg2") and leg1 is not None:
        stale = [o for o in open_o if o.side != leg1.side and o.px == b]
        if stale and try_fill(stale[0], prints, t_end, model, Q): pairs.append(2 * b); leg1 = None
        else: left = (leg1.side, b)
    if not pairs and left is None: return None
    cost = sum(pairs) * SH + (left[1] * SH if left else 0)
    payoff = len(pairs) * SH + ((SH if (left[0] == 0) == bool(m["up_won"]) else 0) if left else 0)
    return {"slug": m["slug"], "series": m["series"], "day": m["end"][:10], "t_entry": m["start"], "cost": cost, "pnl": payoff - cost,
            "ret": (payoff - cost) / cost, "pairs": pairs, "leftover": left is not None, "left_pnl": ((SH if (left[0] == 0) == bool(m["up_won"]) else 0) - left[1] * SH) if left else 0.0}

def run(markets, horizon, b, T, step, model, Q):
    out = []
    for m in markets:
        if ("4h" in m["series"]) != (horizon == "4h"): continue
        r = sim_market(m, b, T, step, model, Q)
        if r: out.append(r)
    return out
