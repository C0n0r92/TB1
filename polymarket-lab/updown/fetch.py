"""Fetch closed 1h/4h BTC/ETH Up-or-Down markets (Gamma) + their public taker trade tape (data-api). READ-ONLY, cached forever.
Also snapshots current CLOB books of open 1h/4h markets to estimate queue depth at price levels."""
import sys, os, json, datetime as dt
sys.path.insert(0, "/workspace/polymarket-lab/weather")
import pmw_common as C
ROOT = os.path.dirname(os.path.abspath(__file__)); C.CACHE = os.path.join(ROOT, "cache"); C.MIN_GAP["awc"] = 0.7
SERIES = os.environ.get("UD_SERIES", "btc-up-or-down-hourly,eth-up-or-down-hourly,btc-up-or-down-4h,eth-up-or-down-4h").split(",")
OUTF = os.environ.get("UD_OUT", "markets.json")
DAYS = int(os.environ.get("UD_DAYS", "7"))

def closed_events(series):
    out, off = [], 0
    since = C.iso(C.now_utc() - dt.timedelta(days=DAYS))
    while True:
        d = C.http(C.GAMMA + "/events", {"series_slug": series, "closed": "true", "limit": 100, "offset": off,
                                         "end_date_min": since, "order": "endDate", "ascending": "false"}, cache_s=6 * 3600)
        out += d
        if len(d) < 100: return out
        off += 100

def main():
    rows = []
    for s in SERIES:
        for e in closed_events(s):
            m = e["markets"][0]
            op = json.loads(m.get("outcomePrices") or "[]"); toks = json.loads(m.get("clobTokenIds") or "[]")
            if not (len(op) == 2 and op[0] in ("0", "1") and len(toks) == 2): continue
            tr = C.http("https://data-api.polymarket.com/trades", {"market": m["conditionId"], "limit": 10000, "takerOnly": "true"}, cache_s=-1)
            rows.append({"series": s, "slug": e["slug"], "cid": m["conditionId"], "tokens": toks, "start": m.get("eventStartTime"),
                         "end": e["endDate"], "up_won": int(op[0] == "1"), "vol": m.get("volumeNum"), "fee": m.get("feeSchedule"),
                         "trades": [{"t": x["timestamp"], "o": x["outcomeIndex"], "s": x["side"], "p": x["price"], "q": x["size"]} for x in tr]})
            print(s, e["slug"], len(tr), flush=True)
    with open(os.path.join(ROOT, "data", OUTF), "w") as fh: json.dump(rows, fh)
    # live depth snapshot (for queue-size assumption)
    toks = []
    for s in SERIES:
        for e in C.http(C.GAMMA + "/events", {"series_slug": s, "closed": "false", "limit": 6, "order": "endDate", "ascending": "true"}):
            toks += json.loads(e["markets"][0]["clobTokenIds"])
    books = C.http(C.CLOB + "/books", body=[{"token_id": t} for t in toks])
    C.append_jsonl(os.path.join(ROOT, "data", "book_snapshots.jsonl"), [{"ts": C.iso(C.now_utc()), "books": books}])
    print("markets", len(rows), "books", len(books))

if __name__ == "__main__":
    main()
