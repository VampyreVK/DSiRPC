#!/usr/bin/env python3
"""
find_idle.py - where does a game wait for its next interrupt?

DSiRPC's ARM9 half writes the game's data cache back to main RAM in the
game's idle time, from the game's OS_Halt, which rpcprobe finds by its three
ARM instructions (mov r0, #0 / mcr p15, 0, r0, c7, c0, 4 / bx lr) and has the
ARM9 patch. A hello saying a9=1 means none was patched: this tool shows why.
With the game running (DSiRPC closed: only one tool can use UDP port 4244 at
a time), it reads the game's ARM9 code from main RAM over Wi-Fi and lists
every ARM "wait for interrupt" instruction (mcr p15, 0, Rd, c7, c0, 4, with
any register), the words around it, whether it's the exact pattern rpcprobe
looks for, and where it is: the static code rpcprobe searches, or an
autoload block (code the game copies to ITCM or elsewhere when it starts:
the copy in main RAM is read, and the address it runs at is shown). It also
counts the BIOS waits (swi 0x04, 0x05, 0x06) in the same code, and reads
DSiRPC's ARM9 half's block (the copies of OS_Halt rpcprobe listed, how many
it patched, the write-backs done) when main RAM's mirror reaches it.

It only reads. The ARM9's ITCM and DTCM can't be read over Wi-Fi (the ARM7
can't see them); an autoload block's source in main RAM normally stays there
after the game copies it, but if the game reused that memory the scan of it
says so (no hits, or garbage around them). Reading is slow (about 6 KB a
second), so a 1 MB game takes a few minutes.

A game copies its autoload blocks (ITCM's code among them) at boot and
often reuses that memory soon after, so the running game's list can be gone;
--rom reads the same things from the game's .nds file instead (no console,
no Wi-Fi, in a second): the ARM9 binary (unpacked if the SDK compressed it),
its module params and autoload list as they were built.

Usage, from the repo root:
  python tools/find_idle.py                 the game running now
  python tools/find_idle.py --rom "Animal Crossing.nds"   the game's file instead
  python tools/find_idle.py --all-ram       also every other byte of main RAM (about 11 minutes)
  python tools/find_idle.py --save adme     also logs/adme.txt
  python tools/find_idle.py --dsi-ip 192.168.2.186
"""

import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dsirpc_client import DSiClient, _hello_fields, arm9_status  # noqa: E402

MAINRAM_LO, MAINRAM_HI = 0x02000000, 0x02400000
HEADER = 0x023FFE00                     # the cartridge header's copy (0x027FFE00, in main RAM's mirror)
WATCH_SCAN = (0x023FC000, 0x3000)       # the ARM9 cardengine (0x027FC000) in the mirror: DSiRPC's block
OS_HALT = (0xE3A00000, 0xEE070F90, 0xE12FFF1E)   # rpcprobe's pattern (dsirpc_watch_block.h)
NITROCODE = (0xDEC00621, 0x2106C0DE)    # the module params' last two words
WATCH_MAGIC = (0x43505244, 0x39435457)  # "DRPC", "WTC9"
CHUNK = 192 * 16                        # bytes a read_ranges() call takes, in requests of 192
CONTEXT = 4                             # words shown before and after a hit


