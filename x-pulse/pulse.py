#!/usr/bin/env python3
"""Pulse: X research helper for runner-radar coins. Stdlib only. Makes NO network/X calls.

  python3 pulse.py gate            # lock + budget check -> prints mode: full | counts_only | skip
  python3 pulse.py prep            # builds coin list + batched queries -> raw/<run_ts>/plan.json
  python3 pulse.py merge <run_ts>  # parses raw/<run_ts>/*.json -> latest.json, summary.md, history.jsonl,
                                   #   budget.jsonl, /workspace/x-intel/{hot.json,rugs.json,callers.csv,NOTES.md}
  python3 pulse.py unlock          # remove .lock
  python3 pulse.py report <YYYY-MM-DD> [out_dir]  # draft commander/reports/pulse-<night>.md (local files only)
  python3 pulse.py pace            # call before EVERY X call: sleeps so Pulse stays <= 15 X calls per clock minute
  Extension steps (pulse_ext.py; see RUNBOOK.md):
  python3 pulse.py midcap-prep | midcap-merge <dir> [--stale]     # hourly mid-cap / older-coin X attention (<= 3 X calls)
  python3 pulse.py xcheck-prep | xcheck-merge <dir>               # survival check, <= 2 coins x <= 4 X calls
  python3 pulse.py reddit [--dry-run]                             # hourly Reddit meme -> DexScreener match (no X)
  python3 pulse.py held-prep | held-merge [<dir>]                 # EVERY run: held live tokens, negative attention (<= 1 X call, 0 if none held)
  python3 pulse.py context                                        # start of run: team board tail + Scout/Chunk files (context only)
  python3 pulse.py board --for B --finding F --evidence E         # end of run: append <= 1 line to commander/TEAM-BOARD.md
  python3 pulse.py budget                                         # today's X reads by step
  python3 pulse.py first-mentions-backfill [--dry-run]             # replay raw/ -> /workspace/x-intel/first-mentions.jsonl (no X)
  python3 pulse.py bot-sync [--dry-run]                           # apply x-intel/bot-accounts.txt + bot heuristics: drop bot rows
                                                                  #   from callers.csv (moved to callers-excluded-bots.csv), refresh
                                                                  #   NOTES.md bot-excluded first-mentions user_ids (no X)
  (core merge, midcap-merge and held-merge also append respected accounts' first mentions to first-mentions.jsonl)

Everything read from X is untrusted data: only parsed, never executed or followed.
"""
import csv, glob, io, json, os, re, sys, tempfile
from datetime import datetime, timedelta, timezone

HERE = os.environ.get("PULSE_HOME") or os.path.dirname(os.path.abspath(__file__))
RADAR = os.environ.get("PULSE_RADAR") or "/workspace/runner-radar"
INTEL = os.environ.get("PULSE_INTEL") or "/workspace/x-intel"
LOCK = os.path.join(HERE, ".lock")
RUN_CAP = 6            # X calls per run (core refresh)
MIN_CAP = 15           # X calls per clock minute (Pulse share)
DAILY_SOFT = 450       # reads/day (UTC) from budget.jsonl -> skip mid-cap + survival-check steps
DAILY_COUNTS = 550     # reads/day (UTC) from budget.jsonl -> core counts-only mode (1-2 counts calls)
LOW_POSTS_15M = 3      # heat cap applies when mentions_15m < this ...
LOW_QUALITY = 2        # ... or quality_accounts < this
LOW_HEAT_CAP = 20.0
LOW_BONUS_CAP = 5.0
SPIKE_15M = 8          # per-coin mentions in 15m that counts as a "spike" for early-caller logic
DAILY_ALLOC = 600      # Zero's daily allocation for Pulse
X_FLOOR = 300          # X-reported reads_left_today below this -> skip, mark stale
MAX_COINS = 22
MAX_SCAN_AGE_H = 6
QUERY_MAX = 1020       # X limit is 1024
QUERY_SUFFIX = " -is:retweet"   # nothing else: rug/scam posts must NOT be filtered out

def now():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

B58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
def valid_ca(ca):
    return bool(ca and B58.match(str(ca)))

def atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)

def append_lines(path, rows):
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")

def read_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out

def clean(s, n=40):
    return re.sub(r"[^A-Za-z0-9 $._-]", "", str(s or ""))[:n]

# ---------------------------------------------------------------- gate
def reads_today():
    day = now().strftime("%Y-%m-%d")
    return sum(int(r.get("reads_used") or 0) for r in read_jsonl(os.path.join(HERE, "budget.jsonl"))
               if str(r.get("ts", "")).startswith(day))

def last_reported_left():
    rows = [r for r in read_jsonl(os.path.join(HERE, "budget.jsonl")) if r.get("reads_left_today") is not None]
    if not rows:
        return None
    r = rows[-1]
    # only trust it if from today (UTC)
    return r["reads_left_today"] if str(r.get("ts", "")).startswith(now().strftime("%Y-%m-%d")) else None

def cmd_gate():
    if os.path.exists(LOCK):
        t = parse_ts(open(LOCK).read().strip())
        if t and now() - t < timedelta(minutes=15):
            print(json.dumps({"mode": "skip", "reason": f"lock held since {iso(t)}"})); return
        print(f"# stale lock ({open(LOCK).read().strip()}), taking over", file=sys.stderr)
    atomic_write(LOCK, iso(now()) + "\n")
    used, left = reads_today(), last_reported_left()
    if left is not None and left < X_FLOOR:
        mode, why = "skip", f"X reported reads_left_today={left} < {X_FLOOR}: no X calls, mark stale"
    elif used >= DAILY_COUNTS:
        mode, why = "counts_only", f"{used} reads today >= {DAILY_COUNTS}: max 2 counts calls"
    else:
        mode, why = "full", f"{used} reads today; per-run cap {RUN_CAP} calls, <= {MIN_CAP}/min"
    out = {"mode": mode, "reason": why, "reads_today": used, "last_reported_left": left, "core_cap": RUN_CAP if mode == "full" else (2 if mode == "counts_only" else 0)}
    try:
        import pulse_ext
        out.update(pulse_ext.gate_extras(mode, used))
        if mode == "counts_only" and out.get("held_due"):
            out["core_cap"] = 1      # >= DAILY_COUNTS: 1 counts call + 1 held-watch search (live money), still <= 2
    except Exception as e:   # extension problems must never block the core refresh
        out.update({"midcap_due": False, "xcheck_due": 0, "reddit_due": False, "extras_error": str(e)[:200]})
    print(json.dumps(out))

def cmd_pace():
    """Before every X call. Keeps Pulse <= MIN_CAP X calls per clock minute (all steps share it)."""
    import time
    path = os.path.join(HERE, ".pace")
    while True:
        minute = now().strftime("%Y-%m-%dT%H:%M")
        stamps = [l.strip() for l in open(path)] if os.path.exists(path) else []
        stamps = [x for x in stamps if x.startswith(minute)]
        if len(stamps) < MIN_CAP:
            stamps.append(iso(now()))
            atomic_write(path, "\n".join(stamps) + "\n")
            print(json.dumps({"ok": True, "calls_this_minute": len(stamps), "cap": MIN_CAP})); return
        time.sleep(61 - now().second)

def cmd_unlock():
    if os.path.exists(LOCK):
        os.remove(LOCK)
    print("unlocked")

# ---------------------------------------------------------------- prep
def radar_first_ts():
    sig = read_jsonl(os.path.join(RADAR, "signals.jsonl"))
    scn = read_jsonl(os.path.join(RADAR, "scanned.jsonl"))
    fsig, fseen = {}, {}
    for r in sorted(sig, key=lambda r: r.get("ts") or ""):
        if r.get("token"): fsig.setdefault(r["token"], r.get("ts"))
    for r in sorted(scn + sig, key=lambda r: r.get("ts") or ""):
        if r.get("token"): fseen.setdefault(r["token"], r.get("ts"))
    return fsig, fseen

