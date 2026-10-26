"""Phase 3: neodot copy replay (PAPER ONLY). Data: keyless public Solana RPC (exact pool state at each fill) +
GeckoTerminal free 1-minute OHLCV (only to detect ladder TP/SL triggers). Fills are always priced on the exact
on-chain pool state = post-state of the last successful pool tx with blockTime < t_his + L.
Costs: venue fee read from pump fee-program return data (curve 1.25%, PumpSwap 0.3%..1.25%), constant-product
slippage at our size, 5000 lamports + priority fee per tx (base 0.001 SOL), optional 1% bot fee. ATA rent ignored (refundable)."""
import json, sys, os, random
sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rpc, pools, gt, legs as Lg
W = Lg.W; RENT = 0.00203928; H = os.path.dirname(os.path.abspath(__file__))
WIPD_POOL = "4GwPgUBJqEP3X1UFhQh24rfjfSXf914qbLiPdowCX6Jh"

def his_tok(t, mint, key): return sum(v[2] for v in Lg.tokbal(t, key).values() if v[0] == mint and v[1] == W)
def rent_adj(t):
    pre, post = Lg.tokbal(t, "preTokenBalances"), Lg.tokbal(t, "postTokenBalances")
    return sum(1 for a, v in post.items() if v[1] == W and a not in pre), sum(1 for a, v in pre.items() if v[1] == W and a not in post)
def his_sol(t):
    k = Lg.keys(t); i = k.index(W); m = t["meta"]; return (m["postBalances"][i] - m["preBalances"][i]) / 1e9, m["fee"] / 1e9
def quote_rate(t, d, side):
    """SOL per quote unit realised in HIS tx (embeds his SOL<->quote hop cost). 1.0 for SOL-quoted pools."""
    if d["quote"] == pools.WSOL: return 1.0
    pre, post = Lg.tokbal(t, "preTokenBalances"), Lg.tokbal(t, "postTokenBalances")
    dq = post[d["vault_q"]][2] - pre[d["vault_q"]][2]; ds, fee = his_sol(t); new, closed = rent_adj(t)
    if side == "buy": return (-ds - fee - new * RENT + closed * RENT) / (dq / (1 - d["fee"]))
    return (ds + fee + new * RENT - closed * RENT) / (-dq * (1 - d["fee"]))

