"""tools/find_idle.py's reading of ARM code, on made-up buffers: where a
wait-for-interrupt instruction is, whether it's rpcprobe's exact OS_Halt
pattern or the same shape with another register or somewhere else, the
module params and autoload list, and the BIOS waits. (Reading a console
needs one; this is what it makes of what it reads.)"""

import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import find_idle as fi  # noqa: E402

PUSH, POP, NOP = 0xE92D4010, 0xE8BD8010, 0xE1A00000


def code(*ws):
    return struct.pack(f"<{len(ws)}I", *ws)


def test_exact_os_halt():
    data = code(NOP, NOP, 0xE3A00000, 0xEE070F90, 0xE12FFF1E, NOP)
    [h] = fi.classify(data, 0x02001000)
    assert h["at"] == h["runs_at"] == 0x0200100C
    assert h["exact"] and h["shape"] and h["reg"] == 0
    assert [a for a, _ in h["context"]][0] == 0x02001000 and len(h["context"]) == 6


def test_same_shape_another_register():
    [h] = fi.classify(code(0xE3A01000, 0xEE071F90, 0xE12FFF1E), 0x02000000)
    assert not h["exact"] and h["shape"] and h["reg"] == 1


def test_mid_function_and_register_mismatch():
    hits = fi.classify(code(PUSH, 0xE3A03000, 0xEE073F90, 0xE3A00001, POP,      # mid-function, r3
                            0xE3A00000, 0xEE071F90, 0xE12FFF1E), 0x02000000)  # mov r0 but mcr r1
    assert [(h["reg"], h["exact"], h["shape"]) for h in hits] == [(3, False, False), (1, False, False)]


def test_autoload_copy_runs_elsewhere():
    [h] = fi.classify(code(NOP, 0xE3A00000, 0xEE070F90, 0xE12FFF1E), 0x02100000, 0x01FF8000)
    assert h["at"] == 0x02100008 and h["runs_at"] == 0x01FF8008 and h["exact"]
    assert fi.region(h["runs_at"]) == "ITCM" and fi.region(0x02000000) == "main RAM"


def test_not_a_wait():
    # c7, c10, 4 (drain the write buffer) and c7, c5, 0 aren't waits
    assert fi.classify(code(0xEE070F9A, 0xEE070F15, 0xEE070F90 | 1 << 20), 0x02000000) == []


def test_module_params_and_autoload_list():
    params = code(0x02180000, 0x02180018, 0x02170000, 0x02180018, 0x021A0000, 0, 0x03017531,
                  *fi.NITROCODE)
    data = code(NOP, NOP) + params + code(NOP)
    p = fi.find_params(data, 0x02000B00)
    assert p["at"] == 0x02000B08 and p["autoload_start"] == 0x02170000 and p["sdk_version"] == 0x03017531
    assert fi.sdk(p["sdk_version"]).startswith("3.01")
    blocks = fi.autoload_blocks(code(0x01FF8000, 0x400, 0, 0x027E0000, 0x80, 0x20), 0x02170000)
    assert blocks == [(0x01FF8000, 0x400, 0, 0x02170000), (0x027E0000, 0x80, 0x20, 0x02170400)]
    assert fi.find_params(code(NOP) * 20, 0x02000000) is None


def test_bios_waits_and_words():
    assert fi.bios_waits(code(0xEF040000, 0xEF060000, 0xEF060000, 0x0F050000, 0xEF070000)) == {4: 1, 5: 1, 6: 2}
    assert fi.describe(0xE12FFF1E) == "bx lr"
    assert fi.describe(0xE3A00000) == "mov r0, #0x0"
    assert "wait for interrupt" in fi.describe(0xEE072F90)
    assert fi.describe(PUSH).startswith("push {r4")


def test_thumb_wait_stubs():
    halfwords = struct.pack("<8H", 0x2000, 0xDF05, 0x4770, 0xDF06, 0x4770, 0xDF04, 0x2001, 0x4770)
    assert fi.thumb_waits(halfwords, 0x02000100) == [(0x02000102, 0x05), (0x02000106, 0x06)]   # the last isn't a stub


def test_autoload_list_plausible():
    assert fi.plausible([(0x01FF8000, 0x7FA0, 0, 0x0216F320), (0x027E0000, 0xE0, 0, 0x021772C0)])
    # what a running game left there: a counting table
    assert not fi.plausible([(0x00001C20, 0x1C24, 0x1C28, 0x020E7500), (0x00001C2C, 0x1C30, 0x1C34, 0x020E9124)])
    assert not fi.plausible([])


@pytest.mark.parametrize("hits,waits,says", [
    ([{"exact": True, "shape": True}], 0, "exact OS_Halt pattern, in static code"),
    ([{"exact": False, "shape": True}], 0, "needs r0"),
    ([{"exact": False, "shape": False}], 0, "none in OS_Halt's three-instruction shape"),
    ([], 3, "may wait through the BIOS"),
    ([], 0, "try --rom"),
])
def test_verdict(hits, waits, says, capsys):
    fi.summary(hits, hits, waits)
    out = capsys.readouterr().out
    assert says in out
    if not waits:
        assert "see the BIOS waits" not in out
