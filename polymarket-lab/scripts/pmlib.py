"""Shared helpers (READ-ONLY public data, PAPER ONLY). No accounts, wallets, keys or orders."""
import json, os, time, sqlite3, urllib.request, urllib.parse, datetime as dt, math
LAB = "/workspace/polymarket-lab"; DATA = f"{LAB}/data"
GAMMA = "https://gamma-api.polymarket.com"; CLOB = "https://clob.polymarket.com"
BINANCE = "https://data-api.binance.vision/api/v3"   # Binance public market-data mirror (api.binance.com returns 451 from this US box)
COINBASE = "https://api.exchange.coinbase.com"
UA = {"User-Agent": "oracle-paper-research/0.1 (read-only)"}
_last = {}
def http(url, params=None, body=None, gap=0.3, retries=3, timeout=25):
    if params: url += "?" + urllib.parse.urlencode(params, doseq=True)
    host = urllib.parse.urlparse(url).netloc
    for i in range(retries):
        w = gap - (time.time() - _last.get(host, 0))
        if w > 0: time.sleep(w)
        _last[host] = time.time()
        try:
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(url, data=data, headers=dict(UA, **({"Content-Type": "application/json"} if data else {})))
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429,) or e.code >= 500: time.sleep(3 * (i + 1)); continue
            raise
        except Exception:
            if i == retries - 1: raise
            time.sleep(2 * (i + 1))
    raise RuntimeError("http failed " + url)
def now(): return dt.datetime.now(dt.timezone.utc)
def iso(t): return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def pts(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
def fee_per_share(p, rate=0.07): return rate * p * (1 - p)
def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def db():
    c = sqlite3.connect(f"{DATA}/updown.sqlite", timeout=60)
    c.executescript("""
    create table if not exists snaps(ts text, track int, series text, slug text, cid text, start text, end text,
      up_tok text, dn_tok text, up_bid real, up_ask real, up_bid_sz real, up_ask_sz real, up_bid_depth5 real, up_ask_depth5 real,
      dn_bid real, dn_ask real, dn_bid_sz real, dn_ask_sz real, dn_bid_depth5 real, dn_ask_depth5 real,
      price_to_beat real, spot real, spot_src text, fee_rate real, res_src text);
    create index if not exists snaps_slug on snaps(slug);
    create table if not exists candles(sym text, src text, t int, o real, h real, l real, c real, v real, primary key(sym, src, t));
    create table if not exists resolutions(slug text primary key, series text, cid text, start text, end text, up_won int, price_to_beat real, final_price real);
    """)
    return c
def append_jsonl(path, rows):
    with open(path, "a") as fh:
        for r in rows: fh.write(json.dumps(r) + "\n")
def read_jsonl(path):
    if not os.path.exists(path): return []
    return [json.loads(l) for l in open(path) if l.strip()]
