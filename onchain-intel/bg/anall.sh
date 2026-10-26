for w in $(cat ftb*.log | grep " need " | awk '{print $1}' | sort -u); do
  full=$(ls tx/ | grep "^$w" | sed 's/.jsonl//')
  [ -z "$full" ] && continue
  [ -f an/$full.json ] && [ an/$full.json -nt tx/$full.jsonl ] && continue
  SNIPE=1 python3 an24.py $full
done
