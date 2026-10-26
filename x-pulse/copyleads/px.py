import json,sys
def load(fn):
    s=open(fn).read(); i=s.find('{'); dec=json.JSONDecoder(); d,end=dec.raw_decode(s[i:]); rest=s[i+end:]
    return d,rest
if __name__=='__main__':
    d,rest=load(sys.argv[1]); print('REST:',rest.strip()[:400].replace('\n',' '))
    u={x['id']:x for x in d.get('includes',{}).get('users',[])}
    if 'data' in d and isinstance(d['data'],dict): d['data']=[d['data']]
    for p in d.get('data',[]):
        if 'text' not in p:
            print('USER',p.get('username'),p.get('id'),p.get('public_metrics',{}).get('followers_count'),p.get('created_at','')[:10],(p.get('description') or '')[:200].replace('\n',' ')); continue
        a=u.get(p.get('author_id'),{}); print('@'+a.get('username','?'),a.get('public_metrics',{}).get('followers_count'),a.get('created_at','')[:10],'|',p['created_at'][:16],p.get('url'),'|',p['text'][:260].replace('\n',' '))
