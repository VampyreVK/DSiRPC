"""The achievement checker's memory in nds-bootstrap (locations.h's
DSIRPC_ACH_LOCATION and DSIRPC_ACH_SIZE: 512 KB right below the in-game
menu's window): what DSiRPC builds sets for matches it, it stays clear of
the menu's window, nds-bootstrap's own block and the 128 KB a DSi-enhanced
game uses at the top of the 16 MB, and the ROM cache's slots, laid out the
way the bootloader does with its own romLocationAdjust() (compiled from
bootloaderi's main.arm7.c), never land in it or in that 128 KB."""

import os
import re
import subprocess

import pytest

from core import offline
from helpers import REPO, cbuild

RETAIL = os.path.join(REPO, "nds-bootstrap", "retail")
LOCATIONS = os.path.join(RETAIL, "common", "include", "locations.h")
MAIN_ARM7 = os.path.join(RETAIL, "bootloaderi", "source", "arm7", "main.arm7.c")
PROBE_ACH = os.path.join(RETAIL, "cardenginei", "arm7", "source", "rpcprobe", "probe_ach.c")


def defines():
    out = {}
    with open(LOCATIONS, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"#define\s+(\w+)\s+(0x[0-9A-Fa-f]+)\s*(?://.*)?$", line.strip())
            if m:
                out[m.group(1)] = int(m.group(2), 16)
    return out


D = defines()
ACH, SIZE = D["DSIRPC_ACH_LOCATION"], D["DSIRPC_ACH_SIZE"]
MENU = 0x0C000000 | (D["INGAME_MENU_LOCATION"] & 0x00FFFFFF)     # (0x02F88000 is the same RAM)
TOP_128K = (0x0CFE0000, 0x0D000000)                                  # a DSi-enhanced game's own
BOOTSTRAP = (0x0C7C0000, 0x0C800000)                                 # (0x027C0000: nds-bootstrap's, the header)


def overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


def test_the_layout():
    area = (ACH, ACH + SIZE)
    assert SIZE == 0x80000 and ACH % 0x8000 == 0          # (32 KB aligned: the cache's slots meet it exactly)
    assert area[1] <= MENU and not overlap(area, (MENU, MENU + D["INGAME_MENU_SIZE"]))
    assert not overlap(area, TOP_128K) and not overlap(area, BOOTSTRAP)
    assert D["ROM_LOCATION"] <= ACH and area[1] <= 0x0D000000       # (in the DSi's 16 MB, the ROM cache's area)
    assert offline.ACH_MEMORY == SIZE - offline.UNLOCK_FILE_SIZE - D["DSIRPC_WATCH_RING_SIZE"]


def test_the_console_takes_the_same_room():
    with open(PROBE_ACH, encoding="utf-8") as f:
        src = f.read()
    assert re.search(r"#define ACH_SET_SPACE\s+\(DSIRPC_ACH_SIZE - ACH_UNLOCK_FILE - DSIRPC_WATCH_RING_SIZE\)", src)
    assert re.search(r"#define ACH_UNLOCK_FILE\s+\(ACH_UNLOCK_SLOT \* ACH_UNLOCK_SLOTS\)", src)
    assert offline.UNLOCK_FILE_SIZE == 16 * 256


def rom_location_adjust():
    """romLocationAdjust() as it is in main.arm7.c"""
    with open(MAIN_ARM7, encoding="utf-8") as f:
        src = f.read()
    start = src.index("bool romLocationAdjust(")
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]


HOST = r"""
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t u32; typedef uint16_t u16; typedef uint8_t u8;
typedef struct { u8 unitCode; } tNDSHeader;
bool pkmnGen5, sharedWramEnabled, hasVramWifiBinary;
int consoleModel;
#define DSIRPC_ACH_LOCATION %(ach)#x
#define DSIRPC_ACH_SIZE %(size)#x
%(func)s
// The bootloader's cache table (hook_arm9.c): every slot from start, as far as RAM goes
int main(int argc, char **argv) {
	u32 start = strtoul(argv[1], 0, 0), block = strtoul(argv[2], 0, 0);
	tNDSHeader h = { (u8)atoi(argv[3]) };
	bool laterSdk = atoi(argv[4]);
	consoleModel = atoi(argv[5]);
	u32 end = consoleModel > 0 ? 0x0E000000 : 0x0D000000 - block, addr = start;
	for (int slot = 0; slot < 4096; slot++) {
		romLocationAdjust(&h, laterSdk, false, &addr, (u16)block);
		if (addr < 0x0C000000 || addr >= end) break;
		printf("%%#x\n", addr);
		addr += block;
	}
	return 0;
}
"""


@pytest.fixture(scope="module")
def slots_exe(cc, tmp_path_factory):
    d = tmp_path_factory.mktemp("romloc")
    src = d / "romloc.c"
    src.write_text(HOST % {"ach": ACH, "size": SIZE, "func": rom_location_adjust()})
    return cbuild.build(str(d / "romloc"), [str(src)], flags=["-std=gnu11"])


@pytest.mark.parametrize("start", [D["ROM_LOCATION"], D["ROM_LOCATION_ALT"], D["ROM_LOCATION_DSIMODE"]])
@pytest.mark.parametrize("block", [0x4000, 0x8000])
@pytest.mark.parametrize("unit", [0, 2])
@pytest.mark.parametrize("later_sdk", [0, 1])
@pytest.mark.parametrize("console", [0, 2])
def test_the_rom_cache_keeps_out(slots_exe, start, block, unit, later_sdk, console):
    out = subprocess.run([slots_exe, hex(start), hex(block), str(unit), str(later_sdk), str(console)],
                         capture_output=True, text=True, env=cbuild.run_env(), check=True).stdout
    slots = [int(x, 16) for x in out.split()]
    assert len(slots) > 100
    for s in slots:
        assert not overlap((s, s + block), (ACH, ACH + SIZE)), hex(s)
        if unit:
            assert not overlap((s, s + block), TOP_128K), hex(s)
    # and the old 256 KB is the cache's again
    assert any(0x0CFA0000 <= s < 0x0CFE0000 for s in slots)
