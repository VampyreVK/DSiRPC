// dsirpc_watch.c - DSiRPC's per-frame capture, the ARM9 half. See
// common/include/dsirpc_watch_block.h for why it exists and how it runs; the
// ARM7 half is cardenginei/arm7/source/rpcprobe/probe_watch.c.
//
// Only the plain cardenginei_arm9 (retail games in DS mode, the variant
// that loads next to rpcprobe's cardenginei_arm7) carries it. The DLDI,
// GSDD and TWLSDK variants compile this file to nothing, and the ARM7 then
// never finds the block and reads by itself.
//
// The snapshot runs from a hook in front of the game's VBlank interrupt
// handler (entry 0 of the game's interrupt table, the same table
// nds-bootstrap hooks for IPC sync and the colour LUT). The hook is only put
// in once a watch list is set (the ARM7 rings the IPC doorbell for it), so a
// game nobody is capturing runs exactly as without DSiRPC.
//
// Offline play's achievement checker uses the same hook: with the block's
// `clean` set (a set with a frame lane is running), it also writes the data
// cache back to main RAM at the start of every VBlank, so the ARM7 samples
// what the game wrote: the whole cache, or only the lines the ARM7 lists in
// the block's runs[] (dsirpc_watch_block.h).

#include <nds/ndstypes.h>

#if !defined(TWLSDK) && !defined(DLDI) && !defined(GSDD)

#include <nds/arm9/cache.h>
#include "cardengine_header_arm9.h"
#include "dsirpc_watch_block.h"

#define MAINRAM_LO 0x02000000u
#define MAINRAM_HI 0x02400000u
#define REG_VCOUNT_RO (*(vu16 *)0x04000006)

// A game can replace its VBlank handler at any time (some do it per scene),
// which takes our hook out; the next doorbell puts a hook back in. Each time
// that's a fresh hook with its own saved handler, never an old one reused:
// a game that saved the handler it replaced (one of our hooks) and puts it
// back later must still get the handler that hook was made for. After the
// last one, the ARM7 reads by itself.
#define DSIRPC_HOOKS     4
#define DSIRPC_HOOK_SIZE 20 // bytes of ARM code per hook, see below

extern cardengineArm9* volatile ce9;

// Two whole cache lines of the ARM7's, seven of the ARM9's, so cleaning or
// invalidating them never touches anything else.
DsirpcWatchBlock dsirpcWatchBlock __attribute__((aligned(32))) = {
	.magic0 = DSIRPC_WATCH_MAGIC0,
	.magic1 = DSIRPC_WATCH_MAGIC1,
	.version = DSIRPC_WATCH_VERSION,
};

// The handler each hook was put in front of. Set once, before the hook goes
// into the table.
u32 dsirpcVBlankOrig[DSIRPC_HOOKS];

void dsirpcWatchSnapshot(void);

