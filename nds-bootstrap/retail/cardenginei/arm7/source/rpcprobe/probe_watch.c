// probe_watch.c - see probe_watch.h.

#include <nds/ndstypes.h>
#include "rpcprobe_build.h"

#if RPCPROBE_REQUESTS

#include "probe_watch.h"
#include "dsirpc_watch_block.h"
#include "locations.h"

// Same limits as 'R' (probe_req.c): main RAM only, since the ARM7 has no
// MMU and a bad read can hang the console.
#define MAINRAM_LO 0x02000000u
#define MAINRAM_HI 0x02400000u

#define REC_HEADER 4 // tick u16 + vcount u16

// Where the ARM9 half's block can be: inside the plain ARM9 cardengine,
// which is linked at CARDENGINEI_ARM9_LOCATION and is 12 KB long.
#ifndef PW_ARM9_SCAN_START
#define PW_ARM9_SCAN_START CARDENGINEI_ARM9_LOCATION
#endif
#define PW_ARM9_SCAN_END   (PW_ARM9_SCAN_START + 0x3000)

#ifndef PW_REG_IPC_SYNC
#define PW_REG_IPC_SYNC (*(vu16 *)0x04000180)
#endif
#ifndef PW_REG_VCOUNT
#define PW_REG_VCOUNT (*(vu16 *)0x04000006)
#endif
#define PW_LINES_PER_FRAME 263
#define PW_IPC_SYNC_IRQ_REQUEST (1 << 13)
#define PW_DOORBELL 3 // nds-bootstrap's own DMA doorbell; the ARM9 does nothing else for it

// While a copy of OS_Halt isn't patched (the ARM9 hasn't answered yet, or
// the game was loaded again), ask again this often, in VBlanks
#define PW_ASK_EVERY 60

// The last two words of the game's module params (NitroSDK's crt0)
#define PW_NITROCODE_BE 0xDEC00621u
#define PW_NITROCODE_LE 0x2106C0DEu

// Reported in the hellos as a9=: 0 = no ARM9 half, 1 = found, 2 or more =
// found and OS_Halt patched (1 + the copies patched).
u8 probeWatchArm9 = 0;

static volatile DsirpcWatchBlock *arm9Block = 0;
static u32 cleanedSeen = 0; // the block's write-back count at the last VBlank
static u8 fresh = 0;        // a write-back came between the last two VBlanks
static u16 askIn = 0;       // VBlanks until asking for the patch again

// Looking for OS_Halt: the game's module params first, for where its static
// code ends, then that code
enum { SCAN_NONE = 0, SCAN_PARAMS, SCAN_HALT, SCAN_DONE };
static u8 scanStage = SCAN_NONE;
static u32 binStart = 0;    // the game's ARM9 binary (NDS header)
static u32 binSize = 0;     // (as stored, so less than its code if it was compressed)
static u32 scanAt = 0, scanEnd = 0;
static u8 sites = 0;        // copies of OS_Halt found
static u32 siteAt[DSIRPC_IDLE_SITES];

typedef struct {
	u32 addr;
	u8 size;
} Watch;

static Watch watches[WATCH_MAX];
static u8 watchCount = 0;
static u8 recSize = 0;    // REC_HEADER + the watches' sizes
static u16 ringSlots = 0; // WATCH_RING_BYTES / recSize
static u32 written = 0;   // records written since the last 'W'
static u16 tick = 0;      // VBlanks sampled since the last 'W'
// The records, in main RAM (the ARM7 cardengine's own is full)
#ifndef PW_RING // (the PC tests have their own)
#define PW_RING ((u8 *)DSIRPC_WATCH_RING_LOCATION)
#endif
#define ring PW_RING
_Static_assert(WATCH_RING_BYTES == DSIRPC_WATCH_RING_SIZE, "the ring's size");

static u16 get16(const u8 *p) { return (u16)((p[0] << 8) | p[1]); }
static u32 get32(const u8 *p) { return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3]; }
static void put16(u8 *p, u16 v) { p[0] = v >> 8; p[1] = v & 0xFF; }

static u16 linesSince(u16 start) {
	u16 now = PW_REG_VCOUNT & 0x1FF;
	return (now >= start) ? now - start : now + PW_LINES_PER_FRAME - start;
}

