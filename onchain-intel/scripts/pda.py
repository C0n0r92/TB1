"""Pure-python Solana PDA derivation (base58 + ed25519 on-curve test). No dependencies."""
import hashlib
A = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58d(s):
    n = 0
    for c in s: n = n * 58 + A.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big"); return b"\0" * (len(s) - len(s.lstrip("1"))) + b
def b58e(b):
    n = int.from_bytes(b, "big"); s = ""
    while n: n, r = divmod(n, 58); s = A[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s
p = 2**255 - 19; d = (-121665 * pow(121666, p - 2, p)) % p
def on_curve(b):
    y = int.from_bytes(b, "little") & ((1 << 255) - 1)
    if y >= p: return False
    u = (y * y - 1) % p; v = (d * y * y + 1) % p
    x2 = u * pow(v, p - 2, p) % p
    if x2 == 0: return True
    x = pow(x2, (p + 3) // 8, p)
    if (x * x - x2) % p == 0: return True
    x = x * pow(2, (p - 1) // 4, p) % p
    return (x * x - x2) % p == 0
def find_pda(seeds, program):
    pr = b58d(program)
    for bump in range(255, -1, -1):
        h = hashlib.sha256(b"".join(seeds) + bytes([bump]) + pr + b"ProgramDerivedAddress").digest()
        if not on_curve(h): return b58e(h), bump
PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
def bonding_curve(mint): return find_pda([b"bonding-curve", b58d(mint).rjust(32, b"\0")], PUMP)[0]
