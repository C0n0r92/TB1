"""Snapshot open Up-or-Down markets (Gamma listing + CLOB /books) + spot + 1m candles into data/updown.sqlite. READ-ONLY.
track 2: 1h/4h BTC/ETH/SOL (run every 5 min).  track 3: SOL 5m/15m (run every 1 min)."""
import sys, json, datetime as dt
sys.path.insert(0, "/workspace/polymarket-lab/scripts")
import pmlib as P
SERIES = {2: ["btc-up-or-down-hourly", "eth-up-or-down-hourly", "solana-up-or-down-hourly", "btc-up-or-down-4h", "eth-up-or-down-4h", "sol-up-or-down-4h"],
          3: ["sol-up-or-down-5m", "sol-up-or-down-15m"]}
SYM = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT"}
def side(book):
    bids = sorted(((float(x["price"]), float(x["size"])) for x in book.get("bids", [])), reverse=True)
    asks = sorted((float(x["price"]), float(x["size"])) for x in book.get("asks", []))
    bb = bids[0] if bids else (None, None); ba = asks[0] if asks else (None, None)
    d5b = sum(s * p for p, s in bids if bb[0] is not None and p >= bb[0] - 0.05)
    d5a = sum(s * p for p, s in asks if ba[0] is not None and p <= ba[0] + 0.05)
    return bb[0], ba[0], bb[1], ba[1], round(d5b, 2), round(d5a, 2)
def main(track):
    t = P.now(); ts = P.iso(t); c = P.db(); rows = []; spots = {}
    for coin, sym in SYM.items():
        if track == 3 and coin != "sol": continue
        try:
            k = P.http(P.BINANCE + "/klines", {"symbol": sym, "interval": "1m", "limit": 30})
            c.executemany("insert or replace into candles values(?,?,?,?,?,?,?,?)", [(coin, "binance", int(x[0]) // 1000, *map(float, x[1:6])) for x in k])
            spots[coin] = (float(k[-1][4]), "binance_1m_close")
        except Exception as e:
            print("binance fail", coin, e)
            try:
                tk = P.http(f"{P.COINBASE}/products/{coin.upper()}-USD/ticker"); spots[coin] = (float(tk["price"]), "coinbase_ticker")
            except Exception as e2: print("coinbase fail", e2)
    mk = []
    for s in SERIES[track]:
        try:
            ev = P.http(P.GAMMA + "/events", {"series_slug": s, "closed": "false", "limit": 4, "end_date_min": ts, "order": "endDate", "ascending": "true"})
        except Exception as e: print("gamma fail", s, e); continue
        for e in ev:
            m = e["markets"][0]; toks = json.loads(m.get("clobTokenIds") or "[]")
            if len(toks) != 2: continue
            st = P.pts(m.get("eventStartTime") or e.get("startTime"))
            if st and st - t > dt.timedelta(hours=5): continue
            mk.append((s, e, m, toks))
    toks = [tk for *_, tl in mk for tk in tl]
    books = {}
    for i in range(0, len(toks), 40):
        try:
            for b in P.http(P.CLOB + "/books", body=[{"token_id": x} for x in toks[i:i + 40]]): books[b["asset_id"]] = b
        except Exception as e: print("books fail", e)
    for s, e, m, (up, dn) in mk:
        coin = {"solana": "sol"}.get(s.split("-")[0], s.split("-")[0]); sp = spots.get(coin, (None, None))
        u = side(books.get(up, {})); d = side(books.get(dn, {}))
        fee = (m.get("feeSchedule") or {}).get("rate")
        rows.append((ts, track, s, e["slug"], m["conditionId"], m.get("eventStartTime"), e["endDate"], up, dn, *u, *d,
                     (e.get("eventMetadata") or {}).get("priceToBeat"), sp[0], sp[1], fee, m.get("resolutionSource") or e.get("resolutionSource")))
    c.executemany("insert into snaps values(" + ",".join("?" * 26) + ")", rows); c.commit()
    # resolutions of recently closed markets
    for s in SERIES[track]:
        try:
            ev = P.http(P.GAMMA + "/events", {"series_slug": s, "closed": "true", "limit": 20, "order": "endDate", "ascending": "false",
                                              "end_date_min": P.iso(t - dt.timedelta(hours=8))})
        except Exception as e: print("gamma res fail", e); continue
        for e in ev:
            m = e["markets"][0]; op = json.loads(m.get("outcomePrices") or "[]")
            if len(op) == 2 and op[0] in ("0", "1"):
                md = e.get("eventMetadata") or {}
                c.execute("insert or replace into resolutions values(?,?,?,?,?,?,?,?)", (e["slug"], s, m["conditionId"], m.get("eventStartTime"), e["endDate"],
                          int(op[0] == "1"), md.get("priceToBeat"), md.get("finalPrice")))
    c.commit()
    print(ts, "track", track, "markets", len(rows), "books", len(books), "spots", {k: v[0] for k, v in spots.items()})
if __name__ == "__main__":
    main(int(sys.argv[1]))
