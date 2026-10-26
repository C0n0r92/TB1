"""Shared helpers for the Polymarket weather paper-research track (READ-ONLY, PAPER ONLY).
No account, no wallet, no keys, no order placement. Only public GET endpoints (+ CLOB POST /books, a read-only batch quote)."""
import json, os, re, time, math, hashlib, datetime as dt
import urllib.request, urllib.parse
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data"); CACHE = os.path.join(ROOT, "cache"); OUT = os.path.join(ROOT, "out")
for d in (DATA, CACHE, OUT): os.makedirs(d, exist_ok=True)
GAMMA = "https://gamma-api.polymarket.com"; CLOB = "https://clob.polymarket.com"
UA = {"User-Agent": "lab-paper-research/0.1 (read-only)"}
_last = {}
MIN_GAP = {"gamma": 0.35, "clob": 0.25, "openmeteo": 1.2, "awc": 1.5}  # seconds between calls per host (gentle)

def now_utc(): return dt.datetime.now(dt.timezone.utc)
def iso(t): return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def parse_ts(s):
    if s is None: return None
    s = s.replace("Z", "+00:00")
    if "." in s: s = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), s)
    return dt.datetime.fromisoformat(s)

def _host(url):
    if "gamma-api" in url: return "gamma"
    if "clob.polymarket" in url: return "clob"
    if "open-meteo" in url: return "openmeteo"
    return "awc"

def http(url, params=None, body=None, cache_s=0, retries=3):
    if params: url = url + "?" + urllib.parse.urlencode(params, doseq=True)
    key = hashlib.sha1((url + (json.dumps(body) if body else "")).encode()).hexdigest()
    cp = os.path.join(CACHE, key[:2], key + ".json")
    if cache_s and os.path.exists(cp) and (cache_s < 0 or time.time() - os.path.getmtime(cp) < cache_s):
        with open(cp) as fh: return json.load(fh)
    h = _host(url)
    for i in range(retries):
        gap = MIN_GAP[h] - (time.time() - _last.get(h, 0))
        if gap > 0: time.sleep(gap)
        _last[h] = time.time()
        try:
            data = json.dumps(body).encode() if body is not None else None
            hdr = dict(UA, **({"Content-Type": "application/json"} if data else {}))
            req = urllib.request.Request(url, data=data, headers=hdr)
            with urllib.request.urlopen(req, timeout=40) as r: raw = r.read().decode()
            out = json.loads(raw) if raw.strip()[:1] in "[{" else raw
            if cache_s:
                os.makedirs(os.path.dirname(cp), exist_ok=True)
                with open(cp + ".tmp", "w") as fh: json.dump(out, fh)
                os.replace(cp + ".tmp", cp)
            return out
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500: time.sleep(5 * (i + 1)); continue
            raise
        except Exception:
            if i == retries - 1: raise
            time.sleep(3 * (i + 1))
    raise RuntimeError("http failed " + url)

def append_jsonl(path, rows):
    with open(path, "a") as fh:
        for r in rows: fh.write(json.dumps(r, separators=(",", ":")) + "\n")

def read_jsonl(path):
    if not os.path.exists(path): return []
    out = []
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except Exception: pass
    return out

# ---------- market parsing ----------
BR_RE = [
    (re.compile(r"^(-?\d+(?:\.\d+)?)\s*°\s*([CF])\s*or\s*(?:below|lower)$", re.I), "le"),
    (re.compile(r"^(-?\d+(?:\.\d+)?)\s*°\s*([CF])\s*or\s*(?:higher|above)$", re.I), "ge"),
    (re.compile(r"^(-?\d+)\s*[-–]\s*(-?\d+)\s*°\s*([CF])$", re.I), "range"),
    (re.compile(r"^(-?\d+)\s*°\s*([CF])$", re.I), "eq"),
]
def parse_bracket(title):
    t = title.strip().replace("º", "°")
    for rx, kind in BR_RE:
        m = rx.match(t)
        if not m: continue
        g = m.groups()
        if kind == "le": return {"lo": None, "hi": int(float(g[0])), "unit": g[1].upper()}
        if kind == "ge": return {"lo": int(float(g[0])), "hi": None, "unit": g[1].upper()}
        if kind == "range": return {"lo": int(g[0]), "hi": int(g[1]), "unit": g[2].upper()}
        if kind == "eq": return {"lo": int(g[0]), "hi": int(g[0]), "unit": g[1].upper()}
    return None

def in_bracket(v_int, br):
    return (br["lo"] is None or v_int >= br["lo"]) and (br["hi"] is None or v_int <= br["hi"])

def round_half_up(x): return math.floor(x + 0.5)

