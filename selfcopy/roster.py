"""Rotating leader roster: load roster.json, score leaders on rolling paper results, pick <=3 LIVE leaders.

Pure functions only (no network, no wallet). The bot calls rank_and_rotate() once per UTC hour and
check_loss_demotions() every minute. Wallets are added by Zero (roster.json) or via roster_inbox.json (merge_inbox,
every minute; written by Scout), capped at 20 active.
"""
import json, os, re, time, datetime, calendar

P = dict(window_h=72, min_trades=4, max_slots=3, hysteresis=2, loss_demote=2, loss_cooldown_h=24, max_roster=20,
         default_live=("_benjitrades",), inactive_s=3600, replace_active_s=1800,
         session_fill_conf=("medium", "medium-high", "high"), session_neg_min_n=2, session_max_slots=15,
         prune_n=4, prune_quick_stop_s=900, prune_cooldown_h=12)
CONF_RANK = {"low": 0, "medium-low": 1, "medium": 2, "medium-high": 3, "high": 4}

def slots(session=None):
    """LIVE leader slots: 3, or session.json max_live_leaders (daytime session only, at most 5)."""
    n = (session or {}).get("max_slots") or P["max_slots"]
    try: n = int(n)
    except Exception: n = P["max_slots"]
    return max(1, min(n, P["session_max_slots"]))
B58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

