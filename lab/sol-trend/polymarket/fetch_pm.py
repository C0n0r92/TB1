"""Polymarket SOL 5m Up-or-Down: closed markets (Gamma) + public taker tape (data-api) for a sample, + live CLOB book snapshots.
READ-ONLY public endpoints, cached; ~1 req/s."""
import sys, os, json, time, datetime as dt
sys.path.insert(0, "/workspace/lab/polymarket-weather")
import pmw_common as C
ROOT = os.path.dirname(os.path.abspath(__file__)); C.CACHE = os.path.join(ROOT, "cache"); C.MIN_GAP["awc"] = 1.0
DAYS = int(os.environ.get("PM_DAYS", "7")); EVERY = int(os.environ.get("PM_EVERY", "3"))
def closed_events():
    out, off = [], 0; since = C.iso(C.now_utc() - dt.timedelta(days=DAYS))
    while True:
        d = C.http(C.GAMMA + "/events", {"series_slug": "sol-up-or-down-5m", "closed": "true", "limit": 100, "offset": off,
                   "end_date_min": since, "order": "endDate", "ascending": "false"}, cache_s=6 * 3600)
        out += d; off += 100
        if len(d) < 100 or off > 5000: return out
def main():
    ev = closed_events(); print("closed events", len(ev), flush=True)
    rows = []
    for i, e in enumerate(sorted(ev, key=lambda e: e["endDate"])):
        m = e["markets"][0]; op = json.loads(m.get("outcomePrices") or "[]")
        if not (len(op) == 2 and op[0] in ("0", "1")): continue
        r = {"slug": e["slug"], "cid": m["conditionId"], "start": m.get("eventStartTime"), "end": e["endDate"], "up_won": int(op[0] == "1"),
             "fee": m.get("feeSchedule"), "trades": None}
        if i % EVERY == 0:
            tr = C.http("https://data-api.polymarket.com/trades", {"market": m["conditionId"], "limit": 10000, "takerOnly": "true"}, cache_s=-1)
            r["trades"] = [{"t": x["timestamp"], "o": x["outcomeIndex"], "s": x["side"], "p": x["price"], "q": x["size"]} for x in tr]
        rows.append(r)
        if i % 50 == 0: print(i, e["slug"], flush=True)
    json.dump(rows, open(os.path.join(ROOT, "data", "markets.json"), "w")); print("saved", len(rows))
def books(n=12, gap=60):
    for _ in range(n):
        t = int(time.time()) // 300 * 300; toks = []
        for k in range(0, 4):
            d = C.http(C.GAMMA + "/events", {"slug": f"sol-updown-5m-{t + k * 300}"})
            if d: toks.append((t + k * 300, json.loads(d[0]["markets"][0]["clobTokenIds"])))
        bk = C.http(C.CLOB + "/books", body=[{"token_id": x} for _, tk in toks for x in tk])
        C.append_jsonl(os.path.join(ROOT, "data", "book_snapshots.jsonl"), [{"ts": C.iso(C.now_utc()), "windows": [w for w, _ in toks], "books": bk}])
        time.sleep(gap)
if __name__ == "__main__":
    if sys.argv[1:] == ["books"]: books()
    else: main()