def words(data):
    return list(struct.unpack(f"<{len(data) // 4}I", data[:len(data) // 4 * 4]))


def is_wfi(w):
    """mcr p15, 0, Rd, c7, c0, 4 (ARM, always): the ARM946's wait for interrupt"""
    return (w & 0xFFFF0FFF) == 0xEE070F90


def wfi_reg(w):
    return (w >> 12) & 0xF


def describe(w):
    """A rough reading of an ARM word, for the context around a hit"""
    rd = (w >> 12) & 0xF
    if w == 0xE12FFF1E:
        return "bx lr"
    if (w & 0x0FFFFFF0) == 0x012FFF10:
        return f"bx r{w & 0xF}" if w >> 28 == 0xE else f"bx(cond) r{w & 0xF}"
    if is_wfi(w):
        return f"mcr p15, 0, r{rd}, c7, c0, 4 (wait for interrupt)"
    if (w & 0xFFFF0FFF) == 0xEE070F9A:
        return f"mcr p15, 0, r{rd}, c7, c10, 4 (drain write buffer)"
    if (w & 0xFFF00000) == 0xE3A00000:
        return f"mov r{rd}, #{w & 0xFF:#x}" + (" (rotated)" if w & 0xF00 else "")
    if (w & 0xFFFF0000) == 0xE92D0000:
        return "push {" + ",".join(f"r{i}" for i in range(16) if w >> i & 1) + "}"
    if (w & 0xFFFF0000) == 0xE8BD0000:
        return "pop {" + ",".join(f"r{i}" for i in range(16) if w >> i & 1) + "}"
    if (w & 0x0F000000) == 0x0B000000:
        return "bl ..." if w >> 28 == 0xE else "bl(cond) ..."
    if (w & 0x0F000000) == 0x0A000000:
        return "b ..." if w >> 28 == 0xE else "b(cond) ..."
    if (w & 0x0FFFFFFF) in (0x0F040000, 0x0F050000, 0x0F060000):
        return f"swi {w >> 16 & 0xFF:#04x}"
    if (w & 0xFFF00000) == 0xE5900000:
        return "ldr ..."
    if (w & 0xFFF00000) == 0xE5800000:
        return "str ..."
    return ""


def classify(data, base, run_base=None):
    """Every wait-for-interrupt instruction in `data` (ARM code read from
    `base`; it runs at `run_base`, if that's elsewhere): [{'at' (where it
    is in main RAM), 'runs_at', 'reg', 'exact' (rpcprobe's pattern, at the
    word before it), 'shape' (the same three instructions with another
    register), 'context': [(address, word)] }]"""
    run_base = base if run_base is None else run_base
    ws = words(data)
    hits = []
    for i, w in enumerate(ws):
        if not is_wfi(w):
            continue
        rd = wfi_reg(w)
        before = ws[i - 1] if i else None
        after = ws[i + 1] if i + 1 < len(ws) else None
        exact = (before, w, after) == OS_HALT
        shape = before == (0xE3A00000 | rd << 12) and after == 0xE12FFF1E
        lo, hi = max(0, i - CONTEXT), min(len(ws), i + CONTEXT + 1)
        hits.append({"at": base + 4 * i, "runs_at": run_base + 4 * i, "reg": rd, "exact": exact, "shape": shape,
                     "context": [(run_base + 4 * k, ws[k]) for k in range(lo, hi)]})
    return hits


def bios_waits(data):
    """{0x04: n, 0x05: n, 0x06: n}: ARM swi IntrWait / VBlankIntrWait / Halt"""
    out = {0x04: 0, 0x05: 0, 0x06: 0}
    for w in words(data):
        if (w & 0x0FFFFFFF) in (0x0F040000, 0x0F050000, 0x0F060000):
            out[w >> 16 & 0xFF] += 1
    return out


def thumb_waits(data, base):
    """Thumb BIOS wait stubs: swi 0x04 / 0x05 / 0x06 (IntrWait,
    VBlankIntrWait, Halt) followed by bx lr, as the SDK's and libnds' BIOS
    calls are. [(address, swi number)]. In a scan of code this can still
    be data that happens to look like it."""
    hs = struct.unpack(f"<{len(data) // 2}H", data[:len(data) // 2 * 2])
    return [(base + 2 * i, h & 0xFF) for i, h in enumerate(hs[:-1])
            if h in (0xDF04, 0xDF05, 0xDF06) and hs[i + 1] == 0x4770]


def show_waits(data, base):
    """The BIOS waits in this code: ARM swi (any), Thumb stubs (swi + bx lr)"""
    arm = bios_waits(data)
    thumb = thumb_waits(data, base)
    print(f"  BIOS waits: ARM swi IntrWait {arm[4]}, VBlankIntrWait {arm[5]}, Halt {arm[6]}; "
          f"Thumb stubs (swi + bx lr, possibly data) {len(thumb)}"
          + (": " + ", ".join(f"0x{a:08X} (swi {n:#04x})" for a, n in thumb[:8]) if thumb else ""))
    return sum(arm.values()) + len(thumb)


def find_params(data, base):
    """The module params (NitroSDK's crt0): {'at', 'autoload_list',
    'autoload_list_end', 'autoload_start', 'bss_start', 'bss_end',
    'compressed_end', 'sdk_version'} or None"""
    ws = words(data)
    for i in range(7, len(ws) - 1):
        if (ws[i], ws[i + 1]) == NITROCODE:
            p = ws[i - 7:i]
            return {"at": base + 4 * (i - 7), "autoload_list": p[0], "autoload_list_end": p[1],
                    "autoload_start": p[2], "bss_start": p[3], "bss_end": p[4], "compressed_end": p[5],
                    "sdk_version": p[6]}
    return None


def autoload_blocks(list_data, start):
    """The autoload list: [(runs at, size, bss size, source in main RAM)],
    the sources one after another from autoload_start"""
    out, src = [], start
    ws = words(list_data)
    for i in range(0, len(ws) - 2, 3):
        dest, size, bss = ws[i:i + 3]
        out.append((dest, size, bss, src))
        src += size
    return out


def plausible(blocks):
    """An autoload list as built: every block runs in ITCM, DTCM or main RAM
    and isn't huge. A running game may have reused the list's memory."""
    return bool(blocks) and all(region(d) != "elsewhere" and n <= 0x100000 and bss <= 0x400000
                                for d, n, bss, _ in blocks)


def blz_unpack(data, compressed_end):
    """The ARM9 binary as it is once it runs: the SDK's backwards LZ ("BLZ",
    which crt0 unpacks in place) undone, or `data` if compressed_end is 0.
    compressed_end is an offset into data here."""
    if not compressed_end:
        return data
    end = compressed_end
    enc_len = int.from_bytes(data[end - 8:end - 5], "little")
    hdr_len = data[end - 5]
    inc_len = int.from_bytes(data[end - 4:end], "little")
    start = end - enc_len                    # before this, the binary is stored as it is
    out = bytearray(data[:start]) + bytearray(enc_len + inc_len)
    raw, pak = len(out), end - hdr_len
    flags = mask = 0
    while raw > start:
        mask >>= 1
        if not mask:
            if pak <= start:
                break
            pak -= 1
            flags, mask = data[pak], 0x80
        if not flags & mask:
            if pak <= start:
                break
            pak -= 1
            raw -= 1
            out[raw] = data[pak]
        else:
            if pak - 2 < start:
                break
            pos = data[pak - 1] << 8 | data[pak - 2]
            pak -= 2
            n, back = (pos >> 12) + 3, (pos & 0xFFF) + 3
            for _ in range(min(n, raw - start)):
                raw -= 1
                out[raw] = out[raw + back]
    return bytes(out) + data[end:]


def region(addr):
    if 0x01FF8000 <= addr < 0x02000000:
        return "ITCM"
    if 0x027E0000 <= addr < 0x02800000 or 0x0B000000 <= addr < 0x0B004000:
        return "DTCM"
    if MAINRAM_LO <= addr < 0x03000000:
        return "main RAM"
    return "elsewhere"


def sdk(v):
    return f"{v >> 24}.{v >> 16 & 0xFF:02d} (build {v & 0xFFFF})" if v else "unknown"


class Reader:
    def __init__(self, client):
        self.c = client
        self.done = 0

    def read(self, addr, n, label=None):
        """Main RAM only; slow, so with a progress line"""
        out = bytearray()
        t0 = time.time()
        for off in range(0, n, CHUNK):
            k = min(CHUNK, n - off)
            out += self.c.read_ranges([(addr + off, k)])[0]
            if label and time.time() - t0 > 2:   # (the terminal only, not --save's file)
                sys.__stdout__.write(f"\r  {label}: {100 * (off + k) // n}%")
                sys.__stdout__.flush()
        if label and time.time() - t0 > 2:
            sys.__stdout__.write("\n")
        self.done += n
        return bytes(out)


def show_hits(hits, where):
    for h in hits:
        kind = ("rpcprobe's exact pattern (OS_Halt)" if h["exact"] else
                f"OS_Halt's shape, with r{h['reg']}" if h["shape"] else "elsewhere in a function")
        at = f"0x{h['runs_at']:08X}" + (f" (its copy at 0x{h['at']:08X})" if h["runs_at"] != h["at"] else "")
        print(f"  {at} [{where}, {region(h['runs_at'])}]: {kind}")
        for a, w in h["context"]:
            mark = ">" if a == h["runs_at"] else " "
            print(f"   {mark} 0x{a:08X}  {w:08X}  {describe(w)}")


def run(args):
    try:
        c = DSiClient(port=args.port, dsi_ip=args.dsi_ip)
    except OSError:
        print(f"UDP port {args.port} is in use: close DSiRPC (or the other tool using it) first.")
        sys.exit(1)
    if not c.wait_for_dsi():
        print("No hello from the DSi within 15 s - is the game running (and DSiRPC closed)?")
        sys.exit(1)
    if c.game is None:
        c.listen(2.5)
    f = _hello_fields(c.last_hello or "")
    print(f"Game: {f.get('gc', '?')} (version {f.get('v', '?')})")
    print("ARM9 half: " + (arm9_status(f) or "not reported by this build") +
          f" [a9={f.get('a9', '-')} a9s={f.get('a9s', '-')}]")
    r = Reader(c)

    # Where the static code is: the header's copy, else NitroSDK's usual 0x02000000
    head = r.read(HEADER, 0x40)
    dest, size = struct.unpack_from("<II", head, 0x28)
    if MAINRAM_LO <= dest < MAINRAM_HI and 0 < size <= MAINRAM_HI - dest:
        print(f"ARM9 binary (from the header at 0x{HEADER:08X}): 0x{dest:08X}, 0x{size:X} bytes as stored")
    else:
        dest, size = MAINRAM_LO, 0x100000
        print(f"No cartridge header at 0x{HEADER:08X}: assuming the ARM9 binary starts at 0x{dest:08X}")
    first = r.read(dest, 0x8000, "looking for the module params")
    params = find_params(first, dest)
    blocks = []
    if params:
        print(f"Module params at 0x{params['at']:08X}: SDK {sdk(params['sdk_version'])}, static code up to "
              f"0x{params['autoload_start']:08X}, autoload list 0x{params['autoload_list']:08X}-"
              f"0x{params['autoload_list_end']:08X}, bss 0x{params['bss_start']:08X}-0x{params['bss_end']:08X}")
        end = params["autoload_start"]
        lst = params["autoload_list"], params["autoload_list_end"]
        if MAINRAM_LO <= lst[0] < lst[1] <= MAINRAM_HI and lst[1] - lst[0] <= 0x300:
            blocks = autoload_blocks(r.read(lst[0], lst[1] - lst[0]), params["autoload_start"])
            if not plausible(blocks):
                print("  the autoload list was overwritten since boot (the game reused that memory), so its "
                      "blocks can't be read at runtime: --rom reads them from the game's file")
                blocks = []
            for d, n, bss, src in blocks:
                print(f"  autoload block: runs at 0x{d:08X} ({region(d)}), 0x{n:X} bytes (+0x{bss:X} bss), "
                      f"source in main RAM at 0x{src:08X}")
    else:
        end = dest + size
        print("No module params in the first 32 KB: scanning the size the header gives")
    if not (dest < end <= MAINRAM_HI):
        end = min(dest + size, MAINRAM_HI)

    print(f"\nStatic code 0x{dest:08X}-0x{end:08X} (what rpcprobe searches), {(end - dest) // 1024} KB:")
    static = first[:end - dest] if end - dest <= len(first) else first + r.read(dest + len(first),
                                                                                 end - dest - len(first), "reading")
    hits = classify(static, dest)
    show_hits(hits, "static")
    if not hits:
        print("  no wait-for-interrupt instruction")
    waits = show_waits(static, dest)
    all_hits = list(hits)
    for d, n, _, src in blocks:
        if not n or not (MAINRAM_LO <= src and src + n <= MAINRAM_HI) or n > 0x40000:
            continue
        print(f"\nAutoload block for 0x{d:08X} ({region(d)}), read from its source at 0x{src:08X}:")
        data = r.read(src, n, "reading")
        bh = classify(data, src, d)
        show_hits(bh, "autoload")
        if not bh:
            print("  no wait-for-interrupt instruction")
        all_hits += bh

    if args.all_ram:
        print("\nThe rest of main RAM (0x02000000-0x02400000 outside the static code), any register:")
        rest = []
        for lo, hi in ((MAINRAM_LO, dest), (end, MAINRAM_HI)):
            if hi > lo:
                data = r.read(lo, hi - lo, "reading main RAM")
                rest += classify(data, lo)
                waits += show_waits(data, lo)
        show_hits(rest, "main RAM")
        if not rest:
            print("  no wait-for-interrupt instruction")
        all_hits += rest

    # DSiRPC's ARM9 half's block, if main RAM's mirror reaches it
    scan = r.read(*WATCH_SCAN)
    ws = words(scan)
    for i in range(0, len(ws) - 15, 8):
        if (ws[i], ws[i + 1]) == WATCH_MAGIC:
            halt_at = [a for a in ws[i + 3:i + 7] if a]
            print(f"\nDSiRPC's ARM9 half's block at 0x{WATCH_SCAN[0] + 4 * i:08X}: version {ws[i + 2] & 0xFFFF}, "
                  f"asked {ws[i + 2] >> 16} time(s), OS_Halt copies listed {len(halt_at)} "
                  f"({', '.join(f'0x{a:08X}' for a in halt_at) or 'none'}), patched {ws[i + 9]}, "
                  f"write-backs {ws[i + 8]}")
            break
    else:
        print("\nDSiRPC's ARM9 half's block isn't readable over Wi-Fi on this console (not in main RAM's mirror)")

    summary(all_hits, hits, waits)


def summary(all_hits, static_hits, waits=0):
    exact = [h for h in all_hits if h["exact"]]
    print("\nIn short: ", end="")
    if exact:
        where = {("static" if h in static_hits else "autoload") for h in exact}
        print(f"{len(exact)} copy(ies) of rpcprobe's exact OS_Halt pattern, in {' and '.join(sorted(where))} code"
              + (" (rpcprobe only searches the static code)" if where == {"autoload"} else ""))
    elif any(h["shape"] for h in all_hits):
        print("OS_Halt's shape with another register: rpcprobe's pattern needs r0")
    elif all_hits:
        print("wait-for-interrupt instructions, but none in OS_Halt's three-instruction shape")
    elif waits:
        print("no wait-for-interrupt instruction in the code read, but BIOS waits (above): the game may wait through "
              "the BIOS instead")
    else:
        print("no wait-for-interrupt instruction and no BIOS wait in the code read: its idle call is somewhere this "
              "didn't read (ITCM can't be read over Wi-Fi: try --rom with the game's file)")


def scan_rom(path):
    """The same report from the game's .nds file: its ARM9 binary as it runs
    (unpacked), the static code and every autoload block as built"""
    with open(path, "rb") as fh:
        rom = fh.read()
    code = rom[0x0C:0x10].decode("ascii", "replace")
    off, _, dest, size = struct.unpack_from("<IIII", rom, 0x20)
    print(f"Game: {code} (version {rom[0x1E]:02X}), from {os.path.basename(path)}")
    print(f"ARM9 binary: 0x{size:X} bytes at file offset 0x{off:X}, runs at 0x{dest:08X}")
    binary = rom[off:off + size]
    params = find_params(binary[:0x8000], dest)
    if not params:
        print("No module params in the first 32 KB: scanning the binary as stored")
        hits = classify(binary, dest)
        show_hits(hits, "static")
        summary(hits, hits)
        return hits
    print(f"Module params at 0x{params['at']:08X}: SDK {sdk(params['sdk_version'])}"
          + (f", compressed up to 0x{params['compressed_end']:08X}" if params["compressed_end"] else ""))
    if params["compressed_end"]:
        binary = blz_unpack(binary, params["compressed_end"] - dest)
        print(f"  unpacked: 0x{len(binary):X} bytes")

    def at(a):
        return a - dest
    static = binary[:at(params["autoload_start"])]
    blocks = autoload_blocks(binary[at(params["autoload_list"]):at(params["autoload_list_end"])],
                             params["autoload_start"])
    print(f"\nStatic code 0x{dest:08X}-0x{params['autoload_start']:08X} (what rpcprobe searches), "
          f"{len(static) // 1024} KB:")
    hits = classify(static, dest)
    show_hits(hits, "static")
    if not hits:
        print("  no wait-for-interrupt instruction")
    waits = show_waits(static, dest)
    all_hits = list(hits)
    for d, n, bss, src in blocks:
        print(f"\nAutoload block: runs at 0x{d:08X} ({region(d)}), 0x{n:X} bytes (+0x{bss:X} bss), "
              f"in the binary at 0x{src:08X}:")
        bh = classify(binary[at(src):at(src) + n], src, d)
        show_hits(bh, "autoload")
        if not bh:
            print("  no wait-for-interrupt instruction")
        waits += show_waits(binary[at(src):at(src) + n], d)
        all_hits += bh
    summary(all_hits, hits, waits)
    return all_hits


def main():
    ap = argparse.ArgumentParser(description="List where a game waits for interrupts (why a9=1)")
    ap.add_argument("--rom", metavar="FILE", help="read the game's .nds file instead of the console")
    ap.add_argument("--all-ram", action="store_true",
                    help="also scan the rest of main RAM for wait-for-interrupt instructions (about 11 minutes)")
    ap.add_argument("--dsi-ip", help="the IP the launcher shows; skips waiting for a hello packet")
    ap.add_argument("--port", type=int, default=4244, help="UDP port (the DSi always uses 4244)")
    ap.add_argument("--save", metavar="NAME", help="also write this report to logs/NAME.txt")
    args = ap.parse_args()
    go = (lambda: scan_rom(args.rom)) if args.rom else (lambda: run(args))
    if not args.save:
        go()
        return
    from frame_check import Tee, log_paths, shown
    _, path = log_paths(args.save)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as report:
        sys.stdout = Tee(sys.stdout, report)
        try:
            go()
        finally:
            sys.stdout.flush()
            sys.stdout = sys.stdout.stream
    print(f"Saved this report to {shown(path)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stdout = sys.__stdout__
        print("\nStopped.")
        sys.exit(130)
