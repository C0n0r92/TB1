import json,collections,urllib.request
j=json.load(urllib.request.urlopen(urllib.request.Request("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",headers={"User-Agent":"Mozilla/5.0"})))
SOL=j['solana']['usd'];print('SOL',SOL)
B=json.load(open('buys.json'))
FOL=set("""4fZFcK8ms3bFMpo1ACzEUz8bH741fQW4zhAMGd5yZMHu 6KR7SorsUQtNH6CB6JpAnWCAKeTysa95iyXeWihdNeGT AH75Bn6QHSt5K2Ad4p1otns3JTwpSJWZTwiwKWNhmnKx Ew4ueQQwA4p5sDf6PqwME54Th4trkQZqJZ2bsEzWqY2y CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o 4vw54BmAogeRV3vPKWyFet5yf8DTLcREzdSzx4rw9Ud9 5hAgYC8TJCcEZV7LTXAzkTrm7YL29YXyQQJPCNrG84zM JDd3hy3gQn2V982mi1zqhNqUw1GfV2UL6g76STojCJPN Beqv6dzTcjV2eodo8RRXCiCcnSYrS1vkQKhfqwHXqeit AGdtsMmphhymH5wYW3dWKSkAxpLYRrNDCTFAfuq8ii9v 9PB1RLFsp65qLJ1SQMmcx2ff8Zn6cPYkYqMCWUfVC3sc 5o3kAZLwEzNF1kfVv8JSEqv6sSB88pZbHxF1oYTxgXzG 5ZuV8eqkvzYFVEKbLvGBdexL2tFv7E5BCd2HZpjqbdg 36A6mEN5rYJdVTb6fMqVvG6ez8g2mTYdr1omWcQ1kDKG DEdEW3SMPU2dCfXEcgj2YppmX9H3bnMDJaU4ctn2BQDQ 4xY9T1Q7foJzJsJ6YZDSsfp9zkzeZsXnxd45SixduMmr""".split())
W=collections.defaultdict(list)
for s,r in B.items():
    for b in r['buys']:
        mc=b['price_sol']*1e9*SOL
        if 0.1<=b['sol']<=50 and mc>=40000:
            W[b['w']].append((s,round(mc),round(r['peak']/mc,1),b['sol'],b['ts']))
multi=sorted(W.items(),key=lambda kv:-len({x[0] for x in kv[1]}))
for w,L in multi[:40]:
    toks={x[0] for x in L}
    print(len(toks),w,'FOLLOWED' if w in FOL else '',[(x[0],x[1],x[2],x[3]) for x in L][:6])
print('followed seen:',[w for w in W if w in FOL])
json.dump({w:L for w,L in W.items()},open('agg.json','w'))
