"""Point-in-time logger: Polymarket daily temperature markets (Gamma listing + CLOB books, read-only) + model probability.
Writes data/snapshots/YYYY-MM-DD.jsonl (UTC date of snapshot), data/events.jsonl (rules/station, once per event),
data/resolutions.jsonl (winning bracket once an event is closed + our own METAR check)."""
import json, os, sys, datetime as dt, traceback
import pmw_common as C, model

SNAPDIR = os.path.join(C.DATA, "snapshots"); os.makedirs(SNAPDIR, exist_ok=True)
EVF = os.path.join(C.DATA, "events.jsonl"); RESF = os.path.join(C.DATA, "resolutions.jsonl")

def open_events():
    evs, off = [], 0
    while off < 1000:
        page = C.http(C.GAMMA + "/events", {"tag_slug": "daily-temperature", "closed": "false", "limit": 100, "offset": off})
        evs += page
        if len(page) < 100: break
        off += 100
    return evs

def books(token_ids):
    out = {}
    for i in range(0, len(token_ids), 100):
        chunk = token_ids[i:i + 100]
        try:
            r = C.http(C.CLOB + "/books", body=[{"token_id": t} for t in chunk])
        except Exception as e:
            print("books batch failed", e, file=sys.stderr); continue
        for b in r or []:
            bids = sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), reverse=True)
            asks = sorted((float(x["price"]), float(x["size"])) for x in b.get("asks", []))
            out[b["asset_id"]] = {"bids": bids[:10], "asks": asks[:10], "book_ts": b.get("timestamp")}
    return out

def main():
    t = C.now_utc(); ts = C.iso(t)
    evs = open_events()
    known = {r["event_id"] for r in C.read_jsonl(EVF)}
    rows, meta_new, tokens = [], [], []
    parsed = []
    for e in evs:
        pe = C.parse_event(e)
        if not pe or not pe["date"]: continue
        if e.get("closed"): continue
        parsed.append((e, pe))
        if pe["event_id"] not in known:
            meta_new.append(dict(pe, description=(e.get("description") or "")[:6000], resolution_source=e.get("resolutionSource"),
                                 neg_risk=e.get("negRisk"), first_seen=ts, n_brackets=len(e.get("markets", []))))
        for m in e.get("markets", []):
            try: tokens.append(json.loads(m["clobTokenIds"])[0])
            except Exception: pass
    bk = books(tokens)
    stations = sorted({pe["station"] for _, pe in parsed if pe["station"] and pe["source"] == "metar"})
    obs = {}
    try: obs = C.metar_obs(stations, hours=40, cache_s=600)
    except Exception as ex: print("metar failed", ex, file=sys.stderr)
    ens = {}
    for e, pe in parsed:
        mk = sorted(e.get("markets", []), key=lambda m: int(m.get("groupItemThreshold") or 0))
        brs = [C.parse_bracket(m.get("groupItemTitle") or "") for m in mk]
        unit = next((b["unit"] for b in brs if b), None)
        probs, info = None, {}
        if pe["station"] and pe["source"] == "metar" and unit:
            try:
                st = C.station_info(pe["station"])
                if pe["station"] not in ens: ens[pe["station"]] = model.ensemble(pe["station"], st)
                times, M = ens[pe["station"]]
                ds, de = model.local_day_bounds(pe["date"], st["tz"])
                probs, info = model.bracket_probs(pe["kind"], unit, brs, t, ds, de, times, M, obs.get(pe["station"], []), station=pe["station"])
                info.update({"day_start": C.iso(ds), "day_end": C.iso(de), "hours_to_day_end": round((de - t).total_seconds() / 3600, 2)})
            except Exception as ex:
                info = {"model_error": repr(ex)[:200]}
        for j, m in enumerate(mk):
            try: yes = json.loads(m["clobTokenIds"])[0]
            except Exception: continue
            b = bk.get(yes, {})
            bb = b["bids"][0][0] if b.get("bids") else None; ba = b["asks"][0][0] if b.get("asks") else None
            rows.append({"ts": ts, "event_id": pe["event_id"], "slug": pe["slug"], "city": pe["city"], "kind": pe["kind"], "date": pe["date"],
                         "station": pe["station"], "source": pe["source"], "rule": pe["rule"], "market_id": m.get("id"), "token": yes,
                         "bracket": m.get("groupItemTitle"), "br": brs[j], "unit": unit,
                         "bid": bb, "ask": ba, "mid": round((bb + ba) / 2, 4) if bb is not None and ba is not None else None,
                         "spread": round(ba - bb, 4) if bb is not None and ba is not None else None,
                         "ask_depth": b.get("asks", [])[:5], "bid_depth": b.get("bids", [])[:5],
                         "g_bid": m.get("bestBid"), "g_ask": m.get("bestAsk"), "last": m.get("lastTradePrice"),
                         "liq": m.get("liquidityNum"), "vol": m.get("volumeNum"), "vol24": m.get("volume24hr"),
                         "accepting": m.get("acceptingOrders"), "fee": m.get("feeSchedule"), "fee_type": m.get("feeType"),
                         "p_model": round(probs[j], 4) if probs and probs[j] is not None else None,
                         "model_info": info if j == 0 else None})
    fn = os.path.join(SNAPDIR, t.strftime("%Y-%m-%d") + ".jsonl")
    C.append_jsonl(fn, rows)
    if meta_new: C.append_jsonl(EVF, meta_new)
    resolve()
    print(f"{ts} snapshot rows={len(rows)} events={len(parsed)} stations={len(stations)} new_events={len(meta_new)}")

def resolve():
    """For every logged event whose local date has passed and that is not yet resolved, ask Gamma once (cached 1h)."""
    done = {r["event_id"] for r in C.read_jsonl(RESF)}
    today = C.now_utc().date()
    todo = [r for r in C.read_jsonl(EVF) if r["event_id"] not in done and r["date"] and dt.date.fromisoformat(r["date"]) < today]
    out = []
    for r in todo[:200]:
        try: e = C.http(C.GAMMA + "/events/" + str(r["event_id"]), cache_s=3600)
        except Exception: continue
        if not e.get("closed"): continue
        win = [m for m in e.get("markets", []) if (json.loads(m.get("outcomePrices") or "[]") or ["0"])[0] in ("1", "1.0")]
        if len(win) != 1: continue
        out.append({"event_id": r["event_id"], "slug": r["slug"], "date": r["date"], "station": r["station"], "kind": r["kind"],
                    "winner_bracket": win[0]["groupItemTitle"], "winner_market_id": win[0]["id"],
                    "winner_token": json.loads(win[0]["clobTokenIds"])[0], "resolved_seen": C.iso(C.now_utc())})
    if out: C.append_jsonl(RESF, out)

if __name__ == "__main__":
    main()
