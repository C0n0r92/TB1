import json,urllib.request,sys,time
U='https://api.mainnet-beta.solana.com'
def rpc(m,p):
    for i in range(6):
        try:
            r=urllib.request.Request(U,json.dumps({"jsonrpc":"2.0","id":1,"method":m,"params":p}).encode(),{'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
            return json.load(urllib.request.urlopen(r,timeout=30)).get('result')
        except Exception as e: time.sleep(3*(i+1))
for line in sys.argv[1:]:
    w,m,sig=line.split(':')
    tx=rpc('getTransaction',[sig,{"encoding":"jsonParsed","maxSupportedTransactionVersion":1}])
    slot=tx['slot']; logs=tx['meta']['logMessages'] or []
    create=any('Instruction: Create' in l or 'InitializeMint' in l for l in logs)
    signer=[a['pubkey'] for a in tx['transaction']['message']['accountKeys'] if a.get('signer')]
    s=rpc('getSignaturesForAddress',[m,{"before":sig,"limit":1000}]) or []
    first=s[-1] if s else None
    print(w[:6],m[:6],'entry_slot',slot,'create_in_tx',create,'signers',[x[:6] for x in signer],'n_prior_sigs',len(s),'oldest_prior_slot',first and first['slot'],'slot_gap',first and slot-first['slot'],'oldest_sig',first and first['signature'][:20])
    time.sleep(2)