def load_coins():
    t0 = now()
    sig = read_jsonl(os.path.join(RADAR, "signals.jsonl"))
    scn = read_jsonl(os.path.join(RADAR, "scanned.jsonl"))
    coins = {}
    first_signal, first_seen = {}, {}
    for r in sorted(scn + sig, key=lambda r: r.get("ts") or ""):
        if r.get("token"):
            first_seen.setdefault(r["token"], r.get("ts"))
    for r in sig:
        tok = r.get("token")
        if not tok:
            continue
        first_signal.setdefault(tok, r.get("ts"))
        c = coins.setdefault(tok, {"contract_address": tok, "is_signal": True})
        c.update(ticker=clean(r.get("symbol"), 20), name=clean(r.get("name")), last_ts=r.get("ts"),
                 score=r.get("score"), mcap=r.get("mcap"), rejects=r.get("rejects") or [])
        c["is_signal"] = True
    for r in scn:
        tok = r.get("token")
        if not tok:
            continue
        c = coins.setdefault(tok, {"contract_address": tok, "is_signal": False})
        if not c.get("last_ts") or (r.get("ts") or "") >= c["last_ts"]:
            c.update(ticker=clean(r.get("symbol"), 20), name=clean(r.get("name")), last_ts=r.get("ts"),
                     score=r.get("score") if not c.get("is_signal") else c.get("score"), mcap=r.get("mcap"),
                     rejects=r.get("rejects") or [])
    out = []
    for c in coins.values():
        t = parse_ts(c.get("last_ts"))
        if not c["is_signal"] and (not t or t0 - t > timedelta(hours=MAX_SCAN_AGE_H)):
            continue
        c["first_signal_ts"] = first_signal.get(c["contract_address"])
        c["first_radar_ts"] = first_seen.get(c["contract_address"])
        out.append(c)
    out.sort(key=lambda c: (not c["is_signal"], -(parse_ts(c["last_ts"]) or t0).timestamp() // 600,
                            -(c.get("score") or 0)))
    return out[:MAX_COINS]

def build_batches(coins):
    batches, cur = [], []
    def q(cas):
        return "(" + " OR ".join(cas) + ")" + QUERY_SUFFIX
    for c in coins:
        if cur and len(q(cur + [c["contract_address"]])) > QUERY_MAX:
            batches.append(cur); cur = []
        cur.append(c["contract_address"])
    if cur:
        batches.append(cur)
    return [{"id": f"b{i+1}", "cas": b, "query": q(b)} for i, b in enumerate(batches)]

THEME_QUERIES = [
    {"id": "t1", "theme": "solana memecoin / pump.fun chatter",
     "query": '(pump.fun OR pumpfun OR "solana memecoin" OR "sol memecoin" OR pumpswap OR letsbonk) -is:retweet'},
]

def cmd_prep():
    run_ts = now().strftime("%Y%m%dT%H%M%SZ")
    coins = load_coins()
    batches = build_batches(coins)
    start = iso(now() - timedelta(minutes=60))
    plan = {"run_ts": run_ts, "start_time": start, "coins": coins, "batches": batches, "themes": THEME_QUERIES,
            "calls": [], "fields": {"post.fields": "created_at,public_metrics,author_id,lang,conversation_id",
                                     "user.fields": "created_at,description,public_metrics,verified",
                                     "expansions": "author_id", "max_results": 25}}
    for b in batches:
        plan["calls"].append({"file": f"counts_{b['id']}.json", "tool": "get_posts_counts_recent",
                              "args": {"query": b["query"], "granularity": "minute", "start_time": start}})
    for b in batches:
        plan["calls"].append({"file": f"search_{b['id']}.json", "tool": "search_posts_all",
                              "args": {"query": b["query"], "start_time": start, "max_results": 25,
                                       "sort_order": "recency", **{k: v for k, v in plan["fields"].items() if k != "max_results"}}})
    for t in THEME_QUERIES:
        plan["calls"].append({"file": f"theme_{t['id']}.json", "tool": "get_posts_counts_recent",
                              "args": {"query": t["query"], "granularity": "minute", "start_time": start}})
    d = os.path.join(HERE, "raw", run_ts)
    os.makedirs(d, exist_ok=True)
    atomic_write(os.path.join(d, "plan.json"), json.dumps(plan, indent=1))
    print(json.dumps({"run_ts": run_ts, "coins": len(coins), "planned_calls": len(plan["calls"]),
                      "raw_dir": d}, indent=1))
    for c in plan["calls"]:
        print(c["file"], c["tool"], len(c["args"]["query"]), "chars")


# ---------------------------------------------------------------- merge: parsing
READS_RE = re.compile(r"X reads left for this user: (\d+) of (\d+) this minute.*?, (\d+) of (\d+) today")
PROMO_RE = re.compile(r"\b(dm (me )?(for|to)|vip|telegram|tg group|join my|alpha group|alpha telegram|"
                      r"paid promo|promo(tion)?s? (available|open)|for promo|shill|collab|marketing|"
                      r"next gem|next early call|get early entries|signals? group|tg|private tg|copy ?trad\w*|link in bio)\b", re.I)
BRAG_RE = re.compile(r"(\d+(\.\d+)?\s?x\b.*(call|profit|gain|pump|hit|up)|\bhit \d+(\.\d+)?x|\b\d+(\.\d+)?x (on|from) my|"
                     r"(profit|gain).*\d+(\.\d+)?x|called (it )?early|from my .* call)", re.I)
RUG_RE = {
    "honeypot": re.compile(r"\b(honey ?pot|can'?t sell|cannot sell|unable to sell|sell (is )?disabled)\b", re.I),
    "dev_dump": re.compile(r"\b(dev (dumped|sold|dumping|rugged)|dev wallet (dumped|sold)|insiders? (dumped|sold))\b", re.I),
    "rug": re.compile(r"\b(rug(ged|pull(ed)?)?|rugging|pulled (the )?liq(uidity)?|liquidity (pulled|removed))\b", re.I),
    "scam": re.compile(r"\b(scam(mer|med)?|fraud|bundled (scam|rug))\b", re.I),
}
RUG_NEG = re.compile(r"\b(not a rug|no rug|anti[- ]?rug|rug[- ]?(proof|check(ed)?|safe)|unruggable|can'?t rug|won'?t rug|"
                     r"rugcheck|no scam|not a scam)\b", re.I)

def load_raw(path):
    t = open(path).read()
    s = t.find('{"data"')
    if s < 0:
        s = t.find("{")
    obj = {}
    if s >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(t[s:])
        except json.JSONDecodeError:
            obj = {}
    m = READS_RE.search(t)
    reads = {"min_left": int(m.group(1)), "min_cap": int(m.group(2)), "day_left": int(m.group(3)),
             "day_cap": int(m.group(4))} if m else None
    return obj, reads

def norm_text(t, cas, tickers):
    t = t.lower()
    for ca in cas:
        t = t.replace(ca.lower(), " ")
    t = re.sub(r"https?://\S+|@\w+|\$\w+|[0-9][0-9.,kmx$%]*", " ", t)
    for tk in tickers:
        if tk:
            t = re.sub(r"\b" + re.escape(tk.lower()) + r"\b", " ", t)
    return set(w for w in re.findall(r"[a-z']{3,}", t))

def jacc(a, b):
    return len(a & b) / max(1, len(a | b))

# ---------------------------------------------------------------- merge: scoring
def author_profile(u, run_dt):
    pm = u.get("public_metrics") or {}
    cr = parse_ts(u.get("created_at"))
    age = (run_dt - cr).days if cr else None
    return {"id": u.get("id"), "handle": u.get("username"), "followers": pm.get("followers_count"),
            "following": pm.get("following_count"), "tweets": pm.get("tweet_count"),
            "created_at": u.get("created_at"), "age_days": age, "verified": bool(u.get("verified")),
            "promo_bio": bool(PROMO_RE.search(u.get("description") or "")),
            "name": u.get("name"), "bot_reason": bot_hint(u.get("id"), u.get("username"), u.get("name"), u.get("description"))}

# ---------------------------------------------------------------- bot / tracker / alert account exclusion (no X calls)
BOT_FILE = os.path.join(INTEL, "bot-accounts.txt")
BOT_HANDLE_RE = re.compile(r"(^bot|_bot|bot$|bot_|bot\d|alert|tracker|radar|scanner|scan$|scan_|sniper|snipr|monitor|"
                           r"newpair|new_pair|detector|notifier|signal|watcher|listing)")
BOT_CAMEL_RE = re.compile(r"Bot(?![a-z])")
BOT_NAME_RE = re.compile(r"\b(bots?|alerts?|tracker|radar|scanner|sniper|monitor|new ?pairs?|detector|notifier|signals?|"
                         r"watcher|listing alerts?|feed)\b", re.I)
BOT_BIO_RE = re.compile(r"(\bautomated\b|\bauto[- ]?(post|posts|posting|posted|generated)\b|\bi'?m an? bot\b|"
                        r"\b(a|this|signal|signals|tracking|tracker|alert|alerts|telegram|tg|trading) bot\b|\bbot by @|"
                        r"\bnot a human\b|机器人|real[- ]?time\s+(?:[\w$-]+\s+){0,3}(alerts|signals|insights|tracking|scans?|notifications)\b)", re.I)
# templated machine posts: "new token/CA detected", "DEX paid", "N smart wallets just bought", "Trending ... Alert", ...
BOT_POST_RE = re.compile(r"(new token\b|token detected|\bca detected|new pairs?\b|\bdex(screener)? paid\b|paid dexscreener|"
                         r"detect paid|dexscreener (push|update)|paid for their dexscreener|new listing\b|"
                         r"smart wallets? just bought|trending [\w ]{0,30}alert|scam alert -|\bjust (launched|migrated)\b|"
                         r"\bmigrat(ed|ion) alert)", re.I)