def ts_of(iso):
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")) if iso else None
def iso_of(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------- roster.json ----------
def load_roster(fn):
    """-> (entries, warnings). entry = dict(label, wallet, source, confidence, added). Only active, valid, unique, first 20."""
    raw = json.load(open(fn)); out, warn, seen_l, seen_w = [], [], set(), set()
    for e in raw.get("leaders", []):
        lab, w = str(e.get("label", "")).strip(), str(e.get("wallet", "")).strip()
        if e.get("active", True) is False: continue
        if not lab or not B58.match(w): warn.append(f"invalid entry skipped: {lab or '?'}"); continue
        if lab in seen_l or w in seen_w: warn.append(f"duplicate skipped: {lab}"); continue
        if len(out) >= P["max_roster"]: warn.append(f"over {P['max_roster']} wallets, skipped: {lab}"); continue
        seen_l.add(lab); seen_w.add(w)
        out.append(dict(label=lab, wallet=w, source=e.get("source", "?"), confidence=e.get("confidence", "?"), added=e.get("added")))
    return out, warn

# ---------- scoring ----------
def qualifying(positions, label, now_ts, net_fn):
    """paper trades of `label` opened in the last 72h that pass the v2 live filters; open ones marked to market."""
    out = []
    for p in positions:
        if p.get("leader") != label or not (p.get("filters") or {}).get("v2_pass"): continue
        if p.get("forced_filter_override"): continue
        t = ts_of(p.get("opened"))
        if t is None or t < now_ts - P["window_h"] * 3600: continue
        mark = p.get("last_value", 0) if p.get("status") == "open" else 0
        out.append(dict(t=t, net=net_fn(p, mark), cost=p.get("cost_usd") or 0, open=p.get("status") == "open"))
    return sorted(out, key=lambda r: r["t"])

def score(trades):
    """EV per trade after costs (mean net $ and mean net % of stake), win rate, max drawdown ($, on the cumulative curve)."""
    n = len(trades)
    if not n: return dict(n=0, ev_usd=None, ev_pct=None, win_rate=None, max_dd_usd=0.0, net_usd=0.0, n_open=0, eligible=False)
    nets = [r["net"] for r in trades]
    ev_usd = sum(nets) / n
    ev_pct = sum(r["net"] / r["cost"] for r in trades if r["cost"]) / n
    cum = peak = dd = 0.0
    for x in nets:
        cum += x; peak = max(peak, cum); dd = max(dd, peak - cum)
    return dict(n=n, ev_usd=ev_usd, ev_pct=ev_pct, win_rate=sum(1 for x in nets if x > 0) / n, max_dd_usd=dd,
                net_usd=sum(nets), n_open=sum(1 for r in trades if r["open"]), eligible=n >= P["min_trades"] and ev_pct > 0)

def rank(scores):
    """eligible leaders (>=4 qualifying trades, score > 0), best EV% first."""
    el = [k for k, s in scores.items() if s["eligible"]]
    return sorted(el, key=lambda k: (-scores[k]["ev_pct"], -scores[k]["n"], k))

# ---------- rotation ----------
def new_state(now_ts):
    return dict(mode="default", live=list(P["default_live"]), streak={}, promoted_at={k: now_ts for k in P["default_live"]},
                cooldown_until={}, log=[], last_rank_key=None, last_rank=[], scores={})

def consecutive_losses(closed, since_ts):
    """closed = [(closed_ts, net_sol)], counted from the latest backwards, only trades closed after promotion."""
    k = 0
    for t, net in sorted([c for c in closed if c[0] >= (since_ts or 0)], reverse=True):
        if net < 0: k += 1
        else: break
    return k

def _ev(st, ts, label, action, why):
    st["log"].append(dict(ts=iso_of(ts), leader=label, action=action, why=why)); del st["log"][:-200]

def check_loss_demotions(st, live_closed, now_ts):
    """demote any live leader (rotation or default) after 2 live losses in a row since it got its slot; 24h cooldown."""
    changed = False
    for lab in list(st["live"]):
        k = consecutive_losses(live_closed.get(lab, []), st["promoted_at"].get(lab))
        if k >= P["loss_demote"]:
            st["live"].remove(lab); st["cooldown_until"][lab] = now_ts + P["loss_cooldown_h"] * 3600
            _ev(st, now_ts, lab, "demoted", f"{k} live losses in a row (cooldown {P['loss_cooldown_h']}h)"); changed = True
    if changed and not st["live"]: _fallback(st, now_ts)
    return changed

def active(last_trade, lab, now_ts, window_s):
    """leader had a buy or sell seen within window_s. last_trade None = activity unknown -> treated as active (tests/back-compat)."""
    if last_trade is None: return True
    t = last_trade.get(lab)
    return t is not None and now_ts - t <= window_s

def _fallback(st, now_ts, last_trade=None):
    """no rotation leader holds a slot -> current behaviour: default leader(s), unless in loss cooldown, off the roster,
    or inactive (no buy/sell seen in 60 min) -> then the slot stays empty."""
    st["mode"] = "default"
    for lab in P["default_live"]:
        if not active(last_trade, lab, now_ts, P["inactive_s"]): continue
        if lab in st.get("_roster", [lab]) and st["cooldown_until"].get(lab, 0) <= now_ts and lab not in st["live"]:
            st["live"].append(lab); st["promoted_at"][lab] = now_ts
            _ev(st, now_ts, lab, "default_live", "no leader qualifies yet; default leader keeps the slot")

def rank_and_rotate(st, scores, roster_labels, live_closed, now_ts, last_trade=None, session=None):
    """One hourly rank. Mutates and returns st. scores: label -> score() dict. last_trade: label -> ts of last buy/sell seen.
    session: None, or dict(conf={label: confidence}, record={label: raw 72h paper record}) while a daytime session with
    roster_fill is open -> hysteresis 1 and session_fill() (see there)."""
    st["_roster"] = list(roster_labels)
    if not session: session_clear(st, now_ts)
    sfill = set(st.get("session_fill") or []) if session else set()
    check_loss_demotions(st, live_closed, now_ts)
    ns = slots(session)
    order = rank(scores); top = order[:ns]
    st["streak"] = {k: (st["streak"].get(k, 0) + 1 if k in top else 0) for k in roster_labels}
    rotation = st["mode"] == "rotation"
    live = list(st["live"]) if rotation else []
    # demotions (rotation slots only; the default slot is only lost to losses or to a qualifying leader)
    for lab in list(live):
        s = scores.get(lab)
        if lab in sfill and lab in roster_labels:
            why = None if (lab in (session.get("manual") or []) or session.get("ignore_neg")) else session_negative(s, (session.get("record") or {}).get(lab))
            if why: live.remove(lab); _ev(st, now_ts, lab, "demoted", why)
            continue
        why = ("removed from roster" if lab not in roster_labels else
               f"fewer than {P['min_trades']} qualifying trades in {P['window_h']}h" if not s or s["n"] < P["min_trades"] else
               "score <= 0" if s["ev_pct"] <= 0 else None)
        if why: live.remove(lab); _ev(st, now_ts, lab, "demoted", why)
    # promotions: in the top 3 for >= 2 consecutive hourly ranks, not in cooldown
    need = 1 if session else P["hysteresis"]          # daytime session: one hourly rank is enough
    cands = [k for k in top if k not in live and st["streak"].get(k, 0) >= need and st["cooldown_until"].get(k, 0) <= now_ts
             and active(last_trade, k, now_ts, P["inactive_s"])]
    for c in cands:
        if len(live) < ns:
            live.append(c); st["promoted_at"][c] = now_ts
            _ev(st, now_ts, c, "promoted", f"rank {order.index(c)+1}, EV {scores[c]['ev_pct']*100:+.1f}%/trade over {scores[c]['n']} trades, top 3 for {st['streak'][c]} ranks")
            continue
        out = [k for k in live if k not in top]
        if not out: break
        worst = min(out, key=lambda k: scores[k]["ev_pct"] if scores.get(k) and scores[k]["ev_pct"] is not None else -9)
        live.remove(worst); _ev(st, now_ts, worst, "demoted", f"swapped out for {c} (no longer top 3)")
        live.append(c); st["promoted_at"][c] = now_ts
        _ev(st, now_ts, c, "promoted", f"rank {order.index(c)+1}, top 3 for {st['streak'][c]} ranks, replaces {worst}")
    if live:
        if not rotation:
            for lab in st["live"]:
                if lab not in live: _ev(st, now_ts, lab, "default_dropped", "a leader qualified; rotation takes over")
        st["mode"] = "rotation"; st["live"] = live[:ns]
    else:
        if rotation: st["live"] = []
        st["live"] = [k for k in st["live"] if k in roster_labels and active(last_trade, k, now_ts, P["inactive_s"])]
        if not st["live"]: _fallback(st, now_ts, last_trade)
        else: st["mode"] = "default"
    st["last_rank"] = order; st["scores"] = scores
    if session: session_fill(st, scores, session, now_ts, last_trade)
    return st

# ---------- daytime session fill ----------
def session_clear(st, now_ts):
    """session closed for entries (or over / roster_fill off): session-filled leaders lose their slots -> changed?"""
    sf = [k for k in (st.get("session_fill") or []) if k in st["live"]]
    for lab in sf:
        st["live"].remove(lab); _ev(st, now_ts, lab, "demoted", "daytime session closed for entries: session-fill slot ends")
    st["session_fill"] = []
    extra = st["live"][P["max_slots"]:]                  # session-only slots 4-5 end with the session
    for lab in extra:
        st["live"].remove(lab); _ev(st, now_ts, lab, "demoted", f"daytime session closed: back to {P['max_slots']} slots")
    sf = sf + extra
    if sf and not st["live"]:
        if st["mode"] == "rotation": st["mode"] = "default"
    return bool(sf)
def session_negative(s, rec):
    """-> reason if the recent record is clearly negative, else None (neutral = no trades yet).
    s: v2 score() dict; rec: dict(n, net_usd) over ALL paper trades of the last 72h (any filters)."""
    k = P["session_neg_min_n"]
    if s and s.get("n", 0) >= k and (s.get("ev_pct") or 0) < 0:
        return f"session fill: negative qualifying record (EV {s['ev_pct']*100:+.1f}%/trade over {s['n']} trades)"
    if rec and rec.get("n", 0) >= k and (rec.get("net_usd") or 0) < 0:
        return f"session fill: negative paper record (net ${rec['net_usd']:+.2f} over {rec['n']} trades in {P['window_h']}h)"
    return None

def session_fill(st, scores, session, now_ts, last_trade):
    """Daytime session only (session.json roster_fill, default on). If a LIVE slot is empty, fill it with a roster wallet
    that: has confidence medium or better, had a buy/sell seen in the last 60 min, is not in loss cooldown, and whose
    recent record is not clearly negative (session_negative). The >=4-trade / score>0 rule and hysteresis are skipped
    for these slots only. 60-min idle demotion (check_inactivity), 2-loss demotion and all exits are unchanged.
    session["manual"] (session.json manual_live) = labels allowed a slot regardless of confidence, this session only,
    filled first; every other condition (active, no cooldown, not clearly negative) still applies. Most recently active first. -> changed?"""
    conf = session.get("conf") or {}; rec = session.get("record") or {}
    roster = list(conf) or st.get("_roster") or []      # current roster (conf is rebuilt on every roster.json reload)
    st["session_fill"] = [k for k in (st.get("session_fill") or []) if k in st["live"]]
    changed = False
    # a session-filled leader whose record turned clearly negative loses the slot
    manual = [k for k in (session.get("manual") or []) if k in roster]
    for lab in list(st["session_fill"]):
        if lab in manual or session.get("ignore_neg"): continue        # user-approved manual_live: the paper "clearly negative" rule does not apply (10:35Z)
        why = session_negative((scores or {}).get(lab), rec.get(lab))
        if why:
            st["live"].remove(lab); st["session_fill"].remove(lab); _ev(st, now_ts, lab, "demoted", why); changed = True
    any_conf = bool(session.get("any_conf"))
    cands = [k for k in roster if k not in st["live"] and (any_conf or conf.get(k) in P["session_fill_conf"] or k in manual)
             and st["cooldown_until"].get(k, 0) <= now_ts and (k in manual or active(last_trade, k, now_ts, P["inactive_s"]))
             and (k in manual or session.get("ignore_neg") or not session_negative((scores or {}).get(k), rec.get(k)))]
    def _ev_of(k):
        s = (scores or {}).get(k) or {}
        return s.get("ev_pct") if s.get("ev_pct") is not None else -1e9
    # manual (session.json manual_live) first, then most recent buy/sell, then score
    cands.sort(key=lambda k: (k not in manual, -((last_trade or {}).get(k) or 0), -_ev_of(k)))
    for c in cands:
        if len(st["live"]) >= slots(session): break
        st["live"].append(c); st["session_fill"].append(c); st["promoted_at"][c] = now_ts; changed = True
        s = (scores or {}).get(c) or {}; r = rec.get(c) or {}
        lt = (last_trade or {}).get(c)
        _ev(st, now_ts, c, "promoted", f"session fill{' (manual_live, this session only)' if c in manual else ''}: {conf.get(c)} confidence, active (last buy/sell {iso_of(lt) if lt else '?'}), "
                                      f"record not negative ({s.get('n', 0)} qualifying, {r.get('n', 0)} paper trades, net ${r.get('net_usd', 0):+.2f}); empty slot")
    return changed

def check_inactivity(st, last_trade, now_ts, session=None):
    """every minute: a live leader with no buy/sell seen in 60 min loses its slot (new entries only; no cooldown).
    The slot goes straight (no 2-rank hysteresis) to the best-scoring ELIGIBLE roster leader (>=4 trades, score > 0,
    from the latest hourly scores) that traded in the last 30 min; otherwise it stays empty.
    Default mode: _benjitrades holds the default slot only while active; it returns when he trades again. -> changed?"""
    scores = st.get("scores") or {}; roster = st.get("_roster") or list(scores)
    changed = False if session else session_clear(st, now_ts)
    for lab in list(st["live"]):
        if active(last_trade, lab, now_ts, P["inactive_s"]): continue
        if lab in ((session or {}).get("manual") or []): continue   # 13:25Z Zero: user-approved manual_live keeps its slot while idle (it only signals when it trades)
        st["live"].remove(lab); changed = True
        lt = last_trade.get(lab)
        _ev(st, now_ts, lab, "demoted", "inactive: no buy/sell seen in 60 min" + (f" (last {iso_of(lt)})" if lt else " (none seen)"))
        repl = [k for k in rank(scores) if k in roster and k not in st["live"] and st["cooldown_until"].get(k, 0) <= now_ts
                and active(last_trade, k, now_ts, P["replace_active_s"])]
        if repl and len(st["live"]) < slots(session):
            c = repl[0]; st["live"].append(c); st["promoted_at"][c] = now_ts; st["mode"] = "rotation"
            _ev(st, now_ts, c, "promoted", f"replaces inactive {lab}: best eligible leader active in the last 30 min (rank {rank(scores).index(c)+1}, "
                                           f"EV {scores[c]['ev_pct']*100:+.1f}%/trade over {scores[c]['n']} trades; hysteresis skipped)")
        else:
            _ev(st, now_ts, lab, "slot_empty", "no eligible leader traded in the last 30 min; slot left empty")
    if st.get("session_fill"): st["session_fill"] = [k for k in st["session_fill"] if k in st["live"]]
    if not st["live"]:
        if st["mode"] == "rotation": st["mode"] = "default"
        before = list(st["live"]); _fallback(st, now_ts, last_trade)
        changed = changed or st["live"] != before
    if session: changed = session_fill(st, st.get("scores") or {}, session, now_ts, last_trade) or changed
    return changed

def live_set(st, session=None):
    return tuple(st["live"][:slots(session)]) if st else P["default_live"]

# ---------- session pruning (user 10:29Z: prune more aggressively) ----------
def prune_check(st, copies, now_ts, since_ts=0, real_only=()):
    """Daytime session only, every minute, on top of the 2-losses-in-a-row demotion:
    (a) a LIVE leader whose last P["prune_n"] (4) closed copies (paper, selfcopy live or Chunk live; deduped) net < 0
        after costs (sum of net % of stake) is demoted;
    (b) a leader whose LAST copy hit the -15% stop within 15 min of entry is demoted (or, if not live, kept out).
    real_only: labels judged on REAL copies only (Chunk / selfcopy live), e.g. user-approved manual_live wallets.
    Both -> P["prune_cooldown_h"] (12h) cooldown. A leader is only judged when a NEW copy closes (after since_ts = session start).
    copies: label -> [dict(opened_ts, closed_ts, net_frac, stop_hit, src, mint)]. -> list of prune events."""
    seen = st.setdefault("prune_seen", {}); out = []
    for lab, cs in (copies or {}).items():
        cs = sorted([c for c in cs if c.get("closed_ts") and not (lab in real_only and c.get("src") == "paper")], key=lambda c: c["closed_ts"])
        if not cs: continue
        last = cs[-1]
        if last["closed_ts"] <= max(seen.get(lab, 0), since_ts): continue     # judged only on a copy closed this session
        live = lab in st["live"]; why = rule = None
        held = (last["closed_ts"] - last["opened_ts"]) if last.get("opened_ts") else None
        if last.get("stop_hit") and held is not None and held <= P["prune_quick_stop_s"]:
            rule = "quick_stop"; why = f"prune: last copy ({last.get('src')}, {str(last.get('mint'))[:8]}) hit the -15% stop {int(held // 60)} min after entry"
        elif live and len(cs) >= P["prune_n"]:
            tot = sum(c["net_frac"] for c in cs[-P["prune_n"]:])
            if tot < 0:
                rule = "last4_negative"; why = f"prune: last {P['prune_n']} closed copies net {tot*100:+.1f}% of stake after costs (" + \
                    ", ".join(f"{c['net_frac']*100:+.1f}%" for c in cs[-P["prune_n"]:]) + ")"
        seen[lab] = last["closed_ts"]
        if not rule: continue
        cd = now_ts + P["prune_cooldown_h"] * 3600
        st["cooldown_until"][lab] = max(st["cooldown_until"].get(lab, 0), cd)
        why += f"; {P['prune_cooldown_h']}h cooldown until {iso_of(cd)}"
        if live:
            st["live"].remove(lab)
            if lab in (st.get("session_fill") or []): st["session_fill"].remove(lab)
            _ev(st, now_ts, lab, "demoted", why)
        else:
            _ev(st, now_ts, lab, "pruned", why + " (was not live)")
        out.append(dict(ts=iso_of(now_ts), leader=lab, rule=rule, was_live=live, why=why, cooldown_until=iso_of(cd),
                        last_copies=[dict(src=c.get("src"), mint=c.get("mint"), net_pct=round(c["net_frac"] * 100, 2), stop_hit=bool(c.get("stop_hit")),
                                          held_min=round((c["closed_ts"] - c["opened_ts"]) / 60, 1) if c.get("opened_ts") else None) for c in cs[-P["prune_n"]:]]))
    if out and not st["live"] and st.get("mode") == "rotation": st["mode"] = "default"
    return out

def dedupe_copies(live_copies, paper_copies, window_s=600):
    """live copies win; a paper copy of the same leader+mint opened within window_s of a live one is dropped"""
    out = list(live_copies)
    for p in paper_copies:
        if any(l.get("mint") == p.get("mint") and abs((l.get("opened_ts") or 0) - (p.get("opened_ts") or 0)) <= window_s for l in live_copies): continue
        out.append(p)
    return out

# ---------- roster_inbox.json (Scout) ----------
LABEL_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,40}$")
def merge_inbox(roster_fn, inbox_fn, seen, last_trade, protect, now_ts):
    """Merge new wallets from roster_inbox.json (a list of {label, wallet, confidence, source}) into roster.json.
    Each inbox wallet is processed once (seen: wallet -> iso, persisted by the caller). Max P["max_roster"] active:
    when full, the idlest low-confidence wallet (low / medium-low / unknown; lowest tier first, then oldest last
    buy/sell, or its added time if later) is set active:false - never one in `protect` (live, open positions, manual_live). If none can be dropped,
    the new wallet waits. -> dict(added=[...], dropped=[...], skipped=[(label, why)], waiting=[...]) ; writes roster.json only on change."""
    res = dict(added=[], dropped=[], skipped=[], waiting=[])
    if not os.path.exists(inbox_fn): return res
    try: inbox = json.load(open(inbox_fn))
    except Exception as e: res["skipped"].append(("roster_inbox.json", f"unreadable: {e!r}"[:120])); return res
    if isinstance(inbox, dict): inbox = inbox.get("wallets") or inbox.get("leaders") or []
    if not isinstance(inbox, list): return res
    raw = json.load(open(roster_fn)); L = raw.setdefault("leaders", [])
    changed = False
    for e in inbox:
        if not isinstance(e, dict): continue
        w = str(e.get("wallet", "")).strip(); lab = str(e.get("label", "")).strip()
        if not w or w in seen: continue
        if not B58.match(w): seen[w] = iso_of(now_ts); res["skipped"].append((lab or w[:8], "invalid wallet")); continue
        if not LABEL_RE.match(lab): lab = "w-" + w[:6]
        if any(x.get("wallet") == w for x in L):
            seen[w] = iso_of(now_ts); res["skipped"].append((lab, "wallet already in roster.json")); continue
        if any(x.get("label") == lab for x in L): lab = f"{lab[:33]}-{w[:6]}"
        act = [x for x in L if x.get("active", True) is not False]
        if len(act) >= P["max_roster"]:
            drop = [x for x in act if x["label"] not in protect and CONF_RANK.get(x.get("confidence"), 0) <= 1]
            if not drop:
                res["waiting"].append(lab); continue
            def _idle_key(x):      # last buy/sell seen, or when it was added (a just-merged wallet is not "idle" yet)
                try: ad = ts_of(x.get("added")) or 0
                except Exception: ad = 0
                return (CONF_RANK.get(x.get("confidence"), 0), max((last_trade or {}).get(x["label"]) or 0, ad))
            v = min(drop, key=_idle_key)
            v["active"] = False; v["dropped"] = f"{iso_of(now_ts)} roster full: idlest low-confidence wallet, replaced by {lab}"
            res["dropped"].append(v["label"])
        conf = str(e.get("confidence", "low")).strip().lower()
        L.append(dict(label=lab, wallet=w, source=str(e.get("source", "roster_inbox.json"))[:200] + " [via roster_inbox.json]",
                      confidence=conf if conf in CONF_RANK else "low", added=iso_of(now_ts), active=True))
        seen[w] = iso_of(now_ts); res["added"].append(lab); changed = True
    if changed:
        tmp = roster_fn + ".tmp"; json.dump(raw, open(tmp, "w"), indent=1); os.replace(tmp, roster_fn)
    return res
