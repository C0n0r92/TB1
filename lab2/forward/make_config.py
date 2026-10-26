"""One-shot: freeze the forward config (refuses to overwrite). PAPER ONLY."""
import json, hashlib, os, sys, datetime as dt
F = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(F, "fvg_trend_config.json")
if os.path.exists(P): sys.exit("config already frozen: " + P)
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
params = json.load(open(os.path.join(F, "..", "results", "smc_params_train_a.json")))
now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
cfg = dict(
    name="maj_1h FVG retest, trend filter on, regime gate = trending (paper forward test)",
    source_rules="results/smc_rules.md (written before any test, 2026-10-24 ~00:40Z)",
    setup="FVG", timeframe="1h", trend_filter=True,
    R=params["maj_1h|FVG|trend=on"], R_source="results/smc_params_train_a.json key maj_1h|FVG|trend=on (picked on train 2025-09-20..2026-08-15 from {1.5,2,3})",
    majors="SOL JUP JTO BONK WIF PYTH RAY W ORCA RENDER PENGU TRUMP BOME".split(),
    cost_per_side=0.003, expire_bars=100, timeout_bars=48, min_zone_atr=0.25, stop_buffer_atr=0.25,
    min_risk="4 x cost_per_side (= 2 x round-trip)", max_risk=0.10, atr="ATR14 simple mean of TR", min_index=200,
    ema=dict(fast=50, slow=200, method="pandas ewm span adjust=False on 1h closes, series starting at cached history start"),
    regime_gate=dict(label="trending", module="forward/frozen/regime.py (copy of src/regime.py)",
                     params=dict(CRASH_RET=-0.08, HV_PCT=0.80, TREND_K=1.0, PCT_WIN=540),
                     inputs="SOL+BTC Binance 1h -> 4h, closed 4h bars only, tag at signal-bar close; both directions of 'trending' allowed (as in backtest)"),
    entry="next bar open after the retest bar", exits="stop first, then target; gap through stop fills at open; 48-bar timeout at close",
    one_position_per_token=True,
    data="data-api.binance.vision /api/v3/klines SYMUSDT 1h, closed bars only",
    start_time=now.isoformat().replace("+00:00", "Z"),
    start_rule="only signals whose retest bar CLOSED strictly after start_time count; nothing before is forward",
    code_hashes={k: sha(os.path.join(F, "frozen", k)) for k in ("smc.py", "regime.py", "data.py")},
    backtest_ref=dict(test_all=dict(n=340, mean=0.0006), test_trending=dict(n=71, mean=0.0163), train_trending=dict(n=138, mean=-0.0051),
                      note="trending gate was NOT selected by train (train trending mean < 0); this is a forward check of a test-window observation"),
)
body = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
cfg["config_sha256"] = hashlib.sha256(body.encode()).hexdigest()
cfg["hash_note"] = "sha256 of json.dumps(config without config_sha256/hash_note, sort_keys=True, separators=(',',':'))"
json.dump(cfg, open(P, "w"), indent=1); os.chmod(P, 0o444); print(cfg["config_sha256"], cfg["start_time"])
