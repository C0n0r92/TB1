#!/usr/bin/env python3
"""_benjitrades probation tracker (PAPER/READ-ONLY: reads Copycat's log, writes out/benji_probation.md; never touches the bot).
Real copies come from /workspace/copyfomo/x-watch-log.md (Copycat). Expectation comes from copy_candidates' simulator (central model).
Parsed line shapes: Copycat's chase-log line '_benjitrades | TOKEN | bot time HH:MM | leader bought $X at mcap $Yk | ... -$Z (-P%)', or any
line naming _benjitrades with 'pnl $±Z (±P%)'. Lines naming _benjitrades with a buy but no P&L = open copy. Others listed for manual review."""
import os, re, sys, csv, json, statistics, time
LAB = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, LAB)
LOG = "/workspace/copyfomo/x-watch-log.md"; OUT = os.path.join(LAB, "out/benji_probation.md")
PROBATION_START = "2026-10-23T22:29Z"; STAKE = 6.00; DRAG = 0.05
RULE = dict(n_check=15, budget=-12.0, fill_gap=0.05, fill_gap_n=3)

def sim_expectation():
    try:
        sys.argv = [sys.argv[0]]; import copy_candidates as cc
        trs, _ = cc.load_trades(); R = cc.per_trader([t for t in trs if t["trader"] == "_benjitrades"], 10).get("_benjitrades", [])
        r = [x["ret"] for x in R if x["status"] == "closed"]
        return dict(n=len(r), mean=statistics.fmean(r), median=statistics.median(r), win=sum(x > 0 for x in r) / len(r),
                    stop_share=sum(x <= -0.25 for x in r) / len(r)) if r else None
    except Exception as e:
        print("sim expectation failed:", e); return None

def parse():
    ev, review = [], []
    if not os.path.exists(LOG): return ev, review
    for line in open(LOG):
        if "_benjitrades" not in line: continue
        if re.search(r"CHANGE|edited in place|copies:|Copies on|copies active", line): continue          # settings/status lines, not copies
        m_tok = re.search(r"_benjitrades\s*\|\s*\$?([A-Za-z0-9]{2,15})\s*\|", line)
        m_pnl = re.search(r"pnl\s*\$?\s*([+-]?\$?-?[\d.]+)\s*\(([+-]?[\d.]+)%\)", line) or re.search(r"([+-])\$([\d.]+)\s*\(([+-]?[\d.]+)%", line)
        m_lead = re.search(r"leader bought \$([\d.,]+) at mcap \$([\d.]+)k", line)
        m_bt = re.search(r"bot time (\d{1,2}):(\d{2})", line); m_d = re.search(r"(2026-\d\d-\d\d)", line)
        if not m_tok: review.append(line.strip()); continue
        pnl = pct = None
        if m_pnl:
            g = m_pnl.groups()
            if len(g) == 2: pnl = float(g[0].replace("$", "")); pct = float(g[1]) / 100
            else: pnl = float(g[1]) * (-1 if g[0] == "-" else 1); pct = float(g[2]) / 100
        t_utc = None
        if m_bt:                                                             # Telegram bot times are UTC-4 (Copycat, 2026-10-23)
            h, mi = int(m_bt.group(1)) + 4, int(m_bt.group(2)); t_utc = f"{(m_d.group(1) if m_d else '2026-10-23')}T{h % 24:02d}:{mi:02d}Z"
        ev.append(dict(token=m_tok.group(1), t=t_utc, lead_usd=m_lead.group(1) if m_lead else None, lead_mcap=float(m_lead.group(2)) * 1e3 if m_lead else None,
                       pnl=pnl, pct=pct, raw=line.strip()))
    return ev, review

