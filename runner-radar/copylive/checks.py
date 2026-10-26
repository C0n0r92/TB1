"""entry safety checks: rugguard (runner-radar) + Jupiter sell-route quote. Read-only public APIs."""
import sys
sys.path.insert(0, "/workspace/runner-radar")
import rugguard
from common import http_json, jup_sell_quote, R

def rug_check(mint, d, now_ts, scout=True):
    """-> (ok, info). d = dex_pairs() summary. Uses rugcheck.xyz report + GeckoTerminal 5m buyers + Scout launch forensics."""
    info = {}
    try:
        rep = http_json(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", timeout=20)
    except Exception as e:
        rep = None; info["rugcheck_err"] = repr(e)[:120]
    x = rugguard.rc_extract(rep, d.get("pair"))
    if rep and rep.get("rugged"): return False, {**info, "rejects": ["rugcheck: rugged"]}
    by5 = None
    try:
        g = http_json(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{d.get('pair')}", timeout=10)
        by5 = float(((((g.get("data") or {}).get("attributes") or {}).get("transactions") or {}).get("m5") or {}).get("buyers") or 0) or None
    except Exception: pass
    age_h = (now_ts - d["created"]) / 3600 if d.get("created") else 0
    row = {"age_h": age_h, "mcap": d.get("mcap"), "liq": d.get("liq"), "features": {"m5": d.get("m5") or 0}}
    rej, pen, why = rugguard.guard(row, x, (), by5)
    # 15:20Z: token age is governed by copylive's own gate (session rules: 5 min normal, 1 min tiny tier, user 14:08Z/15:12Z);
    # rugguard's 45-min radar age reject silently overrode it. Every other rugguard check (holders, wash, crash/spike, danger,
    # LP lock, creator %, Scout launch forensics) still applies.
    young = [r for r in rej if r.startswith("too young")]
    rej = [r for r in rej if not r.startswith("too young")]
    if young: why = why + ["age check left to copylive gate: " + young[0]]
    if scout and not rej:
        lrej, lpen, lwhy = rugguard.scout_verdict(rugguard.scout_check(mint, timeout=40))
        rej += lrej; why += lwhy; pen += lpen
    info.update(rejects=rej, penalty=pen, notes=why, holders=x.get("holders"), buyers5=by5, lp_locked=x.get("lp_locked"),
                creator_pct=x.get("creator_pct"), danger=x.get("danger"))
    return (not rej), info

def route_check(mint, size_sol, px_usd, solpx):
    """Jupiter token->SOL quote for roughly our position size (falls back to a tiny amount); impact must be <= 3%."""
    ui = (size_sol * solpx / px_usd) if (px_usd and solpx) else None
    ok, q = jup_sell_quote(mint, ui) if ui else (False, {"err": "no price"})
    if not ok and ui:   # retry small
        ok, q = jup_sell_quote(mint, ui / 20)
        if ok: q["note"] = "full-size quote failed, small quote ok"
    if ok and q.get("impact", 0) > R["max_impact"]:
        return False, {**q, "err": f"sell impact {q['impact']*100:.1f}% > 3%"}
    return ok, q
