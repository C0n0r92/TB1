"""Track 3 backtest data: closed SOL 5m/15m Up-or-Down markets (Gamma) + Up-token minute price history (CLOB) + Binance 1m SOL candles. READ-ONLY."""
import sys, json, os, datetime as dt
sys.path.insert(0, "/workspace/polymarket-lab/scripts")
import pmlib as P
OUT = f"{P.DATA}/bt3"; os.makedirs(OUT, exist_ok=True)
DAYS = {"sol-up-or-down-5m": 4, "sol-up-or-down-15m": 7}
def main():
    t = P.now(); mk = []
    for s, d in DAYS.items():
        off = 0
        while True:
            ev = P.http(P.GAMMA + "/events", {"series_slug": s, "closed": "true", "limit": 100, "offset": off, "order": "endDate", "ascending": "false",
                                              "end_date_min": P.iso(t - dt.timedelta(days=d)), "end_date_max": P.iso(t)})
            for e in ev:
                m = e["markets"][0]; op = json.loads(m.get("outcomePrices") or "[]"); tk = json.loads(m.get("clobTokenIds") or "[]")
                if len(op) == 2 and op[0] in ("0", "1") and len(tk) == 2:
                    mk.append({"series": s, "slug": e["slug"], "start": m.get("eventStartTime"), "end": e["endDate"], "up_won": int(op[0] == "1"),
                               "meta": e.get("eventMetadata"), "up_tok": tk[0], "twap": "TWAP" in (m.get("description") or ""), "fee": m.get("feeSchedule"), "vol": m.get("volumeNum")})
            if len(ev) < 100: break
            off += 100
        print(s, len([x for x in mk if x["series"] == s]), flush=True)
    done = {json.loads(l)["slug"] for l in open(f"{OUT}/markets.jsonl")} if os.path.exists(f"{OUT}/markets.jsonl") else set()
    for i, x in enumerate(mk):
        if x["slug"] in done: continue
        st = int(P.pts(x["start"]).timestamp()); en = int(P.pts(x["end"]).timestamp())
        try: h = P.http(P.CLOB + "/prices-history", {"market": x["up_tok"], "startTs": st - 120, "endTs": en, "fidelity": 1}, gap=0.25)["history"]
        except Exception as e: print("ph fail", x["slug"], e); h = None
        x["hist"] = h; P.append_jsonl(f"{OUT}/markets.jsonl", [x])
        if i % 200 == 0: print(i, len(mk), flush=True)
    # candles
    st = int((t - dt.timedelta(days=8)).timestamp()) * 1000; rows = []
    while st < t.timestamp() * 1000:
        k = P.http(P.BINANCE + "/klines", {"symbol": "SOLUSDT", "interval": "1m", "startTime": st, "limit": 1000})
        if not k: break
        rows += [[int(r[0]) // 1000, *map(float, r[1:6])] for r in k]; st = k[-1][0] + 60000
    json.dump(rows, open(f"{OUT}/sol_1m.json", "w")); print("candles", len(rows))
if __name__ == "__main__": main()