def to_unit_rounded(c, unit):
    """Polymarket rule (2026 descriptions): value in tenths °C; F = C*9/5+32; round half up to whole degree."""
    v = c * 9 / 5 + 32 if unit == "F" else c
    return round_half_up(round(v, 6))

def parse_event(e):
    """Return dict with city, kind, station, local date, rule flags, or None if not a daily temperature event."""
    slug = e.get("slug", "")
    m = re.match(r"^(highest|lowest)-temperature-in-(.+?)-on-([a-z]+-\d+-\d{4})", slug)
    if not m: return None
    desc = e.get("description") or (e.get("markets") or [{}])[0].get("description") or ""
    rs = e.get("resolutionSource") or ""
    st = re.search(r"ids=([A-Z0-9]{4})", rs) or re.search(r"timeseries\?site=([A-Za-z0-9]{4})", rs) or re.search(r"\(([A-Z]{4})\)", desc)
    rule = []
    if "tenths of a degree" in desc: rule.append("tenths")
    if "rounded to the nearest whole degree" in desc: rule.append("round_nearest")
    if "exactly half rounded up" in desc: rule.append("half_up")
    if "SPECI" in desc: rule.append("no_speci")
    if "weather.gov/wrh/timeseries" in rs: rule.append("noaa_timeseries_whole_deg")
    if "Weather Underground" in desc and "aviationweather" not in desc.lower(): rule.append("wunderground_primary")
    return {"event_id": e.get("id"), "slug": slug, "kind": "high" if m.group(1) == "highest" else "low", "city": m.group(2),
            "date": e.get("eventDate") or None, "station": st.group(1).upper() if st else None,
            "source": "metar" if ("aviationweather" in rs or "weather.gov/wrh/timeseries" in rs) else (rs or "unknown"),
            "rule": "+".join(rule), "end": e.get("endDate"), "title": e.get("title")}

def fee_per_share(price, fee_schedule):
    """Polymarket taker fee: fee = C * rate * p * (1-p) (docs.polymarket.com/polymarket-learn/trading/fees)."""
    rate = (fee_schedule or {}).get("rate", 0.05)
    if rate is None: rate = 0.05
    return rate * price * (1 - price)

# ---------- stations ----------
def station_info(icao):
    p = os.path.join(CACHE, "stations.json")
    db = json.load(open(p)) if os.path.exists(p) else {}
    if icao not in db:
        r = http("https://aviationweather.gov/api/data/stationinfo", {"ids": icao, "format": "json"}, cache_s=-1)
        if not r: return None
        s = r[0]
        # timezone via open-meteo (one tiny call, cached forever)
        tz = http("https://api.open-meteo.com/v1/forecast", {"latitude": s["lat"], "longitude": s["lon"], "daily": "temperature_2m_max",
                  "forecast_days": 1, "timezone": "auto"}, cache_s=-1).get("timezone")
        db[icao] = {"lat": s["lat"], "lon": s["lon"], "elev": s.get("elev"), "site": s.get("site"), "country": s.get("country"), "tz": tz}
        with open(p, "w") as fh: json.dump(db, fh, indent=0)
    return db[icao]

# ---------- METAR observations ----------
TGRP = re.compile(r"\bT([01])(\d{3})([01])(\d{3})\b")
BODY = re.compile(r"\s(M?\d{2})/(M?\d{2})?\s")
def metar_temp_c(raw):
    if raw.strip().startswith("SPECI"): return None
    m = TGRP.search(raw)
    if m: return (-1 if m.group(1) == "1" else 1) * int(m.group(2)) / 10
    m = BODY.search(" " + raw + " ")
    if m:
        v = m.group(1); return -int(v[1:]) if v.startswith("M") else int(v)
    return None

def metar_obs(icaos, hours=40, cache_s=900):
    """Return {icao: [(utc_datetime, temp_c, raw)]} from aviationweather.gov (routine reports only)."""
    out = {}
    for i in range(0, len(icaos), 40):
        chunk = icaos[i:i + 40]
        r = http("https://aviationweather.gov/api/data/metar", {"ids": ",".join(chunk), "format": "json", "hours": hours}, cache_s=cache_s)
        for o in (r or []):
            raw = o.get("rawOb") or ""
            if (o.get("metarType") or "METAR") == "SPECI" or raw.startswith("SPECI"): continue
            t = metar_temp_c(raw)
            if t is None: continue
            ts = dt.datetime.fromtimestamp(o["obsTime"], dt.timezone.utc) if isinstance(o.get("obsTime"), (int, float)) else parse_ts(o.get("reportTime"))
            out.setdefault(o.get("icaoId"), []).append((ts, t, raw))
    return out