class Trip:
    def __init__(s, tr, S):
        s.tr = tr; s.ok = True; s.why = ""; s.nfetch = 0
        legs = [l for l in tr["legs"] if abs(l.get("dsol", 0)) >= 1e-4]
        s.L = [dict(l=l, t=rpc.tx(l["sig"])) for l in legs]
        for x in s.L: x["d"] = pools.define(x["t"], tr["mint"])
        bad = [x["d"] for x in s.L if x["d"] is None or x["d"]["kind"] == "unrecon"]
        if bad: s.ok = False; s.why = (bad[0] or {}).get("why", "no pool"); return
        for x in s.L:
            if x["d"]["kind"] == "pump_q_pending":
                bd = [y["d"] for y in s.L if y["d"]["owner"] == x["d"]["owner"] and y["d"]["kind"] == "pump_q"]
                if not bd: s.ok = False; s.why = "non-SOL-quoted curve sell without buy calibration"; return
                x["d"] = bd[0]
        s.defs = {}
        for x in s.L: s.defs.setdefault(x["d"]["owner"], x["d"])
        # PumpSwap pools here do NOT price off raw vault balances (his fills are 20-50% worse than x*y=k on vaults);
        # fit a virtual quote offset c per pool from HIS legs on that pool: (q0+c)*t0 = (q1+c)*t1  -> median over legs.
        for o, d in s.defs.items():
            if d["kind"] != "pumpswap": continue
            cs = []
            for x in s.L:
                if x["d"]["owner"] != o: continue
                pr, po = Lg.tokbal(x["t"], "preTokenBalances"), Lg.tokbal(x["t"], "postTokenBalances")
                q0, q1, t0_, t1_ = pr[d["vault_q"]][2], po[d["vault_q"]][2], pr[d["vault_tok"]][2], po[d["vault_tok"]][2]
                if t0_ != t1_: cs.append((q1 * t1_ - q0 * t0_) / (t0_ - t1_))
            cs.sort(); d["c"] = max(0.0, cs[len(cs) // 2]) if cs else 0.0; d["c_fits"] = cs
        for x in s.L:
            if x["d"]["kind"] == "pumpswap": x["d"] = s.defs[x["d"]["owner"]]
        s.b0 = [x for x in s.L if x["l"]["side"] == "buy"][0]; s.sells = [x for x in s.L if x["l"]["side"] == "sell"]
        s.idx = {}
        for o in s.defs:
            if o == WIPD_POOL: sl = json.load(open(os.path.join(rpc.D, "wipd_pool_sigs.json")))["sigs"]
            else: sl = rpc.sigs(o, tr["before_sig"], s.b0["l"]["sig"], maxpages=30)["sigs"]
            sl = [(x["slot"], x["t"], x["s"]) for x in sl if not x["err"]] + [(y["l"]["slot"], y["l"]["ts"], y["l"]["sig"]) for y in s.L]
            s.idx[o] = sorted(set(sl))
        for x in s.L:
            x["rate"] = quote_rate(x["t"], x["d"], x["l"]["side"])
            x["pre_h"], x["post_h"] = his_tok(x["t"], tr["mint"], "preTokenBalances"), his_tok(x["t"], tr["mint"], "postTokenBalances")
        t0 = min(x["l"]["ts"] for x in s.L) - 60; t1 = max(x["l"]["ts"] for x in s.L) + 120
        s.cand = {o: gt.candles(o, t0, t1) for o in s.defs}
        s.cache = {}
    def state_at(s, o, cut, slot_min=0):
        """exact pool state: post-state of last successful tx on pool o with blockTime < cut (and slot >= slot_min)."""
        key = (o, cut, slot_min)
        if key in s.cache: return s.cache[key]
        lst = [x for x in s.idx[o] if x[1] < cut and x[0] >= slot_min]
        for slot, t, sig in reversed(lst[-40:]):
            tx = rpc.tx(sig); s.nfetch += 1
            st = pools.state(tx, s.defs[o], s.tr["mint"])
            if st and st[0] > 0 and st[1] > 0: s.cache[key] = (slot, t, sig, o, st[0], st[1]); return s.cache[key]
        s.cache[key] = None; return None
    def active_pool(s, t):
        """pool that traded most recently before t (handles curve->PumpSwap migration)."""
        best, bt = None, -1
        for o, lst in s.idx.items():
            ts = [x[1] for x in lst if x[1] < t]
            if ts and ts[-1] > bt: best, bt = o, ts[-1]
        return best
    def rate_at(s, t):
        r0, t0 = s.b0["rate"], s.b0["l"]["ts"]; r1, t1 = s.sells[-1]["rate"], s.sells[-1]["l"]["ts"]
        if t1 <= t0: return r1
        w = min(1, max(0, (t - t0) / (t1 - t0))); return r0 + w * (r1 - r0)

def sim(T, Lat, x, P=0.001, botfee=0.0, mode="mirror"):
    b = T.b0; d0 = b["d"]; o0 = d0["owner"]; tb = b["l"]["ts"]
    st = T.state_at(o0, tb + 1, b["l"]["slot"]) if Lat == 0 else T.state_at(o0, tb + Lat)
    if Lat == 0:   # reference: land in the tx right after his (his post-state)
        st = pools.state(b["t"], d0, T.tr["mint"]); st = (b["l"]["slot"], tb, b["l"]["sig"], o0, st[0], st[1])
    q = x * (1 - botfee) / b["rate"]; net = q * (1 - d0["fee"])
    tok0 = st[5] * net / (st[4] + net); spent = x + 5000e-9 + P; fillp = q / tok0
    hold = tok0; out = 0.0; log = []
    def sell(tok, ttrig, o=None, slot_min=0):
        o = o or T.active_pool(ttrig + max(Lat, 1))
        stx = T.state_at(o, ttrig + max(Lat, 1), slot_min)
        d = T.defs[o]; qo = stx[4] * tok / (stx[5] + tok) * (1 - d["fee"])
        return qo * T.rate_at(ttrig) * (1 - botfee) - 5000e-9 - P
    ev = []
    for k, sx in enumerate(T.sells):
        frac = 1.0 if k == len(T.sells) - 1 else (max(0.0, min(1.0, (sx["pre_h"] - sx["post_h"]) / sx["pre_h"])) if sx["pre_h"] > 0 else 1.0)
        ev.append((sx["l"]["ts"], frac, sx))
    def his(e):
        nonlocal hold, out
        q = hold * e[1]
        if q > 0: out += sell(q, e[0], e[2]["d"]["owner"], e[2]["l"]["slot"] if Lat == 0 else 0); hold -= q
    if mode == "mirror":
        for e in ev: his(e)
        return (out - spent) / spent, log
    # ladder. Trigger detection on 1-min candles (low checked before high = conservative); fill on exact state at trigger+L.
    t_in = tb + Lat; final = ev[-1][0]; tp1 = tp2 = False; ei = 0
    mins = sorted({c[0] for cs in T.cand.values() for c in cs if c[0] >= (t_in // 60 + 1) * 60 and c[0] < final})
    bymin = {}
    for o, cs in T.cand.items():
        for c in cs: bymin.setdefault(c[0], {})[o] = c
    for m in mins:
        while ei < len(ev) and ev[ei][0] < m and hold > 1e-12: his(ev[ei]); log.append(("his", ev[ei][0])); ei += 1
        if hold <= 1e-12: break
        o = T.active_pool(m + 60); c = bymin[m].get(o) or list(bymin[m].values())[-1]
        lo, hi = c[3] / fillp, c[2] / fillp; tt = m + 30
        stop = 1.0 if tp1 else 0.8
        if lo <= stop:
            out += sell(hold, tt); hold = 0; log.append(("stop%.1f" % stop, m)); break
        if not tp1 and hi >= 1.4: qq = min(hold, 0.25 * tok0); out += sell(qq, tt); hold -= qq; tp1 = True; log.append(("tp1", m))
        if tp1 and not tp2 and hi >= 2.0: qq = min(hold, 0.25 * tok0); out += sell(qq, tt); hold -= qq; tp2 = True; log.append(("tp2", m))
        if hi >= 6.0: out += sell(hold, tt); hold = 0; log.append(("tp500", m)); break
    while hold > 1e-12 and ei < len(ev): his(ev[ei]); log.append(("his", ev[ei][0])); ei += 1
    return (out - spent) / spent, log

if __name__ == "__main__":
    TR = json.load(open(os.path.join(H, "legs.json"))); S = json.load(open(os.path.join(H, "sigs_summary.json")))
    order = sorted(TR, key=lambda r: r["t0"]); held = {r["i"] for r in order[-round(0.3 * len(order)):]}
    rows, unrec, chk = [], [], []
    for tr in TR:
        sp = "held_out" if tr["i"] in held else "train"
        if S.get(str(tr["i"]), {}).get("skip"):
            T = Trip.__new__(Trip); legs = [l for l in tr["legs"] if abs(l.get("dsol", 0)) >= 1e-4]
            why = [pools.define(rpc.tx(l["sig"]), tr["mint"]) for l in legs]; why = [w["why"] for w in why if w and w["kind"] == "unrecon"]
            unrec.append(dict(i=tr["i"], sym=tr["sym"], split=sp, his_gross=tr["pnl_pct_gross"], why=why[0] if why else "?")); continue
        T = Trip(tr, S)
        if not T.ok: unrec.append(dict(i=tr["i"], sym=tr["sym"], split=sp, his_gross=tr["pnl_pct_gross"], why=T.why)); continue
        # sanity: replay HIS buy at his own size on his pre-state -> tokens vs actual
        b = T.b0; pre = pools.pre_state(b["t"], b["d"], tr["mint"]); hs, hf = his_sol(b["t"]); nw, cl = rent_adj(b["t"])
        q = (-hs - hf - nw * RENT + cl * RENT) / b["rate"]; net = q * (1 - b["d"]["fee"]); tk = pre[1] * net / (pre[0] + net)
        chk.append(dict(i=tr["i"], sym=tr["sym"], kind=b["d"]["kind"], quote=b["d"]["quote"][:6], tok_model=tk, tok_actual=b["post_h"] - b["pre_h"],
                        gt_candles=sum(len(v) for v in T.cand.values()), rate_buy=b["rate"], rate_sell=T.sells[-1]["rate"]))
        for Lat in (0, 5, 15, 30):
            for x in (0.05, 0.1):
                for mode in ("mirror", "ladder"):
                    for P, bf, tag in ((0.001, 0, "base"), (0.0002, 0, "lowprio"), (0.003, 0, "highprio"), (0.001, 0.01, "botfee1pct")):
                        if tag != "base" and mode == "ladder": continue
                        r, lg = sim(T, Lat, x, P, bf, mode)
                        rows.append(dict(i=tr["i"], sym=tr["sym"], split=sp, kind=b["d"]["kind"], L=Lat, size=x, exit=mode, cost=tag, ret=r,
                                         his_gross=tr["pnl_pct_gross"] / 100, log=lg))
        print(tr["i"], tr["sym"], sp, b["d"]["kind"], "mirror L5/0.1:", round([r for r in rows if r["i"] == tr["i"] and r["L"] == 5 and r["size"] == 0.1 and r["exit"] == "mirror" and r["cost"] == "base"][0]["ret"] * 100, 1),
              "his", tr["pnl_pct_gross"], "rpc_fetch", T.nfetch, flush=True)
    json.dump(dict(rows=rows, unrec=unrec, held=sorted(held), check=chk), open(os.path.join(H, "replay_rows.json"), "w"), indent=0)
    print("simulated", len({r["i"] for r in rows}), "unrecon", len(unrec))
