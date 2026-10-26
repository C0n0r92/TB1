#!/usr/bin/env python3
"""Build + sign + simulateTransaction (NEVER sendTransaction) a tiny SOL->token Jupiter swap from the bot wallet."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selfcopy, live as L
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import Transaction, VersionedTransaction
from solders.hash import Hash
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
b = selfcopy.Bot(tag="simtest-"); lv = L.Live(b, selfcopy.HERE, False)
lv.send_and_confirm = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("send disabled in test"))   # belt and braces
print("wallet", lv.pub, "SOL balance", lv.get_sol())
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
q, err = lv.jq(L.WSOL, BONK, 1_000_000, 500); assert q, err
built, err = lv.build(q, True, 500); assert built, err
print("built: guard OK, dynamic slippage bps", built["slip"], "priority lamports", built["prio"])
stx = lv.sign(built["tx"])
print("signed by bot wallet:", str(stx.message.account_keys[0]) == lv.pub, "sig", str(stx.signatures[0])[:16] + "…")
sim = lv.simulate(stx)
print("simulateTransaction err:", json.dumps(sim["value"]["err"]) if sim else None)
print("sim logs tail:", (sim or {}).get("value", {}).get("logs", [])[-2:] if sim else None)
# USDC -> SOL conversion swap ($84, 1% cap) built for the bot wallet, guard-checked, signed, simulated (never sent)
q2, err = lv.jq(L.USDC, L.WSOL, 84_000_000, 100); assert q2, err
built2, err = lv.build(q2, True, 100); assert built2, err
ks = [str(k) for k in built2["tx"].message.account_keys]
print("USDC->SOL built: guard OK, programs", sorted({ks[ix.program_id_index][:6] for ix in built2["tx"].message.instructions}), "slip bps", built2["slip"], "quote out SOL", int(q2["outAmount"]) / 1e9)
sim2 = lv.simulate(lv.sign(built2["tx"]))
print("USDC->SOL simulateTransaction err:", json.dumps(sim2["value"]["err"]) if sim2 else None)
# guard negative tests: a transfer of SOL to any other address must be refused before signing
me = Pubkey.from_string(lv.pub); evil = Pubkey.new_unique(); h = Hash.default()
for name, ix in [("SOL transfer to stranger", transfer(TransferParams(from_pubkey=me, to_pubkey=evil, lamports=1))),
                 ("token transfer", Instruction(Pubkey.from_string(L.TOKEN), bytes([3]) + (1).to_bytes(8, "little"), [AccountMeta(evil, False, True), AccountMeta(evil, False, True), AccountMeta(me, True, False)])),
                 ("closeAccount to stranger", Instruction(Pubkey.from_string(L.TOKEN), bytes([9]), [AccountMeta(evil, False, True), AccountMeta(evil, False, True), AccountMeta(me, True, False)])),
                 ("unknown program", Instruction(evil, b"", [AccountMeta(me, True, True)]))]:
    vt = VersionedTransaction.from_legacy(Transaction.new_unsigned(Message.new_with_blockhash([ix], me, h)))
    okk, why = L.verify_swap_tx(vt, lv.pub, lv.wsol_ata)
    print(f"guard rejects {name}: {not okk} ({why})"); assert not okk
okk, _ = L.verify_swap_tx(VersionedTransaction.from_legacy(Transaction.new_unsigned(Message.new_with_blockhash(
    [transfer(TransferParams(from_pubkey=me, to_pubkey=Pubkey.from_string(lv.wsol_ata), lamports=1))], me, h))), lv.pub, lv.wsol_ata)
print("guard allows wrap into own wSOL account:", okk); assert okk
print("repr of Live object:", repr(lv))