BOT_CADENCE_PER_DAY = 50     # >= this many posts/day lifetime + >=1 templated machine post in the run -> bot
BOT_TEMPLATE_POSTS = 2       # or >= this many templated machine posts by one author in one run's sample
_DENY = {"mtime": None, "ids": set(), "handles": set(), "allow_ids": set(), "allow_handles": set()}

def bot_denylist():
    """bot-accounts.txt: one account per line, '<handle> [user_id]  # note'. A line starting with '!' = allowlist (never a bot,
    overrides the heuristics). Re-read whenever the file changes."""
    try:
        mt = os.path.getmtime(BOT_FILE)
    except OSError:
        mt = 0
    if _DENY["mtime"] != mt:
        d = {"mtime": mt, "ids": set(), "handles": set(), "allow_ids": set(), "allow_handles": set()}
        if mt:
            for line in open(BOT_FILE, errors="ignore"):
                line = line.split("#", 1)[0].strip()
                if not line: continue
                allow = line.startswith("!")
                for tok in line.lstrip("!").replace(",", " ").split():
                    tok = tok.strip().lstrip("@")
                    if not tok: continue
                    if tok.isdigit(): d["allow_ids" if allow else "ids"].add(tok)
                    else: d["allow_handles" if allow else "handles"].add(tok.lower())
        _DENY.update(d)
    return _DENY

def bot_allowed(uid, handle):
    d = bot_denylist()
    return str(uid or "") in d["allow_ids"] or (handle or "").lower() in d["allow_handles"]

def bot_denied(uid, handle):
    d = bot_denylist()
    if bot_allowed(uid, handle): return False
    return str(uid or "") in d["ids"] or (handle or "").lower() in d["handles"]

def bot_hint(uid, handle, name=None, bio=None):
    """Static bot reason from denylist / handle / display name / bio ('' = none). Post cadence is checked in classify_authors."""
    if bot_allowed(uid, handle): return ""
    if bot_denied(uid, handle): return "denylist"
    h = handle or ""
    if BOT_CAMEL_RE.search(h) or BOT_HANDLE_RE.search(h.lower()): return "handle"
    if name and BOT_NAME_RE.search(name): return "name"
    if bio and BOT_BIO_RE.search(bio): return "bio"
    return ""

def classify_authors(posts, authors, run_dt):
    """flags per author id. quality = no flags.
    new (<90d), low_followers (<100), promo (VIP/TG/DM-for-promo in bio or posts), template (near-duplicate text
    across different authors), ring (>=3 authors in one template cluster), self_template (same text template reused
    by one author across different coins = caller-bot), brag (post-pump 'hit Nx / Nx from my call' posts),
    bot (automated alert/tracker account: bot-accounts.txt denylist, handle/name/bio heuristics, or templated machine posts
    'new token / DEX paid / smart wallets just bought' with high posting cadence; reason in authors[id]['bot_reason'])."""
    sigs = [(p["author_id"], p["_norm"], tuple(p.get("_coins") or ())) for p in posts if len(p["_norm"]) >= 5]
    parent = {}
    def find(a):
        while parent.setdefault(a, a) != a:
            a = parent[a]
        return a
    template_authors, self_tpl = set(), set()
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            sim = jacc(sigs[i][1], sigs[j][1])
            if sigs[i][0] != sigs[j][0] and sim >= 0.6:
                template_authors.update([sigs[i][0], sigs[j][0]])
                parent[find(sigs[i][0])] = find(sigs[j][0])
            elif sigs[i][0] == sigs[j][0] and sigs[i][2] != sigs[j][2] and sim >= 0.5:
                self_tpl.add(sigs[i][0])
    # paraphrased shill: different authors, same coin, sharing >=2 exact figures ("67K -> 275K", "11.9X")
    nums = [(p["author_id"], tuple(p.get("_coins") or ()), set(re.findall(r"\$?\d+(?:\.\d+)?\s?[kKmMxX]\b", p["text"])))
            for p in posts]
    nums = [(a, c, {n.lower().replace("$", "").replace(" ", "") for n in ns}) for a, c, ns in nums if c and len(ns) >= 2]
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i][0] != nums[j][0] and set(nums[i][1]) & set(nums[j][1]) and len(nums[i][2] & nums[j][2]) >= 2:
                template_authors.update([nums[i][0], nums[j][0]])
                parent[find(nums[i][0])] = find(nums[j][0])
    clusters = {}
    for a in template_authors:
        clusters.setdefault(find(a), set()).add(a)
    ring = set().union(*[c for c in clusters.values() if len(c) >= 3]) if clusters else set()
    promo_posts, brag, machine = {}, set(), {}
    for p in posts:
        if BOT_POST_RE.search(p.get("text") or ""):
            machine[p["author_id"]] = machine.get(p["author_id"], 0) + 1
        if PROMO_RE.search(p["text"]):
            promo_posts[p["author_id"]] = promo_posts.get(p["author_id"], 0) + 1
        if p.get("_brag"):
            brag.add(p["author_id"])
    flags = {}
    for aid, a in authors.items():
        f = set()
        if a["age_days"] is None or a["age_days"] < 90: f.add("new")
        if (a["followers"] or 0) < 100: f.add("low_followers")
        if a["promo_bio"] or promo_posts.get(aid): f.add("promo")
        if aid in template_authors: f.add("template")
        if aid in ring: f.add("ring")
        if aid in self_tpl: f.add("self_template")
        if aid in brag: f.add("brag")
        br = a.get("bot_reason")
        if br is None:   # profile built elsewhere
            br = a["bot_reason"] = bot_hint(aid, a.get("handle"), a.get("name"))
        if not br and not bot_allowed(aid, a.get("handle")):
            m = machine.get(aid, 0)
            rate = (a.get("tweets") or 0) / max(1, a.get("age_days") or 1)
            if m >= BOT_TEMPLATE_POSTS: br = f"template_posts:{m}"
            elif m and rate >= BOT_CADENCE_PER_DAY: br = f"cadence:{rate:.0f}/d+template_post"
            if br: a["bot_reason"] = br
        if br: f.add("bot")
        flags[aid] = f
    return flags

def author_weight(f):
    if not f: return 1.0
    if "bot" in f: return 0.05
    if {"promo", "ring"} & f: return 0.05
    if "template" in f: return 0.1
    if "new" in f and "low_followers" in f: return 0.1
    if {"brag", "self_template"} & f: return 0.3
    return 0.4

def is_quality(f):
    return not f

def trend_word(ratio, n):
    if n < 3: return "flat"
    if ratio >= 1.35: return "up"
    if ratio <= 0.7: return "down"
    return "flat"

def counts_series(obj):
    return [(parse_ts(b["start"]), int(b.get("tweet_count") or 0)) for b in obj.get("data") or []]

def window_rates(series, run_dt):
    c15 = sum(n for t, n in series if t and t >= run_dt - timedelta(minutes=15))
    c60 = sum(n for t, n in series if t and t >= run_dt - timedelta(minutes=60))
    prior = c60 - c15
    ratio = (c15 / 15) / max(prior / 45, 1 / 45)
    return c15, c60, ratio

