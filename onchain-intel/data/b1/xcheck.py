import json,sys,os
sys.path.insert(0,"scripts")
os.environ["SCOUT_PUBLIC_FIRST"]="1"; os.environ["SCOUT_HELIUS_BUDGET_FILE"]="/tmp/b1budget.json"
import sol, pda
MOUS="J9WL4zQVCFvLTydjtHoMGcLasjhRMZomnVmp4Y2cpump"; TP="TokenkegQfeZyiNwAJbNbGqPXZRvb6Jm1dPfhzoN5Tc"; T22="TokenzQdBNbLqP5VEhdkAS6EPFLC1PeYGWG6ShZoTM8bG"
f=sys.argv[1]
rows=json.load(open(f)); owners=sorted({r["owner"] for r in rows if r.get("truth",0)>0 and r.get("usdc",0)<0 or (r.get("truth",0)>0 and r.get("sol",0)<0 and r["owner"]!="GUkDEvSyoJJ5yFHUYKuePjwTTAZYLBmWsHQ2fYaCMKYm")})
from oc_ata import ata