void ProbeWatch_Init(void) {
	arm9Block = 0;
#ifndef DSIRPC_NO_ARM9_HOOK // (a test build: no ARM9 half, so no write-backs)
	for (u32 a = PW_ARM9_SCAN_START; a + sizeof(DsirpcWatchBlock) <= PW_ARM9_SCAN_END; a += 32) {
		volatile DsirpcWatchBlock *b = (volatile DsirpcWatchBlock *)a;
		if (b->magic0 == DSIRPC_WATCH_MAGIC0 && b->magic1 == DSIRPC_WATCH_MAGIC1
		 && b->version == DSIRPC_WATCH_VERSION) {
			arm9Block = b;
			break;
		}
	}
#endif
	if (arm9Block) cleanedSeen = arm9Block->cleaned;
	probeWatchArm9 = arm9Block ? (u8)(1 + arm9Block->hooked) : 0;
	askIn = 0;
}

void ProbeWatch_Game(const void *ndsHeader) {
	if (!ndsHeader || scanStage != SCAN_NONE) return;
	u32 dst = *(const u32 *)((const u8 *)ndsHeader + 0x28);  // arm9destination
	u32 size = *(const u32 *)((const u8 *)ndsHeader + 0x2C); // arm9binarySize
	if (dst < MAINRAM_LO || dst >= MAINRAM_HI || (dst & 3) || size < 12 || size > MAINRAM_HI - dst) return;
	binStart = dst;
	binSize = size & ~3u;
	scanAt = binStart;
	scanEnd = binStart + binSize;
	scanStage = SCAN_PARAMS;
}

// The module params found, with their nitrocode at `at`: the static code
// runs up to where the autoload blocks start (their third word). It was
// decompressed in place, so it can go past the size in the header.
static void foundParams(u32 at) {
	u32 end = binStart + binSize;
	u32 params = at - 0x1C;
	if (params >= binStart) {
		u32 autoLoad = *(vu32 *)(params + 8);
		if (autoLoad > binStart + 12 && autoLoad <= MAINRAM_HI) end = autoLoad & ~3u;
	}
	scanAt = binStart;
	scanEnd = end;
	scanStage = SCAN_HALT;
}

int ProbeWatch_Idle(u16 maxLines, int (*romWaiting)(void)) {
	if (scanStage != SCAN_PARAMS && scanStage != SCAN_HALT) return 0;
	u16 start = PW_REG_VCOUNT & 0x1FF;
	for (;;) {
		if (romWaiting && romWaiting()) return 1; // the ARM9 waits for the ARM7: serve that first
		u32 stop = scanAt + 4 * 256;             // 256 words between looks at the clock
		if (stop > scanEnd) stop = scanEnd;
		if (scanStage == SCAN_PARAMS) {
			for (; scanAt < stop; scanAt += 4) {
				if (*(vu32 *)scanAt == PW_NITROCODE_BE && scanAt + 8 <= scanEnd
				 && *(vu32 *)(scanAt + 4) == PW_NITROCODE_LE) {
					foundParams(scanAt);
					break;
				}
			}
			if (scanStage == SCAN_PARAMS && scanAt >= scanEnd) {
				// None: just the binary's size from the header
				scanAt = binStart;
				scanEnd = binStart + binSize;
				scanStage = SCAN_HALT;
			}
		} else {
			for (; scanAt < stop; scanAt += 4) {
				// OS_Halt's middle word, the rarest of its three, then the other two
				if (*(vu32 *)scanAt != DSIRPC_OS_HALT_1 || scanAt < binStart + 4 || scanAt + 8 > scanEnd) continue;
				if (*(vu32 *)(scanAt - 4) == DSIRPC_OS_HALT_0 && *(vu32 *)(scanAt + 4) == DSIRPC_OS_HALT_2
				 && sites < DSIRPC_IDLE_SITES) {
					siteAt[sites++] = scanAt - 4;
				}
			}
			if (scanAt >= scanEnd) {
				scanStage = SCAN_DONE; // ProbeWatch_Tick() asks for the patch
				return 0;
			}
		}
		if (linesSince(start) >= maxLines) return 0;
	}
}

// Ring the ARM9, but only over our own doorbell value or none: any other
// value is a command of nds-bootstrap's (screen swap, colour LUT, reset,
// in-game menu) that the ARM9 may not have read yet, and it must not be
// replaced. Its interrupt serves our request as well.
static void ringArm9(void) {
	u16 sync = PW_REG_IPC_SYNC;
	u8 out = (sync >> 8) & 0xF;
	if (out == 0 || out == PW_DOORBELL) {
		PW_REG_IPC_SYNC = (sync & 0xF0FF) | (PW_DOORBELL << 8) | PW_IPC_SYNC_IRQ_REQUEST;
	}
}