def _core_load(run_ts, stale=False):
    """Parse raw/<run_ts>/ (core step): shared by cmd_merge and the first-mentions backfill. No writes."""
    d = os.path.join(HERE, "raw", run_ts)
    plan = json.load(open(os.path.join(d, "plan.json")))
    run_dt = datetime.strptime(run_ts, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    coins = plan["coins"]
    fsig, fseen = radar_first_ts()   # recomputed at merge time (radar files are append-only)
    for c in coins:
        c["first_signal_ts"] = fsig.get(c["contract_address"])
        c["first_radar_ts"] = fseen.get(c["contract_address"])
    cas = [c["contract_address"] for c in coins]
    tickers = [c.get("ticker") or "" for c in coins]
    reads, posts, users, batch_counts, theme_counts = [], {}, {}, {}, {}
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        name = os.path.basename(f)
        if name == "plan.json": continue
        obj, r = load_raw(f)
        if r: reads.append(r)
        if name.startswith("search_"):
            for u in (obj.get("includes") or {}).get("users") or []:
                users[u["id"]] = u
            for p in obj.get("data") or []:
                posts[p["id"]] = p
        elif name.startswith("counts_"):
            batch_counts[name[7:].split(".")[0]] = counts_series(obj)
        elif name.startswith("theme_"):
            theme_counts[name[6:].split(".")[0]] = counts_series(obj)
    if stale or not reads:
        stale = True
    calls_used = len(reads)
    if reads:
        run_dt = max(run_dt, max(parse_ts(p["created_at"]) for p in posts.values()) if posts else run_dt)
    authors = {aid: author_profile(u, run_dt) for aid, u in users.items()}
    plist = []
    for p in posts.values():
        txt = p.get("text") or ""
        hit = [c for c in coins if c["contract_address"] in txt]
        if not hit:  # fallback: $TICKER only if ticker unique among tracked coins
            for c in coins:
                tk = c.get("ticker") or ""
                if len(tk) >= 3 and tickers.count(tk) == 1 and re.search(r"\$" + re.escape(tk) + r"\b", txt, re.I):
                    hit.append(c)
        p["_coins"] = [c["contract_address"] for c in hit]
        p["_dt"] = parse_ts(p["created_at"])
        p["_norm"] = norm_text(txt, cas, tickers)
        p["_brag"] = bool(BRAG_RE.search(txt))
        p["_url"] = p.get("url") or f"https://x.com/{(users.get(p['author_id']) or {}).get('username','i')}/status/{p['id']}"
        plist.append(p)
    flags = classify_authors(plist, authors, run_dt)
    return dict(d=d, plan=plan, run_dt=run_dt, coins=coins, cas=cas, tickers=tickers, reads=reads, posts=posts, users=users,
                batch_counts=batch_counts, theme_counts=theme_counts, stale=stale, calls_used=calls_used,
                authors=authors, plist=plist, flags=flags)

def cmd_merge(run_ts, stale=False):
    L = _core_load(run_ts, stale)
    d, plan, run_dt, coins, cas, tickers = L["d"], L["plan"], L["run_dt"], L["coins"], L["cas"], L["tickers"]
    reads, posts, users, batch_counts, theme_counts = L["reads"], L["posts"], L["users"], L["batch_counts"], L["theme_counts"]
    stale, calls_used, authors, plist, flags = L["stale"], L["calls_used"], L["authors"], L["plist"], L["flags"]
    oldest = min((p["_dt"] for p in plist), default=run_dt)
    sample_min = max(1.0, (run_dt - oldest).total_seconds() / 60)
    # batch totals from counts
    b60 = sum(window_rates(s, run_dt)[1] for s in batch_counts.values())
    b15 = sum(window_rates(s, run_dt)[0] for s in batch_counts.values())
    sample_cov15 = min(1.0, sample_min / 15)
    prev = {}
    hist_all = [h for h in read_jsonl(os.path.join(HERE, "history.jsonl")) if h.get("run_ts") != iso(run_dt)]
    for h in hist_all:
        prev[h["contract_address"]] = h
    prev_latest = {}
    if os.path.exists(os.path.join(HERE, "latest.json")):
        try:
            prev_latest = {c["contract_address"]: c for c in json.load(open(os.path.join(HERE, "latest.json")))["coins"]}
        except Exception:
            pass
    out, rugs, caller_rows = [], [], []
    total_tagged = sum(1 for p in plist if p["_coins"])
    for c in coins:
        ca = c["contract_address"]
        if stale:
            pc = dict(prev_latest.get(ca) or {})
            out.append({"contract_address": ca, "ticker": c.get("ticker"), "name": c.get("name"),
                        "heat_score": pc.get("heat_score", 0), "trend": pc.get("trend", "flat"),
                        "mentions_15m": pc.get("mentions_15m", 0), "mentions_60m": pc.get("mentions_60m", 0),
                        "distinct_accounts": pc.get("distinct_accounts", 0), "quality_accounts": pc.get("quality_accounts", 0),
                        "notable_early_callers": pc.get("notable_early_callers", []), "confidence": "low",
                        "notes": "STALE: no X reads this run (budget gate). Values carried from last run.",
                        "updated_at": pc.get("updated_at"), "stale": True,
                        "observed_at": pc.get("observed_at") or pc.get("updated_at"),
                        "trend_direction": pc.get("trend_direction") if pc.get("trend_direction") in ("rising", "fading") else "fading"})
            continue
        cp = sorted([p for p in plist if ca in p["_coins"]], key=lambda p: p["_dt"])
        in15 = [p for p in cp if p["_dt"] >= run_dt - timedelta(minutes=15)]
        m15_obs = len(in15)
        m15 = round(m15_obs / sample_cov15) if sample_cov15 < 1 else m15_obs
        share = len(cp) / max(1, total_tagged)
        m60 = max(m15, round(share * b60)) if b60 else m15
        a15 = {p["author_id"] for p in in15}
        aall = {p["author_id"] for p in cp}
        q = [a for a in aall if is_quality(flags.get(a, {"new"}))]
        w15 = sum(author_weight(flags.get(a, {"new"})) for a in a15)
        # non-brag posts count fully; post-hoc "hit 50x" brag posts count 30%
        brag_frac = sum(1 for p in in15 if p["_brag"]) / max(1, len(in15))
        w15 *= (1 - 0.7 * brag_frac)
        # trend: vs previous run if <=90 min old, else within-sample halves
        pv = prev.get(ca)
        pv_dt = parse_ts(pv.get("run_ts")) if pv else None
        if pv and pv_dt and timedelta(0) < run_dt - pv_dt <= timedelta(minutes=90):
            ratio = (m15 + 0.5) / (float(pv.get("mentions_15m") or 0) + 0.5); basis = "vs prev run"
        else:
            half = run_dt - timedelta(minutes=sample_min / 2)
            newer = sum(1 for p in cp if p["_dt"] >= half); older = len(cp) - newer
            ratio = (newer + 0.5) / (older + 0.5); basis = f"within {sample_min:.0f}m sample"
        trend = trend_word(ratio, len(cp) + (int(pv.get("mentions_15m") or 0) if pv else 0)) if (cp or pv) else "flat"
        # trend_direction (Zero's rule): sign of per-coin 15m rate vs prior-45m rate, only when the sample really covers
        # >= 10 min before the 15m window; else sign of mentions_15m vs previous run (<= 90 min old); tie/no data -> fading
        prior_cover = sample_min - 15
        if cp and prior_cover >= 10:
            prior_n = sum(1 for p in cp if p["_dt"] < run_dt - timedelta(minutes=15))
            diff = m15_obs / 15 - prior_n / min(45, prior_cover); dir_basis = f"15m vs prior {min(45, prior_cover):.0f}m"
        elif pv and pv_dt and timedelta(0) < run_dt - pv_dt <= timedelta(minutes=90):
            diff = m15 - float(pv.get("mentions_15m") or 0); dir_basis = "vs prev run"
        else:
            diff = 0; dir_basis = "no prior data"
        direction = "rising" if diff > 0 else "fading"
        base = 70 * (1 - pow(2.718281828, -w15 / 4))
        bonus = max(-15, min(30, (ratio - 1) * 15)) if cp else 0
        nq = len(q)
        low_sample = bool(cp) and (m15 < LOW_POSTS_15M or nq < LOW_QUALITY)
        if low_sample:
            bonus = min(bonus, LOW_BONUS_CAP)
        heat = 0 if not cp else round(max(0, min(100, base + bonus)) * (1 if q else 0.6), 1)
        cap_note = ""
        if low_sample:
            raw_heat = heat
            heat = min(heat, LOW_HEAT_CAP)
            why = " and ".join(x for x in (f"{m15} posts/15m (<{LOW_POSTS_15M})" if m15 < LOW_POSTS_15M else "",
                                           f"{nq} quality accts (<{LOW_QUALITY})" if nq < LOW_QUALITY else "") if x)
            cap_note = f"; LOW-SAMPLE CAP: {why} -> trend bonus <= {LOW_BONUS_CAP:g}, heat <= {LOW_HEAT_CAP:g} (uncapped {raw_heat})"
        conf = "high" if (len(cp) >= 15 and nq >= 5) else "med" if (len(cp) >= 5 and nq >= 2) else "low"
        # notable callers: quality accounts, earliest first
        firsts = {}
        for p in cp:
            firsts.setdefault(p["author_id"], p)
        # "early" = before the coin's first runner-radar signal (or first radar scan if never signalled),
        # or before the first run where this coin spiked (history mentions_15m >= SPIKE_15M)
        sig_ts = parse_ts(c.get("first_signal_ts") or c.get("first_radar_ts"))
        spike = [parse_ts(h["run_ts"]) for h in hist_all if h["contract_address"] == ca and (h.get("mentions_15m") or 0) >= SPIKE_15M]
        if spike and (not sig_ts or min(spike) - timedelta(minutes=15) < sig_ts):
            sig_ts = min(spike) - timedelta(minutes=15)
        notable = []
        for aid, p in sorted(firsts.items(), key=lambda kv: kv[1]["_dt"]):
            if not is_quality(flags.get(aid, {"new"})): continue
            a = authors.get(aid, {})
            notable.append({"handle": a.get("handle"), "user_id": aid, "followers": a.get("followers"),
                            "account_created": (a.get("created_at") or "")[:10], "age_days": a.get("age_days"),
                            "first_post_ts": p["created_at"], "url": p["_url"],
                            "before_signal": bool(sig_ts and p["_dt"] < sig_ts)})
        notable = notable[:5]
        # rug flags
        rflags = {}
        for p in cp:
            if RUG_NEG.search(p["text"]): continue
            for kind, rx in RUG_RE.items():
                if rx.search(p["text"]):
                    rflags.setdefault(kind, []).append(p); break
        rug_note = ""
        for kind, ps in rflags.items():
            accs = {p["author_id"] for p in ps}
            qacc = {a for a in accs if not ({"new", "promo", "ring", "template"} & flags.get(a, {"new"}))}
            if len(qacc) >= 2:
                rugs.append({"contract_address": ca, "ticker": c.get("ticker"), "flag": kind,
                             "distinct_flagging_accounts": len(accs), "quality_flagging_accounts": len(qacc),
                             "first_flag_ts": min(p["created_at"] for p in ps),
                             "evidence": [p["_url"] for p in ps][:6], "observed_at": iso(run_dt), "_dir": True,
                             "confidence": "high" if len(qacc) >= 4 else "med"})
            else:
                rug_note += f" weak {kind} flag: {len(accs)} acct(s), {len(qacc)} aged/non-bot ({ps[0]['_url']})."
        nf = {k: sum(1 for a in aall if k in flags.get(a, set())) for k in ("new", "promo", "template", "ring", "low_followers")}
        notes = (f"{len(cp)} posts/{len(aall)} accts in {sample_min:.0f}m sample; trend {basis} ratio {ratio:.2f}; "
                 f"brag/post-pump share {brag_frac:.0%}; flagged accts: " + ", ".join(f"{k}={v}" for k, v in nf.items() if v)
                 + ("; mentions_60m estimated from batch counts x share" if b60 else "")
                 + (f"; radar rejects: {', '.join(c['rejects'])}" if c.get("rejects") else "") + cap_note + rug_note)
        if not cp:
            notes = "checked: 0 mentions in sample window" + (f"; radar rejects: {', '.join(c['rejects'])}" if c.get("rejects") else "")
        out.append({"contract_address": ca, "ticker": c.get("ticker"), "name": c.get("name"), "heat_score": heat,
                    "trend": trend, "mentions_15m": m15, "mentions_60m": m60, "distinct_accounts": len(aall),
                    "quality_accounts": nq, "notable_early_callers": notable, "confidence": conf,
                    "notes": (notes + f"; direction {direction} ({dir_basis})")[:700], "updated_at": iso(run_dt),
                    "observed_at": iso(run_dt), "trend_direction": direction})
        for r in rugs:
            if r.pop("_dir", None): r["trend"] = direction
        for n in notable:
            caller_rows.append((n, ca, c.get("ticker"), n["before_signal"]))
    out = [c for c in out if valid_ca(c.get("contract_address")) and c.get("observed_at")]
    rugs = [r for r in rugs if valid_ca(r.get("contract_address"))]
    out.sort(key=lambda c: -c["heat_score"])
    # themes
    themes = []
    if b60 or b15:
        _, _, r = window_rates([x for s in batch_counts.values() for x in s], run_dt)
        themes.append({"theme": "tracked radar coins (all CAs combined)", "trend": trend_word(r, b60),
                       "note": f"{b15} posts last 15m, {b60} last 60m (15m-vs-prior-45m ratio {r:.2f})"})
    for t in plan.get("themes", []):
        s = theme_counts.get(t["id"])
        if s:
            c15, c60, r = window_rates(s, run_dt)
            themes.append({"theme": t["theme"], "trend": trend_word(r, c60),
                           "note": f"{c15} posts last 15m, {c60} last 60m (ratio {r:.2f})"})
    promo_share = sum(1 for p in plist if {"promo", "template", "ring"} & flags.get(p["author_id"], set())) / max(1, len(plist))
    brag_share = sum(1 for p in plist if p["_brag"]) / max(1, len(plist))
    if plist:
        themes.append({"theme": "call-group / VIP-TG shill posting", "trend": "flat",
                       "note": f"{promo_share:.0%} of sampled posts from promo/template accounts; {brag_share:.0%} are post-pump 'hit Nx' brags"})
    rl = min((r["day_left"] for r in reads), default=None)
    budget = {"reads_used_this_run": calls_used, "reads_left_today_reported": rl,
              "reads_left_this_minute_reported": reads[-1]["min_left"] if reads else None}
    latest = {"updated_at": iso(now()), "stale": stale, "budget": budget, "coins": out, "themes": themes}
    atomic_write(os.path.join(HERE, "latest.json"), json.dumps(latest, indent=1))
    done = {r.get("run_ts") for r in read_jsonl(os.path.join(HERE, "budget.jsonl")) if r.get("step", "core") == "core"}
    if run_ts in done:
        print(f"# {run_ts} already merged: rewriting latest/summary/intel only, not re-appending history/budget", file=sys.stderr)
    if not stale and run_ts not in done:
        append_lines(os.path.join(HERE, "history.jsonl"), [
            {"run_ts": iso(run_dt), "contract_address": c["contract_address"], "ticker": c["ticker"],
             "heat_score": c["heat_score"], "trend": c["trend"], "mentions_15m": c["mentions_15m"],
             "mentions_60m": c["mentions_60m"], "distinct_accounts": c["distinct_accounts"],
             "quality_accounts": c["quality_accounts"], "confidence": c["confidence"]} for c in out])
    if run_ts not in done: append_lines(os.path.join(HERE, "budget.jsonl"), [{"ts": iso(now()), "run_ts": run_ts, "reads_used": calls_used,
                                                       "reads_left_today": rl, "stale": stale, "step": "core"}])
    write_summary(latest, rugs, sample_min, len(plist))
    write_intel(latest, rugs, caller_rows, stale)
    fm = safe_first_mentions(plist, authors, flags, "core", run_dt,
                             {c["contract_address"]: c.get("ticker") for c in coins}) if not stale else 0
    print(json.dumps({"coins": len(out), "posts": len(plist), "calls": calls_used, "reads_left_today": rl, "first_mentions_new": fm,
                      "rugs": len(rugs), "stale": stale}))

def write_summary(latest, rugs, sample_min, nposts):
    L = [f"# Pulse summary ({latest['updated_at']})", ""]
    b = latest["budget"]
    L.append(f"X calls this run: {b['reads_used_this_run']}; reads left today (X-reported, shared by all bots): {b['reads_left_today_reported']}."
             + (" **STALE: no X reads this run.**" if latest["stale"] else f" Sample: {nposts} posts over last {sample_min:.0f} min."))
    hot = [c for c in latest["coins"] if c["heat_score"] > 0]
    L += ["", "## Heating (top by heat)"]
    for c in hot[:6]:
        L.append(f"- **{c['ticker']}** `{c['contract_address']}` heat {c['heat_score']} ({c['trend']}, {c['confidence']}): "
                 f"{c['mentions_15m']} posts/15m, {c['distinct_accounts']} accts, {c['quality_accounts']} quality")
    cool = [c for c in latest["coins"] if c["trend"] == "down"]
    L += ["", "## Cooling"] + ([f"- {c['ticker']} heat {c['heat_score']}" for c in cool] or ["- none flagged"])
    zero = [f"{c['ticker']} ({c['contract_address'][:6]})" for c in latest["coins"] if c["heat_score"] == 0]
    L += ["", f"Checked, zero mentions in sample: {', '.join(zero) or 'none'}"]
    L += ["", "## Rug / scam flags (>=2 aged non-bot accounts)"] + (
        [f"- {r['ticker']} `{r['contract_address']}` {r['flag']} ({r['quality_flagging_accounts']} accts): {r['evidence'][0]}" for r in rugs]
        or ["- none met the bar"])
    L += ["", "## Themes"] + [f"- {t['theme']}: {t['trend']}. {t['note']}" for t in latest["themes"]]
    L += ["", "## Caveats",
          "- One OR-batched search; per-coin 60m counts are estimates (batch count x sample share).",
          "- Most CA mentions are call-group/VIP-TG promo and post-pump brags, often from old (possibly bought) accounts; account age alone is not trust.",
          "- Heat measures X attention, not price. Not a buy signal on its own."]
    atomic_write(os.path.join(HERE, "summary.md"), "\n".join(L) + "\n")

CALLER_COLS = ["handle", "user_id", "followers", "account_created", "coins_called", "early_calls",
               "evidence_links", "first_seen", "last_seen", "notes"]
CALLERS_EXCLUDED = os.path.join(INTEL, "callers-excluded-bots.csv")

def drop_bot_callers(rows, dry=False):
    """rows: {user_id: callers.csv row}. Removes denylisted / bot-handle rows; appends them (once) to callers-excluded-bots.csv
    with excluded_at + bot_reason so nothing is lost. Returns (kept_rows, removed_rows)."""
    keep, gone = {}, []
    for k, r in rows.items():
        why = bot_hint(r.get("user_id"), r.get("handle"))
        if why: gone.append(dict(r, excluded_at=iso(now()), bot_reason=why))
        else: keep[k] = r
    if gone and not dry:
        cols = CALLER_COLS + ["excluded_at", "bot_reason"]
        old = list(csv.DictReader(open(CALLERS_EXCLUDED))) if os.path.exists(CALLERS_EXCLUDED) else []
        have = {(r.get("user_id"), r.get("coins_called")) for r in old}
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in old + [g for g in gone if (g.get("user_id"), g.get("coins_called")) not in have]: w.writerow(r)
        atomic_write(CALLERS_EXCLUDED, buf.getvalue())
    return keep, gone

def write_intel(latest, rugs, caller_rows, stale):
    os.makedirs(INTEL, exist_ok=True)
    hot = {"updated_at": latest["updated_at"], "stale": stale, "source": "/workspace/x-pulse/latest.json",
           "coins": [{"contract_address": c["contract_address"], "ticker": c["ticker"], "ts": c.get("observed_at"),
                      "observed_at": c.get("observed_at"),
                      "mentions_15m": c["mentions_15m"], "mentions_60m": c["mentions_60m"],
                      "distinct_accounts": c["distinct_accounts"], "heat_score": c["heat_score"],
                      "trend": c["trend_direction"], "confidence": c["confidence"]}
                     for c in latest["coins"] if valid_ca(c.get("contract_address")) and c.get("observed_at")],
           "narratives": [{"narrative": t["theme"], "trend": "rising" if t["trend"] == "up" else "fading", "note": t["note"]}
                          for t in latest["themes"]]}
    atomic_write(os.path.join(INTEL, "hot.json"), json.dumps(hot, indent=1))
    atomic_write(os.path.join(INTEL, "latest.json"), json.dumps(hot, indent=1))   # exact copy of hot.json, for Chunk
    if not stale:
        atomic_write(os.path.join(INTEL, "rugs.json"), json.dumps({"updated_at": latest["updated_at"], "coins": rugs}, indent=1))
    # callers.csv accumulate
    path = os.path.join(INTEL, "callers.csv")
    rows = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path)):
            rows[r["user_id"]] = r
    rows, _ = drop_bot_callers(rows)
    for n, ca, tk, early in caller_rows:
        if bot_hint(n["user_id"], n["handle"]): continue   # automated alert/tracker accounts are never callers
        if not early and n["user_id"] not in rows:
            continue   # callers.csv only holds accounts with >=1 early call; later mentions just extend existing rows
        r = rows.setdefault(n["user_id"], {k: "" for k in CALLER_COLS})
        r.update(handle=n["handle"], user_id=n["user_id"], followers=n["followers"], account_created=n["account_created"])
        coins = set(filter(None, r["coins_called"].split(";")))
        coins.add(f"{tk}:{ca}")
        r["coins_called"] = ";".join(sorted(coins))
        ec = set(filter(None, r["early_calls"].split(";")))
        if early: ec.add(f"{tk}:{ca}")
        r["early_calls"] = ";".join(sorted(ec))
        ev = list(filter(None, r["evidence_links"].split(" ")))
        if n["url"] not in ev: ev.append(n["url"])
        r["evidence_links"] = " ".join(ev[-10:])
        r["first_seen"] = min(filter(None, [r["first_seen"], n["first_post_ts"]]))
        r["last_seen"] = max(filter(None, [r["last_seen"], n["first_post_ts"]]))
        if not r["notes"]: r["notes"] = "auto: aged>=90d, >=100 followers, no promo/template/brag flags in sample; early = before radar ts or spike"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CALLER_COLS); w.writeheader()
    for r in sorted(rows.values(), key=lambda r: (-len(r["early_calls"].split(";")) if r["early_calls"] else 0, r["handle"] or "")):
        w.writerow(r)
    atomic_write(path, buf.getvalue())
    # NOTES.md: regenerate the top "changed since last update" line, keep the rest (hand-editable)
    npath = os.path.join(INTEL, "NOTES.md")
    body = open(npath).read().split("\n", 1)[1] if os.path.exists(npath) else NOTES_BODY
    top = [c for c in latest["coins"] if c["heat_score"] > 0][:3]
    n_early = sum(1 for r in rows.values() if r["early_calls"])
    line = (f"Changed since last update ({latest['updated_at']}): " + ("STALE run, no X reads; " if stale else "")
            + "top heat " + (", ".join(f"{c['ticker']} {c['heat_score']}" for c in top) or "none")
            + f"; rug flags {len(rugs)}; callers with early calls {n_early}; reads left today {latest['budget']['reads_left_today_reported']}.")
    atomic_write(npath, line + "\n" + body)

