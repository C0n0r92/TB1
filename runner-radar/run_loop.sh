#!/usr/bin/env bash
# Paper-only collector: scan every 10 min, grade every hour, stop after HOURS (default 12).
# variants.py: --snapshot-only after every scan (point-in-time copies of Pulse/Scout files + holder capture),
# full paper-variant grading hourly (variants_latest.txt, variants.csv). Errors -> variants.log.
cd "$(dirname "$0")"
HOURS=${1:-12}; END=$(( $(date +%s) + HOURS*3600 )); i=0
while [ "$(date +%s)" -lt "$END" ]; do
  python3 scan.py >> scan.log 2>&1
  python3 variants.py --snapshot-only >> variants.log 2>&1
  if [ $((i % 6)) -eq 0 ]; then
    python3 grade.py > grade_latest.txt 2>&1
    python3 variants.py > /dev/null 2>> variants.log
  fi
  i=$((i+1)); sleep 600
done
python3 grade.py > grade_latest.txt 2>&1
python3 variants.py > /dev/null 2>> variants.log
