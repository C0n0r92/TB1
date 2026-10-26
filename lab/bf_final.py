#!/usr/bin/env python3
"""Concatenate out/backfill_body.md (auto, bf_report.py) + out/backfill_hand.md (hand-written) -> out/backfill.md"""
import os
O = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
open(os.path.join(O, "backfill.md"), "w").write(open(os.path.join(O, "backfill_body.md")).read() + open(os.path.join(O, "backfill_hand.md")).read())
print("wrote out/backfill.md")
