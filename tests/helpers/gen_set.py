"""Synthetic RetroAchievements sets for testing DSiRPC's checker.

make_set(n, seed) -> RA JSON dict (PatchData form) for a made-up puzzle game
with the usual RA shapes: thresholds with delta checks, mode checks, ResetIf
challenges with hit latches, hit counts, pointer chains (AddAddress),
AddSource sums, alt groups, bit flags, BCD, OrNext/AndNext, PauseIf.
fuzz_set(n, seed) -> random conditions over every size, prefix and flag,
to compare the console's checker with rcheevos on shapes nobody wrote.

Memory map (RetroAchievements addresses):
  0x100 mode (8)        0x104 lines (16)      0x108 score (32)
  0x10C level (8)       0x110 piece (8)       0x111 rotation (8)
  0x112 tspin flag (8)  0x114 timer (32)      0x118 combo (8)
  0x11A flags (8)       0x120 coins BCD (16)  0x200 pointer (32) -> struct
  0x300.. misc bytes
"""

import random

T_SPIN_SINGLE = 900001
ONE_HAND = 900002


def make_set(n=200, seed=1):
    r = random.Random(seed)
    achs = []

    def add(memaddr, title):
        achs.append({"ID": 900000 + len(achs) + 1, "Title": title, "Description": title, "Points": r.choice([1, 2, 3, 5, 10]),
                     "MemAddr": memaddr, "Flags": 3, "BadgeName": "00000"})

    # The two from the bug report
    add("0xH0100=1_0xH0110=6_0xH0112=1_0x 0104>d0x 0104", "T-Spin Single")
    add("0xH0100=1_d0xH0100=0.1._R:0xH0111!=d0xH0111_R:0xH0100!=1_0x 0104>=10", "Look Ma, One Hand")

    misc = [0x300 + i for i in range(48)]
    while len(achs) < n:
        k = r.randrange(12)
        v = r.randrange(1, 200)
        a = r.choice(misc)
        b = r.choice(misc)
        if k == 0:
            add(f"0xH{a:04x}>={v}_d0xH{a:04x}<{v}", "threshold")
        elif k == 1:
            add(f"0xH0100={r.randrange(4)}_0x 0104>={v}_d0x 0104<{v}", "lines in mode")
        elif k == 2:
            add(f"0xH0100=1_d0xH0100=0.1._R:0xH{a:04x}!=d0xH{a:04x}_0xX0108>={v * 1000}", "challenge")
        elif k == 3:
            add(f"0xH0118>={r.randrange(2, 9)}.{r.randrange(2, 90)}._R:0xH0100!=1", "hold combo")
        elif k == 4:
            off = r.randrange(0, 0x40)
            add(f"I:0xX0200_0xH{off:04x}={v & 15}_I:0xX0200_d0xH{off:04x}!={v & 15}", "pointer")
        elif k == 5:
            add(f"A:0xH{a:04x}_A:0xH{b:04x}_0xH{r.choice(misc):04x}>={v}", "sum")
        elif k == 6:
            add(f"0xH0100=2S0xH{a:04x}={v & 7}S0xH{b:04x}={v & 7}", "alts")
        elif k == 7:
            bit = "MNOPQRST"[r.randrange(8)]
            add(f"0x{bit}011a=1_d0x{bit}011a=0", "bit flag")
        elif k == 8:
            add(f"b0xH0120>={v % 99}_0xH0100=1", "bcd coins")
        elif k == 9:
            add(f"O:0xH{a:04x}=1_0xH{b:04x}=1_0xH0100=1", "or next")
        elif k == 10:
            add(f"P:0xH0100!=1_0xH0114>={v * 60}.1._0xH{a:04x}={v & 3}", "pause")
        else:
            add(f"N:0xH{a:04x}={v & 3}_0xH{b:04x}={v & 3}.{r.randrange(1, 5)}._R:0xH0110=0", "and next hits")
    return {"Success": True, "PatchData": {"ID": 99999, "Title": "Test Puzzle DS", "ConsoleID": 18,
                                            "RichPresencePatch": "", "Achievements": achs, "Leaderboards": []}}



ADDRS = [0x100, 0x104, 0x108, 0x10C, 0x110, 0x111, 0x112, 0x114, 0x118, 0x11A, 0x120] + [0x300 + i for i in range(48)]
SIZES = ["H", " ", "X", "W", "L", "U", "M", "N", "O", "P", "Q", "R", "S", "T", "K", "I", "J", "G"]


def _operand(r, allow_const=True):
    if allow_const and r.random() < 0.35:
        return str(r.randrange(0, 20)) if r.random() < 0.8 else f"h{r.randrange(256):x}"
    pre = r.choice(["", "", "", "d", "p", "b", "~"])
    size = r.choice(SIZES)
    if pre == "b" and size not in ("H", " ", "X", "W"):
        pre = ""
    return f"{pre}0x{size}{r.choice(ADDRS):04x}"


def _cond(r, flag):
    a = _operand(r, allow_const=False)
    if flag in ("A:", "B:", "I:", "K:"):
        if r.random() < 0.5:
            return f"{flag}{a}{r.choice(['*', '/', '&', '^', '%', '+', '-'])}{_operand(r)}"
        return f"{flag}{a}"
    op = r.choice(["=", "!=", "<", "<=", ">", ">="])
    hits = f".{r.randrange(1, 6)}." if r.random() < 0.2 else ""
    return f"{flag}{a}{op}{_operand(r)}{hits}"


def fuzz_set(n=200, seed=1):
    r = random.Random(seed)
    achs = []
    while len(achs) < n:
        groups = []
        for g in range(r.choice([1, 1, 1, 2, 3])):
            conds = []
            for _ in range(r.randrange(1, 6)):
                flag = r.choice(["", "", "", "R:", "P:", "A:", "B:", "C:", "D:", "N:", "O:", "Z:", "I:", "K:", "M:", "T:", "Q:"])
                conds.append(_cond(r, flag))
            if conds[-1][:2] in ("A:", "B:", "I:", "K:", "N:", "O:", "Z:", "C:", "D:"):
                conds.append(_cond(r, ""))
            groups.append("_".join(conds))
        achs.append({"ID": 800000 + len(achs), "Title": "fuzz", "Description": "fuzz", "Points": 1,
                     "MemAddr": "S".join(groups), "Flags": 3, "BadgeName": "00000"})
    return {"Success": True, "PatchData": {"ID": 99998, "Title": "Fuzz DS", "ConsoleID": 18,
                                            "RichPresencePatch": "", "Achievements": achs, "Leaderboards": []}}