NOTES_BODY = """
# x-intel notes (Pulse, X research, read-only)

Files (written atomically by /workspace/x-pulse/pulse.py merge; do not hand-edit except this NOTES.md body):
- hot.json: per tracked coin (contract_address, ticker, ts, mentions_15m, mentions_60m, distinct_accounts, heat_score 0-100,
  trend rising|flat|fading, confidence low|med|high) + narratives. Mirrors /workspace/x-pulse/latest.json. `stale: true` = no X reads that run.
- rugs.json: coins flagged rug|honeypot|dev_dump|scam by >=2 distinct aged (>=90d), non-promo, non-template accounts, with post URLs.
  Weaker flags (1 account, or only bot/promo accounts) stay out and appear in latest.json coin notes.
- callers.csv: accumulates accounts that mentioned a CA before the coin's first runner-radar signal (or first radar scan if never
  signalled) or before the first Pulse run where that coin spiked (>=8 mentions/15m). Only aged, >=100-follower accounts with no
  promo/template/brag flags. Evidence = real x.com post URLs from saved raw results.
- first-mentions.jsonl: append-only, ONE line per (account user_id, token) ever = that "respected" account's FIRST post
  mentioning the token that Pulse has seen (deduped against the whole file; never rewritten). Written by the core merge,
  midcap-merge and held-merge from posts already fetched (0 extra X reads); `pulse.py first-mentions-backfill` replays raw/.
  Fields: token (contract address), ticker, handle, user_id, followers, account_created (ISO UTC), respected_reason,
  first_mention_at (post created_at, ISO UTC), post_url (https://x.com/<handle>/status/<id>), observed_at (ISO UTC, newest
  post time of the run that saw it), token_mcap_at_observation (USD, null unless a runner-radar or saved DexScreener snapshot
  exists within 60 min of observed_at), token_age_h (at observed_at, null if unknown), source_step core|midcap|held;
  extra keys: token_age_h_at_first_mention, token_data_source, token_mcap_snapshot_at, matched_by contract_address|ticker,
  quality_flags (Pulse author flags in that run's sample; [] = passed), backfill true|false.
  respected_reason (";"-joined): "quality_filters+followers>=2000" (no new/low_followers/promo/template/ring/self_template/brag
  flag AND >= 2000 followers), "copy-leads.md" (handle in a ranked lead heading of copy-leads.md, not the rejected/red-flag
  lists), "callers.csv" (handle or user_id in callers.csv, read at merge time).
  Caveats: first mention = earliest post in Pulse's samples (60-min windows, <= 25 posts/page), not necessarily the account's
  true first post. Backfilled lines use today's callers.csv/copy-leads.md (hindsight), so filter on respected_reason. Alert/
  tracker bots are excluded from new lines; older bot lines stay (append-only): drop user_ids in NOTES.md <!-- bot-excluded -->.
- bot-accounts.txt (hand-editable): denylist of automated alert/tracker/scanner accounts, one per line
  '<handle> [user_id]  # note'; a line starting with '!' is an allowlist entry (never a bot, overrides heuristics).
  An author is a bot (flag "bot") if denylisted, or handle/display name contains bot/alert/tracker/radar/scanner/scan/sniper/
  monitor/new pair(s)/detector/notifier/signal(s)/watcher/listing, or the bio says automated/auto-post/"<x> bot"/real-time
  alerts|signals, or the run's sample has >= 2 templated machine posts by it ("new token", "DEX paid", "N smart wallets just
  bought", "Trending ... Alert", "SCAM ALERT - ") or 1 such post with >= 50 posts/day lifetime.
  Bots are never quality accounts (quality_accounts counts, notable_early_callers, rug/held alerts, mid-cap quality, xcheck),
  never callers, never respected; heat weight 0.05. callers.csv rows of bots are dropped on every merge (and by `pulse.py
  bot-sync`), moved with excluded_at + bot_reason to callers-excluded-bots.csv. first-mentions.jsonl is append-only, so old
  bot lines stay: the NOTES.md <!-- bot-excluded --> block lists their user_ids; consumers MUST drop those rows.
  token_age_h comes from pair creation (DexScreener) or radar age_h, i.e. the pool's age, not the mint's.

Method:
- One OR query over up to ~22 radar CAs (only `-is:retweet`; no keyword exclusions so rug/scam posts are kept), minute counts for
  60 min + recent-sorted search pages (25 posts each) until ~15 min is covered. Posts attributed to coins by exact CA in text
  ($TICKER only if unique among tracked coins).
- Heat = weighted distinct accounts in last 15 min (quality 1.0; brag/self-template 0.3; template 0.1; promo/ring/new+low 0.05-0.1),
  scaled 0-70, +/- up to 30 for acceleration (15m vs prior run, or newer vs older half of the sample on a first run),
  x0.6 if no quality accounts. Post-pump "hit Nx" brags count 30%.

Caveats:
- Most CA mentions are call-group / VIP-TG promotion and post-pump brags. Many promo accounts are 5-15 years old (likely bought or
  repurposed), so account age alone is NOT trust; text patterns matter more.
- mentions_60m per coin is an estimate (batch count x the coin's share of the 15-min sample).
- Small samples; heat measures X attention, not price, and is never a buy signal on its own.
"""


