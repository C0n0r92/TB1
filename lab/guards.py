"""Guarded-radar helpers (PAPER ONLY, read-only on runner-radar).
- classify(): split a scan row's rejects into the radar's original rejects vs rugguard categories.
- replay(): for rows scanned BEFORE rugguard went live (no `guard` object), recompute rugguard.guard() using the
  best holder snapshot we have and say whether it is point-in-time (captured <= 15 min after the scan) or optimistic.
- scout_at(): Scout's rugcheck_creator verdict captured within 15 min of time t (Lab cache, Scout cache, rugdiag)."""
import glob, json, os, re, sys
from labcore import LAB, DATA, load_json, ts_of, read_jsonl

SCOUT_DIR = os.path.join(DATA, "scout")
PIT_LAG = 900
CATS = [("age", r"^too young"), ("holders", r"^holder count unavailable|^only \d+ holders|mcap per holder"),
        ("wash", r"^wash trading"), ("m5", r"^crashing|^extreme 5m spike"), ("liqdrop", r"^liquidity fell"),
        ("lp_danger", r"^rugcheck danger|^LP only|^creator holds"), ("launch_fullcurve", r"^launch: full-curve"),
        ("launch_rugger", r"^launch: creator is a known rugger"), ("launch_funded", r"^launch: creator funded"),
        ("launch_budget", r"^launch check budget")]

def cat_of(s):
    for c, rx in CATS:
        if re.search(rx, s): return c
    return None

def classify(rejects):
    old, g = [], {}
    for s in rejects or []:
        c = cat_of(s)
        if c: g.setdefault(c, []).append(s)
        else: old.append(s)
    return old, g

_RG = None
def rugguard_mod(radar_dir):
    global _RG
    if _RG is None:
        sys.dont_write_bytecode = True
        if radar_dir not in sys.path: sys.path.insert(0, radar_dir)
        try:
            import rugguard as R; _RG = R
        except Exception as e:
            print(f"warning: cannot import rugguard ({e})", file=sys.stderr); _RG = False
    return _RG or None

def _rc_report(token):
    """(report, fetched_at) candidates: Lab full reports (data/rugcheck_full) then rugdiag rc_*.json (mtime)."""
    out = []
    p = os.path.join(DATA, "rugcheck_full", token + ".json")
    j = load_json(p)
    if j and j.get("report"): out.append((j["report"], j.get("fetched_at", os.path.getmtime(p))))
    p = f"/workspace/rugdiag/rc_{token}.json"
    if os.path.exists(p):
        j = load_json(p)
        if j: out.append((j, os.path.getmtime(p)))
    return out

def replay(cfg, row, prev_rows):
    """-> dict(old, cats, score, pit, src) for a radar row. Live guarded rows are taken as logged."""
    old, g = classify(row.get("rejects"))
    if "guard" in row:
        return {"old": old, "cats": g, "score": row.get("score") or 0, "pit": True, "src": "live"}
    R = rugguard_mod(os.path.dirname(cfg["paths"]["radar_scanned"]))
    if not R: return {"old": old, "cats": {"unavailable": ["rugguard import failed"]}, "score": row.get("score") or 0, "pit": False, "src": "none"}
    reps = _rc_report(row["token"])
    pit_rep = [r for r in reps if 0 <= r[1] - row["t"] <= PIT_LAG]
    rep, pit = (pit_rep[0][0], True) if pit_rep else ((reps[0][0], False) if reps else (None, False))
    x = R.rc_extract(rep, row.get("pair")) if rep else {}
    if not pit: x["danger"] = [d for d in x.get("danger") or [] if d != "Low Liquidity"]   # post-rug artefact
    b = re.search(r"\((\d+) buyers/5m\)", " ".join(row.get("reasons") or [])); b5 = int(b.group(1)) if b else None
    rej, pen, _ = R.guard(row, x, prev_rows, b5)
    sc = scout_at(row["token"], row["t"])
    srej, spen, _ = R.scout_verdict(sc["raw"] if sc else None)
    _, g2 = classify(rej + srej)
    return {"old": old, "cats": g2, "score": max(0, (row.get("score") or 0) - pen - spen), "pit": pit and (sc is None or sc["pit"]),
            "src": "replay_pit" if pit else ("replay_lookahead" if rep else "replay_noholders")}

_SC = None
def _scout_all():
    global _SC
    if _SC is None:
        _SC = {}
        files = glob.glob(os.path.join(SCOUT_DIR, "*.json")) + glob.glob("/workspace/onchain-intel/data/rugcheck/*.json") + \
                glob.glob("/workspace/rugdiag/sc_*.json")
        for f in files:
            j = load_json(f)
            if not isinstance(j, dict) or not j.get("verdict"): continue
            raw = j.get("raw", j); mint = raw.get("mint") or j.get("mint") or os.path.basename(f).replace("sc_", "")[:-5]
            t = j.get("captured_at") or (ts_of(raw["checked_utc"]) if raw.get("checked_utc") else os.path.getmtime(f))
            _SC.setdefault(mint, []).append({"t": t, "verdict": raw.get("verdict"), "raw": raw, "file": f})
        sv = "/workspace/onchain-intel/signal_verdicts.jsonl"   # Scout's after-the-fact verdicts on radar signals
        if os.path.exists(sv):
            for line in open(sv):
                try: j = json.loads(line)
                except Exception: continue
                if j.get("mint") and j.get("verdict") and j.get("checked_at"):
                    _SC.setdefault(j["mint"], []).append({"t": ts_of(j["checked_at"]), "verdict": j["verdict"], "raw": j, "file": sv})
        for v in _SC.values(): v.sort(key=lambda r: r["t"])
    return _SC

def scout_at(token, t, lag=PIT_LAG):
    """Earliest Scout verdict captured in [t-2h, t+15min] (pit=True), else the earliest later one (pit=False)."""
    v = _scout_all().get(token) or []
    ok = [r for r in v if -7200 <= r["t"] - t <= lag]
    if ok:
        return {**ok[0], "pit": True}
    later = [r for r in v if r["t"] > t]
    return {**later[0], "pit": False} if later else None
