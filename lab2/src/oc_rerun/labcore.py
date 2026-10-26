"""Lab shared helpers (PAPER ONLY, stdlib only). Read-only toward every other bot's files."""
import csv, datetime as dt, glob, hashlib, json, os, re, sys, time, tomllib, urllib.request, urllib.error
from zoneinfo import ZoneInfo

LAB = "/workspace/lab"   # Lab 2 copy: READ Lab data only; this copy never writes there
DATA = os.path.join(LAB, "data")
CANDLES = os.path.join(DATA, "candles")
SNAPS = os.path.join(DATA, "intel_snapshots")
RUGC = os.path.join(DATA, "rugcheck")
LIQ_POLLS = os.path.join(DATA, "liq_polls.jsonl")
PAIRS = os.path.join(DATA, "pairs.json")
OUT = os.path.join(LAB, "out")
DUB = ZoneInfo("Europe/Dublin")
UA = {"User-Agent": "lab-paper-backtest/1.0", "Accept": "application/json"}
_ADDR = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_ADDR_IN = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
_SAFE = re.compile(r"[^A-Za-z0-9 $._-]")

def load_config(path=None):
    cfg = tomllib.load(open(path or os.path.join(LAB, "config.toml"), "rb"))
    d = cfg.get("defaults", {})
    cfg["variants"] = [{**d, **v} for v in cfg.get("variant", [])]
    return cfg

def valid_sol(a): return isinstance(a, str) and bool(_ADDR.match(a))
def clean(s, n=24): return _SAFE.sub("", str(s or ""))[:n].strip() or "?"
def fnum(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d
def ts_of(s): return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
def iso(t): return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(timespec="seconds")
def parse_ts(v):
    if v in (None, ""): return None
    if isinstance(v, (int, float)): return v / 1000 if v > 1e11 else float(v)
    try: return ts_of(v)
    except Exception:
        try: x = float(v); return x / 1000 if x > 1e11 else x
        except Exception: return None
def next_dublin_close(t):
    d = dt.datetime.fromtimestamp(t, DUB)
    c = d.replace(hour=8, minute=0, second=0, microsecond=0)
    if c <= d: c = (d + dt.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return c.timestamp()
def night_of(t): return (dt.datetime.fromtimestamp(t, DUB) - dt.timedelta(hours=12)).date().isoformat()

def read_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except ValueError: pass
    return out

def load_json(path, default=None):
    try: return json.load(open(path))
    except Exception: return default

def atomic_write(path, text):
    tmp = path + ".tmp"
    open(tmp, "w").write(text); os.replace(tmp, path)

# ---------- polite HTTP (per-host spacing, shared across a run) ----------
_last = {}
def get_json(url, spacing=6.5, retries=2, timeout=20):
    h = url.split("/")[2]
    for attempt in range(retries + 1):
        wait = spacing - (time.time() - _last.get(h, 0))
        if wait > 0: time.sleep(wait)
        _last[h] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries: time.sleep(20 * (attempt + 1)); continue
            if e.code >= 500 and attempt < retries: time.sleep(5); continue
            return None
        except Exception:
            if attempt < retries: time.sleep(3); continue
            return None

# ---------- candle cache ----------
def cache_path(pair): return os.path.join(CANDLES, pair + ".json")

def load_candles(pair):
    c = load_json(cache_path(pair))
    return c if c and c.get("rows") else None

def merge_candles(pair, rows, fetched_at, covered_until):
    c = load_candles(pair) or {"rows": [], "fetched_at": 0, "covered_until": 0}
    m = {int(r[0]): [int(r[0])] + [float(x) for x in r[1:6]] for r in c["rows"]}
    for r in rows:                                                               # t,o,h,l,c[,volume_usd]
        k = int(r[0]); nr = [k] + [float(x) for x in r[1:6]]
        if len(nr) == 5 and k in m and len(m[k]) == 6: nr.append(m[k][5])      # keep volume if new source lacks it
        m[k] = nr
    allr = sorted(m.values())
    c.update(rows=allr, first=allr[0][0] if allr else None, fetched_at=max(c.get("fetched_at", 0), fetched_at),
             covered_until=max(c.get("covered_until", 0), covered_until))
    os.makedirs(CANDLES, exist_ok=True)
    atomic_write(cache_path(pair), json.dumps(c))
    return c

# ---------- point-in-time intel ----------
def snapshot_intel(cfg):
    """Copy Pulse/Scout files into data/intel_snapshots/ whenever content changes; valid_from = file mtime."""
    p = cfg["paths"]
    srcs = {"x_hot": os.path.join(p["x_intel"], "hot.json"), "x_rugs": os.path.join(p["x_intel"], "rugs.json"),
            "x_pulse": os.path.join(p["x_pulse"], "latest.json"),
            "oc_smart": os.path.join(p["onchain"], "smart_wallets.json"), "oc_avoid": os.path.join(p["onchain"], "avoid.csv")}
    idxp = os.path.join(SNAPS, "index.jsonl")
    known = {(r["src"], r["sha"]) for r in read_jsonl(idxp)}
    for name, path in srcs.items():
        if not os.path.isfile(path): continue
        data = open(path, "rb").read(); sha = hashlib.sha256(data).hexdigest()[:16]
        if (name, sha) in known: continue
        mt = os.path.getmtime(path); d = os.path.join(SNAPS, name); os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, f"{int(mt)}_{sha}{os.path.splitext(path)[1]}")
        open(fn, "wb").write(data)
        with open(idxp, "a") as fh:
            fh.write(json.dumps({"src": name, "sha": sha, "file": fn, "valid_from": mt, "captured": time.time()}) + "\n")

def intel_index(cfg):
    """Union of radar's and Lab's snapshot indexes (dedup by src+sha, earliest valid_from wins)."""
    best = {}
    for r in read_jsonl(os.path.join(cfg["paths"]["radar_snapshots"], "index.jsonl")) + read_jsonl(os.path.join(SNAPS, "index.jsonl")):
        k = (r["src"], r["sha"])
        if os.path.exists(r["file"]) and (k not in best or r["valid_from"] < best[k]["valid_from"]): best[k] = r
    return list(best.values())

def radar_intel_module(cfg):
    """Reuse runner-radar/variants.py's tolerant parsers (x_view / oc_view) without writing bytecode there."""
    sys.dont_write_bytecode = True
    d = os.path.dirname(cfg["paths"]["radar_scanned"])
    if d not in sys.path: sys.path.insert(0, d)
    try:
        import variants as V
        return V
    except Exception as e:
        print(f"warning: cannot import radar variants.py parsers ({e}); Pulse/Scout filters disabled", file=sys.stderr)
        return None

def holders_at(cfg, token, t, max_lag=900):
    """Top holders + creator captured within 15 min after signal (radar holders.jsonl or Lab rugcheck capture)."""
    for h in read_jsonl(os.path.join(cfg["paths"]["radar_snapshots"], "holders.jsonl")):
        if h.get("token") == token and 0 <= h.get("fetched_at", 0) - t <= max_lag: return h
    r = load_json(os.path.join(RUGC, token + ".json"))
    if r and r.get("fetched_at", 0) - t <= max_lag: return r
    return None

def liq_polls():
    by = {}
    for r in read_jsonl(LIQ_POLLS): by.setdefault(r["token"], []).append(r)
    for v in by.values(): v.sort(key=lambda r: r["ts"])
    return by