// The hooks, in ARM code, since the game's interrupt dispatcher jumps to
// table entries in ARM state. Each one saves the registers a C call can
// change (plus two words for the jump below) and passes its own saved
// handler's address to the common part, which takes the snapshot and then
// jumps to that handler with every register as it was, so the handler runs
// exactly as if it had been called directly and returns to the dispatcher
// itself. A hook with no saved handler (0) returns to the dispatcher.
asm(
"	.pushsection .text\n"
"	.syntax unified\n"
"	.arm\n"
"	.align 2\n"
"	.global dsirpcVBlankHooks\n"
"dsirpcVBlankHooks:\n"
"	.irp n, 0, 1, 2, 3\n"                // DSIRPC_HOOKS of them
"	sub	sp, sp, #8\n"                  // room for the jump target (and 8-byte alignment)
"	stmfd	sp!, {r0-r3, r12, lr}\n"
"	ldr	r0, [pc, #0]\n"                // the .word below
"	b	dsirpcVBlankCommon\n"
"	.word	dsirpcVBlankOrig + 4 * \\n\n"
"	.endr\n"
"dsirpcVBlankCommon:\n"
"	ldr	r0, [r0]\n"
"	str	r0, [sp, #24]\n"               // jump target, above the saved registers
"	bl	dsirpcWatchSnapshot\n"
"	ldr	r0, [sp, #24]\n"
"	cmp	r0, #0\n"
"	ldreq	r0, [sp, #20]\n"              // no handler: back to the dispatcher (saved lr)
"	streq	r0, [sp, #24]\n"
"	ldmfd	sp!, {r0-r3, r12, lr}\n"
"	ldr	pc, [sp], #8\n"                // jump (to ARM or Thumb) and drop the two words
// Writes every dirty line of the data cache back to main RAM (clean by
// index: 4 segments of 32 lines, libnds' DC_FlushAll without the
// invalidate), then drains the write buffer. ARM code: Thumb has no MCR.
"	.global dsirpcCleanDCache\n"
"	.type	dsirpcCleanDCache, %function\n"
"dsirpcCleanDCache:\n"
"	mov	r1, #0\n"
"1:	mov	r0, #0\n"
"2:	orr	r2, r1, r0\n"
"	mcr	p15, 0, r2, c7, c10, 2\n"     // clean data cache line (segment, index)
"	add	r0, r0, #32\n"
"	cmp	r0, #1024\n"                  // DCACHE_SIZE / 4 segments
"	bne	2b\n"
"	adds	r1, r1, #0x40000000\n"
"	bne	1b\n"
"	mcr	p15, 0, r1, c7, c10, 4\n"     // drain the write buffer
"	bx	lr\n"
// Writes some lines back to main RAM, the dirty ones (clean by address):
// r0 = the first line's address, r1 = how many (1 or more). The write buffer
// drains after, with the count (DC_FlushRange()).
"	.global dsirpcCleanLines\n"
"	.type	dsirpcCleanLines, %function\n"
"dsirpcCleanLines:\n"
"3:	mcr	p15, 0, r0, c7, c10, 1\n"     // clean data cache line (address)
"	add	r0, r0, #32\n"
"	subs	r1, r1, #1\n"
"	bne	3b\n"
"	bx	lr\n"
"	.thumb\n"
"	.popsection\n"
);
extern u8 dsirpcVBlankHooks[];
void dsirpcCleanDCache(void);
void dsirpcCleanLines(u32 first, u32 lines);

#ifdef DSIRPC_ARM9_DELAY
// A test build's switch (see dsirpcWatchSnapshot)
#define DSIRPC_DELAY_LINES     8
#define DSIRPC_LINES_PER_FRAME 263
#endif

// The watched values into the next slot (n of them)
static void takeSnapshot(DsirpcWatchBlock *b, u32 n, u16 vcount) {
	u32 gen = b->gen;
	if (n > DSIRPC_WATCH_MAX) n = DSIRPC_WATCH_MAX;

	u32 seq = b->latest + 1;
	if (!seq) seq = 1;
	DsirpcWatchSlot *s = &b->slots[seq % DSIRPC_WATCH_SLOTS];
	u8 *v = s->values;
	u8 *end = s->values + sizeof(s->values);
	for (u32 i = 0; i < n; i++) {
		u32 a = b->addrs[i];
		u32 sz = b->sizes[i];
		if ((sz != 1 && sz != 2 && sz != 4) || v + sz > end) break;
		if (a < MAINRAM_LO || a >= MAINRAM_HI || sz > MAINRAM_HI - a) {
			for (u32 k = 0; k < sz; k++) v[k] = 0;
		} else if (sz == 4 && !(a & 3)) {
			u32 x = *(vu32 *)a;
			v[0] = x; v[1] = x >> 8; v[2] = x >> 16; v[3] = x >> 24;
		} else if (sz == 2 && !(a & 1)) {
			u16 x = *(vu16 *)a;
			v[0] = x; v[1] = x >> 8;
		} else {
			for (u32 k = 0; k < sz; k++) v[k] = *(vu8 *)(a + k);
		}
		v += sz;
	}

	// If the ARM7 changed the list meanwhile, this snapshot may be half old,
	// half new: drop it.
	DC_InvalidateRange(b, 32);
	if (b->gen != gen || !b->count) return;

	// The slot out to RAM first, then the number, so an ARM7 that sees the
	// new number also sees the whole slot.
	s->gen = gen;
	s->vcount = vcount;
	s->seq = seq;
	DC_FlushRange(s, sizeof(*s));
	b->latest = seq;
	DC_FlushRange(&b->latest, 4);
}