def main():
    ex = sim_expectation(); ev, review = parse()
    # TRUTH (pre-probation, $9.40): -$2.78 shown on the stop message; /copies realised -$2.81 incl. ~$0.03 gas
    for e in ev:
        if e["token"] == "TRUTH" and e["pnl"] is not None: e["pnl_all"] = -2.81
    rows = []; cum = 0.0; n = 0
    L = [f"# _benjitrades probation tracker ({time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}, PAPER/READ-ONLY, proposals only)", "",
         f"Probation began {PROBATION_START} at ${STAKE:.2f} fixed (Copycat log; Zero's decision). Source: {LOG}. Copies before that are shown as reference only.",
         "Real P&L = the bot's own number (fees and gas included). 'Before drag' adds back the ~5% round-trip cost (2x2% bot fee + ~0.7% pool/route + gas) "
         "to show what the leader-level result was.", ""]
    if ex:
        L += [f"Simulator expectation per copy (central model, {ex['n']} historical copies, 10 s delay): mean {ex['mean']:+.0%} = ${ex['mean']*STAKE:+.2f} at ${STAKE:.0f}; "
              f"median {ex['median']:+.0%} = ${ex['median']*STAKE:+.2f}; win rate {ex['win']:.0%}; {ex['stop_share']:.0%} end at the -25% stop or worse. "
              "The mean is carried by a few big winners: most copies are expected to lose.", ""]
    L += ["| # | token | copy time UTC | leader buy | leader mcap | stake | real P&L $ | real % | before drag % | sim expectation $ (mean / median) | running real $ (probation) | counted |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    gaps = 0
    for i, e in enumerate(ev, 1):
        pre = (e["t"] or "") < PROBATION_START; stake = 9.40 if pre else STAKE
        p = e.get("pnl_all", e["pnl"])
        if p is not None and not pre: cum += p; n += 1
        exp = f"{ex['mean']*stake:+.2f} / {ex['median']*stake:+.2f}" if ex else "-"
        if e["token"] == "TRUTH": exp += " (path sim of this coin: -30.5% = -2.87)"
        L.append(f"| {i} | {e['token']} | {e['t'] or '?'} | {('$' + e['lead_usd']) if e['lead_usd'] else '-'} | {('$%.0fk' % (e['lead_mcap']/1e3)) if e['lead_mcap'] else '-'} | "
                 f"${stake:.2f} | {('%+.2f' % p) if p is not None else 'OPEN'} | {('%+.1f%%' % (100*p/stake)) if p is not None else '-'} | "
                 f"{('%+.1f%%' % (100*(p/stake + DRAG))) if p is not None else '-'} | {exp} | {cum:+.2f} | {'no (pre-probation)' if pre else ('yes' if p is not None else 'when closed')} |")
    if not ev: L.append("| - | no copies logged yet | | | | | | | | | | |")
    exp_cum = (ex["mean"] * STAKE * n) if ex else None
    L += ["", f"**Probation so far: {n} closed copies, real net ${cum:+.2f}** (simulator mean would be ${exp_cum:+.2f}; "
          f"before the 5% drag ${cum + DRAG*STAKE*n:+.2f}).", ""]
    status = "CONTINUE"
    if cum <= RULE["budget"]: status = f"STOP (loss budget ${RULE['budget']:.0f} reached)"
    elif n >= RULE["n_check"]:
        big = any((e.get("pnl_all", e["pnl"]) or 0) / STAKE >= 0.9 for e in ev if (e["t"] or "") >= PROBATION_START)
        status = "PASS -> keep (re-review at 30)" if (cum >= 0 and big) else "STOP (checkpoint failed)"
    L += [f"Rule status: **{status}** (proposal; Zero decides).", "",
          "## Proposed exit rule", "",
          f"1. **Loss budget:** stop as soon as the probation's real net reaches **${RULE['budget']:.0f}** (13% of the $91 balance, about 7 straight stop-outs at $6).",
          f"2. **Checkpoint at {RULE['n_check']} closed copies:** keep only if real net is >= $0 AND at least one copy made >= +90% (a TP hit). Otherwise stop.",
          f"3. **Execution check (any time):** if {RULE['fill_gap_n']} copies fill more than {RULE['fill_gap']:.0%} worse than the simulator on the same coin "
          "(chase or stop slippage), stop. The edge is too thin to absorb more cost.",
          "4. **Cap:** no stake increase during probation, whatever the P&L.", "",
          "Why: the simulated edge (+14% mean, -24% median) comes from about 3 lottery coins in 29. A P&L test over 15 copies can barely tell a real edge "
          "from none. Bootstrap of the simulated copies at $6: if the simulator is right, the rule stops on budget 41% of the time and passes 45%. "
          "With zero edge it stops 50% and passes 35%; with a -5% edge it stops 54% and passes 30%. So this is mainly a **cost cap**: it limits the probation "
          "to about $12 and requires the thing the strategy depends on (a big winner) to show up live. Benji averages about 1 copyable first buy per day, "
          "so 15 copies is about 2-3 weeks.", ""]
    if review:
        L += ["## Lines naming _benjitrades not parsed (check by hand)", ""] + [f"- {x[:220]}" for x in review]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT + ".tmp", "w").write("\n".join(L) + "\n"); os.replace(OUT + ".tmp", OUT); print("benji_probation ->", OUT)

if __name__ == "__main__": main()
