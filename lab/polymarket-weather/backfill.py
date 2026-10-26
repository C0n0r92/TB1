"""BACKFILL (historical, NOT a live forward test). Resolved Polymarket daily temperature events + Open-Meteo previous-runs
forecasts (temperature_2m_previous_day2 = runs ~2 days before valid time, ECMWF IFS + GFS), decision at local-day-start minus 24h.
Market price at decision = CLOB prices-history point <= decision time (a mid/last-type series, NOT the ask): ask is ASSUMED
= price + half_spread (0.02 = half the live median spread). No depth/queue info -> label OPTIMISTIC.
Per-station bias/sd learned on an expanding window of PRIOR days only (shrunk to a prior). Sept = warm-up only."""
import json, os, sys, math, datetime as dt, statistics as S
import pmw_common as C, model, pm_score as PS

CFG = json.load(open(os.path.join(C.ROOT, "config.json")))
BF = os.path.join(C.DATA, "backfill"); os.makedirs(BF, exist_ok=True)
WARM_START = dt.date(2026, 9, 8); TRADE_START = dt.date(2026, 10, 3); END = dt.date(2026, 10, 22)
HALF_SPREAD = 0.02; PRIOR_SD = 1.6; PRIOR_N = 6

def closed_events(day):
    out = []
    for off in (0, 100, 200):
        p = C.http(C.GAMMA + "/events", {"tag_slug": "daily-temperature", "closed": "true", "limit": 100, "offset": off,
                   "end_date_min": f"{day}T00:00:00Z", "end_date_max": f"{day}T23:59:59Z"}, cache_s=-1)
        out += p
        if len(p) < 100: break
    return out

def winner_value(br):
    """Approximate observed value (in market unit) from winning bracket."""
    if br["lo"] is not None and br["hi"] is not None: return (br["lo"] + br["hi"]) / 2
    return br["hi"] - 0.5 if br["lo"] is None else br["lo"] + 0.5

def fc_series(icao, st):
    r = C.http("https://previous-runs-api.open-meteo.com/v1/forecast", {"latitude": st["lat"], "longitude": st["lon"],
               "hourly": "temperature_2m_previous_day2", "models": "ecmwf_ifs025,gfs_seamless",
               "start_date": str(WARM_START - dt.timedelta(days=1)), "end_date": str(END + dt.timedelta(days=1)), "timezone": "GMT"}, cache_s=-1)
    h = r["hourly"]; times = [dt.datetime.fromisoformat(x).replace(tzinfo=dt.timezone.utc) for x in h["time"]]
    keys = [k for k in h if k != "time"]
    return times, {k: h[k] for k in keys}