// The data cache out to main RAM for the checker: only the lines in runs[]
// if the ARM7 listed them (the ones its frame lane reads), the whole cache
// if it didn't, none while it's rewriting them.
static void cleanCache(DsirpcWatchBlock *b) {
	u32 n = b->runCount;
	if (!n) {
		dsirpcCleanDCache();
		return;
	}
	if (n > DSIRPC_CLEAN_RUNS) return; // DSIRPC_RUNS_UPDATING
	DC_InvalidateRange(b->runs, sizeof(b->runs)); // the ARM7 writes them straight to RAM
	for (u32 i = 0; i < n; i++) {
		u32 r = b->runs[i];
		dsirpcCleanLines(r & ~31u, (r & 31) + 1);
	}
}

// Called by the hooks at the start of every VBlank interrupt, before the
// game's own handler. Cheap when there's nothing to do: one cache-line
// invalidate and a compare.
void dsirpcWatchSnapshot(void) {
	DsirpcWatchBlock *b = &dsirpcWatchBlock;
	u16 vcount = REG_VCOUNT_RO;

	// The ARM7 writes the first two lines straight to RAM; drop any copy the
	// cache still holds. Never dirty here, since this side never writes them.
	DC_InvalidateRange(b, 0x40);
	u32 n = b->count;
	if (n) takeSnapshot(b, n, vcount);
	if (b->clean) {
		// Everything the game wrote out to main RAM, then the count (its
		// own line written back last, so the ARM7 never sees the new count
		// before the rest)
#if defined(DSIRPC_ARM9_NO_CLEAN)
		// (a test build: the hook runs and counts, but writes nothing back)
#elif defined(DSIRPC_ARM9_DELAY)
		// (a test build: nothing written back, but the game's VBlank handler
		// waits about as long as a write-back of the whole cache could take)
		for (;;) {
			s32 d = (s32)REG_VCOUNT_RO - (s32)vcount;
			if (d < 0) d += DSIRPC_LINES_PER_FRAME;
			if (d >= DSIRPC_DELAY_LINES) break;
		}
#else
		cleanCache(b);
#endif
		b->cleaned++;
		DC_FlushRange(&b->cleaned, 4);
	}
}

// Called from myIrqHandlerIPC on every IPC sync interrupt (the ARM7 rings
// when it needs the hook). Puts a hook in front of the game's VBlank handler
// if there's a watch list and none of ours is there.
void dsirpcWatchService(void) {
	DsirpcWatchBlock *b = &dsirpcWatchBlock;
	DC_InvalidateRange(b, 32);
	if (!b->count && !b->clean) return;

	vu32 *vblank = (vu32 *)ce9->irqTable; // entry 0: VBlank
	if (!vblank) return;
	u32 cur = *vblank;
	u32 used = b->hooks;
	for (u32 i = 0; i < used && i < DSIRPC_HOOKS; i++) {
		if (cur == (u32)&dsirpcVBlankHooks[i * DSIRPC_HOOK_SIZE]) return;
	}
	if (used >= DSIRPC_HOOKS) return;

	// This runs in an interrupt, so the VBlank one can't come in between.
	dsirpcVBlankOrig[used] = cur;
	*vblank = (u32)&dsirpcVBlankHooks[used * DSIRPC_HOOK_SIZE];
	b->hooks = used + 1;
	DC_FlushRange(&b->hooks, 4);
}

// Called from nds-bootstrap's reset() (misc.c), with interrupts off, when
// the game is about to be loaded again (a soft reset, or the in-game menu's
// reset). Nothing of the old game can still hold one of our hooks, so they
// can all be used again; otherwise every soft reset would use one up.
void dsirpcWatchReset(void) {
	DsirpcWatchBlock *b = &dsirpcWatchBlock;
	b->hooks = 0;
	DC_FlushRange(&b->hooks, 4);
}

#endif
