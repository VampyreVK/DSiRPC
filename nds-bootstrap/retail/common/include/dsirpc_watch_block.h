// dsirpc_watch_block.h - the block rpcprobe (the ARM7) and DSiRPC's ARM9
// half share. See cardenginei/arm7/source/rpcprobe/probe_watch.c (the ARM7
// half) and cardenginei/arm9/source/dsirpc_watch.c (the ARM9 half).
//
// Why the ARM9 is involved at all: the game runs on the ARM9, whose data
// cache holds its writes back from main RAM for a while (measured on
// Platinum: a frame late on a third of frames in menus and battles, several
// frames during loading; a value set for just one frame may never reach main
// RAM at all). rpcprobe reads main RAM directly, for offline play's
// achievement checker (rpcprobe/probe_ach.c) and for DSiRPC (its memory
// reads and per-frame capture), so it would see those values late or never.
//
// So the ARM9 writes its whole data cache back to main RAM (a clean: the
// cache keeps its contents) whenever the game has nothing to do: its idle
// thread calls the SDK's OS_Halt to wait for the next interrupt, and the ARM9
// half patches OS_Halt to do the write-back first. A game busy all frame
// (Pokemon Black and White loading a battle) never gets there, so this never
// takes time the game wants; anything done in the ARM9's VBlank interrupt
// did, even a few microseconds of it, and slowed those battle loads to a
// crawl. A game that idles once its frame is done, as most do, has every
// frame's values in main RAM by the next VBlank, which is when rpcprobe
// samples them.
//
// Finding OS_Halt: rpcprobe searches the game's ARM9 binary in main RAM for
// its three instructions, in the ARM7's own idle time, and lists every copy
// in haltAt. Then it rings the ARM9 (IPC sync 3, nds-bootstrap's do-nothing
// doorbell) after raising ask; the ARM9 checks that each address still holds
// OS_Halt and makes it jump to its write-back routine instead, which then
// does what OS_Halt does.
//
// The block lives in the ARM9 cardengine's .data. rpcprobe finds it by
// scanning that cardengine's region for the two magic words and the version
// (so a build or variant without it is simply never found, and rpcprobe reads
// main RAM as it is).
//
// Ownership is split by cache line, so neither CPU ever writes a line the
// other one writes: the ARM9 never writes the first line (and invalidates it
// before reading), and the ARM7 never writes the second.

#ifndef DSIRPC_WATCH_BLOCK_H
#define DSIRPC_WATCH_BLOCK_H

#include <nds/ndstypes.h>

#define DSIRPC_WATCH_MAGIC0  0x43505244u // "DRPC"
#define DSIRPC_WATCH_MAGIC1  0x39435457u // "WTC9"
#define DSIRPC_WATCH_VERSION 4
#define DSIRPC_IDLE_SITES    4           // copies of OS_Halt rpcprobe can list

// The SDK's OS_Halt (ARM code): mov r0, #0 / mcr p15, 0, r0, c7, c0, 4 / bx lr
#define DSIRPC_OS_HALT_0 0xE3A00000u
#define DSIRPC_OS_HALT_1 0xEE070F90u
#define DSIRPC_OS_HALT_2 0xE12FFF1Eu

typedef struct {
	// Written by the ARM7 only.
	u32 magic0;                       // 0x00
	u32 magic1;                       // 0x04
	u16 version;                      // 0x08
	u16 ask;                          // 0x0A  one more each time rpcprobe asks for the patch
	u32 haltAt[DSIRPC_IDLE_SITES];    // 0x0C  OS_Halt's copies in the game, 0 = none
	u32 pad1;                         // 0x1C
	// Written by the ARM9 only.
	u32 cleaned;                      // 0x20  write-backs done in the game's idle time (counts up)
	u32 hooked;                       // 0x24  copies of OS_Halt patched (0 again after a reset)
	u32 pad2[6];                      // 0x28
} DsirpcWatchBlock;                   // 0x40

// For dsirpc_watch.c's assembly
#define DSIRPC_BLOCK_CLEANED 0x20

_Static_assert(sizeof(DsirpcWatchBlock) == 0x40, "DsirpcWatchBlock must be whole cache lines");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, haltAt) == 0x0C, "DsirpcWatchBlock layout");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, cleaned) == DSIRPC_BLOCK_CLEANED, "DsirpcWatchBlock layout");
_Static_assert(__builtin_offsetof(DsirpcWatchBlock, hooked) == 0x24, "DsirpcWatchBlock layout");

#endif // DSIRPC_WATCH_BLOCK_H