# ---------------------------------------------------------------- first mentions by respected accounts (no X calls)
FIRST_MENTIONS = os.path.join(INTEL, "first-mentions.jsonl")
RESPECTED_MIN_FOLLOWERS = 2000   # (a) quality filters (no flags) AND >= this many followers
MCAP_MAX_GAP_MIN = 60            # token_mcap_at_observation only from a snapshot within this many minutes of observed_at

def respected_lists():
    """(copy_lead_handles, caller_handles, caller_ids). copy-leads.md: only the ranked lead headings ('### N. name: @handle'),
    not handles mentioned as rejected/red-flag examples. callers.csv: handle + user_id."""
    leads, ch, cid = set(), set(), set()
    p = os.path.join(INTEL, "copy-leads.md")
    if os.path.exists(p):
        for line in open(p, errors="ignore"):
            m = re.match(r"^#{2,4}\s*\d+\.\s[^\n]*?@([A-Za-z0-9_]{1,15})\b", line)
            if m: leads.add(m.group(1).lower())
    p = os.path.join(INTEL, "callers.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            if r.get("handle"): ch.add(r["handle"].lower())
            if r.get("user_id"): cid.add(str(r["user_id"]))
    return leads, ch, cid

def respected_reason(a, f, lists):
    leads, ch, cid = lists
    if "bot" in (f or ()) or bot_hint(a.get("id"), a.get("handle"), a.get("name")):
        return ""   # automated alert/tracker accounts are never respected
    why = []
    if is_quality(f) and (a.get("followers") or 0) >= RESPECTED_MIN_FOLLOWERS:
        why.append(f"quality_filters+followers>={RESPECTED_MIN_FOLLOWERS}")
    h = (a.get("handle") or "").lower()
    if h and h in leads: why.append("copy-leads.md")
    if (h and h in ch) or str(a.get("id") or "") in cid: why.append("callers.csv")
    return "; ".join(why)

_SNAPS = None
def token_snapshots():
    """ca -> [(snapshot_dt, mcap, created_dt, source)] from data already on disk: runner-radar signals/scanned rows
    (mcap, age_h at row ts) and DexScreener rows saved in raw/*-midcap/plan.json (mcap, pair_created_ms). No network."""
    global _SNAPS
    if _SNAPS is not None: return _SNAPS
    S = {}
    def num(x):
        try: return float(x) if x is not None and x != "" else None
        except (TypeError, ValueError): return None
    for fn in ("signals.jsonl", "scanned.jsonl"):
        for r in read_jsonl(os.path.join(RADAR, fn)):
            t, ca = parse_ts(r.get("ts")), r.get("token")
            if not t or not valid_ca(ca): continue
            age = num(r.get("age_h"))
            S.setdefault(ca, []).append((t, num(r.get("mcap")), t - timedelta(hours=age) if age is not None else None, f"runner-radar/{fn}"))
    for pf in glob.glob(os.path.join(HERE, "raw", "*-midcap", "plan.json")):
        try:
            pl = json.load(open(pf)); t = datetime.strptime(pl["run_ts"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        src = "dexscreener (raw/" + os.path.basename(os.path.dirname(pf)) + "/plan.json)"
        for c in pl.get("coins") or []:
            ca = c.get("contract_address")
            if not valid_ca(ca): continue
            pc = num(c.get("pair_created_ms"))
            S.setdefault(ca, []).append((t, num(c.get("mcap")), datetime.fromtimestamp(pc / 1000, timezone.utc) if pc else None, src))
    _SNAPS = S
    return S

def token_info(ca, obs_dt, first_dt):
    snaps = token_snapshots().get(ca) or []
    near = sorted([s for s in snaps if s[1] is not None and abs((s[0] - obs_dt).total_seconds()) <= MCAP_MAX_GAP_MIN * 60],
                  key=lambda s: abs((s[0] - obs_dt).total_seconds()))
    mc = near[0] if near else None
    cr = [s for s in snaps if s[2] is not None]
    if mc and mc[2] is not None: cr = [mc] + cr
    created = cr[0][2] if cr else None
    def hours(x): return round((x - created).total_seconds() / 3600, 2) if created else None
    return {"token_mcap_at_observation": mc[1] if mc else None, "token_age_h": hours(obs_dt),
            "token_age_h_at_first_mention": hours(first_dt) if first_dt else None,
            "token_data_source": "; ".join(dict.fromkeys(x for x in ((mc[3] if mc else None), (cr[0][3] if cr else None)) if x)) or None,
            "token_mcap_snapshot_at": iso(mc[0]) if mc else None}

def log_first_mentions(plist, authors, flags, source_step, obs_dt, tickers, backfill=False, dry=False):
    """For posts already fetched: each respected account's earliest post per token -> FIRST_MENTIONS (append-only,
    one line per (user_id, token) ever, deduped against the file). Returns number of new lines."""
    import fcntl
    lists = respected_lists()
    best = {}
    for p in plist:
        aid, dt = p.get("author_id"), p.get("_dt") or parse_ts(p.get("created_at"))
        if not aid or not dt: continue
        for ca in p.get("_coins") or []:
            if valid_ca(ca) and ((aid, ca) not in best or dt < best[(aid, ca)][1]):
                best[(aid, ca)] = (p, dt)
    rows = []
    for (aid, ca), (p, dt) in sorted(best.items(), key=lambda kv: kv[1][1]):
        a = authors.get(aid) or {}
        if not a.get("handle"): continue
        why = respected_reason(a, flags.get(aid, {"new"}), lists)
        if not why: continue
        r = {"token": ca, "ticker": (tickers.get(ca) or "").strip() or None, "handle": a["handle"], "user_id": str(aid),
             "followers": a.get("followers"),
             "account_created": iso(parse_ts(a["created_at"])) if parse_ts(a.get("created_at")) else None, "respected_reason": why,
             "first_mention_at": iso(dt), "post_url": f"https://x.com/{a['handle']}/status/{p['id']}",
             "observed_at": iso(obs_dt)}
        ti = token_info(ca, obs_dt, dt)
        r.update(token_mcap_at_observation=ti["token_mcap_at_observation"], token_age_h=ti["token_age_h"], source_step=source_step)
        r.update(token_age_h_at_first_mention=ti["token_age_h_at_first_mention"], token_data_source=ti["token_data_source"],
                 token_mcap_snapshot_at=ti["token_mcap_snapshot_at"],
                 matched_by="contract_address" if ca in (p.get("text") or "") else "ticker",
                 quality_flags=sorted(flags.get(aid, {"new"})), backfill=bool(backfill))
        rows.append(r)
    if dry or not rows:
        return rows if dry else 0
    os.makedirs(INTEL, exist_ok=True)
    with open(FIRST_MENTIONS + ".lock", "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        seen = {(str(r.get("user_id")), r.get("token")) for r in read_jsonl(FIRST_MENTIONS)}
        new = []
        for r in rows:
            k = (r["user_id"], r["token"])
            if k not in seen: seen.add(k); new.append(r)
        if new: append_lines(FIRST_MENTIONS, new)
    return len(new)

def safe_first_mentions(*a, **k):
    try:
        n = log_first_mentions(*a, **k)
    except Exception as e:   # never block a merge
        print(f"# first-mentions logging failed: {e}", file=sys.stderr); return 0
    try:
        if not k.get("dry"): bot_sidecar_update()
    except Exception as e:
        print(f"# bot sidecar update failed: {e}", file=sys.stderr)
    return n

BOT_MARK = ("<!-- bot-excluded -->", "<!-- /bot-excluded -->")

def bot_sidecar_update(dry=False):
    """first-mentions.jsonl is append-only, so bot rows are never deleted: list their user_ids in a NOTES.md block instead.
    Returns the sorted [(user_id, handle, reason, n_lines)]."""
    found = {}
    for r in read_jsonl(FIRST_MENTIONS):
        why = bot_hint(r.get("user_id"), r.get("handle"))
        if why:
            e = found.setdefault(str(r.get("user_id")), [r.get("handle"), why, 0]); e[2] += 1
    out = sorted((k, *v) for k, v in found.items())
    npath = os.path.join(INTEL, "NOTES.md")
    if dry or not os.path.exists(npath): return out
    ids = ",".join(k for k, *_ in out)
    block = (f"{BOT_MARK[0]}\nfirst-mentions.jsonl bot/tracker exclusions ({len(out)} accounts, {sum(x[3] for x in out)} lines; "
             f"updated from bot-accounts.txt + handle heuristics). Consumers MUST drop rows whose user_id is in:\n"
             f"excluded_user_ids: {ids or '(none)'}\n"
             + "".join(f"- {k} @{h} ({why}, {n} line{'s' if n != 1 else ''})\n" for k, h, why, n in out) + BOT_MARK[1])
    t = open(npath).read()
    if BOT_MARK[0] in t and BOT_MARK[1] in t:
        a, rest = t.split(BOT_MARK[0], 1); b = rest.split(BOT_MARK[1], 1)[1]
        new = a + block + b
    else:
        new = t.rstrip("\n") + "\n\n" + block + "\n"
    if new != t: atomic_write(npath, new)
    return out

def cmd_bot_sync(dry=False):
    """Apply bot-accounts.txt + handle heuristics to callers.csv and the first-mentions sidecar. No X calls."""
    path = os.path.join(INTEL, "callers.csv")
    rows = {r["user_id"]: r for r in csv.DictReader(open(path))} if os.path.exists(path) else {}
    keep, gone = drop_bot_callers(rows, dry=dry)
    if gone and not dry:
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=CALLER_COLS, extrasaction="ignore"); w.writeheader()
        for r in rows.values():
            if r["user_id"] in keep: w.writerow(r)
        atomic_write(path, buf.getvalue())
    side = bot_sidecar_update(dry=dry)
    d = bot_denylist()
    print(json.dumps({"dry_run": dry, "denylist_handles": len(d["handles"]), "denylist_user_ids": len(d["ids"]),
                      "callers_rows_removed": len(gone), "callers_removed": [(g["handle"], g["user_id"], g["bot_reason"]) for g in gone],
                      "callers_rows_kept": len(keep), "first_mentions_excluded_accounts": len(side),
                      "first_mentions_excluded_lines": sum(x[3] for x in side),
                      "first_mentions_excluded": side}, indent=1))

def cmd_first_mentions_backfill(dry=False):
    """Replay saved raw/ dirs (core, -midcap, -held) in time order. No X calls. Dedup makes it safe to re-run."""
    import pulse_ext as E
    tot, per = 0, []
    seen = {(str(r.get("user_id")), r.get("token")) for r in read_jsonl(FIRST_MENTIONS)}   # dry-run dedup only
    dirs = sorted(d for d in glob.glob(os.path.join(HERE, "raw", "*")) if os.path.isfile(os.path.join(d, "plan.json")))
    for d in dirs:
        name = os.path.basename(d)
        try:
            if re.fullmatch(r"\d{8}T\d{6}Z", name):
                L = _core_load(name)
                if L["stale"]: continue
                args = (L["plist"], L["authors"], L["flags"], "core", L["run_dt"], {c["contract_address"]: c.get("ticker") for c in L["coins"]})
            elif name.endswith("-midcap"):
                L = E.midcap_load(d)
                args = (L["plist"], L["authors"], L["flags"], "midcap", L["run_dt"], {c["contract_address"]: c.get("ticker") for c in L["coins"]})
            elif name.endswith("-held"):
                L = E.held_load(d)
                args = (L["plist_all"], L["authors"], L["flags_all"], "held", L["run_dt"], {h["contract_address"]: h.get("ticker") for h in L["held"]})
            else:
                continue
        except Exception as e:
            per.append({"dir": name, "error": str(e)[:200]}); continue
        res = log_first_mentions(*args, backfill=True, dry=dry)
        if dry:
            res = [r for r in res if (r["user_id"], r["token"]) not in seen]; seen.update((r["user_id"], r["token"]) for r in res)
        n = len(res) if dry else res
        tot += n; per.append({"dir": name, "lines": n, "posts": len(args[0])})
    print(json.dumps({"dry_run": dry, "lines": tot, "dirs": per}, indent=1))

# ---------------------------------------------------------------- daily report (local files only, no X)
def cmd_report(night, out_dir="/workspace/commander/reports"):
    """Draft pulse-<night>.md. night = date the night started (Dublin evening), YYYY-MM-DD."""
    winners = {}
    p = os.path.join(RADAR, "outcomes.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            try:
                mx = float(r.get("max_ret") or 0)
            except ValueError:
                mx = 0
            if r.get("hit_2x") == "1" or mx >= 1.0:
                winners[r["token"]] = f"{r['symbol']} max {mx:+.0%}"
    traded = set()
    for f in glob.glob(os.path.join(RADAR, "live", "*.md")) + glob.glob("/workspace/copyfomo/*.md") + glob.glob("/workspace/copyfomo/*.json"):
        traded.update(re.findall(r"[1-9A-HJ-NP-Za-km-z]{32,44}", open(f, errors="ignore").read()))
    callers = list(csv.DictReader(open(os.path.join(INTEL, "callers.csv")))) if os.path.exists(os.path.join(INTEL, "callers.csv")) else []
    early_win = []
    for r in callers:
        for item in filter(None, r["early_calls"].split(";")):
            ca = item.split(":")[-1]
            if ca in winners:
                early_win.append(f"- @{r['handle']} ({r['followers']} followers, since {r['account_created']}) early on {winners[ca]} `{ca}`"
                                 + (" (we traded it)" if ca in traded else "") + f": {r['evidence_links'].split(' ')[0]}")
    rugs = json.load(open(os.path.join(INTEL, "rugs.json")))["coins"] if os.path.exists(os.path.join(INTEL, "rugs.json")) else []
    hist = [h for h in read_jsonl(os.path.join(HERE, "history.jsonl")) if h["run_ts"] >= night]
    budget = [b for b in read_jsonl(os.path.join(HERE, "budget.jsonl")) if b["ts"] >= night]
    latest = json.load(open(os.path.join(HERE, "latest.json"))) if os.path.exists(os.path.join(HERE, "latest.json")) else {"coins": []}
    shill = [c for c in latest["coins"] if c["distinct_accounts"] >= 3 and c["quality_accounts"] <= 1]
    L = [f"# Pulse daily report, night of {night}", "",
         f"Runs: {len(budget)} ({sum(1 for b in budget if b.get('stale'))} stale); X reads used: {sum(int(b.get('reads_used') or 0) for b in budget)}; "
         f"coin-runs scored: {len(hist)}.", "", "## Callers who were early on our winners"]
    L += early_win or ["- none yet (needs winners in outcomes.csv and accumulated early calls in callers.csv)"]
    L += ["", "## Coins flagged as rugs or shills", "Rugs (>=2 aged non-bot accounts):"]
    L += [f"- {r['ticker']} `{r['contract_address']}` {r['flag']}, {r['quality_flagging_accounts']} accts, first {r['first_flag_ts']}: {' '.join(r['evidence'][:3])}" for r in rugs] or ["- none"]
    L += ["Shill-dominated (>=3 accounts, <=1 quality) in latest run:"]
    L += [f"- {c['ticker']} `{c['contract_address']}`: {c['notes'][:200]}" for c in shill] or ["- none"]
    L += ["", "## Proposed changes", "- (fill in: threshold/weight tweaks, callers to promote/demote, budget changes)"]
    path = os.path.join(out_dir, f"pulse-{night}.md")
    atomic_write(path, "\n".join(L) + "\n")
    print(path)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "gate": cmd_gate()
    elif cmd == "unlock": cmd_unlock()
    elif cmd == "prep": cmd_prep()
    elif cmd == "report": cmd_report(sys.argv[2], *(sys.argv[3:4]))
    elif cmd == "merge": cmd_merge(sys.argv[2], stale="--stale" in sys.argv)
    elif cmd == "pace": cmd_pace()
    elif cmd == "first-mentions-backfill": cmd_first_mentions_backfill(dry="--dry-run" in sys.argv)
    elif cmd == "bot-sync": cmd_bot_sync(dry="--dry-run" in sys.argv)
    elif cmd in ("midcap-prep", "midcap-merge", "xcheck-prep", "xcheck-cond", "xcheck-merge", "reddit", "budget",
                 "held-prep", "held-merge", "context", "board"):
        import pulse_ext
        pulse_ext.main(cmd, sys.argv[2:])
    else: print(__doc__)
