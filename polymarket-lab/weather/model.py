"""Forecast model: P(bracket) for a daily high/low temperature event at the exact resolution station.
Inputs known at snapshot time t only: Open-Meteo ensemble (ECMWF IFS 0.25 51 members + GFS 0.25 31 members) fetched at t,
and METAR routine observations already reported for the local observation date before t."""
import json, os, datetime as dt, random
from zoneinfo import ZoneInfo
import numpy as np, math
import pmw_common as C

CFG = json.load(open(os.path.join(C.ROOT, "config.json")))
_cp = os.path.join(C.DATA, "calib.json")
CALIB = json.load(open(_cp))["calib"] if os.path.exists(_cp) else {}

def ensemble(icao, st):
    r = C.http("https://ensemble-api.open-meteo.com/v1/ensemble",
               {"latitude": st["lat"], "longitude": st["lon"], "hourly": "temperature_2m", "models": ",".join(CFG["ensemble_models"]),
                "forecast_days": 4, "past_days": 1, "timezone": "GMT"}, cache_s=CFG["forecast_cache_s"])
    h = r["hourly"]
    times = [dt.datetime.fromisoformat(x).replace(tzinfo=dt.timezone.utc) for x in h["time"]]
    members = [np.array([np.nan if v is None else v for v in h[k]], dtype=float) for k in h if k.startswith("temperature_2m") and "member" in k or k.startswith("temperature_2m_") and k.endswith("_ensemble") and "member" not in k]
    return times, np.vstack(members) if members else None

def local_day_bounds(date_str, tz):
    z = ZoneInfo(tz); d = dt.date.fromisoformat(date_str)
    s = dt.datetime(d.year, d.month, d.day, tzinfo=z); e = s + dt.timedelta(days=1)
    return s.astimezone(dt.timezone.utc), e.astimezone(dt.timezone.utc)

def bracket_probs(kind, unit, brackets, t, day_s, day_e, times, M, obs, rng=None, station=None):
    """brackets: list of parsed bracket dicts. obs: list of (ts, tempC). Returns (probs, info)."""
    mc = CFG["model"]; rng = rng or np.random.default_rng(12345)
    seen = [v for (ts, v, *_) in obs if day_s <= ts < day_e and ts <= t]
    obs_ext = (max(seen) if kind == "high" else min(seen)) if seen else None
    idx = [i for i, ts in enumerate(times) if ts > t and day_s <= ts < day_e]
    info = {"obs_ext_c": obs_ext, "n_obs": len(seen), "n_fc_hours": len(idx)}
    if idx and M is not None:
        sub = M[:, idx]
        sub = sub[~np.all(np.isnan(sub), axis=1)]
        ext = np.nanmax(sub, axis=1) if kind == "high" else np.nanmin(sub, axis=1)
        lead_h = max(0.0, (day_e - t).total_seconds() / 3600 - 12)
        sig = mc["sigma0_c"] + mc["sigma_per_24h_c"] * lead_h / 24
        bias = mc["bias_high_c"] if kind == "high" else mc["bias_low_c"]
        cal = CALIB.get(f"{station}|{kind}") if station else None
        if cal and cal.get("n", 0) >= 5:
            # station bias/rmse learned from resolved PAST days only (backfill through calib 'through' date, day-2 forecasts)
            u = 1.8 if cal.get("unit") == "F" else 1.0
            bias = cal["bias_u"] / u
            rmse_c = cal["rmse_u"] / u if u == 1.0 else cal["rmse_u"] / u  # rmse_u prior is in unit terms
            # v2: total predictive sd ~ day-2 rmse, mildly shrunk with lead (v1 shrank to 0.4x and hit the 0.3C floor -> overconfident)
            shrink = min(1.0, max(0.6, 0.5 + 0.5 * ((day_e - t).total_seconds() / 3600) / 48))
            ens_sd = float(np.std(ext))
            sig = math.sqrt(max(0.25, (rmse_c * shrink) ** 2 - ens_sd ** 2))
            info["calib"] = {"bias_c": round(bias, 2), "rmse_c": round(rmse_c, 2), "n": cal["n"]}
        draws = (ext[:, None] + bias + rng.normal(0, sig, (len(ext), mc["draws_per_member"]))).ravel()
        if obs_ext is not None:
            draws = np.maximum(draws, obs_ext) if kind == "high" else np.minimum(draws, obs_ext)
        info.update({"ens_n": int(len(ext)), "ens_mean_c": round(float(np.mean(ext)), 2), "ens_sd_c": round(float(np.std(ext)), 2), "sigma_c": round(sig, 2)})
    elif obs_ext is not None and not idx and t >= day_e - dt.timedelta(hours=1):
        draws = np.array([obs_ext] * 50 + list(obs_ext + rng.normal(0, 0.15, 50)))  # day over: tiny correction risk
    else:
        return None, info
    vals = draws * 9 / 5 + 32 if unit == "F" else draws
    ints = np.floor(np.round(vals, 6) + 0.5).astype(int)
    probs = []
    for br in brackets:
        if br is None: probs.append(None); continue
        ok = np.ones_like(ints, dtype=bool)
        if br["lo"] is not None: ok &= ints >= br["lo"]
        if br["hi"] is not None: ok &= ints <= br["hi"]
        p = float(ok.mean()); c = mc["p_clip"]
        probs.append(min(1 - c, max(c, p)))
    return probs, info
