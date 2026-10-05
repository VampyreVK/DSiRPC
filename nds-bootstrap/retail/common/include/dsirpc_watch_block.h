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
// The block lives in the ARM9 cardengine's .data. The ARM7 finds it by
// scanning that cardengine's region for the two magic words (so a build or
// variant without it is simply never found, and the ARM7 reads by itself as
// before).
//
// Ownership is split by cache line, so neither CPU ever writes a line the
// other one writes: the ARM9 never writes the first two lines (and
// invalidates them before reading), and the ARM7 never writes the last two.
//
// One round, once per VBlank:
//   ARM7: write the list (only when it changes), then req = a new number,
//         then ring the ARM9 (IPC sync 3, nds-bootstrap's do-nothing doorbell).
//   ARM9 (in its IPC sync interrupt): if req != ack, read every watched
//         value, write them to values[], write them back to RAM, then
//         ack = req and write that back too (values first, so an ARM7 that
//         sees the new ack also sees the new values).
//   ARM7, next VBlank: if ack == the number it sent, use values[];
//         otherwise read main RAM itself and mark the record as such.

#ifndef DSIRPC_WATCH_BLOCK_H
#define DSIRPC_WATCH_BLOCK_H

#include <nds/ndstypes.h>

#define DSIRPC_WATCH_MAGIC0  0x43505244u // "DRPC"
#define DSIRPC_WATCH_MAGIC1  0x39435457u // "WTC9"
#define DSIRPC_WATCH_VERSION 1
#define DSIRPC_WATCH_MAX     8           // values, at most 4 bytes each

typedef struct {
	// Written by the ARM7 only.
	u32 magic0;                       // 0x00
	u32 magic1;                       // 0x04
	u16 version;                      // 0x08
	u8  count;                        // 0x0A  watches in use
	u8  pad0;                         // 0x0B
	u32 req;                          // 0x0C  request number, never 0 once used
	u8  sizes[DSIRPC_WATCH_MAX];      // 0x10  1, 2 or 4
	u32 pad1[2];                      // 0x18
	u32 addrs[DSIRPC_WATCH_MAX];      // 0x20  main RAM addresses
	// Written by the ARM9 only.
	u32 ack;                          // 0x40  the request these values answer
	u16 vcount;                       // 0x44  scanline they were read on
	u16 pad2;                         // 0x46
	u32 pad3[6];                      // 0x48
	u8  values[4 * DSIRPC_WATCH_MAX]; // 0x60  each watch's bytes, in list order
} DsirpcWatchBlock;                   // 0x80

_Static_assert(sizeof(DsirpcWatchBlock) == 0x80, "DsirpcWatchBlock must be four cache lines");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, addrs) == 0x20, "DsirpcWatchBlock layout");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, ack) == 0x40, "DsirpcWatchBlock layout");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, values) == 0x60, "DsirpcWatchBlock layout");

#endif // DSIRPC_WATCH_BLOCK_H
