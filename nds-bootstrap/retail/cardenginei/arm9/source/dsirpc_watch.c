// dsirpc_watch.c - DSiRPC's ARM9 half: writes the game's data cache back to
// main RAM in the game's idle time, so rpcprobe (the ARM7) reads every value
// the game wrote. See common/include/dsirpc_watch_block.h for why and how;
// the ARM7 half is cardenginei/arm7/source/rpcprobe/probe_watch.c.
//
// Only the plain cardenginei_arm9 (retail games in DS mode, the variant
// that loads next to rpcprobe's cardenginei_arm7) carries it. The DLDI,
// GSDD and TWLSDK variants compile this file to nothing, and the ARM7 then
// never finds the block and reads main RAM as it is.
//
// The write-back runs from the game's own OS_Halt, patched to jump here once
// rpcprobe has found it and rings: the game calls OS_Halt when it has nothing
// else to do, so the write-back only ever uses time the ARM9 would have spent
// halted. Nothing runs in any of the game's interrupts any more (a hook on
// its VBlank interrupt, before or after the game's own handler, slowed
// Pokemon Black and White's battle loads to a crawl).

#include <nds/ndstypes.h>

#if !defined(TWLSDK) && !defined(DLDI) && !defined(GSDD)

#include <nds/arm9/cache.h>
#include "dsirpc_watch_block.h"

#define MAINRAM_LO 0x02000000u
#define MAINRAM_HI 0x02400000u

// What a patched OS_Halt starts with: ldr pc, [pc, #-4], then the address
// it jumps to
#define IDLE_PATCH 0xE51FF004u

// The ARM7's line, then the ARM9's, so cleaning or invalidating one never
// touches the other.
DsirpcWatchBlock dsirpcWatchBlock __attribute__((aligned(32))) = {
	.magic0 = DSIRPC_WATCH_MAGIC0,
	.magic1 = DSIRPC_WATCH_MAGIC1,
	.version = DSIRPC_WATCH_VERSION,
};

#define XSTR(x) STR(x)
#define STR(x) #x

// The patched OS_Halt jumps here, in ARM state, with the game's return
// address in lr. Writes every dirty line of the data cache back to main RAM
// (clean by index: 4 segments of 32 lines, libnds' DC_FlushAll without the
// invalidate), counts it in `cleaned` and writes that line back too, drains
// the write buffer, then halts until the next interrupt and returns, as
// OS_Halt does. Interrupts stay as the game had them (on, in its idle
// thread), so one that comes in meanwhile is taken at once, and the rest of
// the write-back waits until the game is idle again. No stack: the game's
// idle thread has very little.
asm(
"	.pushsection .text\n"
"	.syntax unified\n"
"	.arm\n"
"	.align 2\n"
"	.global dsirpcIdle\n"
"	.type	dsirpcIdle, %function\n"
"dsirpcIdle:\n"
"	mov	r1, #0\n"
"1:	mov	r0, #0\n"
"2:	orr	r2, r1, r0\n"
"	mcr	p15, 0, r2, c7, c10, 2\n"     // clean data cache line (segment, index)
"	add	r0, r0, #32\n"
"	cmp	r0, #1024\n"                  // DCACHE_SIZE / 4 segments
"	bne	2b\n"
"	adds	r1, r1, #0x40000000\n"
"	bne	1b\n"
"	ldr	r0, =dsirpcWatchBlock + " XSTR(DSIRPC_BLOCK_CLEANED) "\n"
"	ldr	r1, [r0]\n"
"	add	r1, r1, #1\n"
"	str	r1, [r0]\n"                   // cleaned + 1
"	mcr	p15, 0, r0, c7, c10, 1\n"     // clean that line (by address)
"	mov	r0, #0\n"
"	mcr	p15, 0, r0, c7, c10, 4\n"     // drain the write buffer
"	mcr	p15, 0, r0, c7, c0, 4\n"      // halt until an interrupt (OS_Halt's own instruction)
"	bx	lr\n"
"	.ltorg\n"
"	.thumb\n"
"	.popsection\n"
);
void dsirpcIdle(void);

// The last ask this side answered
static u16 served = 0;

// Called from myIrqHandlerIPC on every IPC sync interrupt (rpcprobe rings
// when it has found OS_Halt, and again while a copy isn't patched). Cheap
// when there's nothing new: one cache-line invalidate and a compare.
void dsirpcWatchService(void) {
	DsirpcWatchBlock *b = &dsirpcWatchBlock;

	// The ARM7 writes the first line straight to RAM; drop any copy the
	// cache still holds. Never dirty here, since this side never writes it.
	DC_InvalidateRange(b, 32);
	u16 ask = b->ask;
	if (ask == served) return;
	served = ask;

	// This runs in an interrupt, so the game's idle thread can't be in the
	// middle of the two words being replaced.
	u32 hooked = 0;
	for (u32 i = 0; i < DSIRPC_IDLE_SITES; i++) {
		u32 a = b->haltAt[i];
		if (a < MAINRAM_LO || a > MAINRAM_HI - 12 || (a & 3)) continue;
		vu32 *p = (vu32 *)a;
		if (p[0] == IDLE_PATCH && p[1] == (u32)dsirpcIdle) {
			hooked++; // already in
			continue;
		}
		// Only over OS_Halt itself (the game may have been loaded again
		// meanwhile, or not be all there yet)
		if (p[0] != DSIRPC_OS_HALT_0 || p[1] != DSIRPC_OS_HALT_1 || p[2] != DSIRPC_OS_HALT_2) continue;
		p[1] = (u32)dsirpcIdle; // the address before the jump that uses it
		p[0] = IDLE_PATCH;
		DC_FlushRange((void *)a, 8);       // out to main RAM,
		IC_InvalidateRange((void *)a, 8);  // where the next fetch gets it
		hooked++;
	}
	b->hooked = hooked;
	DC_FlushRange(&b->hooked, 4);
}

// Called from nds-bootstrap's reset() (misc.c), with interrupts off, when
// the game is about to be loaded again (a soft reset, or the in-game menu's
// reset): its fresh OS_Halt isn't patched, and rpcprobe asks again while
// hooked says so.
void dsirpcWatchReset(void) {
	DsirpcWatchBlock *b = &dsirpcWatchBlock;
	b->hooked = 0;
	DC_FlushRange(&b->hooked, 4);
}

#endif
