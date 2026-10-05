// dsirpc_watch_block.h - DSiRPC's per-frame capture, the block the two CPUs
// share. See cardenginei/arm7/source/rpcprobe/probe_watch.c (the ARM7 half)
// and cardenginei/arm9/source/dsirpc_watch.c (the ARM9 half).
//
// Why the ARM9 is involved at all: the game runs on the ARM9, whose data
// cache holds its writes back from main RAM for a while (measured on
// Platinum: a frame late on a third of frames in menus and battles, several
// frames during loading). The ARM7 reads main RAM directly, so it sees those
// values late. The ARM9 reads through its own cache and always sees what the
// game just wrote, so it does the reading and hands the values over here.
//
// When it reads matters too. Games update some values the moment VBlank
// starts (Platinum's VBlank counter, for one), so a read made a little after
// that sometimes lands before the update and sometimes after it. The ARM9
// takes its snapshot at the very start of its VBlank interrupt, before the
// game's own VBlank code runs, so every frame is read at the same point.
//
// The block lives in the ARM9 cardengine's .data. The ARM7 finds it by
// scanning that cardengine's region for the two magic words and the version
// (so a build or variant without it is simply never found, and the ARM7
// reads by itself as before).
//
// Ownership is split by cache line, so neither CPU ever writes a line the
// other one writes: the ARM9 never writes the first two lines (and
// invalidates them before reading), and the ARM7 never writes the rest.
//
// How it runs:
//   ARM7, on a new watch list: count = 0, write the list, gen = a new
//         number, count = n. Then ring the ARM9 (IPC sync 3, nds-bootstrap's
//         do-nothing doorbell) so it hooks its VBlank interrupt.
//   ARM9, every VBlank while count > 0 (before the game's VBlank handler):
//         read every watched value into the next slot, tag it with gen and
//         its number, write the slot back to RAM, then latest = its number
//         and write that back too (slot first, so an ARM7 that sees the new
//         latest also sees the whole slot). A snapshot taken while the list
//         was changing is dropped.
//   ARM7, every VBlank: record the oldest slot it hasn't recorded yet (it
//         starts one snapshot behind the newest, since the ARM9's VBlank and
//         its own start at almost the same moment). If there's none, read
//         main RAM itself and mark the record as such; if that goes on, ring
//         the ARM9 again (the game may have replaced its VBlank handler).

#ifndef DSIRPC_WATCH_BLOCK_H
#define DSIRPC_WATCH_BLOCK_H

#include <nds/ndstypes.h>

#define DSIRPC_WATCH_MAGIC0  0x43505244u // "DRPC"
#define DSIRPC_WATCH_MAGIC1  0x39435457u // "WTC9"
#define DSIRPC_WATCH_VERSION 2
#define DSIRPC_WATCH_MAX     8           // values, at most 4 bytes each
#define DSIRPC_WATCH_SLOTS   4           // snapshots kept, newest overwrites oldest

typedef struct {
	u32 seq;                          // 0x00  snapshot number (1, 2, ...), written last
	u32 gen;                          // 0x04  the list it was taken with
	u16 vcount;                       // 0x08  scanline it was taken on
	u16 pad;                          // 0x0A
	u8  values[4 * DSIRPC_WATCH_MAX]; // 0x0C  each watch's bytes, in list order
} DsirpcWatchSlot;                    // 0x2C

typedef struct {
	// Written by the ARM7 only.
	u32 magic0;                       // 0x00
	u32 magic1;                       // 0x04
	u16 version;                      // 0x08
	u8  count;                        // 0x0A  watches in use, 0 = off
	u8  pad0;                         // 0x0B
	u32 gen;                          // 0x0C  list number, a new one after every change
	u8  sizes[DSIRPC_WATCH_MAX];      // 0x10  1, 2 or 4
	u32 pad1[2];                      // 0x18
	u32 addrs[DSIRPC_WATCH_MAX];      // 0x20  main RAM addresses
	// Written by the ARM9 only.
	u32 latest;                       // 0x40  number of the newest finished snapshot, 0 = none yet
	u32 hooks;                        // 0x44  times the VBlank hook was put in (1 normally)
	u32 pad2[6];                      // 0x48
	DsirpcWatchSlot slots[DSIRPC_WATCH_SLOTS]; // 0x60  snapshot n is in slots[n % DSIRPC_WATCH_SLOTS]
	u32 pad3[4];                      // 0x110
} DsirpcWatchBlock;                   // 0x120

_Static_assert(sizeof(DsirpcWatchSlot) == 0x2C, "DsirpcWatchSlot layout");
_Static_assert(sizeof(DsirpcWatchBlock) == 0x120, "DsirpcWatchBlock must be whole cache lines");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, addrs) == 0x20, "DsirpcWatchBlock layout");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, latest) == 0x40, "DsirpcWatchBlock layout");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, slots) == 0x60, "DsirpcWatchBlock layout");

#endif // DSIRPC_WATCH_BLOCK_H
