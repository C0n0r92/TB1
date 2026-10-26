"""Pool definitions + point-in-time pool state from any tx touching the pool. Read-only."""
import sys, os
sys.dont_write_bytecode = True; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import legs as Lg
WSOL = Lg.WSOL

def owner_accounts(t, own):
    pre, post = Lg.tokbal(t, "preTokenBalances"), Lg.tokbal(t, "postTokenBalances"); out = {}
    for a in set(pre) | set(post):
        m, o, *_ = post.get(a) or pre.get(a)
        if o == own: out[a] = (m, pre.get(a, (0, 0, 0))[2], post.get(a, (0, 0, 0))[2])
    return out

def define(t, mint, user=Lg.W):
    """pool definition from one of HIS txs: kind, owner, token vault, quote mint+vault, virtual quote offset, fee bps."""
    p = Lg.pool_of(t, mint, user)
    if not p: return None
    own = p["owner"]; acc = owner_accounts(t, own); k = Lg.keys(t)
    ev = [e for e in Lg.trade_events(t) if e["mint"] == mint]
    fees = Lg.pfee_bps(t); fee = (sum(fees[-1]) / 1e4) if fees else None
    if ev:
        e = ev[-1]
        if e["vsol"] > 0:   # SOL-quoted pump curve: event carries virtual reserves
            return dict(kind="pump_sol", owner=own, quote=WSOL, vault_tok=p["vault_tok"], fee=fee if fee is not None else 0.0125, c=None)
        qa = [(abs(v[2] - v[1]), a, v) for a, v in acc.items() if v[0] != mint]
        if not qa: return dict(kind="unrecon", why="pump curve w/o SOL reserves and no quote vault", owner=own)
        _, qv, (qm, q0, q1) = max(qa)
        if not e["buy"] or e["tok"] <= 0: return dict(kind="pump_q_pending", owner=own, quote=qm, vault_tok=p["vault_tok"], vault_q=qv, fee=fee)
        vt_post = e["vtok"]; dq = q1 - q0
        vq_pre = dq * vt_post / e["tok"]; c = vq_pre - q0
        return dict(kind="pump_q", owner=own, quote=qm, vault_tok=p["vault_tok"], vault_q=qv, c=c, fee=fee if fee is not None else 0.0125)
    if p["kind"] == "amm" or True:
        qa = [(abs(v[2] - v[1]), a, v) for a, v in acc.items() if v[0] != mint]
        if not qa: return dict(kind="unrecon", why="no quote vault owned by pool", owner=own)
        _, qv, (qm, q0, q1) = max(qa)
        progs = {x["programId"] for ii in t["meta"].get("innerInstructions") or [] for x in ii["instructions"]} | {i["programId"] for i in t["transaction"]["message"]["instructions"]}
        if "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA" not in progs:
            return dict(kind="unrecon", why="non-pump venue (" + ",".join(sorted(x[:6] for x in progs))[:80] + ")", owner=own)
        return dict(kind="pumpswap", owner=own, quote=qm, vault_tok=p["vault_tok"], vault_q=qv, fee=fee if fee is not None else 0.0030)

def state(t, pd_, mint):
    """(quote_reserve_virtual, token_reserve_virtual) AFTER tx t, or None if t does not move/show the pool."""
    if t is None or t["meta"].get("err") is not None: return None
    if pd_["kind"] == "pump_sol":
        ev = [e for e in Lg.trade_events(t) if e["mint"] == mint and e["vsol"] > 0]
        return (ev[-1]["vsol"], ev[-1]["vtok"]) if ev else None
    if pd_["kind"] == "pump_q":
        ev = [e for e in Lg.trade_events(t) if e["mint"] == mint]
        post = Lg.tokbal(t, "postTokenBalances")
        if not ev or pd_["vault_q"] not in post: return None
        return (post[pd_["vault_q"]][2] + pd_["c"], ev[-1]["vtok"])
    if pd_["kind"] == "pumpswap":
        post = Lg.tokbal(t, "postTokenBalances")
        if pd_["vault_q"] not in post or pd_["vault_tok"] not in post: return None
        return (post[pd_["vault_q"]][2] + pd_.get("c", 0.0), post[pd_["vault_tok"]][2])
    return None

def pre_state(t, pd_, mint):
    """state BEFORE tx t (for his own legs)."""
    if pd_["kind"] == "pump_sol":
        ev = [e for e in Lg.trade_events(t) if e["mint"] == mint and e["vsol"] > 0]
        if not ev: return None
        e = ev[0]; s = -1 if e["buy"] else 1
        return (e["vsol"] + s * e["sol"], e["vtok"] - s * e["tok"])
    pre = Lg.tokbal(t, "preTokenBalances")
    if pd_["kind"] == "pump_q":
        ev = [e for e in Lg.trade_events(t) if e["mint"] == mint]
        if not ev or pd_["vault_q"] not in pre: return None
        e = ev[0]; s = -1 if e["buy"] else 1
        return (pre[pd_["vault_q"]][2] + pd_["c"], e["vtok"] - s * e["tok"])
    if pd_["kind"] == "pumpswap":
        if pd_["vault_q"] not in pre or pd_["vault_tok"] not in pre: return None
        return (pre[pd_["vault_q"]][2] + pd_.get("c", 0.0), pre[pd_["vault_tok"]][2])
