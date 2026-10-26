python3 an/ev2.py "$@" 2>&1 | python3 -c "
import sys,ast
for l in sys.stdin:
  w,_,d=l.partition(' ');
  try: d=ast.literal_eval(d)
  except: print(l.strip());continue
  ok=d.get('med_pct',-1)>0 and d.get('sum_ex_best',-1)>0 and d.get('med_hold',0)>=45
  print('PASS?' if ok else '    ',w[:6],{k:d.get(k) for k in ['span_d','last','sw1h','sw2h','closed','day_share','win','med_pct','sum_sol','sum_ex_best','med_hold','pump_share']})"