void ProbeWatch_Tick(void) {
	volatile DsirpcWatchBlock *b = arm9Block;
	if (!b) {
		fresh = 0;
		return;
	}
	u32 c = b->cleaned;
	fresh = c != cleanedSeen;
	cleanedSeen = c;
	u32 hooked = b->hooked;
	probeWatchArm9 = (u8)(1 + (hooked < DSIRPC_IDLE_SITES ? hooked : DSIRPC_IDLE_SITES));

	// Every copy of OS_Halt found and not patched yet (or not any more,
	// after a reset): hand them over and ring, now and then again
	if (scanStage != SCAN_DONE || hooked >= sites) return;
	if (askIn) {
		askIn--;
		return;
	}
	askIn = PW_ASK_EVERY;
	for (int i = 0; i < DSIRPC_IDLE_SITES; i++) b->haltAt[i] = i < sites ? siteAt[i] : 0;
	b->ask = (u16)(b->ask + 1);
	ringArm9();
}

int ProbeWatch_Fresh(void) {
	return fresh;
}

void ProbeWatch_Sample(u16 vcount) {
	if (!watchCount) return;
	u8 *rec = &ring[(written % ringSlots) * recSize];
	put16(&rec[0], tick);
	u8 *v = &rec[REC_HEADER];
	for (int i = 0; i < watchCount; i++) {
		u32 a = watches[i].addr;
		u8 n = watches[i].size;
		// One load per value when it's aligned, so a value the game is
		// writing at that moment can't be read half old, half new.
		if (n == 4 && !(a & 3)) {
			u32 x = *(vu32 *)a;
			v[0] = x; v[1] = x >> 8; v[2] = x >> 16; v[3] = x >> 24;
		} else if (n == 2 && !(a & 1)) {
			u16 x = *(vu16 *)a;
			v[0] = x; v[1] = x >> 8;
		} else {
			for (u8 k = 0; k < n; k++) v[k] = *(vu8 *)(a + k);
		}
		v += n;
	}
	// Up to date if the ARM9 wrote its cache back since the last VBlank;
	// if not, a value may be a frame late: marked.
	put16(&rec[2], (vcount & WATCH_REC_VCOUNT) | (fresh ? 0 : WATCH_REC_ARM7));
	written++;
	tick++;
}

u16 ProbeWatch_Set(const u8 *req, int len, u8 *count, u8 *status) {
	u8 raw = (len >= 4) ? req[3] : 0;
	u8 n = raw & ~WATCH_ARM7_ONLY;
	*count = raw;
	if (len < 4 || n > WATCH_MAX || len < 4 + 5 * n) {
		*status = 1;
		return 0;
	}
	u8 size = REC_HEADER;
	for (int i = 0; i < n; i++) {
		const u8 *w = &req[4 + 5 * i];
		u32 a = get32(w);
		u8 s = w[4];
		if (s != 1 && s != 2 && s != 4) { *status = 1; return 0; }
		if (a < MAINRAM_LO || a >= MAINRAM_HI || s > MAINRAM_HI - a) { *status = 2; return 0; }
		size += s;
	}
	// Valid: replace the list and start the ring over
	watchCount = 0;
	for (int i = 0; i < n; i++) {
		const u8 *w = &req[4 + 5 * i];
		watches[i].addr = get32(w);
		watches[i].size = w[4];
	}
	recSize = size;
	ringSlots = WATCH_RING_BYTES / size;
	written = 0;
	tick = 0;
	watchCount = n;
	*status = 0;
	return 0;
}

u16 ProbeWatch_Fetch(const u8 *req, int len, u8 *out, u16 maxOut, u8 *count, u8 *status) {
	*count = 0;
	if (len < 6) { *status = 1; return 0; }
	if (!watchCount) { *status = 3; return 0; }

	// Everything is counted in records; `from` is the low 16 bits of a
	// record number, so it's compared as a distance back from the newest.
	u32 have = written < ringSlots ? written : ringSlots; // records still in the ring
	u16 back = (u16)((u16)written - get16(&req[4]));      // records from `from` to the newest
	u32 lost = 0;
	if (back > have) {
		lost = back - have;
		back = (u16)have;
	}
	u32 first = written - back;

	u16 room = (u16)((maxOut - 5) / recSize);
	u16 k = back < room ? back : room;
	if (k > 255) k = 255;

	put16(&out[0], (u16)first);
	put16(&out[2], lost > 0xFFFF ? 0xFFFF : (u16)lost);
	out[4] = recSize;
	u8 *p = &out[5];
	for (u16 i = 0; i < k; i++) {
		const u8 *rec = &ring[((first + i) % ringSlots) * recSize];
		for (u8 b = 0; b < recSize; b++) p[b] = rec[b];
		p += recSize;
	}
	*count = (u8)k;
	*status = 0;
	return (u16)(5 + k * recSize);
}

#endif // RPCPROBE_REQUESTS