def norm_cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def main():
    events = []
    d = WARM_START
    while d <= END:
        for e in closed_events(d):
            pe = C.parse_event(e)
            if not pe or pe["source"] != "metar" or not pe["station"] or not pe["date"]: continue
            mk = sorted(e.get("markets", []), key=lambda m: int(m.get("groupItemThreshold") or 0))
            brs = [C.parse_bracket(m.get("groupItemTitle") or "") for m in mk]
            win = [i for i, m in enumerate(mk) if (json.loads(m.get("outcomePrices") or "[]") or ["0"])[0] in ("1", "1.0")]
            if len(win) != 1 or any(b is None for b in brs): continue
            events.append({"pe": pe, "mk": [{"id": m["id"], "title": m["groupItemTitle"], "token": json.loads(m["clobTokenIds"])[0],
                           "fee": m.get("feeSchedule"), "fee_type": m.get("feeType")} for m in mk], "brs": brs, "win": win[0]})
        d += dt.timedelta(days=1)
    print("events", len(events), file=sys.stderr)
    stations = sorted({e["pe"]["station"] for e in events})
    fcs = {}
    for s in stations:
        try: fcs[s] = (C.station_info(s), fc_series(s, C.station_info(s)))
        except Exception as ex: print("fc fail", s, ex, file=sys.stderr)
    # forecast ext per event
    for e in events:
        pe = e["pe"]
        if pe["station"] not in fcs: e["fc"] = None; continue
        st, (times, ser) = fcs[pe["station"]]
        ds, de = model.local_day_bounds(pe["date"], st["tz"])
        idx = [i for i, t in enumerate(times) if ds <= t < de]
        vals = []
        for k, arr in ser.items():
            v = [arr[i] for i in idx if arr[i] is not None]
            if len(v) >= 20: vals.append(max(v) if pe["kind"] == "high" else min(v))
        e["fc"] = S.fmean(vals) if vals else None
        e["unit"] = e["brs"][0]["unit"]; e["ds"] = ds
        fc_u = (e["fc"] * 9 / 5 + 32) if (e["fc"] is not None and e["unit"] == "F") else e["fc"]
        e["fc_u"] = fc_u; e["obs_u"] = winner_value(e["brs"][e["win"]])
    events = [e for e in events if e.get("fc") is not None]
    events.sort(key=lambda e: e["pe"]["date"])
    # expanding calibration (prior days only)
    hist = {}
    rows = []
    for e in events:
        key = (e["pe"]["station"], e["pe"]["kind"])
        h = [x for x in hist.get(key, []) if x[0] < e["pe"]["date"]]
        scale = 1.8 if e["unit"] == "F" else 1.0
        n = len(h); errs = [x[1] for x in h]
        bias = (sum(errs) / (n + PRIOR_N)) if n else 0.0
        sd = math.sqrt((PRIOR_N * (PRIOR_SD * scale) ** 2 + sum((x - bias) ** 2 for x in errs)) / (PRIOR_N + n))
        sd = max(sd, 0.6 * scale)
        mu = e["fc_u"] + bias
        probs = []
        for br in e["brs"]:
            lo = -1e9 if br["lo"] is None else br["lo"] - 0.5; hi = 1e9 if br["hi"] is None else br["hi"] + 0.5
            probs.append(min(.998, max(.002, norm_cdf((hi - mu) / sd) - norm_cdf((lo - mu) / sd))))
        e["probs"] = probs; e["bias"] = bias; e["sd"] = sd; e["n_hist"] = n
        hist.setdefault(key, []).append((e["pe"]["date"], e["obs_u"] - e["fc_u"]))
    # save calibration learned through END for the live model
    calib = {}
    units = {}
    for e in events: units[f"{e['pe']['station']}|{e['pe']['kind']}"] = e["unit"]
    for (s, k), h in hist.items():
        n = len(h); errs = [x[1] for x in h]; u = units.get(f"{s}|{k}"); sc = 1.8 if u == "F" else 1.0
        b = sum(errs) / (n + PRIOR_N)
        calib[f"{s}|{k}"] = {"n": n, "unit": u, "bias_u": b,
                             "rmse_u": math.sqrt((PRIOR_N * (PRIOR_SD * sc) ** 2 + sum((x - b) ** 2 for x in errs)) / (PRIOR_N + n))}
    json.dump({"through": str(END), "calib": calib}, open(os.path.join(C.DATA, "calib.json"), "w"), indent=0)
    # prices at decision time for candidate brackets
    tr_events = [e for e in events if dt.date.fromisoformat(e["pe"]["date"]) >= TRADE_START]
    print("trade-window events", len(tr_events), file=sys.stderr)
    calib_pts = []
    ncall = 0
    for e in tr_events:
        T = e["ds"] - dt.timedelta(hours=24); Tts = int(T.timestamp())
        for j, (br, m) in enumerate(zip(e["brs"], e["mk"])):
            p = e["probs"][j]
            rec = {"date": e["pe"]["date"], "slug": e["pe"]["slug"], "station": e["pe"]["station"], "kind": e["pe"]["kind"],
                   "city": e["pe"]["city"], "bracket": m["title"], "token": m["token"], "p_model": round(p, 4), "won": int(j == e["win"]),
                   "decision_ts": C.iso(T), "fc_u": round(e["fc_u"], 2), "bias": round(e["bias"], 2), "sd": round(e["sd"], 2), "n_hist": e["n_hist"],
                   "fee_rate": (m["fee"] or {}).get("rate"), "price": None}
            if p >= 0.05:
                try:
                    hh = C.http(C.CLOB + "/prices-history", {"market": m["token"], "startTs": Tts - 6 * 3600, "endTs": Tts, "fidelity": 10}, cache_s=-1)
                    ncall += 1
                    pts = [x for x in hh.get("history", []) if x["t"] <= Tts]
                    if pts: rec["price"] = pts[-1]["p"]; rec["price_age_min"] = round((Tts - pts[-1]["t"]) / 60, 1)
                except Exception as ex: rec["price_err"] = repr(ex)[:100]
            rows.append(rec)
    with open(os.path.join(BF, "brackets.jsonl"), "w") as fh:
        for r in rows: fh.write(json.dumps(r) + "\n")
    print("prices-history calls", ncall, "rows", len(rows), file=sys.stderr)

if __name__ == "__main__":
    main()
