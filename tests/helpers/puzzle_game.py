"""A made-up puzzle game writing gen_set.py's memory map, frame by frame,
plus rcheevos as the ground truth to check the console's checker and the PC
side against."""

import random

RAM_SIZE = 0x400000


class Game:
    """The game: step() is one frame. Pauses now and then (nothing changes
    for a while), switches modes, scores, flips bits, moves a pointer."""

    def __init__(self, ram, seed):
        self.ram = ram
        self.r = random.Random(seed)
        self.paused = 0
        self.tspin_left = 0
        self.ptr_targets = [0x310000, 0x320000]
        self.w32(0x200, 0x02000000 + self.ptr_targets[0])

    def w8(self, a, v): self.ram[a] = v & 0xFF
    def w16(self, a, v): self.ram[a:a + 2] = (v & 0xFFFF).to_bytes(2, "little")
    def w32(self, a, v): self.ram[a:a + 4] = (v & 0xFFFFFFFF).to_bytes(4, "little")
    def r8(self, a): return self.ram[a]
    def r16(self, a): return int.from_bytes(self.ram[a:a + 2], "little")
    def r32(self, a): return int.from_bytes(self.ram[a:a + 4], "little")

    def step(self):
        r = self.r
        if self.paused:
            self.paused -= 1
            return
        if r.random() < 0.004:
            self.paused = r.randrange(5, 400)
            return
        if self.tspin_left:
            self.tspin_left -= 1
            if not self.tspin_left:
                self.w8(0x112, 0)
        mode = self.r8(0x100)
        if r.random() < (0.01 if mode != 1 else 0.002):
            self.w8(0x100, r.choice([0, 1, 1, 2, 3]))
            mode = self.r8(0x100)
            if mode == 1 and r.random() < 0.5:
                self.w16(0x104, 0)
        if mode == 1:
            self.w32(0x114, self.r32(0x114) + 1)
            if r.random() < 0.04:
                self.w8(0x110, r.randrange(7))
            if r.random() < 0.05:
                self.w8(0x111, r.randrange(4))
            if r.random() < 0.02:
                self.w16(0x104, self.r16(0x104) + r.randrange(1, 5))
                self.w32(0x108, self.r32(0x108) + r.randrange(100, 5000))
                self.w8(0x10C, self.r16(0x104) // 10)
                if self.r8(0x110) == 6 and r.random() < 0.5:
                    self.w8(0x112, 1)
                    self.tspin_left = r.choice([1, 1, 1, 2, 3])
            if r.random() < 0.03:
                self.w8(0x118, r.randrange(10))
        if r.random() < 0.03:
            self.w8(0x300 + r.randrange(48), r.randrange(256) if r.random() < 0.5 else r.randrange(4))
        if r.random() < 0.005:
            self.w8(0x11A, self.r8(0x11A) ^ (1 << r.randrange(8)))
        if r.random() < 0.004:
            self.w16(0x120, int(str(r.randrange(100)), 16))
        if r.random() < 0.002:
            self.w32(0x200, 0x02000000 + r.choice(self.ptr_targets))
        if r.random() < 0.02:
            t = r.choice(self.ptr_targets)
            self.w8(t + r.randrange(0x40), r.randrange(16))


def peek_from(ram):
    """rcheevos' memory reader over `ram` (RetroAchievements addresses)."""
    def peek(a, n):
        if a + n > RAM_SIZE:
            return 0
        return int.from_bytes(ram[a:a + n], "little")
    return peek


def rc_runtime(achievements):
    """An rcheevos runtime with [(id, MemAddr)] active: the ground truth."""
    from core import rcheevos
    rt = rcheevos.Runtime()
    for aid, memaddr in achievements:
        rt.activate_achievement(aid, memaddr)
    return rt
